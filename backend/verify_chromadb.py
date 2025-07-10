import sys
import os

# Add the parent directory to the Python path to allow importing VectorDatabase
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from VectorDatabase import connect_to_chromadb, load_chroma_config

def verify_chromadb_connection():
    print("Attempting to connect to ChromaDB...")
    try:
        chroma_config = load_chroma_config()
        client = connect_to_chromadb(chroma_config)
        
        # List collections as a simple verification
        collections = client.list_collections()
        print("ChromaDB Collections:")
        if collections:
            for collection in collections:
                print(f"- {collection.name}")
                # Optionally, print count of documents in each collection
                print(f"  Documents in {collection.name}: {collection.count()}")
        else:
            print("No collections found in ChromaDB.")
        
        print("Successfully connected to ChromaDB and listed collections.")
    except Exception as e:
        print(f"Failed to connect to ChromaDB or list collections: {e}")

if __name__ == "__main__":
    verify_chromadb_connection()
