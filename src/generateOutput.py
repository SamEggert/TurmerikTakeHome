#!/usr/bin/env python3
import os
import json
import argparse
import pandas as pd
from datetime import datetime
import sys
import logging
import glob
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_eligibility_results(input_path):
    """
    Load eligibility results from a JSON file.

    Args:
        input_path: Path to the eligibility results JSON file

    Returns:
        Dictionary containing eligibility results
    """
    logger.info(f"Loading eligibility results from {input_path}")
    try:
        with open(input_path, 'r') as f:
            results = json.load(f)
            logger.info(f"Successfully loaded results for patient {results.get('patient_id', 'Unknown')}")
            return results
    except Exception as e:
        logger.error(f"Error loading eligibility results: {str(e)}")
        return None

def format_simple_results(eligibility_results):
    """
    Format eligibility results into a simple format that only includes
    trials the patient actually matched to.

    Args:
        eligibility_results: Dictionary containing eligibility results

    Returns:
        Dictionary with simplified results containing only matched trials
    """
    patient_id = eligibility_results.get("patient_id", "unknown")
    eligible_trials = []

    # Check the trial results
    trial_results = eligibility_results.get("results", [])

    for trial in trial_results:
        # Skip if there's an error or no evaluation
        if 'error' in trial or 'evaluation' not in trial:
            continue

        evaluation = trial.get('evaluation', [])

        # Check if all criteria are met (this is how eligibility is determined)
        all_criteria_met = all(criterion.get('is_met', False) for criterion in evaluation)

        if all_criteria_met:
            # Extract only criteria names that were met
            criteria_met = [criterion.get("criterion", "") for criterion in evaluation
                        if criterion.get("is_met") == True]

            if criteria_met:  # Only include trials where criteria are met
                eligible_trials.append({
                    "trialId": trial.get("trial_id", ""),
                    "trialName": trial.get("trial_title", ""),
                    "eligibilityCriteriaMet": criteria_met
                })

    return {
        "patientId": patient_id,
        "eligibleTrials": eligible_trials
    }


def format_results_for_output(eligibility_results):
    """
    Format eligibility results into a structured format for output.

    Args:
        eligibility_results: Dictionary containing eligibility results

    Returns:
        Dictionary with formatted results
    """
    logger.info("Formatting results for output")

    patient_id = eligibility_results.get('patient_id', 'Unknown')
    evaluation_date = eligibility_results.get('evaluation_date', datetime.now().strftime("%Y-%m-%d"))
    trial_results = eligibility_results.get('results', [])

    # Create structured output
    formatted_output = {
        "patient_id": patient_id,
        "evaluation_date": evaluation_date,
        "total_trials_evaluated": eligibility_results.get('trials_evaluated', 0),
        "eligible_trials": [],
        "ineligible_trials": [],
        "indeterminate_trials": []
    }

    # Process each trial result
    for trial in trial_results:
        trial_id = trial.get('trial_id', 'Unknown')
        trial_title = trial.get('trial_title', 'Unknown')
        semantic_score = trial.get('semantic_score', 0)

        # Skip if there's an error or no evaluation
        if 'error' in trial or 'evaluation' not in trial:
            formatted_output["indeterminate_trials"].append({
                "trial_id": trial_id,
                "trial_title": trial_title,
                "semantic_score": semantic_score,
                "reason": trial.get('error', 'Unknown error')
            })
            continue

        # Get evaluation criteria
        evaluation = trial.get('evaluation', [])

        # Check if all criteria are met
        all_criteria_met = all(criterion.get('is_met', False) for criterion in evaluation)
        high_confidence = all(criterion.get('confidence', 'low') != 'low' for criterion in evaluation)

        # Create trial summary
        trial_summary = {
            "trial_id": trial_id,
            "trial_title": trial_title,
            "semantic_score": semantic_score,
            "criteria_summary": []
        }

        # Add each criterion evaluation
        for criterion in evaluation:
            criterion_summary = {
                "criterion": criterion.get('criterion', 'Unknown'),
                "is_met": criterion.get('is_met', False),
                "confidence": criterion.get('confidence', 'low'),
                "rationale": criterion.get('rationale', ''),
                "medications_and_supplements": criterion.get('medications_and_supplements', [])
            }
            trial_summary["criteria_summary"].append(criterion_summary)

        # Add to appropriate category
        if all_criteria_met:
            formatted_output["eligible_trials"].append(trial_summary)
        else:
            formatted_output["ineligible_trials"].append(trial_summary)

    # Sort trials by semantic score
    formatted_output["eligible_trials"].sort(key=lambda x: x["semantic_score"], reverse=True)
    formatted_output["ineligible_trials"].sort(key=lambda x: x["semantic_score"], reverse=True)
    formatted_output["indeterminate_trials"].sort(key=lambda x: x["semantic_score"], reverse=True)

    logger.info(f"Found {len(formatted_output['eligible_trials'])} eligible trials, "
                f"{len(formatted_output['ineligible_trials'])} ineligible trials, and "
                f"{len(formatted_output['indeterminate_trials'])} indeterminate trials")

    return formatted_output

