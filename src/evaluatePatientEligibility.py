import json
import os
import datetime
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import sys

# Import from the enhanced parser module to parse CCDA files
sys.path.append('../')  # Add parent directory to path to import custom modules
from src.parseXMLs import parse_ccda_file, register_namespaces, extract_key_clinical_info

def evaluate_patient_eligibility(
    patient_data: Dict[str, Any],
    trials_json_path: str,
    model_name: str = "gpt-4o-mini",
    top_k: int = 20,
    temperature: float = 0.1,
    current_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates whether a patient meets the inclusion criteria for the top k trials.

    Args:
        patient_data: Dictionary containing patient information
        trials_json_path: Path to the JSON file with ranked trials data (output from findTrialsByChroma)
        model_name: The GPT model to use
        top_k: Number of top trials to evaluate (default: 20)
        temperature: Temperature setting for the LLM
        current_date: Optional date string (defaults to today's date)

    Returns:
        Dictionary with evaluation results for each trial
    """
    # Load environment variables from .env file
    load_dotenv()

    # Set current date if not provided
    if current_date is None:
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Load the trials data
    with open(trials_json_path, 'r') as f:
        trials_data = json.load(f)

    # Extract ranked trials
    ranked_trials = trials_data.get("matched_trials", [])

    # Limit to top k trials
    top_trials = ranked_trials[:min(top_k, len(ranked_trials))]

    # Initialize the LLM with API key from environment variables
    llm = ChatOpenAI(
        model=model_name,
        temperature=temperature
    )

    # Extract patient clinical note from the data
    key_clinical_info = patient_data.get("key_clinical_info", {})

    # Construct a comprehensive clinical note from patient data
    clinical_note = f"""
Patient Demographics: {key_clinical_info.get('demographic_summary', 'Not available')}

Medical Conditions: {key_clinical_info.get('condition_summary', 'None recorded')}

Current Medications: {key_clinical_info.get('medication_summary', 'None recorded')}

Recent Lab Results: {key_clinical_info.get('lab_summary', 'None recorded')}

Recent Procedures: {key_clinical_info.get('procedure_summary', 'None recorded')}
"""

    # Process each trial
    results = []

    for i, trial in enumerate(top_trials):
        # Extract inclusion criteria
        trial_id = trial.get("trial_id", "Unknown")
        trial_title = trial.get("trial_title", "Unknown")

        print(f"Evaluating trial {i+1}/{len(top_trials)}: {trial_id} - {trial_title}")

        # For this example, we'll query the database to get inclusion criteria
        # In a real implementation, you might want to include these in the JSON output
        inclusion_criteria = extract_inclusion_criteria(trial, trials_json_path)

        # Format the criteria for the prompt
        formatted_criteria = format_inclusion_criteria(inclusion_criteria)

        # Construct the prompt
        prompt = f"""# Task
Your job is to decide which of the following inclusion criteria the given patient meets.

# Patient
Below is a clinical note describing the patient's current health status:
```
{clinical_note}
```

# Current Date
Assume that the current date is: {current_date}

# Inclusion Criteria
The inclusion criteria being assessed are listed below, followed by their definitions:
{formatted_criteria}

# Assessment
For each of the criteria above, use the patient's clinical note to determine whether the patient meets each criteria. Think step by step, and
justify your answer.

Format your response as a JSON list of dictionaries, where each dictionary contains the following elements:
* criterion: str - The name of the criterion being assessed
* medications_and_supplements: List[str] - The names of all current medications and supplements that the patient is taking
* rationale: str - Your reasoning as to why the patient does or does not meet that criterion
* is_met: bool - "true" if the patient meets that criterion, or it can be inferred that they meet that criterion with common sense. "false" if the
patient does not or it is impossible to assess this given the provided information.
* confidence: str - Either "low", "medium", or "high" to reflect your confidence in your response

Please provide your JSON response:
"""

        # Send to the LLM
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            response_text = response.content.strip()

            # Try to parse JSON from the response
            # Find JSON content (between triple backticks if present)
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0].strip()

            try:
                evaluation = json.loads(json_match)

                # Add trial info to the evaluation
                trial_result = {
                    "trial_id": trial_id,
                    "trial_title": trial_title,
                    "semantic_score": trial.get("semantic_score", 0),
                    "evaluation": evaluation
                }

                results.append(trial_result)
                print(f"Successfully evaluated trial {trial_id}")

            except json.JSONDecodeError:
                # If JSON parsing fails, save the raw response
                results.append({
                    "trial_id": trial_id,
                    "trial_title": trial_title,
                    "semantic_score": trial.get("semantic_score", 0),
                    "raw_response": response_text,
                    "error": "Failed to parse JSON response"
                })
                print(f"Warning: Failed to parse JSON response for trial {trial_id}")

        except Exception as e:
            # Handle any API errors
            results.append({
                "trial_id": trial_id,
                "trial_title": trial_title,
                "semantic_score": trial.get("semantic_score", 0),
                "error": str(e)
            })
            print(f"Error evaluating trial {trial_id}: {e}")

    # Return the full set of results
    return {
        "patient_id": patient_data.get("patientId", "Unknown"),
        "evaluation_date": current_date,
        "trials_evaluated": len(results),
        "results": results
    }

def extract_inclusion_criteria(trial: Dict[str, Any], trials_json_path: str) -> List[str]:
    """
    Extract inclusion criteria for a trial. In a real implementation,
    this would likely query a database or use data already in the JSON.

    For demonstration purposes, this creates sample criteria based on the trial data.
    """
    # This is a placeholder implementation
    # In practice, you would extract real inclusion criteria from the database
    criteria = []

    # Add age criteria
    min_age = trial.get("minimum_age")
    max_age = trial.get("maximum_age")
    if min_age is not None and max_age is not None:
        criteria.append(f"Patient must be between {min_age} and {max_age} years of age")
    elif min_age is not None:
        criteria.append(f"Patient must be at least {min_age} years of age")
    elif max_age is not None:
        criteria.append(f"Patient must be no more than {max_age} years of age")

    # Add sex criteria
    sex = trial.get("sex")
    if sex == "MALE":
        criteria.append("Patient must be male")
    elif sex == "FEMALE":
        criteria.append("Patient must be female")

    # Add condition criteria
    conditions = trial.get("conditions", [])
    if conditions:
        criteria.append(f"Patient must have one of the following conditions: {', '.join(conditions)}")

    # Add intervention-related criteria
    interventions = trial.get("interventions", [])
    for intervention in interventions:
        intervention_text = intervention.get("intervention", "")
        if "Drug" in intervention_text:
            criteria.append(f"Patient must be eligible for medication: {intervention_text}")
        elif "Procedure" in intervention_text:
            criteria.append(f"Patient must be eligible for procedure: {intervention_text}")

    # Add placeholders for common criteria if list is too short
    if len(criteria) < 3:
        criteria.append("Patient must be able to provide informed consent")
        criteria.append("Patient must be willing to comply with all study procedures")

    return criteria

def format_inclusion_criteria(criteria: List[str]) -> str:
    """Format inclusion criteria for the prompt"""
    if not criteria:
        return "No specific inclusion criteria found for this trial."

    formatted = ""
    for i, criterion in enumerate(criteria):
        formatted += f"{i+1}. {criterion}\n"

    return formatted

def save_eligibility_results(results: Dict[str, Any], output_path: str) -> None:
    """Save the eligibility evaluation results to a JSON file"""
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {output_path}")

def main():
    """
    Main function to evaluate patient eligibility for clinical trials using default values.
    """
    # Default values
    patient_file = "../data/synthea_sample_data_ccda_latest/Ada662_Sari509_Balistreri607_dbc4a3f7-9c69-4435-3ce3-4e1988ab6b91.xml"
    ranked_trials_json = "../data/matched_trials_results.json"
    output_path = "../data/eligibility_results.json"

    # Register namespaces for XML parsing
    register_namespaces()

    # Parse the patient file
    print(f"Parsing patient file: {patient_file}")
    patient_data = parse_ccda_file(patient_file)

    if not patient_data:
        print("Failed to parse the patient file.")
        return

    # Generate key clinical information if not already present
    if "key_clinical_info" not in patient_data:
        print("Generating key clinical information...")
        patient_data["key_clinical_info"] = extract_key_clinical_info(patient_data)

    # Run evaluation with default parameters
    print(f"Evaluating patient eligibility for top 10 trials...")
    results = evaluate_patient_eligibility(
        patient_data=patient_data,
        trials_json_path=ranked_trials_json,
        top_k=10
    )

    # Save results
    save_eligibility_results(results, output_path)
    print(f"Evaluation complete. Results saved to {output_path}")

if __name__ == "__main__":
    main()