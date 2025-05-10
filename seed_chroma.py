import os
import json
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables (especially OPENAI_API_KEY)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env file or environment variables. Please ensure it is set.")

# Initialize OpenAI client
try:
    client_openai = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    exit()

# Initialize ChromaDB client (persistent)
# This will store data in the 'db_chroma' directory
try:
    # Ensure the directory for ChromaDB exists, create if not
    db_path = "./db_chroma"
    if not os.path.exists(db_path):
        os.makedirs(db_path)
    client_chroma = chromadb.PersistentClient(path=db_path)
except Exception as e:
    print(f"Error initializing ChromaDB client: {e}")
    exit()


# Define the embedding model (OpenAI's text-embedding-ada-002 is a common choice)
EMBEDDING_MODEL = "text-embedding-ada-002" # Or "text-embedding-3-small" etc.

# Get or create a collection (like a table in a database)
COLLECTION_NAME = "jersey_faqs"
print(f"Attempting to get or create ChromaDB collection: '{COLLECTION_NAME}'")
try:
    collection = client_chroma.get_or_create_collection(name=COLLECTION_NAME)
    print(f"Collection '{COLLECTION_NAME}' ready.")
except Exception as e:
    print(f"Error with ChromaDB collection '{COLLECTION_NAME}': {e}")
    exit()

def get_embedding(text_to_embed):
    """Helper function to get embeddings from OpenAI."""
    try:
        response = client_openai.embeddings.create(
            input=[text_to_embed],  # Input must be a list of strings
            model=EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding for text: '{text_to_embed[:50]}...' - {e}")
        return None

def load_faqs_into_chroma():
    """Loads FAQs from seed_faq.json into ChromaDB."""
    try:
        with open('seed_faq.json', 'r', encoding='utf-8') as f:
            faqs = json.load(f)
    except FileNotFoundError:
        print("Error: seed_faq.json not found. Make sure it's in the project root directory.")
        return
    except json.JSONDecodeError:
        print("Error: Could not decode seed_faq.json. Please check its JSON format.")
        return
    except Exception as e:
        print(f"An unexpected error occurred opening seed_faq.json: {e}")
        return

    print(f"\nFound {len(faqs)} FAQs in seed_faq.json. Starting ingestion...")

    documents_to_add = []
    embeddings_to_add = []
    ids_to_add = []
    metadatas_to_add = [] 

    processed_ids = set() # To track IDs already processed for this run

    for faq_item in faqs:
        faq_id = faq_item.get('id')
        question = faq_item.get('question')
        answer = faq_item.get('answer')
        source = faq_item.get('source', '') 
        category = faq_item.get('category', '') 

        if not faq_id or not question or not answer:
            print(f"Skipping FAQ due to missing id, question, or answer: {faq_item}")
            continue
        
        faq_id_str = str(faq_id) # Ensure ID is a string for ChromaDB

        if faq_id_str in processed_ids:
            print(f"Warning: Duplicate FAQ ID '{faq_id_str}' found in seed_faq.json. Skipping.")
            continue
        processed_ids.add(faq_id_str)

        text_for_embedding = f"Question: {question}\nAnswer: {answer}"
        
        print(f"  Processing FAQ ID: {faq_id_str} - '{question[:50]}...'")
        embedding = get_embedding(text_for_embedding)

        if embedding:
            documents_to_add.append(text_for_embedding) 
            embeddings_to_add.append(embedding)
            ids_to_add.append(faq_id_str) 
            metadatas_to_add.append({
                "question": question,
                "answer": answer, 
                "source": source,
                "category": category
            })
        else:
            print(f"  Skipping FAQ ID: {faq_id_str} due to embedding error.")
    
    if documents_to_add:
        try:
            print(f"\nAttempting to add {len(documents_to_add)} documents to ChromaDB...")
            # If IDs already exist, ChromaDB by default will skip them or you can use update/upsert.
            # For a seeding script, 'add' is usually fine, assuming you clear the collection if re-seeding from scratch
            # or that IDs are unique and you only want to add new ones.
            # For simplicity, this script assumes we're adding new items or items that don't yet exist by ID.
            # If an ID already exists, 'add' will typically ignore that specific item silently or throw an error
            # depending on the ChromaDB version and configuration if IDs are not unique.
            # The current behavior with unique IDs is that it should add them if they don't exist.
            collection.add(
                embeddings=embeddings_to_add,
                documents=documents_to_add,
                metadatas=metadatas_to_add,
                ids=ids_to_add
            )
            print(f"Successfully processed {len(documents_to_add)} FAQs for ChromaDB collection '{COLLECTION_NAME}'.")
            print(f"Current item count in collection: {collection.count()}")
        except Exception as e:
            print(f"Error adding documents to Chroma: {e}")
            print("Please check if items with these IDs already exist or if there's another issue with the data.")
    else:
        print("\nNo new documents were prepared to be added to ChromaDB.")

if __name__ == "__main__":
    print("Starting FAQ ingestion process for ChromaDB...")
    
    # Optional: Clear the collection if you want to re-seed from scratch each time
    # This is useful during development to ensure a clean state.
    # Be careful with this in a production-like environment.
    # try:
    #     print(f"Attempting to delete collection '{COLLECTION_NAME}' for a fresh start...")
    #     client_chroma.delete_collection(name=COLLECTION_NAME)
    #     print(f"Collection '{COLLECTION_NAME}' deleted.")
    #     collection = client_chroma.create_collection(name=COLLECTION_NAME) # Recreate it
    #     print(f"Collection '{COLLECTION_NAME}' recreated.")
    # except Exception as e:
    #     print(f"Note: Could not delete and recreate collection (it might not have existed): {e}")
    #     # If deletion fails, try to get_or_create_collection again to ensure it exists
    #     try:
    #        collection = client_chroma.get_or_create_collection(name=COLLECTION_NAME)
    #     except Exception as e_create:
    #         print(f"Critical error: Could not ensure collection '{COLLECTION_NAME}' exists: {e_create}")
    #         exit()


    load_faqs_into_chroma()
    print("\nFAQ ingestion process finished.")

    # Example query to test if data was loaded (optional)
    # try:
    #     if collection.count() > 0:
    #         print("\nPerforming a test query on the collection...")
    #         results = collection.query(
    #             query_texts=["What are income tax rates in Jersey?"], # Example query
    #             n_results=1 # Number of results to return
    #         )
    #         print("Test query results:")
    #         if results and results.get('documents'):
    #             for i, doc in enumerate(results['documents'][0]):
    #                 print(f"  Result {i+1}:")
    #                 print(f"    ID: {results['ids'][0][i]}")
    #                 print(f"    Document: {doc[:100]}...") # Print first 100 chars
    #                 print(f"    Metadata: {results['metadatas'][0][i]}")
    #                 print(f"    Distance: {results['distances'][0][i]}")
    #         else:
    #             print("  No documents found for the test query or an issue with results structure.")
    #     else:
    #         print("\nSkipping test query as the collection is empty.")
    # except Exception as e:
    #     print(f"Error during test query: {e}")