def save_json_output(formatted_results, output_dir):
    """
    Save formatted results to a JSON file.

    Args:
        formatted_results: Dictionary with formatted eligibility results
        output_dir: Directory to save the output file

    Returns:
        Path to the saved JSON file
    """
    patient_id = formatted_results.get("patient_id", "unknown")
    date_stamp = datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(output_dir, f"patient_{patient_id}_eligibility_{date_stamp}.json")

    os.makedirs(output_dir, exist_ok=True)

    try:
        with open(output_file, 'w') as f:
            json.dump(formatted_results, f, indent=2)
        logger.info(f"JSON results saved to {output_file}")
        return output_file
    except Exception as e:
        logger.error(f"Error saving JSON results: {str(e)}")
        return None

def create_simple_dataframe(formatted_results):
    # formatted_results is the output from format_simple_results
    patient_id = formatted_results.get("patientId", "unknown")
    rows = []
    for trial in formatted_results.get("eligibleTrials", []):
        rows.append({
            "Patient ID": patient_id,
            "Trial ID": trial.get("trialId", ""),
            "Trial Name": trial.get("trialName", ""),
            # Join the list of met criteria into a single string (or keep it as a list if preferred)
            "Eligibility Criteria Met": ", ".join(trial.get("eligibilityCriteriaMet", []))
        })
    return pd.DataFrame(rows)


