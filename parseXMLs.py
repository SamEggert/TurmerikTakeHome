import os
import xml.etree.ElementTree as ET
import json
import pandas as pd
from datetime import datetime

# Define namespaces used in C-CDA
namespaces = {
    'cda': 'urn:hl7-org:v3',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'sdtc': 'urn:hl7-org:sdtc'
}

def register_namespaces():
    """Register namespaces for better XPath handling"""
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

def parse_ccda_file(file_path):
    """
    Parse a C-CDA XML file and extract patient information relevant for clinical trial matching.

    Args:
        file_path: Path to the C-CDA XML file

    Returns:
        dict: Dictionary containing patient information
    """
    try:
        # Parse the XML file
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Extract patient data
        patient_data = {
            "patientId": extract_patient_id(root),
            "demographics": extract_demographics(root),
            "conditions": extract_conditions(root),
            "medications": extract_medications(root),
            "labs": extract_lab_results(root),
            "procedures": extract_procedures(root),
            "vitals": extract_vitals(root)
        }

        return patient_data

    except Exception as e:
        print(f"Error parsing {file_path}: {str(e)}")
        return None

def extract_patient_id(root):
    """Extract patient ID from C-CDA"""
    try:
        # Try to find the patient ID in the recordTarget element
        record_target = root.find('.//{{{0}}}recordTarget'.format(namespaces['cda']))
        if record_target is not None:
            patient_role = record_target.find('.//{{{0}}}patientRole'.format(namespaces['cda']))
            if patient_role is not None:
                id_element = patient_role.find('.//{{{0}}}id'.format(namespaces['cda']))
                if id_element is not None:
                    return id_element.get('extension', 'unknown')
        return "unknown"
    except Exception as e:
        print(f"Error extracting patient ID: {str(e)}")
        return "unknown"

def extract_demographics(root):
    """Extract patient demographics from C-CDA"""
    demographics = {}

    try:
        # Get recordTarget element
        record_target = root.find('.//{{{0}}}recordTarget'.format(namespaces['cda']))
        if record_target is None:
            return demographics

        # Get patient element
        patient_role = record_target.find('.//{{{0}}}patientRole'.format(namespaces['cda']))
        if patient_role is None:
            return demographics

        patient_element = patient_role.find('.//{{{0}}}patient'.format(namespaces['cda']))
        if patient_element is None:
            return demographics

        # Extract gender
        gender_element = patient_element.find('.//{{{0}}}administrativeGenderCode'.format(namespaces['cda']))
        if gender_element is not None:
            demographics['gender'] = gender_element.get('code')

        # Extract birth date
        birth_time = patient_element.find('.//{{{0}}}birthTime'.format(namespaces['cda']))
        if birth_time is not None:
            birth_date = birth_time.get('value')
            if birth_date:
                # Convert YYYYMMDD to age
                try:
                    # Format is often YYYYMMDD
                    year = int(birth_date[:4])
                    month = int(birth_date[4:6])
                    day = int(birth_date[6:8])
                    birth_date_obj = datetime(year, month, day)
                    today = datetime.now()
                    age = today.year - birth_date_obj.year - ((today.month, today.day) < (birth_date_obj.month, birth_date_obj.day))
                    demographics['age'] = age
                    demographics['birthDate'] = f"{year}-{month:02d}-{day:02d}"
                except:
                    demographics['birthDate'] = birth_date

        # Extract race
        race_element = patient_element.find('.//{{{0}}}raceCode'.format(namespaces['cda']))
        if race_element is not None:
            demographics['race'] = race_element.get('displayName', race_element.get('code'))

        # Extract ethnicity
        ethnicity_element = patient_element.find('.//{{{0}}}ethnicGroupCode'.format(namespaces['cda']))
        if ethnicity_element is not None:
            demographics['ethnicity'] = ethnicity_element.get('displayName', ethnicity_element.get('code'))

        # Extract address
        address_element = patient_role.find('.//{{{0}}}addr'.format(namespaces['cda']))
        if address_element is not None:
            city = address_element.find('.//{{{0}}}city'.format(namespaces['cda']))
            if city is not None and city.text:
                demographics['city'] = city.text

            state = address_element.find('.//{{{0}}}state'.format(namespaces['cda']))
            if state is not None and state.text:
                demographics['state'] = state.text

            zip_code = address_element.find('.//{{{0}}}postalCode'.format(namespaces['cda']))
            if zip_code is not None and zip_code.text:
                demographics['zipCode'] = zip_code.text

    except Exception as e:
        print(f"Error extracting demographics: {str(e)}")

    return demographics

