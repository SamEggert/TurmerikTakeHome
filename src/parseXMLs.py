import os
import xml.etree.ElementTree as ET
import json
import pandas as pd
from datetime import datetime
import re

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
            "vitals": extract_vitals(root),
            "clinicalNotes": extract_clinical_notes(root)  # Add clinical notes extraction
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

def extract_clinical_notes(root):
    """Extract clinical notes from C-CDA document"""
    notes = []

    try:
        # Common clinical note section codes
        note_section_codes = [
            "11488-4",  # Consultation Note
            "18842-5",  # Discharge Summary
            "28570-0",  # Procedure Note
            "34117-2",  # History and Physical Note
            "34839-1",  # Progress Note
            "51845-6",  # Assessment and Plan
            "51847-2",  # Evaluation Note
            "47039-3",  # Hospital Admission Diagnosis
            "8648-8",   # Hospital Course
            "10184-0"   # Surgical Operation Note
        ]

        # Find all matching sections
        for section_code in note_section_codes:
            section = find_section_by_code(root, section_code)
            if section is not None:
                # Get section title
                title_element = section.find('.//{{{0}}}title'.format(namespaces['cda']))
                section_title = title_element.text if title_element is not None and title_element.text else f"Note Section {section_code}"

                # Get text content
                text_element = section.find('.//{{{0}}}text'.format(namespaces['cda']))
                if text_element is not None:
                    # Extract pure text and remove XML formatting
                    text_content = get_text_from_element(text_element)

                    if text_content:
                        # Get date for this note if available
                        effective_time = section.find('.//{{{0}}}effectiveTime'.format(namespaces['cda']))
                        note_date = None
                        if effective_time is not None:
                            low_element = effective_time.find('.//{{{0}}}low'.format(namespaces['cda']))
                            if low_element is not None:
                                note_date = low_element.get('value', '')
                            else:
                                note_date = effective_time.get('value', '')

                            if note_date and len(note_date) >= 8:
                                year = note_date[:4]
                                month = note_date[4:6]
                                day = note_date[6:8]
                                note_date = f"{year}-{month}-{day}"

                        note = {
                            "type": section_title,
                            "code": section_code,
                            "date": note_date,
                            "content": text_content
                        }
                        notes.append(note)

        # If we didn't find specific note sections, look for general clinical documents
        if not notes:
            # Check for document-level narrative
            component = root.find('.//{{{0}}}component'.format(namespaces['cda']))
            if component is not None:
                structured_body = component.find('.//{{{0}}}structuredBody'.format(namespaces['cda']))
                if structured_body is not None:
                    for comp in structured_body.findall('.//{{{0}}}component'.format(namespaces['cda'])):
                        section = comp.find('.//{{{0}}}section'.format(namespaces['cda']))
                        if section is not None:
                            title_element = section.find('.//{{{0}}}title'.format(namespaces['cda']))
                            if title_element is not None and title_element.text:
                                section_title = title_element.text
                                text_element = section.find('.//{{{0}}}text'.format(namespaces['cda']))
                                if text_element is not None:
                                    text_content = get_text_from_element(text_element)
                                    if text_content:
                                        note = {
                                            "type": section_title,
                                            "content": text_content
                                        }
                                        notes.append(note)

    except Exception as e:
        print(f"Error extracting clinical notes: {str(e)}")

    return notes

def get_text_from_element(element):
    """
    Extract clean text from an XML element, stripping tags but preserving structure.
    Args:
        element: XML element containing text

    Returns:
        str: Clean text content
    """
    if element is None:
        return ""

    # First try to get element text directly
    result = ""
    if element.text:
        result += element.text.strip() + " "

    # Process paragraph elements
    for paragraph in element.findall('.//{{{0}}}paragraph'.format(namespaces['cda'])):
        if paragraph.text:
            result += paragraph.text.strip() + "\n"
        # Get text from all children
        for child in paragraph:
            if child.text:
                result += child.text.strip() + " "
            if child.tail:
                result += child.tail.strip() + " "

    # Process list items
    for item in element.findall('.//{{{0}}}item'.format(namespaces['cda'])):
        if item.text:
            result += "- " + item.text.strip() + "\n"
        # Get text from all children
        for child in item:
            if child.text:
                result += child.text.strip() + " "
            if child.tail:
                result += child.tail.strip() + " "

    # Process content referenced by IDs
    for content in element.findall('.//{{{0}}}content'.format(namespaces['cda'])):
        if content.text:
            result += content.text.strip() + " "

    # Clean up the text - replace multiple spaces with single space
    result = re.sub(r'\s+', ' ', result)
    # Remove XML tags that might have been included as text
    result = re.sub(r'<[^>]+>', '', result)

    return result.strip()

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
            "notes_count": len(patient["clinicalNotes"]),
            "conditions": ", ".join([c["name"] for c in patient["conditions"] if "name" in c and c["name"]]),
            "medications": ", ".join([m["name"] for m in patient["medications"] if "name" in m and m["name"]])
        }
        summaries.append(summary)

    return pd.DataFrame(summaries)

