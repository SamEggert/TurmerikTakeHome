#!/usr/bin/env python3
import os
import argparse
import json
from datetime import datetime
import sys
import glob
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Make sure the parent directory is in the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import functions from existing files
from parseXMLs import parse_ccda_file, register_namespaces, extract_key_clinical_info
from createCorpusDB import process_json_file
from createVectorDB import create_corpus_db
from findTrialsByChroma import match_and_rank_trials, print_patient_summary
from evaluatePatientEligibility import evaluate_patient_eligibility
from generateOutput import generate_output

def process_single_patient(
    patient_file_path,
    trials_json_path,
    sqlite_db_path,
    chroma_db_path,
    output_dir,
    sample_size=5000,
    batch_size=100,
    top_k=10,
    model_name="gpt-4o-mini"
):
    """
    Process a single patient through the clinical trial matching pipeline.

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
    # Create patient-specific output directory
    patient_filename = os.path.basename(patient_file_path)
    patient_name = os.path.splitext(patient_filename)[0]
    patient_output_dir = os.path.join(output_dir, patient_name)
    os.makedirs(patient_output_dir, exist_ok=True)

    logger.info(f"Processing patient: {patient_name}")

    # Step 3: Parse patient CCDA file
    logger.info("Step 3: Parsing patient CCDA file")
    register_namespaces()
    patient_data = parse_ccda_file(patient_file_path)

    if not patient_data:
        logger.error(f"Failed to parse the patient file: {patient_file_path}")
        return None

    # Generate key clinical information if not already present
    if "key_clinical_info" not in patient_data:
        logger.info("Generating key clinical information...")
        patient_data["key_clinical_info"] = extract_key_clinical_info(patient_data)

    # Print patient summary
    logger.info("Patient summary:")
    print_patient_summary(patient_data)

    # Step 4: Match and rank trials for the patient
    logger.info("Step 4: Matching and ranking trials for the patient")
    matched_trials_output = os.path.join(patient_output_dir, "matched_trials_results.txt")
    matched_trials_json = os.path.join(patient_output_dir, "matched_trials_results.json")

    # This function saves both text and JSON output files
    match_and_rank_trials(
        file_path=patient_file_path,
        db_path=sqlite_db_path,
        chroma_path=chroma_db_path,
        output_path=matched_trials_output,
        top_k=top_k
    )

    # Step 5: Evaluate patient eligibility for top trials
    logger.info("Step 5: Evaluating patient eligibility for top trials")
    eligibility_output = os.path.join(patient_output_dir, "eligibility_results.json")

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

    logger.info(f"Eligibility evaluation complete. Results saved to {eligibility_output}")

    # Step 6: Generate output files
    logger.info("Step 6: Generating formatted output files")
    formatted_output_dir = os.path.join(patient_output_dir, "formatted_outputs")

    output_results = generate_output(
        eligibility_results_path=eligibility_output,
        output_dir=formatted_output_dir
    )

    logger.info(f"Output generation complete.")
    logger.info(f"JSON output: {output_results.get('json_path', 'None')}")
    logger.info(f"Excel output: {output_results.get('excel_path', 'None')}")

    # Return results for this patient
    return {
        "patient_name": patient_name,
        "patient_id": patient_data.get("patientId", "unknown"),
        "eligibility_results": eligibility_output,
        "output_files": output_results
    }

def run_pipeline(
    patient_path,
    trials_json_path,
    sqlite_db_path,
    chroma_db_path,
    output_dir,
    sample_size=5000,
    batch_size=100,
    top_k=10,
    model_name="gpt-4o-mini",
    max_patients=20
):
    """
    Run the entire clinical trial matching pipeline for one or multiple patients:
    1. Parse the clinical trials JSON and create SQLite database
    2. Create vector database from SQLite
    3-6. Process each patient (parse, match, evaluate, generate output)
    7. Generate a summary report for all patients

    Args:
        patient_path: Path to patient CCDA file or directory with multiple patient files
        trials_json_path: Path to clinical trials JSON
        sqlite_db_path: Path to create/use SQLite database
        chroma_db_path: Path to create/use ChromaDB
        output_dir: Directory to store outputs
        sample_size: Number of trials to sample from JSON
        batch_size: Batch size for vector DB creation
        top_k: Number of top trials to evaluate
        model_name: LLM model to use for eligibility evaluation
        max_patients: Maximum number of patients to process (0 for all)

    Returns:
        Dictionary with paths to output files
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Process clinical trials JSON to SQLite if needed
    print(f"\n{'='*80}\nStep 1: Creating/Using SQLite database from clinical trials JSON\n{'='*80}")
    if not os.path.exists(sqlite_db_path):
        total_trials, processed_trials = process_json_file(
            json_file_path=trials_json_path,
            db_path=sqlite_db_path,
            sample_size=sample_size
        )
        print(f"Processed {processed_trials} of {total_trials} trials")
    else:
        print(f"Using existing SQLite database at {sqlite_db_path}")

    # Step 2: Create vector database if needed
    print(f"\n{'='*80}\nStep 2: Creating/Using vector database from SQLite database\n{'='*80}")
    if not os.path.exists(chroma_db_path) or not os.listdir(chroma_db_path):
        create_corpus_db(
            sqlite_path=sqlite_db_path,
            chroma_path=chroma_db_path,
            batch_size=batch_size
        )
    else:
        print(f"Using existing vector database at {chroma_db_path}")

    # Step 3-6: Process all patients
    patient_results = []

    # Determine if we're processing a single file or a directory of files
    if os.path.isdir(patient_path):
        print(f"\n{'='*80}\nProcessing all patients in directory: {patient_path}\n{'='*80}")
        patient_files = glob.glob(os.path.join(patient_path, "*.xml"))
        print(f"Found {len(patient_files)} patient files")

        # Limit number of patients if requested
        if max_patients and max_patients < len(patient_files):
            print(f"Limiting processing to {max_patients} patients out of {len(patient_files)}")
            patient_files = patient_files[:max_patients]
        else:
            print(f"Processing all {len(patient_files)} patients")

        for i, patient_file in enumerate(patient_files, 1):
            print(f"\n{'='*80}\nProcessing patient {i}/{len(patient_files)}: {os.path.basename(patient_file)}\n{'='*80}")

            result = process_single_patient(
                patient_file_path=patient_file,
                trials_json_path=trials_json_path,
                sqlite_db_path=sqlite_db_path,
                chroma_db_path=chroma_db_path,
                output_dir=output_dir,
                sample_size=sample_size,
                batch_size=batch_size,
                top_k=top_k,
                model_name=model_name
            )

            if result:
                patient_results.append(result)
    else:
        # Single patient file
        print(f"\n{'='*80}\nProcessing single patient: {os.path.basename(patient_path)}\n{'='*80}")

        result = process_single_patient(
            patient_file_path=patient_path,
            trials_json_path=trials_json_path,
            sqlite_db_path=sqlite_db_path,
            chroma_db_path=chroma_db_path,
            output_dir=output_dir,
            sample_size=sample_size,
            batch_size=batch_size,
            top_k=top_k,
            model_name=model_name
        )

        if result:
            patient_results.append(result)

    # Step 7: Create a summary report if we have multiple patients
    if len(patient_results) > 1:
        print(f"\n{'='*80}\nStep 7: Creating multi-patient summary report\n{'='*80}")

        # Create a directory to store all eligibility results
        all_eligibility_dir = os.path.join(output_dir, "all_eligibility_results")
        os.makedirs(all_eligibility_dir, exist_ok=True)

        # Copy all eligibility results to this directory
        for result in patient_results:
            if result.get("eligibility_results") and os.path.exists(result["eligibility_results"]):
                patient_id = result.get("patient_id", "unknown")
                dest_path = os.path.join(all_eligibility_dir, f"eligibility_{patient_id}.json")

                try:
                    with open(result["eligibility_results"], 'r') as src, open(dest_path, 'w') as dest:
                        json.dump(json.load(src), dest, indent=2)
                except Exception as e:
                    print(f"Error copying eligibility results: {e}")

        # Generate summary output
        summary_output_dir = os.path.join(output_dir, "summary")
        os.makedirs(summary_output_dir, exist_ok=True)

        # Generate summary from all eligibility results
        summary_results = generate_output(
            eligibility_results_path=all_eligibility_dir,
            output_dir=summary_output_dir
        )

        print(f"Multi-patient summary complete.")
        if isinstance(summary_results, dict) and "summary_spreadsheet" in summary_results:
            print(f"Summary spreadsheet: {summary_results.get('summary_spreadsheet', 'None')}")

        # Highlight the simple format outputs
        print(f"Simple format files have been generated in {summary_output_dir}")
        print(f"Simple JSON file: {os.path.join(summary_output_dir, 'all_patients_simple_' + datetime.now().strftime('%Y%m%d') + '.json')}")
        print(f"Simple Excel file: {os.path.join(summary_output_dir, 'all_patients_simple_' + datetime.now().strftime('%Y%m%d') + '.xlsx')}")

        return {
            "patient_results": patient_results,
            "summary_dir": summary_output_dir,
            "summary_results": summary_results,
            "simple_json": os.path.join(summary_output_dir, 'all_patients_simple_' + datetime.now().strftime('%Y%m%d') + '.json'),
            "simple_excel": os.path.join(summary_output_dir, 'all_patients_simple_' + datetime.now().strftime('%Y%m%d') + '.xlsx')
        }
    elif len(patient_results) == 1:
        # Return the single patient result with simple format outputs highlighted
        output_files = patient_results[0].get('output_files', {})
        return {
            **patient_results[0],
            "simple_json": output_files.get('simple_json_path'),
            "simple_excel": output_files.get('simple_excel_path')
        }
    else:
        print("No patients were successfully processed.")
        return None

