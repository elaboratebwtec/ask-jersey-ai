import os
import json # For handling JSON request data
import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, jsonify, Blueprint, render_template, request

# Load environment variables (especially OPENAI_API_KEY)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not found. API calls to OpenAI will fail.")

# Initialize OpenAI client
client_openai = None # Initialize to None
try:
    if OPENAI_API_KEY: # Only attempt to initialize if key is present
        client_openai = OpenAI(api_key=OPENAI_API_KEY)
    else:
        print("OpenAI client not initialized due to missing API key.")
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    # client_openai remains None

# --- Global constants for ChromaDB and Embeddings ---
DB_PATH = "./db_chroma"
COLLECTION_NAME = "jersey_faqs"
EMBEDDING_MODEL = "text-embedding-ada-002"

# --- Function to populate ChromaDB if empty ---
def populate_chroma_if_empty(chroma_collection, openai_client_instance, embedding_model_name):
    """
    Populates the ChromaDB collection from seed_faq.json if the collection is empty.
    """
    print("Checking if ChromaDB collection needs population...")
    if chroma_collection.count() == 0:
        print(f"Collection '{chroma_collection.name}' is empty. Attempting to populate from seed_faq.json...")
        try:
            with open('seed_faq.json', 'r', encoding='utf-8') as f:
                faqs = json.load(f)
        except FileNotFoundError:
            print("CRITICAL ERROR: seed_faq.json not found. Cannot populate ChromaDB.")
            return
        except json.JSONDecodeError:
            print("CRITICAL ERROR: Could not decode seed_faq.json. Cannot populate ChromaDB.")
            return
        except Exception as e_open_json:
            print(f"CRITICAL ERROR: Could not open or read seed_faq.json: {e_open_json}")
            return


        print(f"Found {len(faqs)} FAQs in seed_faq.json for populating.")

        documents_to_add = []
        embeddings_to_add = []
        ids_to_add = []
        metadatas_to_add = []
        processed_ids = set()

        for faq_item in faqs:
            faq_id = str(faq_item.get('id'))
            question = faq_item.get('question')
            answer = faq_item.get('answer')
            source = faq_item.get('source', '')
            category = faq_item.get('category', '')

            if not faq_id or not question or not answer:
                print(f"  Skipping FAQ in population due to missing id, question, or answer: {faq_item}")
                continue
            
            if faq_id in processed_ids:
                print(f"  Warning: Duplicate FAQ ID '{faq_id}' during population. Skipping.")
                continue
            processed_ids.add(faq_id)

            text_for_embedding = f"Question: {question}\nAnswer: {answer}"
            print(f"  Populating: FAQ ID: {faq_id} - '{question[:30]}...'")
            
            try:
                if not openai_client_instance: # Check if client is valid
                    print(f"  Skipping FAQ ID: {faq_id} - OpenAI client not available for embedding.")
                    continue

                response = openai_client_instance.embeddings.create(
                    input=[text_for_embedding],
                    model=embedding_model_name
                )
                embedding = response.data[0].embedding
                
                if embedding:
                    documents_to_add.append(text_for_embedding)
                    embeddings_to_add.append(embedding)
                    ids_to_add.append(faq_id)
                    metadatas_to_add.append({
                        "question": question, "answer": answer,
                        "source": source, "category": category
                    })
                else:
                    print(f"  Skipping FAQ ID: {faq_id} due to empty embedding during population.")
            except Exception as e_embed:
                print(f"  Error getting embedding for FAQ ID {faq_id} during population: {e_embed}")
                continue 
        
        if documents_to_add:
            try:
                chroma_collection.add(
                    embeddings=embeddings_to_add,
                    documents=documents_to_add,
                    metadatas=metadatas_to_add,
                    ids=ids_to_add
                )
                print(f"Successfully added {len(documents_to_add)} FAQs to ChromaDB collection '{chroma_collection.name}'.")
                print(f"Collection count now: {chroma_collection.count()}")
            except Exception as e_add:
                print(f"Error adding documents to Chroma during population: {e_add}")
        else:
            print("No new documents were prepared for population (possibly all skipped or empty JSON).")
    else:
        print(f"ChromaDB collection '{chroma_collection.name}' already populated with {chroma_collection.count()} items. Skipping population.")

# --- Initialize ChromaDB client (persistent) and populate if empty ---
collection = None # Initialize collection to None globally
client_chroma = None # Initialize client_chroma globally