def generate_semantic_search_query(patient_data):
    """
    Generate a semantic search query for clinical trial matching based on patient data.

    Args:
        patient_data: Dictionary containing patient information

    Returns:
        str: A natural language query for semantic search
    """
    query_parts = []

    # Add demographic information
    demographics = patient_data.get("demographics", {})
    if demographics:
        age = demographics.get("age")
        gender = demographics.get("gender")
        if age and gender:
            if gender == "M":
                query_parts.append(f"{age}-year-old male patient")
            elif gender == "F":
                query_parts.append(f"{age}-year-old female patient")
            else:
                query_parts.append(f"{age}-year-old patient")
        elif age:
            query_parts.append(f"{age}-year-old patient")
        elif gender:
            if gender == "M":
                query_parts.append("Male patient")
            elif gender == "F":
                query_parts.append("Female patient")

    # Add primary conditions (up to 3 most recent)
    conditions = patient_data.get("conditions", [])
    if conditions:
        # Sort by onset date if available, most recent first
        sorted_conditions = sorted(
            [c for c in conditions if "name" in c and c["name"]],
            key=lambda x: x.get("onsetDate", ""),
            reverse=True
        )

        condition_names = [c["name"] for c in sorted_conditions[:3]]
        if condition_names:
            if len(condition_names) == 1:
                query_parts.append(f"diagnosed with {condition_names[0]}")
            else:
                conditions_text = ", ".join(condition_names[:-1]) + f" and {condition_names[-1]}"
                query_parts.append(f"diagnosed with {conditions_text}")

    # Add relevant medications (up to 3)
    medications = patient_data.get("medications", [])
    if medications:
        med_names = [m["name"] for m in medications[:3] if "name" in m and m["name"]]
        if med_names:
            if len(med_names) == 1:
                query_parts.append(f"currently taking {med_names[0]}")
            else:
                meds_text = ", ".join(med_names[:-1]) + f" and {med_names[-1]}"
                query_parts.append(f"currently taking {meds_text}")

    # Add significant lab values (abnormal results)
    labs = patient_data.get("labs", [])
    abnormal_labs = []

    for lab in labs:
        if "name" in lab and "value" in lab:
            lab_name = lab["name"]
            lab_value = lab["value"]
            lab_unit = lab.get("unit", "")
            ref_range = lab.get("referenceRange", "")

            # Check if outside reference range if available
            if ref_range and "-" in ref_range:
                try:
                    range_parts = ref_range.split("-")
                    low = float(range_parts[0].strip())
                    high = float(range_parts[1].strip())
                    value = float(lab_value)

                    if value < low or value > high:
                        abnormal_labs.append(f"{lab_name} {lab_value} {lab_unit}")
                except:
                    pass

    if abnormal_labs and len(abnormal_labs) <= 2:
        abnormal_text = " and ".join(abnormal_labs)
        query_parts.append(f"with abnormal {abnormal_text}")

    # Add recent procedures (up to 2 most recent)
    procedures = patient_data.get("procedures", [])
    if procedures:
        # Sort by date if available, most recent first
        sorted_procedures = sorted(
            [p for p in procedures if "name" in p and p["name"]],
            key=lambda x: x.get("date", ""),
            reverse=True
        )

        procedure_names = [p["name"] for p in sorted_procedures[:2]]
        if procedure_names:
            if len(procedure_names) == 1:
                query_parts.append(f"underwent {procedure_names[0]}")
            else:
                procedures_text = " and ".join(procedure_names)
                query_parts.append(f"underwent {procedures_text}")

    # Extract key information from clinical notes
    clinical_notes = patient_data.get("clinicalNotes", [])

    # First, look for assessment and plan notes
    assessment_notes = [note for note in clinical_notes if
                       "type" in note and
                       ("Assessment" in note["type"] or "Plan" in note["type"])]

    if assessment_notes:
        # Get the most recent assessment note
        latest_note = sorted(assessment_notes, key=lambda x: x.get("date", ""), reverse=True)[0]
        note_content = latest_note.get("content", "")

        # Extract key phrases (simplified approach)
        # Look for sentences with important medical terms
        important_terms = ["recommended", "referred", "indicated", "suspected",
                         "diagnosed", "assessment", "plan", "follow-up", "risk",
                         "monitoring", "considering", "evaluated", "eligible"]

        sentences = re.split(r'[.!?]', note_content)
        relevant_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and any(term in sentence.lower() for term in important_terms):
                # Limit sentence length
                if len(sentence) < 100:
                    relevant_sentences.append(sentence)

        if relevant_sentences:
            # Take up to 2 relevant sentences
            for sentence in relevant_sentences[:2]:
                query_parts.append(f"note: {sentence}")

    # Compile the final query
    if query_parts:
        return " ".join(query_parts)
    else:
        return "patient requires clinical trial matching"

