# tests/test_parseXMLs.py
import unittest
import os
from src.parseXMLs import register_namespaces, parse_ccda_file, extract_demographics, extract_conditions, extract_key_clinical_info

class TestParseXMLs(unittest.TestCase):
    def setUp(self):
        register_namespaces()
        # Create path to test XML file
        self.test_file = os.path.join('tests', 'fixtures', 'sample_patient.xml')

    def test_parse_ccda_file(self):
        patient_data = parse_ccda_file(self.test_file)
        self.assertIsNotNone(patient_data)
        self.assertIn('patientId', patient_data)
        self.assertIn('demographics', patient_data)

    def test_extract_demographics(self):
        # You could use a small XML snippet for this test
        from xml.etree import ElementTree as ET
        xml_string = """<cda:patient xmlns:cda="urn:hl7-org:v3">
            <cda:administrativeGenderCode code="M"/>
            <cda:birthTime value="19800101"/>
        </cda:patient>"""
        root = ET.fromstring(xml_string)
        demographics = extract_demographics(root)
        self.assertEqual(demographics.get('gender'), 'M')
        self.assertIn('age', demographics)

    # More tests for other extraction functions...