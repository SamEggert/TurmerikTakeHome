import chromadb
from chromadb.utils import embedding_functions
import argparse
import json

def test_chroma_db(chroma_path):
    """
    Test the ChromaDB with different types of queries

    Args:
        chroma_path: Path to the ChromaDB directory
    """
    print(f"Connecting to ChromaDB at {chroma_path}")
    client = chromadb.PersistentClient(path=chroma_path)

    # Set up embedding function
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-large-en-v1.5"
    )

    # Get collection
    collection = client.get_collection(
        name="clinical_trials",
        embedding_function=embedding_function
    )

    # Print collection info
    print(f"Collection 'clinical_trials' has {collection.count()} documents")

    # Test 5: Interactive query
    print("\n--- Test 5: Interactive query ---")
    user_query = input("Enter your own search query: ")
    results = collection.query(
        query_texts=[user_query],
        n_results=5
    )

    print(f"Query: '{user_query}'")
    print("Top 5 results:")
    for i, (doc_id, document, distance) in enumerate(zip(results['ids'][0], results['documents'][0], results['distances'][0])):
        print(f"\nResult #{i+1}: (ID: {doc_id}, Distance: {distance:.4f})")
        print_trial_summary(document)

def print_trial_summary(document):
    """Print a summarized version of a trial document"""
    lines = document.split('\n')

    # Print ID and title
    for line in lines[:2]:
        print(line)

    # Print conditions
    for line in lines:
        if line.startswith("Conditions:"):
            print(line)
            break

    # Print abbreviated inclusion/exclusion criteria
    for line in lines:
        if line.startswith("Inclusion Criteria:"):
            criteria = line[19:].split(';')
            print(f"Inclusion Criteria: {criteria[0]}" + (" ..." if len(criteria) > 1 else ""))
        elif line.startswith("Exclusion Criteria:"):
            criteria = line[19:].split(';')
            print(f"Exclusion Criteria: {criteria[0]}" + (" ..." if len(criteria) > 1 else ""))

def main():
    parser = argparse.ArgumentParser(description="Test ChromaDB clinical trials vector database")
    parser.add_argument("--chroma", "-c", type=str, default="../data/chroma_db",
                      help="Path to the ChromaDB directory")

    args = parser.parse_args()

    test_chroma_db(args.chroma)

if __name__ == "__main__":
    main()