def create_dataframes(formatted_results):
    """
    Create pandas DataFrames for Excel output.

    Args:
        formatted_results: Dictionary with formatted eligibility results

    Returns:
        Tuple of DataFrames (summary_df, eligible_df, ineligible_df, eligible_criteria_df)
    """
    logger.info("Creating DataFrames for Excel output")

    patient_id = formatted_results.get("patient_id", "Unknown")
    evaluation_date = formatted_results.get("evaluation_date", "Unknown")

    # Create summary DataFrame
    summary_data = {
        "Patient ID": [patient_id],
        "Evaluation Date": [evaluation_date],
        "Total Trials Evaluated": [formatted_results.get("total_trials_evaluated", 0)],
        "Eligible Trials": [len(formatted_results.get("eligible_trials", []))],
        "Ineligible Trials": [len(formatted_results.get("ineligible_trials", []))],
        "Indeterminate Trials": [len(formatted_results.get("indeterminate_trials", []))]
    }
    summary_df = pd.DataFrame(summary_data)

    # Create eligible trials DataFrame
    eligible_trials = formatted_results.get("eligible_trials", [])
    eligible_data = []

    for trial in eligible_trials:
        row = {
            "Trial ID": trial.get("trial_id", ""),
            "Trial Title": trial.get("trial_title", ""),
            "Semantic Score": trial.get("semantic_score", 0),
            "Number of Criteria": len(trial.get("criteria_summary", [])),
            "All Criteria Met": "Yes",
            "Link": f"https://clinicaltrials.gov/study/{trial.get('trial_id', '')}"
        }
        eligible_data.append(row)

    eligible_df = pd.DataFrame(eligible_data) if eligible_data else pd.DataFrame()

    # Create ineligible trials DataFrame
    ineligible_trials = formatted_results.get("ineligible_trials", [])
    ineligible_data = []

    for trial in ineligible_trials:
        # Count unmet criteria
        criteria_summary = trial.get("criteria_summary", [])
        unmet_criteria = sum(1 for c in criteria_summary if not c.get("is_met", False))

        # Find first unmet criterion for summary
        first_unmet = next((c for c in criteria_summary if not c.get("is_met", False)), None)
        unmet_reason = first_unmet.get("criterion", "") + ": " + first_unmet.get("rationale", "") if first_unmet else "Unknown"

        row = {
            "Trial ID": trial.get("trial_id", ""),
            "Trial Title": trial.get("trial_title", ""),
            "Semantic Score": trial.get("semantic_score", 0),
            "Unmet Criteria": unmet_criteria,
            "Primary Reason": unmet_reason[:100] + "..." if len(unmet_reason) > 100 else unmet_reason,
            "Link": f"https://clinicaltrials.gov/study/{trial.get('trial_id', '')}"
        }
        ineligible_data.append(row)

    ineligible_df = pd.DataFrame(ineligible_data) if ineligible_data else pd.DataFrame()

    # Create detailed criteria DataFrame for eligible trials
    eligible_criteria_data = []

    for trial in eligible_trials:
        trial_id = trial.get("trial_id", "")
        trial_title = trial.get("trial_title", "")

        for criterion in trial.get("criteria_summary", []):
            row = {
                "Trial ID": trial_id,
                "Trial Title": trial_title,
                "Criterion": criterion.get("criterion", ""),
                "Is Met": "Yes" if criterion.get("is_met", False) else "No",
                "Confidence": criterion.get("confidence", "").capitalize(),
                "Rationale": criterion.get("rationale", ""),
                "Medications": ", ".join(criterion.get("medications_and_supplements", []))
            }
            eligible_criteria_data.append(row)

    eligible_criteria_df = pd.DataFrame(eligible_criteria_data) if eligible_criteria_data else pd.DataFrame()

    logger.info(f"Created DataFrames: Summary ({summary_df.shape[0]} rows), "
                f"Eligible ({eligible_df.shape[0] if not eligible_df.empty else 0} rows), "
                f"Ineligible ({ineligible_df.shape[0] if not ineligible_df.empty else 0} rows), "
                f"Criteria Detail ({eligible_criteria_df.shape[0] if not eligible_criteria_df.empty else 0} rows)")

    return summary_df, eligible_df, ineligible_df, eligible_criteria_df

