# tests/integration/test_parser_to_matcher.py
import unittest
import os
import tempfile
import shutil
import sqlite3
from src.parseXMLs import register_namespaces, parse_ccda_file
from src.findTrialsByChroma import match_patient_to_trials

class TestParserToMatcher(unittest.TestCase):
    def setUp(self):
        register_namespaces()
        # Set up test paths
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test.db")

        # Create test database with data that should match the test patient
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        # Create tables and insert test data designed to match test patient
        # ...
        conn.commit()
        conn.close()

        # Path to test patient XML
        self.test_patient_path = os.path.join('tests', 'fixtures', 'sample_patient.xml')

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_parse_and_match(self):
        # Parse patient data
        patient_data = parse_ccda_file(self.test_patient_path)
        self.assertIsNotNone(patient_data)

        # Match patient to trials
        matched_trials, total_matches = match_patient_to_trials(patient_data, self.test_db_path)

        # Check that matching works correctly
        self.assertGreater(len(matched_trials), 0)
        self.assertEqual(total_matches, len(matched_trials))  # Since we're not using a limit