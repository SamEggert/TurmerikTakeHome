import json
import sys
import sqlite3
import os
from parseXMLs import parse_ccda_file, register_namespaces

def match_patient_to_trials(patient_data, db_path="clinical_trials.db", limit=100):
    """
    Match patient data against clinical trials in the database based on demographics.
    Uses a single optimized query for performance.

    Args:
        patient_data: Dictionary containing parsed patient data from C-CDA file
        db_path: Path to the SQLite database containing clinical trials
        limit: Maximum number of trials to return (default: 100)

    Returns:
        List of matching trial dictionaries
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} not found")
        return []

    # Extract demographic information
    demographics = patient_data.get('demographics', {})
    age = demographics.get('age')
    sex = demographics.get('sex')
    race = demographics.get('race')
    ethnicity = demographics.get('ethnicity')

    # Default sex mapping (map patient sex to trial sex format)
    sex_mapping = {
        'M': 'MALE',
        'F': 'FEMALE',
        'Male': 'MALE',
        'Female': 'FEMALE'
    }

    # Map patient sex to database format
    mapped_sex = sex_mapping.get(sex)

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

    print(f"Returning {len(matches)} of {total_matches} total matching trials")

    conn.close()
    return matches, total_matches

def parse_and_match_trials(file_path, db_path="clinical_trials.db", limit=100):
    """
    Parse a C-CDA file and match the patient to clinical trials.

    Args:
        file_path: Path to the C-CDA XML file
        db_path: Path to the SQLite database containing clinical trials
        limit: Maximum number of trials to return
    """
    # Register namespaces (required for proper XML parsing)
    register_namespaces()

    print(f"Parsing file: {file_path}")

    # Parse the file
    patient_data = parse_ccda_file(file_path)

    if not patient_data:
        print("Failed to parse the patient file.")
        return

    # Print basic patient information
    print("\n=== PATIENT INFORMATION ===")
    print(f"Patient ID: {patient_data['patientId']}")

    # Print demographics
    print("\n=== DEMOGRAPHICS ===")
    for key, value in patient_data['demographics'].items():
        print(f"{key}: {value}")

    # Find matching trials
    print("\nMatching patient to clinical trials...")
    matching_trials, total_matches = match_patient_to_trials(patient_data, db_path, limit)

    # Display only summary results
    print(f"\n=== MATCHING TRIALS ({len(matching_trials)} of {total_matches} total) ===")
    if not matching_trials:
        print("No matching trials found.")

    # Save full results to a JSON file
    output_file = f"{os.path.splitext(os.path.basename(file_path))[0]}_matching_trials.json"
    with open(output_file, 'w') as f:
        json.dump(matching_trials, f, indent=2)

    print(f"\nComplete matching trial data saved to {output_file}")

    return patient_data, matching_trials

def main():
    """
    Main function to handle command line arguments and run the program.
    """
    # Default values
    file_path = "data/synthea_sample_data_ccda_latest/Yolanda648_Baca589_355f70c7-b1f4-b1db-8843-56b8b193a30c.xml"
    db_path = "clinical_trials.db"
    limit = 100  # Default limit on number of trials to return

    # Parse command line arguments if provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    if len(sys.argv) > 2:
        db_path = sys.argv[2]
    if len(sys.argv) > 3:
        try:
            limit = int(sys.argv[3])
        except ValueError:
            print(f"Warning: Invalid limit value '{sys.argv[3]}'. Using default limit of 100.")

    parse_and_match_trials(file_path, db_path, limit)

if __name__ == "__main__":
    main()