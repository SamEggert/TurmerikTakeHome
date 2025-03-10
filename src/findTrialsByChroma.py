import sqlite3
import chromadb
from chromadb.utils import embedding_functions
import argparse
import os
import json
import sys

# Import from the enhanced parser module
from parseXMLs import (
    parse_ccda_file,
    register_namespaces,
    generate_semantic_search_query,  # Import the new query generator
    extract_key_clinical_info        # Import the clinical info extractor
)

def match_patient_to_trials(patient_data, db_path="../data/clinical_trials.db", limit=1000):
    """
    Match patient data against clinical trials in the database based on demographics.
    Uses a single optimized query for performance.

    Args:
        patient_data: Dictionary containing parsed patient data from C-CDA file
        db_path: Path to the SQLite database containing clinical trials
        limit: Maximum number of trials to return (default: 1000)

    Returns:
        List of matching trial dictionaries and total count of matches
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} not found")
        return [], 0

    # Extract demographic information
    demographics = patient_data.get('demographics', {})
    age = demographics.get('age')
    gender = demographics.get('gender')  # Updated field name to match the enhanced parser
    race = demographics.get('race')
    ethnicity = demographics.get('ethnicity')

    # Default gender mapping (map patient gender to trial sex format)
    gender_mapping = {
        'M': 'MALE',
        'F': 'FEMALE',
        'Male': 'MALE',
        'Female': 'FEMALE'
    }

    # Map patient gender to database format
    mapped_sex = gender_mapping.get(gender)

    # Connect to database
    conn = sqlite3.connect(db_path)

    # Create custom row factory to handle the query results
    def dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    conn.row_factory = dict_factory
    cursor = conn.cursor()

    # Build the base query without limit for counting
    base_query = """
    SELECT
        COUNT(DISTINCT t.trial_id) as total_count
    FROM
        trials t
    WHERE 1=1
    """

    count_params = []

    # Add age criteria if available
    if age is not None:
        base_query += " AND (t.minimum_age IS NULL OR t.minimum_age <= ?)"
        count_params.append(age)
        base_query += " AND (t.maximum_age IS NULL OR t.maximum_age >= ?)"
        count_params.append(age)

    # Add sex criteria if available
    if mapped_sex:
        base_query += " AND (t.sex = ? OR t.sex = 'ALL')"
        count_params.append(mapped_sex)

    # Execute the count query
    cursor.execute(base_query, count_params)
    total_matches = cursor.fetchone()['total_count']
    print(f"Total matching trials (before limit): {total_matches}")

    # Build a single optimized query that gets all the data we need
    query = """
    SELECT
        t.trial_id,
        t.trial_title,
        t.minimum_age,
        t.maximum_age,
        t.sex,
        t.accepts_healthy_volunteers,
        t.requires_english,
        t.requires_internet,
        GROUP_CONCAT(DISTINCT c.condition_name) AS conditions,
        GROUP_CONCAT(DISTINCT i.intervention_type || ': ' || i.intervention_name) AS interventions
    FROM
        trials t
    LEFT JOIN
        conditions c ON t.trial_id = c.trial_id
    LEFT JOIN
        interventions i ON t.trial_id = i.trial_id
    WHERE 1=1
    """

    params = []

    # Add age criteria if available
    if age is not None:
        query += " AND (t.minimum_age IS NULL OR t.minimum_age <= ?)"
        params.append(age)
        query += " AND (t.maximum_age IS NULL OR t.maximum_age >= ?)"
        params.append(age)

    # Add sex criteria if available
    if mapped_sex:
        query += " AND (t.sex = ? OR t.sex = 'ALL')"
        params.append(mapped_sex)

    # Group by trial_id to combine the GROUP_CONCAT results properly
    query += " GROUP BY t.trial_id"

    # Add limit to improve performance
    query += f" LIMIT {limit}"

    # Execute the query
    print(f"Executing optimized query...")
    cursor.execute(query, params)

    # Process the results
    matches = []
    for row in cursor.fetchall():
        trial = dict(row)

        # Process concatenated fields
        if trial.get('conditions'):
            trial['conditions'] = trial['conditions'].split(',')
        else:
            trial['conditions'] = []

        if trial.get('interventions'):
            trial['interventions'] = [
                {'intervention': intervention}
                for intervention in trial['interventions'].split(',')
            ]
        else:
            trial['interventions'] = []

        matches.append(trial)

    print(f"Retrieved {len(matches)} of {total_matches} total matching trials")

    conn.close()
    return matches, total_matches

def rank_matched_trials(matched_trials, patient_data, chroma_path, top_k=None):
    """
    Rank the matched trials using semantic search based on patient data

    Args:
        matched_trials: List of trials that matched the demographics criteria
        patient_data: Dictionary containing parsed patient data from C-CDA file
        chroma_path: Path to the ChromaDB directory
        top_k: Number of top results to return (None for all)

    Returns:
        List of ranked trials with search scores
    """
    if not matched_trials:
        return []

    # Get the trial IDs
    trial_ids = [trial['trial_id'] for trial in matched_trials]
    print(f"Number of trial IDs to rank: {len(trial_ids)}")
    print(f"Example trial IDs: {trial_ids[:5] if len(trial_ids) >= 5 else trial_ids}")

    # Connect to ChromaDB
    print(f"Connecting to ChromaDB at {chroma_path}")
    client = chromadb.PersistentClient(path=chroma_path)

    # List collections (in ChromaDB v0.6.0, this returns collection names only)
    collections = client.list_collections()
    print(f"Available collections: {collections}")

    if "clinical_trials" not in collections:
        print("Error: 'clinical_trials' collection not found in ChromaDB")
        return matched_trials

    # Set up embedding function
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-large-en-v1.5"
    )

    # Get collection
    try:
        collection = client.get_collection(
            name="clinical_trials",
            embedding_function=embedding_function
        )
        print(f"Collection count: {collection.count()}")
    except Exception as e:
        print(f"Error connecting to ChromaDB collection: {e}")
        return matched_trials

    # Use the enhanced semantic search query generator
    if "key_clinical_info" in patient_data and "semantic_search_query" in patient_data["key_clinical_info"]:
        query = patient_data["key_clinical_info"]["semantic_search_query"]
        print(f"Using pre-generated semantic search query from patient data")
    else:
        query = generate_semantic_search_query(patient_data)
        print(f"Generated new semantic search query")

    print(f"Semantic search query: '{query}'")

    # Try to fetch some results using ChromaDB v0.6.0 API
    try:
        print("Using ChromaDB v0.6.0 compatible query...")

        # In v0.6.0, we use where_document.ids instead of ids parameter
        results = collection.query(
            query_texts=[query],
            where={"$id": {"$in": trial_ids}},
            n_results=min(len(trial_ids), collection.count())
        )

        if results and results['ids'] and results['ids'][0]:
            print(f"Query returned {len(results['ids'][0])} results")
        else:
            print("Query returned no results, trying without filters...")

            # Try without filtering
            results = collection.query(
                query_texts=[query],
                n_results=min(100, collection.count())
            )

            if results and results['ids'] and results['ids'][0]:
                print(f"Unfiltered query returned {len(results['ids'][0])} results")
                # Filter results manually
                filtered_ids = []
                filtered_distances = []

                for i, doc_id in enumerate(results['ids'][0]):
                    if doc_id in trial_ids:
                        filtered_ids.append(doc_id)
                        filtered_distances.append(results['distances'][0][i])

                results = {
                    'ids': [filtered_ids],
                    'distances': [filtered_distances]
                }
                print(f"After filtering: {len(filtered_ids)} matches")
            else:
                print("Unfiltered query also returned no results")

    except Exception as e:
        print(f"Error during ChromaDB query: {e}")
        # Try a different syntax
        try:
            print("Trying alternative query syntax...")
            results = collection.query(
                query_texts=[query],
                n_results=min(100, collection.count())
            )
        except Exception as e2:
            print(f"Alternative query also failed: {e2}")
            results = None

    # If we got results, process them
    if results and results['ids'] and results['ids'][0]:
        # Create a dictionary to look up original trial data
        trial_dict = {trial['trial_id']: trial for trial in matched_trials}

        # Create list of ranked trials with scores
        ranked_trials = []
        for i, (doc_id, distance) in enumerate(zip(results['ids'][0], results['distances'][0])):
            if doc_id in trial_dict:
                trial = trial_dict[doc_id]
                # Add search score
                trial['semantic_score'] = 1.0 - distance  # Convert distance to similarity score
                ranked_trials.append(trial)

        print(f"Ranked {len(ranked_trials)} trials using semantic search")

        # Limit to top_k if specified
        if top_k is not None and top_k > 0:
            ranked_trials = ranked_trials[:top_k]
            print(f"Returning top {top_k} results")

        return ranked_trials
    else:
        print("No semantic search results returned, using fallback approach")

        # FALLBACK: Calculate similarity scores manually
        try:
            # Import required libraries
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            query_embedding = embedding_function([query])[0]
            ranked_trials = []

            print(f"Calculating similarity scores for {len(matched_trials)} trials...")
            for trial in matched_trials:
                # Create a text representation of the trial
                trial_text = f"{trial['trial_title']} {' '.join(trial['conditions'])}"
                trial_embedding = embedding_function([trial_text])[0]

                # Calculate cosine similarity
                similarity = cosine_similarity([query_embedding], [trial_embedding])[0][0]

                # Add score to trial
                trial['semantic_score'] = float(similarity)
                ranked_trials.append(trial)

            # Sort by score
            ranked_trials = sorted(ranked_trials, key=lambda x: x['semantic_score'], reverse=True)
            print(f"Ranked {len(ranked_trials)} trials using fallback semantic ranking")

            # Limit to top_k if specified
            if top_k is not None and top_k > 0:
                ranked_trials = ranked_trials[:top_k]
                print(f"Returning top {top_k} results")

            return ranked_trials
        except Exception as e:
            print(f"Error in fallback approach: {e}")
            print("Returning unranked trials")
            return matched_trials

def print_trial_summary(trial, file=None):
    """Print a summarized version of a trial document"""
    # Format the trial information
    trial_summary = [
        f"Trial ID: {trial.get('trial_id', 'N/A')}",
        f"Title: {trial.get('trial_title', 'N/A')}",
        f"Score: {trial.get('semantic_score', 'N/A'):.4f}" if 'semantic_score' in trial else "",
        f"Age Range: {trial.get('minimum_age', 'N/A')} to {trial.get('maximum_age', 'N/A')}",
        f"Sex: {trial.get('sex', 'N/A')}",
        f"Conditions: {', '.join(trial.get('conditions', []))}"
    ]

    # Filter out empty lines
    trial_summary = [line for line in trial_summary if line]

    # Print to file if specified, otherwise to console
    if file:
        print("\n".join(trial_summary), file=file)
        print("-" * 50, file=file)
    else:
        print("\n".join(trial_summary))
        print("-" * 50)

def print_patient_summary(patient_data, file=None):
    """Print a nicely formatted summary of the patient data"""
    # Check if we have extracted key clinical info
    if "key_clinical_info" in patient_data:
        key_info = patient_data["key_clinical_info"]

        # Format the patient information
        patient_summary = [
            "=== PATIENT SUMMARY ===",
            f"Patient ID: {patient_data.get('patientId', 'Unknown')}",
            "",
            "=== DEMOGRAPHICS ===",
            key_info.get("demographic_summary", "Not available"),
            "",
            "=== CONDITIONS ===",
            key_info.get("condition_summary", "None recorded"),
            "",
            "=== MEDICATIONS ===",
            key_info.get("medication_summary", "None recorded"),
            "",
            "=== RECENT LAB RESULTS ===",
            key_info.get("lab_summary", "None recorded"),
            "",
            "=== PROCEDURES ===",
            key_info.get("procedure_summary", "None recorded"),
            "",
            "=== GENERATED SEMANTIC SEARCH QUERY ===",
            key_info.get("semantic_search_query", "No query generated")
        ]
    else:
        # Legacy format without key clinical info
        patient_summary = [
            "=== PATIENT SUMMARY ===",
            f"Patient ID: {patient_data.get('patientId', 'Unknown')}",
            "",
            "=== DEMOGRAPHICS ===",
        ]

        for key, value in patient_data.get('demographics', {}).items():
            patient_summary.append(f"{key}: {value}")

        patient_summary.append("")
        patient_summary.append("=== CONDITIONS ===")
        for condition in patient_data.get('conditions', []):
            name = condition.get('name', 'Unknown')
            onset = condition.get('onsetDate', 'Unknown date')
            patient_summary.append(f"- {name} (onset: {onset})")

        patient_summary.append("")
        patient_summary.append("=== MEDICATIONS ===")
        for med in patient_data.get('medications', []):
            name = med.get('name', 'Unknown')
            dose = f"{med.get('dose', '')} {med.get('unit', '')}"
            patient_summary.append(f"- {name} {dose}")

    # Print to file if specified, otherwise to console
    if file:
        print("\n".join(patient_summary), file=file)
        print("=" * 50, file=file)
    else:
        print("\n".join(patient_summary))
        print("=" * 50)

def match_and_rank_trials(file_path, db_path, chroma_path, output_path, top_k=None):
    """
    Match a patient to clinical trials based on demographics and rank by semantic search

    Args:
        file_path: Path to the C-CDA XML file
        db_path: Path to the SQLite database containing clinical trials
        chroma_path: Path to the ChromaDB directory
        output_path: Path to save results
        top_k: Number of top results to return (None for all)
    """
    # Register namespaces (required for proper XML parsing)
    register_namespaces()

    print(f"Parsing file: {file_path}")

    # Parse the file
    patient_data = parse_ccda_file(file_path)

    if not patient_data:
        print("Failed to parse the patient file.")
        return

    # Generate key clinical information and semantic search query if not already present
    if "key_clinical_info" not in patient_data:
        print("Generating key clinical information and semantic search query...")
        patient_data["key_clinical_info"] = extract_key_clinical_info(patient_data)

    # Print enhanced patient summary
    print_patient_summary(patient_data)

    # Find matching trials
    print("\nMatching patient to clinical trials based on demographics...")
    matched_trials, total_matches = match_patient_to_trials(patient_data, db_path)

    if not matched_trials:
        print("No matching trials found.")
        return

    # Rank trials using semantic search with the enhanced query
    print("\nRanking matched trials using enhanced semantic search query...")
    ranked_trials = rank_matched_trials(matched_trials, patient_data, chroma_path, top_k)

    # Make sure the output directory exists for the specified output_path
    output_dir = os.path.dirname(output_path)
    if output_dir:  # Only create if there's a directory specified
        os.makedirs(output_dir, exist_ok=True)

    # Write results to output file
    with open(output_path, 'w') as f:
        # Write enhanced patient summary
        print_patient_summary(patient_data, f)

        f.write(f"\n=== RANKED MATCHING TRIALS ({len(ranked_trials)} of {total_matches} total) ===\n\n")

        # Write each trial
        for i, trial in enumerate(ranked_trials):
            f.write(f"Rank #{i+1}\n")
            print_trial_summary(trial, f)

    print(f"\nResults saved to {output_path}")

    # Also save full JSON data
    json_output_path = os.path.splitext(output_path)[0] + ".json"
    with open(json_output_path, 'w') as f:
        json.dump({
            "patient": {
                "patientId": patient_data.get("patientId"),
                "key_clinical_info": patient_data.get("key_clinical_info", {})
            },
            "matched_trials": ranked_trials,
            "total_matches": total_matches
        }, f, indent=2)

    print(f"Complete data saved to {json_output_path}")

    # Display top 5 results on console
    display_count = min(5, len(ranked_trials))
    print(f"\n=== TOP {display_count} RANKED TRIALS ===")
    for i in range(display_count):
        print(f"\nRank #{i+1}")
        print_trial_summary(ranked_trials[i])

def main():
    parser = argparse.ArgumentParser(description="Match and rank clinical trials for a patient")
    parser.add_argument("--patient", "-p", type=str,
                      default="../data/synthea_sample_data_ccda_latest/Yolanda648_Baca589_355f70c7-b1f4-b1db-8843-56b8b193a30c.xml",
                      help="Path to the C-CDA XML file")
    parser.add_argument("--sqlite", "-s", type=str,
                      default="../data/clinical_trials.db",
                      help="Path to the SQLite database file")
    parser.add_argument("--chroma", "-c", type=str,
                      default="../data/chroma_db",
                      help="Path to the ChromaDB directory")
    parser.add_argument("--output", "-o", type=str,
                      default="../data/matched_trials_results.txt",
                      help="Path to save results")
    parser.add_argument("--top", "-k", type=int,
                      default=None,
                      help="Number of top results to return (default: all)")

    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)

    output_dir = os.path.dirname(args.output)
    if output_dir:  # Only create if there's a directory specified
        os.makedirs(output_dir, exist_ok=True)

    match_and_rank_trials(args.patient, args.sqlite, args.chroma, args.output, args.top)

if __name__ == "__main__":
    main()