import json
import sys
from pprint import pprint
from parseXMLs import parse_ccda_file, register_namespaces

def parse_and_display_single_file(file_path):
    """
    Parse a single C-CDA file and display its contents in a readable format.

    Args:
        file_path: Path to the C-CDA XML file
    """
    # Register namespaces (required for proper XML parsing)
    register_namespaces()

    print(f"Parsing file: {file_path}")

    # Parse the file
    patient_data = parse_ccda_file(file_path)

    if patient_data:
        # Print basic patient info
        print("\n=== PATIENT INFORMATION ===")
        print(f"Patient ID: {patient_data['patientId']}")

        # Print demographics
        print("\n=== DEMOGRAPHICS ===")
        for key, value in patient_data['demographics'].items():
            print(f"{key}: {value}")

        # Print conditions (problems)
        print(f"\n=== CONDITIONS ({len(patient_data['conditions'])}) ===")
        for i, condition in enumerate(patient_data['conditions'], 1):
            print(f"\nCondition {i}:")
            for key, value in condition.items():
                print(f"  {key}: {value}")

        # Print medications
        print(f"\n=== MEDICATIONS ({len(patient_data['medications'])}) ===")
        for i, medication in enumerate(patient_data['medications'], 1):
            print(f"\nMedication {i}:")
            for key, value in medication.items():
                print(f"  {key}: {value}")

        # Print lab results (first 5 only if there are many)
        lab_count = len(patient_data['labs'])
        print(f"\n=== LAB RESULTS ({lab_count}) ===")
        for i, lab in enumerate(patient_data['labs'][:5], 1):
            print(f"\nLab Result {i}:")
            for key, value in lab.items():
                print(f"  {key}: {value}")
        if lab_count > 5:
            print(f"  ... and {lab_count - 5} more lab results")

        # Print procedures
        print(f"\n=== PROCEDURES ({len(patient_data['procedures'])}) ===")
        for i, procedure in enumerate(patient_data['procedures'], 1):
            print(f"\nProcedure {i}:")
            for key, value in procedure.items():
                print(f"  {key}: {value}")

        # Print vitals (first 5 only if there are many)
        vital_count = len(patient_data['vitals'])
        print(f"\n=== VITAL SIGNS ({vital_count}) ===")
        for i, vital in enumerate(patient_data['vitals'][:5], 1):
            print(f"\nVital Sign {i}:")
            for key, value in vital.items():
                print(f"  {key}: {value}")
        if vital_count > 5:
            print(f"  ... and {vital_count - 5} more vital signs")

        # Save to JSON file for reference
        output_file = "single_patient_data.json"
        with open(output_file, 'w') as f:
            json.dump(patient_data, f, indent=2)
        print(f"\nComplete patient data saved to {output_file}")
    else:
        print("Failed to parse the file.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Use file path from command line argument
        file_path = sys.argv[1]
    else:
        # Default file path if none provided
        file_path = "data/synthea_sample_data_ccda_latest/Yolanda648_Baca589_355f70c7-b1f4-b1db-8843-56b8b193a30c.xml"

    parse_and_display_single_file(file_path)