def save_excel_output(dataframes, output_dir, patient_id):
    """
    Save DataFrames to an Excel file with improved error handling.

    Args:
        dataframes: Tuple of DataFrames (summary_df, eligible_df, ineligible_df, eligible_criteria_df)
        output_dir: Directory to save the output file
        patient_id: Patient ID for the filename

    Returns:
        Path to the saved Excel file
    """
    summary_df, eligible_df, ineligible_df, eligible_criteria_df = dataframes

    date_stamp = datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(output_dir, f"patient_{patient_id}_eligibility_{date_stamp}.xlsx")

    os.makedirs(output_dir, exist_ok=True)

    try:
        logger.info(f"Creating Excel file at {output_file}")

        # Debug info about dataframes
        logger.info(f"Summary DF shape: {summary_df.shape}")
        logger.info(f"Eligible DF shape: {eligible_df.shape if not eligible_df.empty else '(empty)'}")
        logger.info(f"Ineligible DF shape: {ineligible_df.shape if not ineligible_df.empty else '(empty)'}")
        logger.info(f"Criteria DF shape: {eligible_criteria_df.shape if not eligible_criteria_df.empty else '(empty)'}")

        # First check if pandas and openpyxl are properly installed
        try:
            import openpyxl
            logger.info(f"Using openpyxl version: {openpyxl.__version__}")
        except ImportError:
            logger.error("openpyxl is not installed. Please install with: pip install openpyxl")
            return None

        # Create writer
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            logger.info("Writing Summary sheet...")
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

            if not eligible_df.empty:
                logger.info("Writing Eligible Trials sheet...")
                eligible_df.to_excel(writer, sheet_name='Eligible Trials', index=False)
            else:
                logger.info("No eligible trials to write")

            if not ineligible_df.empty:
                logger.info("Writing Ineligible Trials sheet...")
                ineligible_df.to_excel(writer, sheet_name='Ineligible Trials', index=False)
            else:
                logger.info("No ineligible trials to write")

            if not eligible_criteria_df.empty:
                logger.info("Writing Eligibility Details sheet...")
                eligible_criteria_df.to_excel(writer, sheet_name='Eligibility Details', index=False)
            else:
                logger.info("No eligibility details to write")

        # Verify the file was created
        if os.path.exists(output_file):
            logger.info(f"Excel file successfully created: {output_file}")
            return output_file
        else:
            logger.error(f"Excel file was not created despite no exceptions: {output_file}")
            return None

    except Exception as e:
        logger.error(f"Error saving Excel results: {str(e)}")
        logger.error(f"Error traceback: {traceback.format_exc()}")

        # Try alternative method using CSV files
        try:
            logger.info("Attempting alternative Excel creation method...")
            return save_excel_output_alternative(dataframes, output_dir, patient_id)
        except Exception as alt_e:
            logger.error(f"Alternative method also failed: {str(alt_e)}")
            return None

def save_excel_output_alternative(dataframes, output_dir, patient_id):
    """
    Alternative method to save DataFrames to an Excel file by first creating CSVs.

    Args:
        dataframes: Tuple of DataFrames
        output_dir: Directory to save the output file
        patient_id: Patient ID for the filename

    Returns:
        Path to the saved Excel file
    """
    summary_df, eligible_df, ineligible_df, eligible_criteria_df = dataframes

    date_stamp = datetime.now().strftime("%Y%m%d")
    base_name = f"patient_{patient_id}_eligibility_{date_stamp}"
    csv_dir = os.path.join(output_dir, "temp_csv")
    output_file = os.path.join(output_dir, f"{base_name}.xlsx")

    os.makedirs(csv_dir, exist_ok=True)

    try:
        # Save each DataFrame as CSV
        summary_csv = os.path.join(csv_dir, f"{base_name}_summary.csv")
        eligible_csv = os.path.join(csv_dir, f"{base_name}_eligible.csv")
        ineligible_csv = os.path.join(csv_dir, f"{base_name}_ineligible.csv")
        details_csv = os.path.join(csv_dir, f"{base_name}_details.csv")

        logger.info("Saving DataFrames as CSV files")
        summary_df.to_csv(summary_csv, index=False)

        if not eligible_df.empty:
            eligible_df.to_csv(eligible_csv, index=False)

        if not ineligible_df.empty:
            ineligible_df.to_csv(ineligible_csv, index=False)

        if not eligible_criteria_df.empty:
            eligible_criteria_df.to_csv(details_csv, index=False)

        # Now load CSVs and create Excel
        logger.info("Creating Excel file from CSVs")
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            pd.read_csv(summary_csv).to_excel(writer, sheet_name='Summary', index=False)

            if os.path.exists(eligible_csv):
                pd.read_csv(eligible_csv).to_excel(writer, sheet_name='Eligible Trials', index=False)

            if os.path.exists(ineligible_csv):
                pd.read_csv(ineligible_csv).to_excel(writer, sheet_name='Ineligible Trials', index=False)

            if os.path.exists(details_csv):
                pd.read_csv(details_csv).to_excel(writer, sheet_name='Eligibility Details', index=False)

        logger.info(f"Excel file successfully created: {output_file}")
        return output_file

    except Exception as e:
        logger.error(f"Error in alternative Excel creation: {str(e)}")
        return None

