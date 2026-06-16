import json
import faiss
import numpy as np
import re
from sentence_transformers import SentenceTransformer

# File paths
JSONL_PATH = "output.jsonl"
FAISS_INDEX_PATH = "iso27001.index"
METADATA_PATH = "iso27001_metadata.json"

def load_data(filepath):
    print(f"Loading data from {filepath}...")
    documents = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                documents.append(json.loads(line))
    return documents

def prepare_texts(documents):
    # Combine title and description to give the embedding model rich context
    texts = []
    for doc in documents:
        # Example format: "Control 5.1: Policies for information security. Control Information security policy..."
        title = re.sub(r"\s+", " ", str(doc.get("title", "")).strip())
        desc = re.sub(r"\s+", " ", str(doc.get("description", "")).strip())
        combined_text = f"Control {doc.get('control_id', '')}: {title}. {desc}"
        texts.append(combined_text)
    return texts

def main():
    documents = load_data(JSONL_PATH)
    if not documents:
        print("No documents found to index.")
        return

    texts = prepare_texts(documents)
    
    # 1. Load Embedding Model
    # all-MiniLM-L6-v2 is extremely fast, lightweight, and perfect for semantic search
    print("Loading embedding model (this may take a moment to download the first time)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # 2. Generate Embeddings
    print(f"Generating embeddings for {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True)
    
    # Normalize embeddings for cosine similarity
    faiss.normalize_L2(embeddings)
    
    # 3. Initialize FAISS Index
    # We use IndexFlatIP (Inner Product) which is equivalent to cosine similarity since vectors are normalized
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    
    # 4. Add vectors to the index
    print("Adding vectors to FAISS index...")
    index.add(embeddings)
    
    # 5. Save the FAISS index to disk
    print(f"Saving FAISS index to {FAISS_INDEX_PATH}...")
    faiss.write_index(index, FAISS_INDEX_PATH)
    
    # 6. Save the metadata mapping to disk so we know which vector ID corresponds to which chunk
    print(f"Saving metadata to {METADATA_PATH}...")
    with open(METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)

    print("Index preparation complete! The knowledge base is now ready for RAG retrieval.")

if __name__ == "__main__":
    main()