def find_section_by_code(root, section_code):
    """Find a section in the document by its code attribute"""
    try:
        # Navigate to component/structuredBody
        component = root.find('.//{{{0}}}component'.format(namespaces['cda']))
        if component is None:
            return None

        structured_body = component.find('.//{{{0}}}structuredBody'.format(namespaces['cda']))
        if structured_body is None:
            return None

        # Look through all components to find the section with matching code
        for comp in structured_body.findall('.//{{{0}}}component'.format(namespaces['cda'])):
            section = comp.find('.//{{{0}}}section'.format(namespaces['cda']))
            if section is not None:
                code_element = section.find('.//{{{0}}}code'.format(namespaces['cda']))
                if code_element is not None and code_element.get('code') == section_code:
                    return section

        return None
    except Exception as e:
        print(f"Error finding section {section_code}: {str(e)}")
        return None

def extract_conditions(root):
    """Extract patient conditions/problems from C-CDA"""
    conditions = []

    try:
        # Find the problem section (code 11450-4)
        problem_section = find_section_by_code(root, "11450-4")

        if problem_section is not None:
            # Get all entries in the problem section
            entries = problem_section.findall('.//{{{0}}}entry'.format(namespaces['cda']))

            for entry in entries:
                condition = {}

                # Get observation (problem)
                observation = entry.find('.//{{{0}}}observation'.format(namespaces['cda']))
                if observation is None:
                    continue

                # Extract code
                code_element = observation.find('.//{{{0}}}code'.format(namespaces['cda']))
                if code_element is not None:
                    condition['code'] = code_element.get('code')
                    condition['codeSystem'] = code_element.get('codeSystem')

                # Extract value (diagnosis)
                value_element = observation.find('.//{{{0}}}value'.format(namespaces['cda']))
                if value_element is not None:
                    condition['name'] = value_element.get('displayName', '')
                    if not condition['name']:
                        # Try to find a translation
                        translation = value_element.find('.//{{{0}}}translation'.format(namespaces['cda']))
                        if translation is not None:
                            condition['name'] = translation.get('displayName', '')

                # Extract status
                status_element = observation.find('.//{{{0}}}statusCode'.format(namespaces['cda']))
                if status_element is not None:
                    condition['status'] = status_element.get('code')

                # Extract onset date
                effective_time = observation.find('.//{{{0}}}effectiveTime'.format(namespaces['cda']))
                if effective_time is not None:
                    low_time = effective_time.find('.//{{{0}}}low'.format(namespaces['cda']))
                    if low_time is not None:
                        condition['onsetDate'] = low_time.get('value', '')
                        if condition['onsetDate'] and len(condition['onsetDate']) >= 8:
                            year = condition['onsetDate'][:4]
                            month = condition['onsetDate'][4:6]
                            day = condition['onsetDate'][6:8]
                            condition['onsetDate'] = f"{year}-{month}-{day}"

                if 'name' in condition and condition['name']:
                    conditions.append(condition)

    except Exception as e:
        print(f"Error extracting conditions: {str(e)}")

    return conditions

def extract_medications(root):
    """Extract patient medications from C-CDA"""
    medications = []

    try:
        # Find the medications section (code 10160-0)
        med_section = find_section_by_code(root, "10160-0")

        if med_section is not None:
            # Get all entries in the medications section
            entries = med_section.findall('.//{{{0}}}entry'.format(namespaces['cda']))

            for entry in entries:
                medication = {}

                # Get substance administration
                substance_admin = entry.find('.//{{{0}}}substanceAdministration'.format(namespaces['cda']))
                if substance_admin is None:
                    continue

                # Extract medication details
                product = substance_admin.find('.//{{{0}}}manufacturedProduct'.format(namespaces['cda']))
                if product is not None:
                    material = product.find('.//{{{0}}}manufacturedMaterial'.format(namespaces['cda']))
                    if material is not None:
                        code_element = material.find('.//{{{0}}}code'.format(namespaces['cda']))
                        if code_element is not None:
                            medication['code'] = code_element.get('code')
                            medication['name'] = code_element.get('displayName', '')

                            # If no display name in the code, try to find it in the translation
                            if not medication['name']:
                                translation = code_element.find('.//{{{0}}}translation'.format(namespaces['cda']))
                                if translation is not None:
                                    medication['name'] = translation.get('displayName', '')

                # Extract dosage
                doseQuantity = substance_admin.find('.//{{{0}}}doseQuantity'.format(namespaces['cda']))
                if doseQuantity is not None:
                    medication['dose'] = doseQuantity.get('value', '')
                    medication['unit'] = doseQuantity.get('unit', '')

                # Extract dates
                effective_time = substance_admin.find('.//{{{0}}}effectiveTime'.format(namespaces['cda']))
                if effective_time is not None:
                    low_time = effective_time.find('.//{{{0}}}low'.format(namespaces['cda']))
                    if low_time is not None:
                        medication['startDate'] = low_time.get('value', '')
                        if medication['startDate'] and len(medication['startDate']) >= 8:
                            year = medication['startDate'][:4]
                            month = medication['startDate'][4:6]
                            day = medication['startDate'][6:8]
                            medication['startDate'] = f"{year}-{month}-{day}"

                if 'name' in medication and medication['name']:
                    medications.append(medication)

    except Exception as e:
        print(f"Error extracting medications: {str(e)}")

    return medications

