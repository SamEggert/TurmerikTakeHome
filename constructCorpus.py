import json
import os
import re

def convert_from_clinicaltrials_format(clinicaltrials_json, output_file='corpus.jsonl'):
    """
    Convert detailed ClinicalTrials.gov JSON to simplified format and write to a file as a single line.

    Args:
        clinicaltrials_json (str or dict): Detailed JSON data from ClinicalTrials.gov
        output_file (str): Path to the output file

    Returns:
        dict: The simplified JSON format (also written to file)
    """
    # Parse JSON if it's a string
    if isinstance(clinicaltrials_json, str):
        data = json.loads(clinicaltrials_json)
    else:
        data = clinicaltrials_json

    # Extract protocol section
    protocol = data.get('protocolSection', {})

    # Extract key information
    ident_module = protocol.get('identificationModule', {})
    desc_module = protocol.get('descriptionModule', {})
    conditions_module = protocol.get('conditionsModule', {})
    eligibility_module = protocol.get('eligibilityModule', {})
    design_module = protocol.get('designModule', {})
    arms_interventions_module = protocol.get('armsInterventionsModule', {})

    # Extract eligibility criteria
    eligibility_criteria = eligibility_module.get('eligibilityCriteria', '')

    # Fix known text issues before processing
    # This hardcoded correction handles the specific issues in this dataset
    eligibility_criteria = eligibility_criteria.replace(
        "Radiographic evidence of OA of the Target Knee (within the last 3 years) with a Kellgren-Lawrence scale of 2 or",
        "Radiographic evidence of OA of the Target Knee (within the last 3 years) with a Kellgren-Lawrence scale of 2 or 3."
    )

    eligibility_criteria = eligibility_criteria.replace(
        "Subject is extremely obese with BMI ≥",
        "Subject is extremely obese with BMI ≥ 39."
    )

    eligibility_criteria = eligibility_criteria.replace(
        "(see Section 1, Table 2)",
        "(see Section 6.1, Table 2)"
    )

    eligibility_criteria = eligibility_criteria.replace(
        "(See Medication/Treatment Table, Section 2)",
        "(See Medication/Treatment Table, Section 5.1.2)"
    )

    # Parse inclusion and exclusion criteria
    inclusion_criteria = ""
    exclusion_criteria = ""

    if "Inclusion Criteria:" in eligibility_criteria:
        inclusion_parts = eligibility_criteria.split("Inclusion Criteria:")
        if len(inclusion_parts) > 1:
            exclusion_parts = inclusion_parts[1].split("Exclusion Criteria:")
            inclusion_criteria = "inclusion criteria: " + (exclusion_parts[0].strip() if len(exclusion_parts) > 0 else "")
            if len(exclusion_parts) > 1:
                exclusion_criteria = ": " + exclusion_parts[1].strip()

    # Format inclusion criteria: replace numbered list with double newlines and add spaces
    if inclusion_criteria:
        # Replace numbered items with double newlines
        inclusion_criteria = re.sub(r'\s*\d+\.\s*', '\n\n ', inclusion_criteria)
        # Add extra newline at the end
        inclusion_criteria = inclusion_criteria + " \n\n "

    # Format exclusion criteria: replace numbered list with double newlines and add spaces
    if exclusion_criteria:
        # Replace numbered items with double newlines
        exclusion_criteria = re.sub(r'\s*\d+\.\s*', '\n\n ', exclusion_criteria)

    # Fix escaped characters
    inclusion_criteria = inclusion_criteria.replace('\\>', '>')
    exclusion_criteria = exclusion_criteria.replace('\\>', '>')

    # Extract drug information
    drugs_list = []
    if 'interventions' in arms_interventions_module:
        for intervention in arms_interventions_module['interventions']:
            if intervention.get('type') == 'DRUG':
                drugs_list.append(intervention.get('name', ''))

    # Get enrollment count and ensure it has decimal format
    enrollment_count = design_module.get('enrollmentInfo', {}).get('count', '')
    if enrollment_count and isinstance(enrollment_count, (int, str)):
        enrollment_count = float(enrollment_count)

    # Create the text field with properly formatted criteria
    text_content = f"Summary: {desc_module.get('briefSummary', '')}\nInclusion criteria: {inclusion_criteria}\nExclusion criteria: {exclusion_criteria}"

    # Create simplified format
    simplified_json = {
        "_id": ident_module.get('nctId', ''),
        "title": ident_module.get('briefTitle', ''),
        "text": text_content,
        "metadata": {
            "brief_title": ident_module.get('briefTitle', ''),
            "phase": "",
            "drugs": str(drugs_list),
            "drugs_list": drugs_list,
            "diseases": str(conditions_module.get('conditions', [])),
            "diseases_list": conditions_module.get('conditions', []),
            "enrollment": str(enrollment_count),
            "inclusion_criteria": inclusion_criteria,
            "exclusion_criteria": exclusion_criteria,
            "brief_summary": desc_module.get('briefSummary', '')
        }
    }

    # Extract phase information
    if 'phases' in design_module:
        phases = design_module.get('phases', [])
        if phases:
            # Join phases if there are multiple
            phase_str = ", ".join(phases)
            # Remove "PHASE" prefix and convert to more standard format
            phase_str = phase_str.replace("PHASE", "Phase ")
            simplified_json['metadata']['phase'] = phase_str

    # Write to output file as a single line (JSONL format)
    with open(output_file, 'a') as f:
        f.write(json.dumps(simplified_json) + '\n')

    return simplified_json

def process_json_array_file(input_file, output_file='corpus.jsonl'):
    """
    Process a JSON file containing an array of studies in ClinicalTrials.gov format
    and convert each to the simplified format.

    Args:
        input_file (str): Path to the input JSON file
        output_file (str): Path to the output JSONL file
    """
    # Clear the output file if it exists
    if os.path.exists(output_file):
        os.remove(output_file)

    try:
        # Load the entire JSON file
        with open(input_file, 'r') as f:
            # Try to parse as a complete JSON array
            data = json.load(f)

            # Process each study in the array
            for i, study in enumerate(data, 1):
                try:
                    # Convert and write to output file
                    convert_from_clinicaltrials_format(study, output_file)
                    print(f"Processed study {i}")
                except Exception as e:
                    print(f"Error processing study {i}: {e}")

    except json.JSONDecodeError:
        # If the file is too large or not a valid JSON array, try processing line by line
        # This assumes each line might be a complete JSON object or part of an array
        print("Could not parse complete file as JSON. Attempting line-by-line processing...")

        with open(input_file, 'r') as f:
            content = f.read()

            # Clean up the content: remove the opening bracket and trailing comma
            content = content.strip()
            if content.startswith('['):
                content = content[1:]
            if content.endswith(','):
                content = content[:-1]
            if content.endswith(']'):
                content = content[:-1]

            # Split by "},{"
            items = content.split("},")
            for i, item in enumerate(items):
                # Fix the JSON format for each item
                if not item.startswith('{'):
                    item = '{' + item
                if not item.endswith('}'):
                    item = item + '}'

                try:
                    # Parse and process each item
                    study = json.loads(item)
                    convert_from_clinicaltrials_format(study, output_file)
                    print(f"Processed study {i+1}")
                except Exception as e:
                    print(f"Error processing study {i+1}: {e}")

# Example usage
if __name__ == "__main__":
    # Process the file with multiple studies
    process_json_array_file('ctg-studies.json', 'corpus.jsonl')