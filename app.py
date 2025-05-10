import os
import json # For handling JSON request data
import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, jsonify, Blueprint, render_template, request # Added 'request'

# Load environment variables (especially OPENAI_API_KEY)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    # This check is good, but if the app starts, we assume key is available for OpenAI client
    # For production, better error handling or startup checks might be needed if key is critical for app to run
    print("Warning: OPENAI_API_KEY not found. API calls to OpenAI will fail.")

# Initialize OpenAI client
# It's good practice to handle potential errors during client initialization
try:
    client_openai = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    client_openai = None # Set to None so we can check before using

# Initialize ChromaDB client (persistent)
DB_PATH = "./db_chroma"
COLLECTION_NAME = "jersey_faqs"
EMBEDDING_MODEL = "text-embedding-ada-002" # Ensure this matches your seeding script

try:
    client_chroma = chromadb.PersistentClient(path=DB_PATH)
    collection = client_chroma.get_collection(name=COLLECTION_NAME) # Get existing collection
    print(f"Successfully connected to ChromaDB collection '{COLLECTION_NAME}'. Count: {collection.count()}")
    if collection.count() == 0:
        print(f"Warning: ChromaDB collection '{COLLECTION_NAME}' is empty. Did the seeding script run correctly?")
except Exception as e:
    print(f"Error initializing ChromaDB client or getting collection '{COLLECTION_NAME}': {e}")
    print(f"Make sure ChromaDB is initialized and the collection exists. Run seed_chroma.py if needed.")
    collection = None # Set to None so we can check before using


# --- Flask App Setup ---
app = Flask(__name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')

# --- Helper function to get embedding ---
def get_embedding(text_to_embed):
    """Gets embedding from OpenAI for a given text."""
    if not client_openai:
        print("OpenAI client not initialized.")
        return None
    try:
        response = client_openai.embeddings.create(
            input=[text_to_embed],
            model=EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

# --- API Route for Queries ---
@api_bp.route('/query', methods=['POST'])
def handle_query():
    if not client_openai or not collection:
        return jsonify({"error": "Backend services (OpenAI or ChromaDB) not initialized correctly. Please check server logs."}), 503

    try:
        data = request.get_json()
        user_question = data.get('question')

        if not user_question:
            return jsonify({"error": "No question provided."}), 400

        print(f"Received question: {user_question}")

        # 1. Get embedding for the user's question
        question_embedding = get_embedding(user_question)
        if not question_embedding:
            return jsonify({"error": "Could not generate embedding for the question."}), 500

        # 2. Query ChromaDB for relevant documents
        print("Querying ChromaDB...")
        try:
            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=3 # Number of relevant documents to retrieve
            )
            retrieved_documents = results.get('documents', [[]])[0] # Get the list of documents
            retrieved_metadatas = results.get('metadatas', [[]])[0] # Get metadatas
            print(f"Retrieved {len(retrieved_documents)} documents from ChromaDB.")
        except Exception as e:
            print(f"Error querying ChromaDB: {e}")
            return jsonify({"error": f"Error querying knowledge base: {e}"}), 500

        if not retrieved_documents:
            # Fallback or simple "I don't know" if no relevant docs found
            # For now, let's try to answer with general knowledge or say we couldn't find specifics
            print("No relevant documents found in ChromaDB. Attempting general knowledge response.")
            context_for_gpt = "No specific local information found."
        else:
            # Prepare context for GPT-4o
            context_for_gpt = "\n\n".join(retrieved_documents)
            # You might want to include metadata like sources if available and relevant
            # For example, if metadatas contain 'source' and 'question'/'answer' fields:
            context_details = []
            for i, doc_text in enumerate(retrieved_documents):
                meta = retrieved_metadatas[i] if i < len(retrieved_metadatas) else {}
                q = meta.get('question', 'Related information')
                # a = meta.get('answer', doc_text) # doc_text is "Question: ... Answer: ..."
                s = meta.get('source', '')
                detail = f"Context from source '{s}':\n{doc_text}" if s else f"Context:\n{doc_text}"
                context_details.append(detail)
            context_for_gpt = "\n\n".join(context_details)


        # 3. Construct prompt for GPT-4o
        prompt = f"""
        You are 'Ask Jersey!', a helpful AI assistant for information about Jersey.
        Answer the user's question based *only* on the provided context below.
        If the context doesn't contain the answer, state that you couldn't find specific information in your current documents and try to answer generally if possible, but clearly indicate it's general knowledge.
        Be concise and helpful. If you use information from a source in the context, mention it if the source is provided.

        Context from Jersey FAQs:
        ---
        {context_for_gpt}
        ---

        User's Question: {user_question}

        Answer:
        """
        print(f"Constructed prompt for GPT-4o:\n{prompt[:500]}...") # Log first 500 chars of prompt

        # 4. Call OpenAI Chat Completions API (GPT-4o)
        print("Calling OpenAI GPT-4o...")
        try:
            chat_completion = client_openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are 'Ask Jersey!', a helpful AI assistant providing information about Jersey based on the context given."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3 # Adjust for more factual/creative responses
            )
            generated_answer = chat_completion.choices[0].message.content
            print(f"GPT-4o generated answer: {generated_answer}")
        except Exception as e:
            print(f"Error calling OpenAI Chat Completions API: {e}")
            return jsonify({"error": f"Error generating AI response: {e}"}), 500
        
        # For now, just return the answer. We can add sources later.
        # Try to find which source was most relevant if possible (more advanced)
        # For simplicity, let's just return the answer.
        # You could also parse sources from the retrieved_metadatas if they were used.

        final_response = {"answer": generated_answer}
        # Example of adding sources if you can determine them:
        # if retrieved_documents and retrieved_metadatas:
        #    primary_source = retrieved_metadatas[0].get('source')
        #    if primary_source:
        #        final_response['source'] = primary_source
        
        return jsonify(final_response), 200

    except Exception as e:
        print(f"An unexpected error occurred in /api/query: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500


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