def create_consolidated_json(all_patient_results, output_dir):
    """
    Create a consolidated JSON file with data from all patients.

    Args:
        all_patient_results: List of formatted patient result dictionaries
        output_dir: Directory to save the consolidated file

    Returns:
        Path to the saved consolidated JSON file
    """
    logger.info("Creating consolidated JSON file with all patient data")

    # Create a consolidated structure
    consolidated_data = {
        "generation_date": datetime.now().strftime("%Y-%m-%d"),
        "total_patients": len(all_patient_results),
        "patients": []
    }

    # Add summaries of each patient and their eligible trials
    for patient_result in all_patient_results:
        patient_id = patient_result.get("patient_id", "Unknown")
        eligible_trials = patient_result.get("eligible_trials", [])

        patient_summary = {
            "patient_id": patient_id,
            "evaluation_date": patient_result.get("evaluation_date", "Unknown"),
            "total_trials_evaluated": patient_result.get("total_trials_evaluated", 0),
            "eligible_trials_count": len(eligible_trials),
            "ineligible_trials_count": len(patient_result.get("ineligible_trials", [])),
            "eligible_trials": eligible_trials
        }

        consolidated_data["patients"].append(patient_summary)

    # Save consolidated JSON
    date_stamp = datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(output_dir, f"all_patients_consolidated_{date_stamp}.json")

    try:
        with open(output_file, 'w') as f:
            json.dump(consolidated_data, f, indent=2)
        logger.info(f"Consolidated JSON saved to {output_file}")
        return output_file
    except Exception as e:
        logger.error(f"Error saving consolidated JSON: {str(e)}")
        return None

