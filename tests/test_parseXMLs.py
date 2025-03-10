# tests/test_parseXMLs.py
import unittest
import os
import sys
from xml.etree import ElementTree as ET

# Add the root directory to sys.path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the module to test
from src.parseXMLs import register_namespaces, extract_demographics, parse_ccda_file, extract_conditions, extract_key_clinical_info

class TestParseXMLs(unittest.TestCase):
    def setUp(self):
        register_namespaces()
        # Create path to test XML file
        fixtures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
        self.test_file = os.path.join(fixtures_dir, 'sample_patient.xml')

    def test_extract_demographics(self):
        # Use a direct XML string for testing instead of a file
        xml_string = '''<?xml version="1.0" encoding="UTF-8"?>
        <ClinicalDocument xmlns:cda="urn:hl7-org:v3">
            <cda:recordTarget>
                <cda:patientRole>
                    <cda:patient>
                        <cda:administrativeGenderCode code="M"/>
                        <cda:birthTime value="19800101"/>
                    </cda:patient>
                </cda:patientRole>
            </cda:recordTarget>
        </ClinicalDocument>'''

        # Parse the XML directly
        root = ET.fromstring(xml_string)

        # Extract demographics using the function
        demographics = extract_demographics(root)

        # Check the extracted data
        self.assertEqual(demographics.get('gender'), 'M')
        self.assertIn('age', demographics)

    def test_parse_ccda_file(self):
        if not os.path.exists(self.test_file):
            self.skipTest(f"Test file not found: {self.test_file}")

        # If the file exists, test parsing it
        patient_data = parse_ccda_file(self.test_file)
        self.assertIsNotNone(patient_data)
        self.assertIn('demographics', patient_data)