def main():
    parser = argparse.ArgumentParser(description="Clinical Trial Matching Pipeline")

    parser.add_argument("--patient", "-p", type=str,
                      default="../data/synthea_sample_data_ccda_latest/",
                      help="Path to a single patient CCDA XML file or a directory of patient files")

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
                      default=10000,
                      help="Number of trials to sample from the JSON (default: 5000)")

    parser.add_argument("--batch-size", "-b", type=int,
                      default=100,
                      help="Number of trials to process in each batch for vector DB creation (default: 100)")

    parser.add_argument("--top-k", "-k", type=int,
                      default=25,
                      help="Number of top trials to evaluate for eligibility (default: 10)")

    parser.add_argument("--model", "-m", type=str,
                      default="gpt-4o-mini",
                      help="LLM model to use for eligibility evaluation (default: gpt-4o-mini)")

    parser.add_argument("--max-patients", type=int,
                      default=10,
                      help="Maximum number of patients to process (default: 20, 0 for all)")

    args = parser.parse_args()

    # Check that patient path exists
    if not os.path.exists(args.patient):
        print(f"Error: Patient path not found at {args.patient}")
        return

    # Check that trials JSON exists
    if not os.path.exists(args.trials_json):
        print(f"Error: Clinical trials JSON not found at {args.trials_json}")
        return

    # Run the pipeline
    print(f"Starting clinical trial matching pipeline for patient(s): {args.patient}")
    final_output = run_pipeline(
        patient_path=args.patient,
        trials_json_path=args.trials_json,
        sqlite_db_path=args.sqlite_db,
        chroma_db_path=args.chroma_db,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        batch_size=args.batch_size,
        top_k=args.top_k,
        model_name=args.model,
        max_patients=args.max_patients
    )

    # Inside main() function, in the final output section, add:
    if final_output:
        print(f"\nPipeline completed successfully!")

        # Check if we processed multiple patients
        if "patient_results" in final_output:
            # Multi-patient case
            patient_count = len(final_output.get("patient_results", []))
            print(f"Processed {patient_count} patients")
            print(f"Summary directory: {final_output.get('summary_dir', 'Unknown')}")

            # Print paths to the simple format files
            print(f"\nSIMPLE FORMAT OUTPUT:")
            print(f"Simple JSON file: {final_output.get('simple_json', 'Not available')}")
            print(f"Simple Excel file: {final_output.get('simple_excel', 'Not available')}")

            # Rest of output...
        else:
            # Single patient case
            print(f"Eligibility results saved to: {final_output.get('eligibility_results', 'Unknown')}")

            print(f"\nSIMPLE FORMAT OUTPUT:")
            print(f"Simple JSON file: {final_output.get('simple_json', 'Not available')}")
            print(f"Simple Excel file: {final_output.get('simple_excel', 'Not available')}")

            # Rest of output...
    else:
        print("\nPipeline failed to complete.")

if __name__ == "__main__":
    main()