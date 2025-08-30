import chromadb

# Connect to your Chroma DB (default path is ./chroma)
client = chromadb.PersistentClient(path="./shared_data/chroma")

# List all collections
collections = client.list_collections()
print("Collections:", collections)

# Pick a collection
collection = client.get_collection("solana_tokens_knowledge")

# Get all stored items (documents + metadata + embeddings if needed)
results = collection.get(include=["documents", "metadatas"])  
print(results)