def create_comprehensive_excel(all_patient_results, output_dir):
    """
    Create a comprehensive Excel file with detailed data from all patients.

    Args:
        all_patient_results: List of formatted patient result dictionaries
        output_dir: Directory to save the consolidated file

    Returns:
        Path to the saved comprehensive Excel file
    """
    logger.info("Creating comprehensive Excel file with all patient data")

    # Prepare DataFrames
    # 1. Patient summary
    patient_summary_data = []
    # 2. All eligible trials
    all_eligible_trials_data = []
    # 3. All eligible trials criteria
    all_criteria_data = []

    # Fill the DataFrames with data from each patient
    for patient_result in all_patient_results:
        patient_id = patient_result.get("patient_id", "Unknown")

        # Patient summary
        patient_summary_data.append({
            "Patient ID": patient_id,
            "Evaluation Date": patient_result.get("evaluation_date", "Unknown"),
            "Total Trials Evaluated": patient_result.get("total_trials_evaluated", 0),
            "Eligible Trials": len(patient_result.get("eligible_trials", [])),
            "Ineligible Trials": len(patient_result.get("ineligible_trials", [])),
            "Indeterminate Trials": len(patient_result.get("indeterminate_trials", []))
        })

        # All eligible trials for this patient
        for trial in patient_result.get("eligible_trials", []):
            trial_id = trial.get("trial_id", "")
            trial_title = trial.get("trial_title", "")

            all_eligible_trials_data.append({
                "Patient ID": patient_id,
                "Trial ID": trial_id,
                "Trial Title": trial_title,
                "Semantic Score": trial.get("semantic_score", 0),
                "Number of Criteria": len(trial.get("criteria_summary", [])),
                "Link": f"https://clinicaltrials.gov/study/{trial_id}"
            })

            # All criteria for this trial
            for criterion in trial.get("criteria_summary", []):
                all_criteria_data.append({
                    "Patient ID": patient_id,
                    "Trial ID": trial_id,
                    "Trial Title": trial_title,
                    "Criterion": criterion.get("criterion", ""),
                    "Is Met": "Yes" if criterion.get("is_met", False) else "No",
                    "Confidence": criterion.get("confidence", "").capitalize(),
                    "Rationale": criterion.get("rationale", ""),
                    "Medications": ", ".join(criterion.get("medications_and_supplements", []))
                })

    # Create DataFrames
    patient_summary_df = pd.DataFrame(patient_summary_data)
    all_eligible_trials_df = pd.DataFrame(all_eligible_trials_data)
    all_criteria_df = pd.DataFrame(all_criteria_data)

    # Sort DataFrames
    if not patient_summary_df.empty:
        patient_summary_df = patient_summary_df.sort_values("Patient ID")

    if not all_eligible_trials_df.empty:
        all_eligible_trials_df = all_eligible_trials_df.sort_values(["Patient ID", "Semantic Score"], ascending=[True, False])

    if not all_criteria_df.empty:
        all_criteria_df = all_criteria_df.sort_values(["Patient ID", "Trial ID"])

    # Save to Excel
    date_stamp = datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(output_dir, f"all_patients_comprehensive_{date_stamp}.xlsx")

    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            patient_summary_df.to_excel(writer, sheet_name='Patient Summary', index=False)

            if not all_eligible_trials_df.empty:
                all_eligible_trials_df.to_excel(writer, sheet_name='All Eligible Trials', index=False)

            if not all_criteria_df.empty:
                all_criteria_df.to_excel(writer, sheet_name='All Eligibility Criteria', index=False)

        logger.info(f"Comprehensive Excel file saved to {output_file}")
        return output_file
    except Exception as e:
        logger.error(f"Error saving comprehensive Excel: {str(e)}")

        # Try alternative method
        try:
            logger.info("Attempting alternative Excel creation method...")

            csv_dir = os.path.join(output_dir, "temp_csv")
            os.makedirs(csv_dir, exist_ok=True)

            summary_csv = os.path.join(csv_dir, "all_patients_summary.csv")
            trials_csv = os.path.join(csv_dir, "all_eligible_trials.csv")
            criteria_csv = os.path.join(csv_dir, "all_eligibility_criteria.csv")

            patient_summary_df.to_csv(summary_csv, index=False)
            all_eligible_trials_df.to_csv(trials_csv, index=False)
            all_criteria_df.to_csv(criteria_csv, index=False)

            # Now load CSVs and create Excel
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                pd.read_csv(summary_csv).to_excel(writer, sheet_name='Patient Summary', index=False)
                pd.read_csv(trials_csv).to_excel(writer, sheet_name='All Eligible Trials', index=False)
                pd.read_csv(criteria_csv).to_excel(writer, sheet_name='All Eligibility Criteria', index=False)

            logger.info(f"Comprehensive Excel file saved to {output_file} (alternative method)")
            return output_file
        except Exception as alt_e:
            logger.error(f"Alternative method also failed: {str(alt_e)}")
            return None

def process_single_eligibility_file(file_path, output_dir):
    """
    Process a single eligibility results file.
    """
    # Load the eligibility results
    eligibility_results = load_eligibility_results(file_path)
    if not eligibility_results:
        logger.error(f"Failed to load eligibility results from {file_path}")
        return {"error": f"Failed to load eligibility results from {file_path}"}

    patient_id = eligibility_results.get("patient_id", "unknown")

    # Format results for both detailed and simple output
    formatted_results = format_results_for_output(eligibility_results)
    simple_results = format_simple_results(eligibility_results)

    # Save JSON output (both formats)
    json_path = save_json_output(formatted_results, output_dir)

    # Save simple JSON format
    simple_json_path = os.path.join(output_dir, f"patient_{patient_id}_simple_eligibility_{datetime.now().strftime('%Y%m%d')}.json")
    with open(simple_json_path, 'w') as f:
        json.dump(simple_results, f, indent=2)
    logger.info(f"Simple JSON results saved to {simple_json_path}")

    # Create DataFrames for tabular output (original detailed format)
    dataframes = create_dataframes(formatted_results)

    # Create simple dataframe
    simple_df = create_simple_dataframe(simple_results)

    # Save Excel output (original format)
    excel_path = save_excel_output(
        dataframes,
        output_dir,
        patient_id
    )

    # Save simple Excel output
    simple_excel_path = os.path.join(output_dir, f"patient_{patient_id}_simple_eligibility_{datetime.now().strftime('%Y%m%d')}.xlsx")
    try:
        simple_df.to_excel(simple_excel_path, sheet_name='Eligible Trials', index=False)
        logger.info(f"Simple Excel results saved to {simple_excel_path}")
    except Exception as e:
        logger.error(f"Error saving simple Excel results: {str(e)}")
        simple_excel_path = None

    # Return output paths and formatted results
    return {
        "patient_id": patient_id,
        "json_path": json_path,
        "excel_path": excel_path,
        "simple_json_path": simple_json_path,
        "simple_excel_path": simple_excel_path,
        "formatted_results": formatted_results,  # Include the formatted results for consolidation
        "simple_results": simple_results  # Include simple results
    }

