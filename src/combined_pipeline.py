#!/usr/bin/env python3
import os
import argparse
import json
from datetime import datetime
import sys

# Make sure the parent directory is in the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import functions from existing files
from parseXMLs import parse_ccda_file, register_namespaces, extract_key_clinical_info
from createCorpusDB import process_json_file
from createVectorDB import create_corpus_db
from findTrialsByChroma import match_and_rank_trials, print_patient_summary
from evaluatePatientEligibility import evaluate_patient_eligibility
from generateOutput import generate_output

def run_pipeline(
    patient_file_path,
    trials_json_path,
    sqlite_db_path,
    chroma_db_path,
    output_dir,
    sample_size=1000,
    batch_size=100,
    top_k=20,
    model_name="gpt-4o-mini"
):
    """
    Run the entire clinical trial matching pipeline:
    1. Parse the clinical trials JSON and create SQLite database
    2. Create vector database from SQLite
    3. Parse patient CCDA file
    4. Match and rank trials for the patient
    5. Evaluate patient eligibility for top trials
    6. Generate output files (JSON and Excel)

    Args:
        patient_file_path: Path to patient CCDA file
        trials_json_path: Path to clinical trials JSON
        sqlite_db_path: Path to create/use SQLite database
        chroma_db_path: Path to create/use ChromaDB
        output_dir: Directory to store outputs
        sample_size: Number of trials to sample from JSON
        batch_size: Batch size for vector DB creation
        top_k: Number of top trials to evaluate
        model_name: LLM model to use for eligibility evaluation

    Returns:
        Dictionary with paths to output files
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Process clinical trials JSON to SQLite if needed
    if not os.path.exists(sqlite_db_path):
        print(f"\n{'='*80}\nStep 1: Creating SQLite database from clinical trials JSON\n{'='*80}")
        total_trials, processed_trials = process_json_file(
            json_file_path=trials_json_path,
            db_path=sqlite_db_path,
            sample_size=sample_size
        )
        print(f"Processed {processed_trials} of {total_trials} trials")
    else:
        print(f"\n{'='*80}\nStep 1: Using existing SQLite database at {sqlite_db_path}\n{'='*80}")

    # Step 2: Create vector database if needed
    if not os.path.exists(chroma_db_path) or not os.listdir(chroma_db_path):
        print(f"\n{'='*80}\nStep 2: Creating vector database from SQLite database\n{'='*80}")
        create_corpus_db(
            sqlite_path=sqlite_db_path,
            chroma_path=chroma_db_path,
            batch_size=batch_size
        )
    else:
        print(f"\n{'='*80}\nStep 2: Using existing vector database at {chroma_db_path}\n{'='*80}")

    # Step 3: Parse patient CCDA file
    print(f"\n{'='*80}\nStep 3: Parsing patient CCDA file\n{'='*80}")
    register_namespaces()
    patient_data = parse_ccda_file(patient_file_path)

    if not patient_data:
        print("Failed to parse the patient file.")
        return None

    # Generate key clinical information if not already present
    if "key_clinical_info" not in patient_data:
        print("Generating key clinical information...")
        patient_data["key_clinical_info"] = extract_key_clinical_info(patient_data)

    # Print patient summary
    print("\nPatient summary:")
    print_patient_summary(patient_data)

    # Step 4: Match and rank trials for the patient
    print(f"\n{'='*80}\nStep 4: Matching and ranking trials for the patient\n{'='*80}")
    matched_trials_output = os.path.join(output_dir, "matched_trials_results.txt")
    matched_trials_json = os.path.join(output_dir, "matched_trials_results.json")

    # This function saves both text and JSON output files
    match_and_rank_trials(
        file_path=patient_file_path,
        db_path=sqlite_db_path,
        chroma_path=chroma_db_path,
        output_path=matched_trials_output,
        top_k=top_k
    )

    # Step 5: Evaluate patient eligibility for top trials
    print(f"\n{'='*80}\nStep 5: Evaluating patient eligibility for top trials\n{'='*80}")
    eligibility_output = os.path.join(output_dir, "eligibility_results.json")

    # Evaluate eligibility using the matched trials JSON
    eligibility_results = evaluate_patient_eligibility(
        patient_data=patient_data,
        trials_json_path=matched_trials_json,
        model_name=model_name,
        top_k=top_k,
        temperature=0.1,
        current_date=datetime.now().strftime("%Y-%m-%d")
    )

    # Save eligibility results
    with open(eligibility_output, 'w') as f:
        json.dump(eligibility_results, f, indent=2)

    print(f"\nEligibility evaluation complete. Results saved to {eligibility_output}")

    # Step 6: Generate output files
    print(f"\n{'='*80}\nStep 6: Generating formatted output files\n{'='*80}")
    output_subdir = os.path.join(output_dir, "formatted_outputs")

    output_results = generate_output(
        eligibility_results_path=eligibility_output,
        output_dir=output_subdir
    )

    print(f"\nOutput generation complete.")
    print(f"JSON output: {output_results.get('json_path', 'None')}")
    print(f"Excel output: {output_results.get('excel_path', 'None')}")

    # Return both eligibility results and output files
    return {
        "eligibility_results": eligibility_output,
        "output_files": output_results
    }

def main():
    parser = argparse.ArgumentParser(description="Clinical Trial Matching Pipeline")

    parser.add_argument("--patient", "-p", type=str,
                      default="../data/synthea_sample_data_ccda_latest/Ada662_Sari509_Balistreri607_dbc4a3f7-9c69-4435-3ce3-4e1988ab6b91.xml",
                      help="Path to the patient CCDA XML file")

    parser.add_argument("--trials-json", "-j", type=str,
                      default="../data/ctg-studies.json",
                      help="Path to the clinical trials JSON file")

    parser.add_argument("--sqlite-db", "-s", type=str,
                      default="../data/clinical_trials.db",
                      help="Path to the SQLite database (will be created if it doesn't exist)")

    parser.add_argument("--chroma-db", "-c", type=str,
                      default="../data/chroma_db",
                      help="Path to the ChromaDB directory (will be created if it doesn't exist)")

    parser.add_argument("--output-dir", "-o", type=str,
                      default="../data/results",
                      help="Directory to store output files")

    parser.add_argument("--sample-size", type=int,
                      default=1000,
                      help="Number of trials to sample from the JSON (default: 1000)")

    parser.add_argument("--batch-size", "-b", type=int,
                      default=100,
                      help="Number of trials to process in each batch for vector DB creation (default: 100)")

    parser.add_argument("--top-k", "-k", type=int,
                      default=20,
                      help="Number of top trials to evaluate for eligibility (default: 20)")

    parser.add_argument("--model", "-m", type=str,
                      default="gpt-4o-mini",
                      help="LLM model to use for eligibility evaluation (default: gpt-4o-mini)")

    args = parser.parse_args()

    # Check that patient file exists
    if not os.path.exists(args.patient):
        print(f"Error: Patient file not found at {args.patient}")
        return

    # Check that trials JSON exists
    if not os.path.exists(args.trials_json):
        print(f"Error: Clinical trials JSON not found at {args.trials_json}")
        return

    # Run the pipeline
    print(f"Starting clinical trial matching pipeline for patient: {args.patient}")
    final_output = run_pipeline(
        patient_file_path=args.patient,
        trials_json_path=args.trials_json,
        sqlite_db_path=args.sqlite_db,
        chroma_db_path=args.chroma_db,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        batch_size=args.batch_size,
        top_k=args.top_k,
        model_name=args.model
    )

    if final_output:
        print(f"\nPipeline completed successfully!")
        print(f"Eligibility results saved to: {final_output.get('eligibility_results', 'Unknown')}")

        output_files = final_output.get('output_files', {})
        if output_files:
            print(f"Formatted JSON saved to: {output_files.get('json_path', 'None')}")
            print(f"Excel file saved to: {output_files.get('excel_path', 'None')}")
    else:
        print("\nPipeline failed to complete.")

if __name__ == "__main__":
    main()