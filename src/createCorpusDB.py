import json
import sqlite3
import re
import random
from typing import Dict, List, Any, Optional, Tuple
import os

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

def create_database(db_path: str):
    """
    Create SQLite database with appropriate tables for clinical trial data.

    Args:
        db_path: Path where the SQLite database should be created
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create trials table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trials (
        id INTEGER PRIMARY KEY,
        trial_id TEXT UNIQUE,
        trial_title TEXT,
        minimum_age INTEGER,
        maximum_age INTEGER,
        sex TEXT,
        accepts_healthy_volunteers BOOLEAN,
        participant_count INTEGER,
        requires_dsm5_diagnosis BOOLEAN,
        requires_straw_criteria BOOLEAN,
        requires_english BOOLEAN,
        requires_internet BOOLEAN,
        requires_specific_tests BOOLEAN,
        has_medication_requirements BOOLEAN,
        has_comorbidity_restrictions BOOLEAN,
        has_substance_restrictions BOOLEAN,
        has_psychiatric_restrictions BOOLEAN,
        has_pregnancy_restrictions BOOLEAN,
        targets_perimenopausal_women BOOLEAN,
        involves_online_therapy BOOLEAN,
        requires_assessments BOOLEAN,
        requires_followup BOOLEAN
    )
    ''')

    # Create conditions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conditions (
        id INTEGER PRIMARY KEY,
        trial_id TEXT,
        condition_name TEXT,
        FOREIGN KEY (trial_id) REFERENCES trials (trial_id)
    )
    ''')

    # Create interventions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interventions (
        id INTEGER PRIMARY KEY,
        trial_id TEXT,
        intervention_type TEXT,
        intervention_name TEXT,
        FOREIGN KEY (trial_id) REFERENCES trials (trial_id)
    )
    ''')

    # Create standard ages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS std_ages (
        id INTEGER PRIMARY KEY,
        trial_id TEXT,
        std_age TEXT,
        FOREIGN KEY (trial_id) REFERENCES trials (trial_id)
    )
    ''')

    # Create inclusion criteria table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inclusion_criteria (
        id INTEGER PRIMARY KEY,
        trial_id TEXT,
        criterion TEXT,
        FOREIGN KEY (trial_id) REFERENCES trials (trial_id)
    )
    ''')

    # Create exclusion criteria table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exclusion_criteria (
        id INTEGER PRIMARY KEY,
        trial_id TEXT,
        criterion TEXT,
        FOREIGN KEY (trial_id) REFERENCES trials (trial_id)
    )
    ''')

    # Create indexes for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trial_id ON trials (trial_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_min_age ON trials (minimum_age)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_max_age ON trials (maximum_age)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sex ON trials (sex)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conditions ON conditions (condition_name)')

    conn.commit()
    conn.close()

def insert_trial_data(db_path: str, parsed_data: Dict[str, Any]):
    """
    Insert parsed clinical trial data into the SQLite database.

    Args:
        db_path: Path to the SQLite database
        parsed_data: Dictionary containing parsed trial data
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert into trials table
    struct_criteria = parsed_data["structured_criteria"]
    add_criteria = parsed_data["additional_criteria"]

    cursor.execute('''
    INSERT OR REPLACE INTO trials (
        trial_id, trial_title, minimum_age, maximum_age, sex, accepts_healthy_volunteers,
        participant_count, requires_dsm5_diagnosis, requires_straw_criteria, requires_english,
        requires_internet, requires_specific_tests, has_medication_requirements,
        has_comorbidity_restrictions, has_substance_restrictions, has_psychiatric_restrictions,
        has_pregnancy_restrictions, targets_perimenopausal_women, involves_online_therapy,
        requires_assessments, requires_followup
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        parsed_data["trial_id"],
        parsed_data["trial_title"],
        struct_criteria["minimum_age"],
        struct_criteria["maximum_age"],
        struct_criteria["sex"],
        struct_criteria["accepts_healthy_volunteers"],
        parsed_data["participant_count"],
        add_criteria.get("requires_dsm5_diagnosis", False),
        add_criteria.get("requires_straw_criteria", False),
        add_criteria.get("requires_english", False),
        add_criteria.get("requires_internet", False),
        add_criteria.get("requires_specific_tests", False),
        add_criteria.get("has_medication_requirements", False),
        add_criteria.get("has_comorbidity_restrictions", False),
        add_criteria.get("has_substance_restrictions", False),
        add_criteria.get("has_psychiatric_restrictions", False),
        add_criteria.get("has_pregnancy_restrictions", False),
        add_criteria.get("targets_perimenopausal_women", False),
        add_criteria.get("involves_online_therapy", False),
        add_criteria.get("requires_assessments", False),
        add_criteria.get("requires_followup", False)
    ))

    # Insert conditions
    for condition in parsed_data["conditions"]:
        cursor.execute('''
        INSERT INTO conditions (trial_id, condition_name)
        VALUES (?, ?)
        ''', (parsed_data["trial_id"], condition))

    # Insert interventions
    for intervention in parsed_data["interventions"]:
        cursor.execute('''
        INSERT INTO interventions (trial_id, intervention_type, intervention_name)
        VALUES (?, ?, ?)
        ''', (
            parsed_data["trial_id"],
            intervention.get("type", ""),
            intervention.get("name", "")
        ))

    # Insert standard ages
    for std_age in struct_criteria.get("std_ages", []):
        cursor.execute('''
        INSERT INTO std_ages (trial_id, std_age)
        VALUES (?, ?)
        ''', (parsed_data["trial_id"], std_age))

    # Insert inclusion criteria
    for criterion in parsed_data["inclusion_criteria"]:
        cursor.execute('''
        INSERT INTO inclusion_criteria (trial_id, criterion)
        VALUES (?, ?)
        ''', (parsed_data["trial_id"], criterion))

    # Insert exclusion criteria
    for criterion in parsed_data["exclusion_criteria"]:
        cursor.execute('''
        INSERT INTO exclusion_criteria (trial_id, criterion)
        VALUES (?, ?)
        ''', (parsed_data["trial_id"], criterion))

    conn.commit()
    conn.close()

def process_json_file(json_file_path: str, db_path: str, sample_size: int = 1000):
    """
    Process a JSON file containing clinical trial data and insert into SQLite database.
    Allows sampling a specific number of trials from the dataset.

    Args:
        json_file_path: Path to the JSON file containing trial data
        db_path: Path where the SQLite database should be created/updated
        sample_size: Number of trials to sample from the dataset (default: 1000)

    Returns:
        Tuple of (total_trials, processed_trials)
    """
    # Create database if it doesn't exist
    if not os.path.exists(db_path):
        create_database(db_path)

    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)

            # Handle array of trials
            if isinstance(data, list):
                total_trials = len(data)
                print(f"Found {total_trials} trials in the dataset")

                # Sample trials if the dataset is larger than the sample size
                if total_trials > sample_size:
                    sampled_trials = random.sample(data, sample_size)
                    print(f"Sampling {sample_size} trials from the dataset")
                else:
                    sampled_trials = data
                    print(f"Using all {total_trials} trials (sample size {sample_size} is larger than dataset)")

                processed_trials = 0
                for i, trial in enumerate(sampled_trials):
                    try:
                        parsed_data = parse_clinical_trial_eligibility(trial)
                        insert_trial_data(db_path, parsed_data)
                        processed_trials += 1

                        # Print progress every 100 trials or 10% of sample size, whichever is smaller
                        progress_interval = min(100, max(1, sample_size // 10))
                        if (i + 1) % progress_interval == 0:
                            print(f"Processed {i + 1}/{len(sampled_trials)} trials ({(i+1)/len(sampled_trials)*100:.1f}%)")
                    except Exception as e:
                        print(f"Error processing trial: {e}")
            else:
                # Handle single trial
                total_trials = 1
                print("Found a single trial in the dataset")
                try:
                    parsed_data = parse_clinical_trial_eligibility(data)
                    insert_trial_data(db_path, parsed_data)
                    processed_trials = 1
                except Exception as e:
                    print(f"Error processing trial: {e}")
                    processed_trials = 0

            return total_trials, processed_trials
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return 0, 0

def main():
    """
    Main function to process the clinical trial data and create a SQLite database.
    """
    import argparse

    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description="Process clinical trial data from JSON to SQLite database with sampling option")
    parser.add_argument("--sample", "-s", type=int, default=5000,
                        help="Number of trials to sample from the dataset (default: 5000)")
    parser.add_argument("--input", "-i", type=str, default="../data/ctg-studies.json",
                        help="Path to the JSON file with clinical trial data")
    parser.add_argument("--output", "-o", type=str, default="../data/clinical_trials.db",
                        help="Path where the SQLite database will be created")

    args = parser.parse_args()

    # Configuration settings
    json_file_path = args.input   # Path to the JSON file with clinical trial data
    db_path = args.output         # Path where the SQLite database will be created
    sample_size = args.sample     # Number of trials to sample

    print(f"Processing clinical trial data from {json_file_path}...")
    print(f"Creating/updating database at {db_path}")
    print(f"Sampling {sample_size} trials")

    total, processed = process_json_file(json_file_path, db_path, sample_size)

    print(f"Processing complete: {processed}/{sample_size} trials successfully processed")
    if total > sample_size:
        print(f"Sampled {sample_size} out of {total} total trials in the dataset")

if __name__ == "__main__":
    main()