def extract_key_clinical_info(patient_data):
    """
    Extract key clinical information from patient data for improved semantic search.

    Args:
        patient_data: Dictionary containing patient information

    Returns:
        dict: Dictionary with key clinical information
    """
    key_info = {
        "demographic_summary": "",
        "condition_summary": "",
        "medication_summary": "",
        "lab_summary": "",
        "procedure_summary": "",
        "clinical_notes_summary": "",
        "semantic_search_query": ""
    }

    # Demographics summary
    demographics = patient_data.get("demographics", {})
    if demographics:
        demo_parts = []

        if "age" in demographics:
            demo_parts.append(f"Age: {demographics['age']}")

        if "gender" in demographics:
            gender_map = {"M": "Male", "F": "Female"}
            gender = gender_map.get(demographics.get("gender", ""), demographics.get("gender", ""))
            demo_parts.append(f"Gender: {gender}")

        if "race" in demographics:
            demo_parts.append(f"Race: {demographics['race']}")

        if "ethnicity" in demographics:
            demo_parts.append(f"Ethnicity: {demographics['ethnicity']}")

        if demo_parts:
            key_info["demographic_summary"] = "; ".join(demo_parts)

    # Conditions summary
    conditions = patient_data.get("conditions", [])
    if conditions:
        # Sort by onset date if available
        sorted_conditions = sorted(
            [c for c in conditions if "name" in c and c["name"]],
            key=lambda x: x.get("onsetDate", ""),
            reverse=True
        )

        condition_items = []
        for condition in sorted_conditions:
            item = condition["name"]
            if "onsetDate" in condition and condition["onsetDate"]:
                item += f" (onset: {condition['onsetDate']})"
            if "status" in condition and condition["status"]:
                item += f" - {condition['status']}"
            condition_items.append(item)

        if condition_items:
            key_info["condition_summary"] = "; ".join(condition_items)

    # Medications summary
    medications = patient_data.get("medications", [])
    if medications:
        medication_items = []
        for med in medications:
            if "name" in med and med["name"]:
                item = med["name"]
                if "dose" in med and med["dose"] and "unit" in med and med["unit"]:
                    item += f" {med['dose']} {med['unit']}"
                if "startDate" in med and med["startDate"]:
                    item += f" (started: {med['startDate']})"
                medication_items.append(item)

        if medication_items:
            key_info["medication_summary"] = "; ".join(medication_items)

    # Labs summary - focus on abnormal results
    labs = patient_data.get("labs", [])
    abnormal_labs = []
    normal_labs = []

    for lab in labs:
        if "name" in lab and "value" in lab:
            lab_name = lab["name"]
            lab_value = lab["value"]
            lab_unit = lab.get("unit", "")
            ref_range = lab.get("referenceRange", "")
            date = lab.get("date", "")

            lab_item = f"{lab_name}: {lab_value} {lab_unit}"
            if date:
                lab_item += f" ({date})"

            # Check if outside reference range if available
            if ref_range and "-" in ref_range:
                try:
                    range_parts = ref_range.split("-")
                    low = float(range_parts[0].strip())
                    high = float(range_parts[1].strip())
                    value = float(lab_value)

                    if value < low or value > high:
                        lab_item += f" [Abnormal: ref range {ref_range} {lab_unit}]"
                        abnormal_labs.append(lab_item)
                    else:
                        normal_labs.append(lab_item)
                except:
                    normal_labs.append(lab_item)
            else:
                normal_labs.append(lab_item)

    # Prioritize abnormal labs in the summary
    lab_items = abnormal_labs + normal_labs[:max(0, 5-len(abnormal_labs))]  # Include up to 5 labs total
    if lab_items:
        key_info["lab_summary"] = "; ".join(lab_items)

    # Procedures summary
    procedures = patient_data.get("procedures", [])
    if procedures:
        # Sort by date if available, most recent first
        sorted_procedures = sorted(
            [p for p in procedures if "name" in p and p["name"]],
            key=lambda x: x.get("date", ""),
            reverse=True
        )

        procedure_items = []
        for proc in sorted_procedures:
            item = proc["name"]
            if "date" in proc and proc["date"]:
                item += f" ({proc['date']})"
            procedure_items.append(item)

        if procedure_items:
            key_info["procedure_summary"] = "; ".join(procedure_items)

    # Clinical notes summary - extract key information
    clinical_notes = patient_data.get("clinicalNotes", [])
    if clinical_notes:
        # Sort by date if available, most recent first
        sorted_notes = sorted(
            [n for n in clinical_notes if "content" in n and n["content"]],
            key=lambda x: x.get("date", ""),
            reverse=True
        )

        note_summaries = []
        for note in sorted_notes[:3]:  # Include up to 3 most recent notes
            note_type = note.get("type", "Clinical Note")
            note_date = note.get("date", "")
            note_content = note.get("content", "")

            # Truncate long notes and add an indicator
            content_summary = note_content[:200] + "..." if len(note_content) > 200 else note_content

            summary = f"{note_type}"
            if note_date:
                summary += f" ({note_date})"
            summary += f": {content_summary}"

            note_summaries.append(summary)

        if note_summaries:
            key_info["clinical_notes_summary"] = "\n\n".join(note_summaries)

    # Generate semantic search query
    key_info["semantic_search_query"] = generate_semantic_search_query(patient_data)

    return key_info