try:
    if not os.path.exists(DB_PATH):
        print(f"ChromaDB path '{DB_PATH}' does not exist. Attempting to create it.")
        os.makedirs(DB_PATH)
        print(f"ChromaDB path '{DB_PATH}' created.")

    client_chroma = chromadb.PersistentClient(path=DB_PATH)
    
    try:
        collection = client_chroma.get_collection(name=COLLECTION_NAME)
        print(f"Successfully connected to existing ChromaDB collection '{COLLECTION_NAME}'.")
    except Exception: # More specific exceptions can be caught if known, e.g., chromadb.exceptions.CollectionNotFoundError
        print(f"Collection '{COLLECTION_NAME}' not found. Attempting to create it.")
        try:
            collection = client_chroma.create_collection(name=COLLECTION_NAME)
            print(f"Successfully created new ChromaDB collection '{COLLECTION_NAME}'.")
        except Exception as e_create_coll:
            print(f"CRITICAL ERROR: Failed to create ChromaDB collection '{COLLECTION_NAME}': {e_create_coll}")
            # collection remains None

    if collection and client_openai: 
        populate_chroma_if_empty(collection, client_openai, EMBEDDING_MODEL)
    elif not client_openai:
        print("CRITICAL ERROR: OpenAI client not initialized. Cannot populate ChromaDB or perform RAG.")
    elif not collection: # This case means collection creation/retrieval failed.
        print(f"CRITICAL ERROR: ChromaDB collection '{COLLECTION_NAME}' could not be initialized. RAG will not function.")
    
    if collection:
        print(f"Final ChromaDB collection '{COLLECTION_NAME}' count after startup check: {collection.count()}")
    else:
        print(f"ChromaDB collection '{COLLECTION_NAME}' is not available after startup.")

except Exception as e_chroma_init:
    print(f"General critical error initializing ChromaDB client or populating collection: {e_chroma_init}")
    # collection and client_chroma might be None

# --- Flask App Setup ---
app = Flask(__name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')

# --- Helper function to get embedding ---
def get_embedding(text_to_embed):
    """Gets embedding from OpenAI for a given text."""
    if not client_openai: # Check if client_openai was initialized
        print("OpenAI client not available for get_embedding.")
        return None
    try:
        response = client_openai.embeddings.create(
            input=[text_to_embed],
            model=EMBEDDING_MODEL # Uses global EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

# --- API Route for Queries ---
@api_bp.route('/query', methods=['POST'])
def handle_query():
    if not client_openai or not collection: # Check if services are available
        error_message = "Backend services not fully initialized: "
        if not client_openai: error_message += "OpenAI client missing. "
        if not collection: error_message += "ChromaDB collection missing."
        print(error_message) # Log for server admin
        return jsonify({"error": "Sorry, the AI service is currently experiencing technical difficulties. Please try again later."}), 503
    
    try:
        data = request.get_json()
        user_question = data.get('question')

        if not user_question:
            return jsonify({"error": "No question provided."}), 400

        print(f"Received question: {user_question}")

        question_embedding = get_embedding(user_question)
        if not question_embedding:
            return jsonify({"error": "Could not generate embedding for the question due to an internal error."}), 500

        print("Querying ChromaDB...")
        try:
            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=3
            )
            retrieved_documents = results.get('documents', [[]])[0]
            retrieved_metadatas = results.get('metadatas', [[]])[0]
            print(f"Retrieved {len(retrieved_documents)} documents from ChromaDB.")
        except Exception as e_query_chroma:
            print(f"Error querying ChromaDB: {e_query_chroma}")
            return jsonify({"error": f"Error querying knowledge base."}), 500

        context_for_gpt = "No specific local information found."
        if retrieved_documents:
            context_details = []
            for i, doc_text in enumerate(retrieved_documents):
                meta = retrieved_metadatas[i] if i < len(retrieved_metadatas) else {}
                s = meta.get('source', '')
                detail = f"Context (Source: {s if s else 'N/A'}):\n{doc_text}"
                context_details.append(detail)
            context_for_gpt = "\n\n".join(context_details)
        else:
             print("No relevant documents found in ChromaDB for this query.")


        prompt = f"""
        You are 'Ask Jersey!', a helpful AI assistant for information about Jersey.
        Answer the user's question based *only* on the provided context below.
        If the context states "No specific local information found." or if the context is clearly irrelevant to the question, state that you couldn't find specific information in your current documents for this query, then try to answer the question generally if you can, clearly indicating it's general knowledge.
        Be concise and helpful. If you use information from a source in the context, you can subtly weave it in or mention it if appropriate (e.g., "According to [source]...").

        Context from Jersey FAQs:
        ---
        {context_for_gpt}
        ---

        User's Question: {user_question}

        Answer:
        """
        print(f"Constructed prompt for GPT-4o (first 500 chars):\n{prompt[:500]}...")

        print("Calling OpenAI GPT-4o...")
        try:
            chat_completion = client_openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are 'Ask Jersey!', a helpful AI assistant providing information about Jersey based on the context given."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            generated_answer = chat_completion.choices[0].message.content
            print(f"GPT-4o generated answer: {generated_answer}")
        except Exception as e_openai_chat:
            print(f"Error calling OpenAI Chat Completions API: {e_openai_chat}")
            return jsonify({"error": f"Error generating AI response."}), 500
        
        final_response = {"answer": generated_answer}
        return jsonify(final_response), 200

    except Exception as e_handle_query:
        print(f"An unexpected error occurred in /api/query: {e_handle_query}")
        return jsonify({"error": "An unexpected error occurred while processing your question."}), 500

app.register_blueprint(api_bp)

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/ping")
def ping():
    return jsonify({"status": "alive", "message": "pong"})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
