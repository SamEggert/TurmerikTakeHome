import sqlite3
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
import argparse
import os
from tqdm import tqdm

def create_corpus_db(sqlite_path, chroma_path, batch_size=100):
    """
    Extract data from clinical trials SQLite DB and add to ChromaDB

    Args:
        sqlite_path: Path to the SQLite database
        chroma_path: Path where the ChromaDB will be stored
        batch_size: Number of trials to process in each batch
    """
    # Check if the database file exists
    if not os.path.exists(sqlite_path):
        print(f"Error: SQLite database file not found at {sqlite_path}")
        return

    print(f"SQLite file exists at {sqlite_path}")

    # Connect to SQLite database
    print(f"Connecting to SQLite database")
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    # List all tables in the database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables in the database: {[table[0] for table in tables]}")

    if not tables:
        print("No tables found in the database. Please check if the database was created properly.")
        conn.close()
        return

    # Check if the expected 'trials' table exists
    if 'trials' not in [table[0] for table in tables]:
        print("The 'trials' table was not found. Please check your database structure.")
        # Try to find an alternative main table
        print("Available tables are:")
        for table in tables:
            print(f"- {table[0]}")
            # Show first few rows of schema for this table
            cursor.execute(f"PRAGMA table_info({table[0]})")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
        conn.close()
        return

    # Get total count of trials for progress tracking
    cursor.execute("SELECT COUNT(*) FROM trials")
    total_trials = cursor.fetchone()[0]
    print(f"Found {total_trials} trials in the database")

    # Initialize Chroma client
    print(f"Initializing ChromaDB at {chroma_path}")
    client = chromadb.PersistentClient(path=chroma_path)

    # Set up embedding function with BGE model
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-large-en-v1.5"
    )

    # Create or get collection
    collection = client.get_or_create_collection(
        name="clinical_trials",
        embedding_function=embedding_function
    )

    # Get all trial IDs
    cursor.execute("SELECT trial_id FROM trials")
    trial_ids = [row[0] for row in cursor.fetchall()]

    # Process trials in batches
    for i in range(0, len(trial_ids), batch_size):
        batch_ids = trial_ids[i:i+batch_size]
        documents = []
        metadatas = []
        ids = []

        print(f"Processing batch {i//batch_size + 1}/{(total_trials+batch_size-1)//batch_size}")

        for trial_id in tqdm(batch_ids):
            # Get basic trial info
            cursor.execute("""
                SELECT trial_id, trial_title, minimum_age, maximum_age, sex,
                       accepts_healthy_volunteers, participant_count
                FROM trials WHERE trial_id = ?
            """, (trial_id,))
            trial_info = cursor.fetchone()

            if not trial_info:
                continue

            # Get conditions
            cursor.execute("SELECT condition_name FROM conditions WHERE trial_id = ?", (trial_id,))
            conditions = [row[0] for row in cursor.fetchall()]

            # Get interventions
            cursor.execute("""
                SELECT intervention_type, intervention_name
                FROM interventions WHERE trial_id = ?
            """, (trial_id,))
            interventions = [f"{row[0]}: {row[1]}" for row in cursor.fetchall()]

            # Get inclusion criteria
            cursor.execute("SELECT criterion FROM inclusion_criteria WHERE trial_id = ?", (trial_id,))
            inclusion = [row[0] for row in cursor.fetchall()]

            # Get exclusion criteria
            cursor.execute("SELECT criterion FROM exclusion_criteria WHERE trial_id = ?", (trial_id,))
            exclusion = [row[0] for row in cursor.fetchall()]

            # Combine all information into a single document
            trial_text = (
                f"Trial ID: {trial_info[0]}\n"
                f"Title: {trial_info[1]}\n"
                f"Age Range: {trial_info[2] or 'N/A'} to {trial_info[3] or 'N/A'}\n"
                f"Sex: {trial_info[4]}\n"
                f"Accepts Healthy Volunteers: {trial_info[5]}\n"
                f"Participant Count: {trial_info[6]}\n"
                f"Conditions: {', '.join(conditions)}\n"
                f"Interventions: {'; '.join(interventions)}\n"
                f"Inclusion Criteria: {'; '.join(inclusion)}\n"
                f"Exclusion Criteria: {'; '.join(exclusion)}"
            )

            # Create metadata
            metadata = {
                "trial_id": trial_info[0],
                "title": trial_info[1],
                "min_age": trial_info[2] if trial_info[2] is not None else -1,
                "max_age": trial_info[3] if trial_info[3] is not None else 999,
                "sex": trial_info[4],
                "healthy_volunteers": trial_info[5] == 1,
                "participant_count": trial_info[6] if trial_info[6] is not None else 0,
                "conditions_count": len(conditions),
                "interventions_count": len(interventions)
            }

            documents.append(trial_text)
            metadatas.append(metadata)
            ids.append(trial_id)

        # Add batch to ChromaDB
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added {len(documents)} trials to ChromaDB (batch {i//batch_size + 1})")

    print(f"Completed! Added {collection.count()} trials to ChromaDB.")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Create a vector database from clinical trials data")
    parser.add_argument("--sqlite", "-s", type=str, default="../data/clinical_trials.db",
                      help="Path to the SQLite database file")
    parser.add_argument("--output", "-o", type=str, default="../data/chroma_db",
                      help="Path where ChromaDB will be stored")
    parser.add_argument("--batch-size", "-b", type=int, default=100,
                      help="Number of trials to process in each batch")

    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    create_corpus_db(args.sqlite, args.output, args.batch_size)

if __name__ == "__main__":
    main()