def save_patient_data_with_summary(patient_data_list, output_json_path):
    """
    Process patient data with summaries and save to JSON.

    Args:
        patient_data_list: List of patient data dictionaries
        output_json_path: Path to save enhanced output JSON file
    """
    enhanced_patient_data = []

    for patient_data in patient_data_list:
        # Extract key information
        key_clinical_info = extract_key_clinical_info(patient_data)

        # Add key information to patient data
        enhanced_data = patient_data.copy()
        enhanced_data["key_clinical_info"] = key_clinical_info

        enhanced_patient_data.append(enhanced_data)

    # Save the enhanced data to JSON
    with open(output_json_path, 'w') as json_file:
        json.dump(enhanced_patient_data, json_file, indent=2)

    print(f"Enhanced patient data with clinical summaries and semantic search queries saved to {output_json_path}")
    return enhanced_patient_data

# Example usage
if __name__ == "__main__":
    # Register namespaces
    register_namespaces()

    # Path to directory containing C-CDA files
    ccda_directory = "../data/synthea_sample_data_ccda_latest"

    # Path to save output JSON
    output_json = "../data/patient_data.json"

    # Path to save enhanced output JSON with summaries
    enhanced_output_json = "../data/enhanced_patient_data.json"

    # Process all C-CDA files
    patient_data_list = process_ccda_directory(ccda_directory, output_json)

    # Create and save summary as CSV
    if patient_data_list:
        summary_df = create_patient_summary(patient_data_list)
        summary_df.to_csv("patient_summary.csv", index=False)
        print(f"Summary saved to patient_summary.csv")

        # Save enhanced patient data with clinical summaries and semantic search queries
        enhanced_data = save_patient_data_with_summary(patient_data_list, enhanced_output_json)

        # Example of generating a semantic search query for the first patient
        if enhanced_data:
            print("\nExample Semantic Search Query:")
            print(enhanced_data[0]["key_clinical_info"]["semantic_search_query"])