def extract_lab_results(root):
    """Extract patient lab results from C-CDA"""
    labs = []

    try:
        # Find the results section (code 30954-2)
        results_section = find_section_by_code(root, "30954-2")

        if results_section is not None:
            # Get all entries in the results section
            entries = results_section.findall('.//{{{0}}}entry'.format(namespaces['cda']))

            for entry in entries:
                # Get organizer (panel)
                organizer = entry.find('.//{{{0}}}organizer'.format(namespaces['cda']))
                if organizer is None:
                    continue

                # Get individual results within the panel
                components = organizer.findall('.//{{{0}}}component'.format(namespaces['cda']))

                for component in components:
                    observation = component.find('.//{{{0}}}observation'.format(namespaces['cda']))
                    if observation is None:
                        continue

                    lab = {}

                    # Extract test code
                    code_element = observation.find('.//{{{0}}}code'.format(namespaces['cda']))
                    if code_element is not None:
                        lab['code'] = code_element.get('code')
                        lab['name'] = code_element.get('displayName', '')

                    # Extract result
                    value_element = observation.find('.//{{{0}}}value'.format(namespaces['cda']))
                    if value_element is not None:
                        lab['value'] = value_element.get('value', '')
                        lab['unit'] = value_element.get('unit', '')

                    # Extract reference range
                    reference_range = observation.find('.//{{{0}}}referenceRange'.format(namespaces['cda']))
                    if reference_range is not None:
                        obs_range = reference_range.find('.//{{{0}}}observationRange'.format(namespaces['cda']))
                        if obs_range is not None:
                            text = obs_range.find('.//{{{0}}}text'.format(namespaces['cda']))
                            if text is not None and text.text:
                                lab['referenceRange'] = text.text

                    # Extract date
                    effective_time = observation.find('.//{{{0}}}effectiveTime'.format(namespaces['cda']))
                    if effective_time is not None:
                        lab['date'] = effective_time.get('value', '')
                        if lab['date'] and len(lab['date']) >= 8:
                            year = lab['date'][:4]
                            month = lab['date'][4:6]
                            day = lab['date'][6:8]
                            lab['date'] = f"{year}-{month}-{day}"

                    if 'name' in lab and lab['name'] and 'value' in lab:
                        labs.append(lab)

    except Exception as e:
        print(f"Error extracting lab results: {str(e)}")

    return labs

def extract_procedures(root):
    """Extract patient procedures from C-CDA"""
    procedures = []

    try:
        # Find the procedures section (code 47519-4)
        procedures_section = find_section_by_code(root, "47519-4")

        if procedures_section is not None:
            # Get all entries in the procedures section
            entries = procedures_section.findall('.//{{{0}}}entry'.format(namespaces['cda']))

            for entry in entries:
                procedure = {}

                # Get procedure information
                procedure_element = entry.find('.//{{{0}}}procedure'.format(namespaces['cda']))
                if procedure_element is None:
                    continue

                # Extract procedure code
                code_element = procedure_element.find('.//{{{0}}}code'.format(namespaces['cda']))
                if code_element is not None:
                    procedure['code'] = code_element.get('code')
                    procedure['name'] = code_element.get('displayName', '')

                # Extract date
                effective_time = procedure_element.find('.//{{{0}}}effectiveTime'.format(namespaces['cda']))
                if effective_time is not None:
                    procedure['date'] = effective_time.get('value', '')
                    if procedure['date'] and len(procedure['date']) >= 8:
                        year = procedure['date'][:4]
                        month = procedure['date'][4:6]
                        day = procedure['date'][6:8]
                        procedure['date'] = f"{year}-{month}-{day}"

                if 'name' in procedure and procedure['name']:
                    procedures.append(procedure)

    except Exception as e:
        print(f"Error extracting procedures: {str(e)}")

    return procedures