def generate_output(eligibility_results_path, output_dir):
    """
    Generate JSON and Excel output from eligibility results.
    """
    # Handle both single file and directory paths
    if os.path.isdir(eligibility_results_path):
        # Process all JSON files in the directory
        json_files = glob.glob(os.path.join(eligibility_results_path, "*.json"))
        logger.info(f"Found {len(json_files)} JSON files in {eligibility_results_path}")

        all_outputs = []
        all_formatted_results = []
        all_simple_results = []

        for json_file in json_files:
            result = process_single_eligibility_file(json_file, output_dir)
            if result and "error" not in result:
                all_outputs.append(result)
                # Store formatted results for consolidated output
                if "formatted_results" in result:
                    all_formatted_results.append(result["formatted_results"])
                if "simple_results" in result:
                    all_simple_results.append(result["simple_results"])

        # If we have multiple patients, create consolidated outputs
        if len(all_formatted_results) > 1:
            # Create consolidated JSON with all patient data (original format)
            consolidated_json = create_consolidated_json(all_formatted_results, output_dir)

            # Create comprehensive Excel with all patient data (original format)
            comprehensive_excel = create_comprehensive_excel(all_formatted_results, output_dir)

            # Create consolidated simple format
            simple_consolidated = {
                "patients": all_simple_results
            }
            simple_consolidated_path = os.path.join(output_dir, f"all_patients_simple_{datetime.now().strftime('%Y%m%d')}.json")
            with open(simple_consolidated_path, 'w') as f:
                json.dump(simple_consolidated, f, indent=2)

            # Create simple Excel with all patients
            simple_rows = []
            for patient in all_simple_results:
                patient_id = patient.get("patientId", "unknown")
                for trial in patient.get("eligibleTrials", []):
                    row = {
                        "Patient ID": patient_id,
                        "Trial ID": trial.get("trialId", ""),
                        "Trial Name": trial.get("trialName", ""),
                        "Eligibility Criteria Met": ", ".join(trial.get("eligibilityCriteriaMet", []))
                    }
                    simple_rows.append(row)

            if simple_rows:
                simple_all_df = pd.DataFrame(simple_rows)
                simple_all_excel = os.path.join(output_dir, f"all_patients_simple_{datetime.now().strftime('%Y%m%d')}.xlsx")
                simple_all_df.to_excel(simple_all_excel, sheet_name='Eligible Trials', index=False)
            else:
                simple_all_excel = None

            # Also create the existing summary spreadsheet for backward compatibility
            summary_file = create_summary_spreadsheet(all_outputs, output_dir)

            return {
                "individual_outputs": all_outputs,
                "summary_spreadsheet": summary_file,
                "consolidated_json": consolidated_json,
                "comprehensive_excel": comprehensive_excel,
                "simple_consolidated_json": simple_consolidated_path,
                "simple_consolidated_excel": simple_all_excel
            }
        elif len(all_outputs) == 1:
            return all_outputs[0]
        else:
            return {"error": "No valid eligibility results processed"}
    else:
        # Process single file
        return process_single_eligibility_file(eligibility_results_path, output_dir)

