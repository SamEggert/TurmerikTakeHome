import json
import re
from typing import Dict, List, Any, Optional, Tuple

def parse_clinical_trial_eligibility(trial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a clinical trial JSON data to extract eligibility criteria and other relevant information.

    Args:
        trial_data: Dictionary containing the clinical trial data in condensed format

    Returns:
        Dictionary with structured eligibility criteria and trial information
    """
    # Extract the protocol section which contains all the relevant data
    protocol_section = trial_data.get("protocolSection", {})

    # Basic trial identification
    identification = protocol_section.get("identificationModule", {})
    trial_id = identification.get("nctId", "")
    trial_title = identification.get("briefTitle", "")

    # Extract eligibility criteria
    eligibility_module = protocol_section.get("eligibilityModule", {})

    # Parse structured criteria
    structured_criteria = {
        "sex": eligibility_module.get("sex", ""),
        "minimum_age": parse_age(eligibility_module.get("minimumAge", "")),
        "maximum_age": parse_age(eligibility_module.get("maximumAge", "")),
        "accepts_healthy_volunteers": eligibility_module.get("healthyVolunteers", False),
        "std_ages": eligibility_module.get("stdAges", []),
    }

    # Parse free-text inclusion and exclusion criteria
    eligibility_text = eligibility_module.get("eligibilityCriteria", "")
    inclusion_criteria, exclusion_criteria = extract_inclusion_exclusion(eligibility_text)

    # Extract condition information
    conditions_module = protocol_section.get("conditionsModule", {})
    conditions = conditions_module.get("conditions", [])

    # Extract arms and interventions information
    arms_interventions = protocol_section.get("armsInterventionsModule", {})
    interventions = [
        {
            "type": intervention.get("type", ""),
            "name": intervention.get("name", "")
        }
        for intervention in arms_interventions.get("interventions", [])
    ]

    # Extract enrollment information
    design_module = protocol_section.get("designModule", {})
    enrollment_info = design_module.get("enrollmentInfo", {})
    participant_count = enrollment_info.get("count", 0)

    # Extract brief summary for additional context
    description_module = protocol_section.get("descriptionModule", {})
    brief_summary = description_module.get("briefSummary", "")

    # Look for specific criteria in eligibility text
    additional_criteria = extract_additional_criteria(eligibility_text)

    # Extract keywords from brief summary if they're eligibility-related
    summary_criteria = extract_criteria_from_summary(brief_summary)
    additional_criteria.update(summary_criteria)

    return {
        "trial_id": trial_id,
        "trial_title": trial_title,
        "structured_criteria": structured_criteria,
        "inclusion_criteria": inclusion_criteria,
        "exclusion_criteria": exclusion_criteria,
        "conditions": conditions,
        "interventions": interventions,
        "participant_count": participant_count,
        "additional_criteria": additional_criteria
    }

def parse_age(age_string: str) -> Optional[int]:
    """
    Parse age string to extract numeric value in years.

    Args:
        age_string: String representing age (e.g., "40 Years")

    Returns:
        Integer age in years or None if parsing fails
    """
    if not age_string:
        return None

    match = re.search(r'(\d+)', age_string)
    if match:
        return int(match.group(1))
    return None

def extract_inclusion_exclusion(criteria_text: str) -> Tuple[List[str], List[str]]:
    """
    Extract inclusion and exclusion criteria from free text.

    Args:
        criteria_text: Free text containing eligibility criteria

    Returns:
        Tuple of (inclusion criteria list, exclusion criteria list)
    """
    inclusion_criteria = []
    exclusion_criteria = []

    # Split by sections
    sections = re.split(r'Inclusion Criteria:|Exclusion Criteria:', criteria_text)

    if len(sections) >= 2:
        # Extract inclusion criteria
        inclusion_text = sections[1]
        inclusion_end = inclusion_text.find("Exclusion Criteria:") if "Exclusion Criteria:" in inclusion_text else None
        if inclusion_end:
            inclusion_text = inclusion_text[:inclusion_end]

        # Extract bullet points
        inclusion_criteria = [item.strip() for item in re.findall(r'\*\s*(.*?)(?=\n\*|\n\n|$)', inclusion_text)]

    if len(sections) >= 3:
        # Extract exclusion criteria
        exclusion_text = sections[2]

        # Extract bullet points
        exclusion_criteria = [item.strip() for item in re.findall(r'\*\s*(.*?)(?=\n\*|\n\n|$)', exclusion_text)]

    return inclusion_criteria, exclusion_criteria

def extract_additional_criteria(eligibility_text: str) -> Dict[str, Any]:
    """
    Extract additional eligibility criteria from eligibility text.

    Args:
        eligibility_text: Eligibility criteria text

    Returns:
        Dictionary with additional criteria information
    """
    additional_criteria = {}

    # Look for specific diagnostic criteria
    if "DSM-5" in eligibility_text or "DSM 5" in eligibility_text:
        additional_criteria["requires_dsm5_diagnosis"] = True

    # Look for STRAW criteria for menopause staging
    if "STRAW" in eligibility_text:
        additional_criteria["requires_straw_criteria"] = True

    # Look for language requirements
    if re.search(r'speak.+English|English.+speak|read.+English|English.+read', eligibility_text, re.IGNORECASE):
        additional_criteria["requires_english"] = True

    # Look for internet access requirements
    if re.search(r'internet access|access to.+internet', eligibility_text, re.IGNORECASE):
        additional_criteria["requires_internet"] = True

    # Look for references to specific tests or assessments
    if re.search(r'test|assessment|score|scale|measurement', eligibility_text, re.IGNORECASE):
        additional_criteria["requires_specific_tests"] = True

    # Look for medication requirements or restrictions
    if re.search(r'medication|drug|treatment|therapy', eligibility_text, re.IGNORECASE):
        additional_criteria["has_medication_requirements"] = True

    # Look for comorbidity exclusions
    if re.search(r'comorbid|co-morbid|other condition|other disorder', eligibility_text, re.IGNORECASE):
        additional_criteria["has_comorbidity_restrictions"] = True

    # Look for substance use restrictions
    if re.search(r'alcohol|substance|drug use|addiction', eligibility_text, re.IGNORECASE):
        additional_criteria["has_substance_restrictions"] = True

    # Look for psychiatric condition restrictions
    if re.search(r'psychosis|mania|suicidal|homicidal|psychiatric', eligibility_text, re.IGNORECASE):
        additional_criteria["has_psychiatric_restrictions"] = True

    # Look for pregnancy-related criteria
    if re.search(r'pregnan|birth control|contracepti', eligibility_text, re.IGNORECASE):
        additional_criteria["has_pregnancy_restrictions"] = True

    return additional_criteria

def extract_criteria_from_summary(summary: str) -> Dict[str, Any]:
    """
    Extract potential eligibility criteria from the brief summary.

    Args:
        summary: Brief summary text

    Returns:
        Dictionary with additional criteria information
    """
    additional_criteria = {}

    # Look for indicators of eligibility in the summary
    if re.search(r'women.+perimenopause|perimenopause.+women', summary, re.IGNORECASE):
        additional_criteria["targets_perimenopausal_women"] = True

    if re.search(r'online.+therapy|internet.+therapy|e-CBT|electronic.+therapy', summary, re.IGNORECASE):
        additional_criteria["involves_online_therapy"] = True

    if re.search(r'questionnaire|survey|assessment|interview', summary, re.IGNORECASE):
        additional_criteria["requires_assessments"] = True

    if re.search(r'follow.?up|follow.up visit', summary, re.IGNORECASE):
        additional_criteria["requires_followup"] = True

    return additional_criteria

def main(json_file_path: str) -> List[Dict[str, Any]]:
    """
    Parse eligibility criteria from a JSON file containing multiple clinical trials.

    Args:
        json_file_path: Path to the JSON file containing trial data

    Returns:
        List of dictionaries with parsed eligibility information
    """
    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)

            results = []

            # Handle array of trials
            if isinstance(data, list):
                for trial in data:
                    results.append(parse_clinical_trial_eligibility(trial))
            else:
                # Handle single trial
                results.append(parse_clinical_trial_eligibility(data))

            return results
    except Exception as e:
        return [{"error": str(e)}]

if __name__ == "__main__":
    # Example usage
    results = main("smallerExample.json")
    print(json.dumps(results, indent=2))