def extract_vitals(root):
    """Extract patient vital signs from C-CDA"""
    vitals = []

    try:
        # Find the vitals section (code 8716-3)
        vitals_section = find_section_by_code(root, "8716-3")

        if vitals_section is not None:
            # Get all entries in the vitals section
            entries = vitals_section.findall('.//{{{0}}}entry'.format(namespaces['cda']))

            for entry in entries:
                # Get organizer (vital signs panel)
                organizer = entry.find('.//{{{0}}}organizer'.format(namespaces['cda']))
                if organizer is None:
                    continue

                # Extract date for this set of vitals
                effective_time = organizer.find('.//{{{0}}}effectiveTime'.format(namespaces['cda']))
                measurement_date = None
                if effective_time is not None:
                    measurement_date = effective_time.get('value', '')
                    if measurement_date and len(measurement_date) >= 8:
                        year = measurement_date[:4]
                        month = measurement_date[4:6]
                        day = measurement_date[6:8]
                        measurement_date = f"{year}-{month}-{day}"

                # Get individual vital signs within the panel
                components = organizer.findall('.//{{{0}}}component'.format(namespaces['cda']))

                for component in components:
                    observation = component.find('.//{{{0}}}observation'.format(namespaces['cda']))
                    if observation is None:
                        continue

                    vital = {}

                    # Extract vital type
                    code_element = observation.find('.//{{{0}}}code'.format(namespaces['cda']))
                    if code_element is not None:
                        vital['code'] = code_element.get('code')
                        vital['name'] = code_element.get('displayName', '')

                    # Extract value
                    value_element = observation.find('.//{{{0}}}value'.format(namespaces['cda']))
                    if value_element is not None:
                        vital['value'] = value_element.get('value', '')
                        vital['unit'] = value_element.get('unit', '')

                    # Add date
                    if measurement_date:
                        vital['date'] = measurement_date

                    if 'name' in vital and vital['name'] and 'value' in vital:
                        vitals.append(vital)

    except Exception as e:
        print(f"Error extracting vitals: {str(e)}")

    return vitals

def process_ccda_directory(directory_path, output_json_path):
    """
    Process all C-CDA files in a directory and save the extracted data to a JSON file.

    Args:
        directory_path: Path to directory containing C-CDA files
        output_json_path: Path to save output JSON file
    """
    patient_data_list = []

    # Get all XML files in the directory
    xml_files = [f for f in os.listdir(directory_path) if f.endswith('.xml')]

    for xml_file in xml_files:
        file_path = os.path.join(directory_path, xml_file)
        print(f"Processing {file_path}")

        patient_data = parse_ccda_file(file_path)
        if patient_data:
            patient_data_list.append(patient_data)

    # Save the extracted data to JSON
    with open(output_json_path, 'w') as json_file:
        json.dump(patient_data_list, json_file, indent=2)

    print(f"Processed {len(patient_data_list)} C-CDA files. Data saved to {output_json_path}")
    return patient_data_list

def create_patient_summary(patient_data_list):
    """
    Create a summary DataFrame of patient information for easier analysis.

    Args:
        patient_data_list: List of patient data dictionaries

    Returns:
        pandas DataFrame with patient summaries
    """
    summaries = []

    for patient in patient_data_list:
        summary = {
            "patientId": patient["patientId"],
            "age": patient["demographics"].get("age", "Unknown"),
            "gender": patient["demographics"].get("gender", "Unknown"),
            "race": patient["demographics"].get("race", "Unknown"),
            "ethnicity": patient["demographics"].get("ethnicity", "Unknown"),
            "conditions_count": len(patient["conditions"]),
            "medications_count": len(patient["medications"]),
            "labs_count": len(patient["labs"]),
            "procedures_count": len(patient["procedures"]),
            "conditions": ", ".join([c["name"] for c in patient["conditions"] if "name" in c and c["name"]]),
            "medications": ", ".join([m["name"] for m in patient["medications"] if "name" in m and m["name"]])
        }
        summaries.append(summary)

    return pd.DataFrame(summaries)

# Example usage
if __name__ == "__main__":
    # Register namespaces
    register_namespaces()

    # Path to directory containing C-CDA files
    ccda_directory = "data/synthea_sample_data_ccda_latest"

    # Path to save output JSON
    output_json = "patient_data.json"

    # Process all C-CDA files
    patient_data_list = process_ccda_directory(ccda_directory, output_json)

    # Create and save summary as CSV
    if patient_data_list:
        summary_df = create_patient_summary(patient_data_list)
        summary_df.to_csv("patient_summary.csv", index=False)
        print(f"Summary saved to patient_summary.csv")