def create_summary_spreadsheet(output_files, output_dir):
    """
    Create a summary spreadsheet with data from all patients.

    Args:
        output_files: List of dictionaries with output file info
        output_dir: Directory to save the summary file

    Returns:
        Path to the saved summary Excel file
    """
    logger.info("Creating multi-patient summary spreadsheet")

    # Prepare summary data
    summary_data = []
    eligible_trials_all = []

    for patient_output in output_files:
        patient_id = patient_output.get("patient_id", "Unknown")
        json_path = patient_output.get("json_path")

        if json_path and os.path.exists(json_path):
            # Load formatted results for this patient
            with open(json_path, 'r') as f:
                patient_results = json.load(f)

            # Add to summary
            summary_data.append({
                "Patient ID": patient_id,
                "Evaluation Date": patient_results.get("evaluation_date", "Unknown"),
                "Total Trials Evaluated": patient_results.get("total_trials_evaluated", 0),
                "Eligible Trials": len(patient_results.get("eligible_trials", [])),
                "Ineligible Trials": len(patient_results.get("ineligible_trials", [])),
                "Excel Report": patient_output.get("excel_path", "Not available")
            })

            # Add eligible trials for this patient to the consolidated list
            for trial in patient_results.get("eligible_trials", []):
                eligible_trials_all.append({
                    "Patient ID": patient_id,
                    "Trial ID": trial.get("trial_id", ""),
                    "Trial Title": trial.get("trial_title", ""),
                    "Semantic Score": trial.get("semantic_score", 0),
                    "Link": f"https://clinicaltrials.gov/study/{trial.get('trial_id', '')}"
                })

    # Create DataFrames
    summary_df = pd.DataFrame(summary_data)
    eligible_trials_df = pd.DataFrame(eligible_trials_all)

    # Save to Excel
    date_stamp = datetime.now().strftime("%Y%m%d")
    summary_file = os.path.join(output_dir, f"all_patients_summary_{date_stamp}.xlsx")

    try:
        with pd.ExcelWriter(summary_file, engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Patient Summary', index=False)
            if not eligible_trials_df.empty:
                eligible_trials_df.to_excel(writer, sheet_name='All Eligible Trials', index=False)

        logger.info(f"Multi-patient summary saved to {summary_file}")
        return summary_file
    except Exception as e:
        logger.error(f"Error saving summary file: {str(e)}")
        return None

def main():
    """
    Main function to parse command line arguments and generate output files.
    """
    parser = argparse.ArgumentParser(description="Generate output files from eligibility results")

    parser.add_argument("--input", "-i", type=str, required=True,
                      help="Path to the eligibility results JSON file or directory")

    parser.add_argument("--output-dir", "-o", type=str, default="../data/outputs",
                      help="Directory to save output files")

    args = parser.parse_args()

    # Ensure input exists
    if not os.path.exists(args.input):
        logger.error(f"Input not found: {args.input}")
        sys.exit(1)

    # Generate outputs
    results = generate_output(args.input, args.output_dir)

    # Print results
    if "error" in results:
        logger.error(results["error"])
    elif "individual_outputs" in results:
        # Multi-patient results
        logger.info(f"Output generation completed successfully for {len(results['individual_outputs'])} patients.")

        # Log summary spreadsheet
        if "summary_spreadsheet" in results:
            logger.info(f"Summary spreadsheet: {results.get('summary_spreadsheet', 'None')}")

        # Log consolidated JSON
        if "consolidated_json" in results:
            logger.info(f"Consolidated JSON with all patient data: {results.get('consolidated_json', 'None')}")

        # Log comprehensive Excel
        if "comprehensive_excel" in results:
            logger.info(f"Comprehensive Excel with all patient data: {results.get('comprehensive_excel', 'None')}")
    else:
        # Single patient results
        logger.info("Output generation completed successfully:")
        logger.info(f"JSON output: {results.get('json_path', 'None')}")
        logger.info(f"Excel output: {results.get('excel_path', 'None')}")

if __name__ == "__main__":
    main()