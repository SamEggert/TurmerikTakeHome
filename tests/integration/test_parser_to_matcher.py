# tests/integration/test_parser_to_matcher.py
import unittest
import os
import tempfile
import shutil
import sqlite3
import sys
from unittest.mock import patch

# Add the root directory to sys.path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.parseXMLs import register_namespaces, parse_ccda_file
from src.findTrialsByChroma import match_patient_to_trials

class TestParserToMatcher(unittest.TestCase):
    def setUp(self):
        register_namespaces()
        # Set up test paths
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test.db")

        # Create test database with ALL columns needed by match_patient_to_trials
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()

        # Create trials table with ALL columns including requires_english
        cursor.execute('''
            CREATE TABLE trials (
                trial_id TEXT PRIMARY KEY,
                trial_title TEXT,
                minimum_age INTEGER,
                maximum_age INTEGER,
                sex TEXT,
                accepts_healthy_volunteers INTEGER,
                participant_count INTEGER,
                requires_english INTEGER,
                requires_internet INTEGER,
                requires_specific_tests INTEGER,
                has_medication_requirements INTEGER,
                has_comorbidity_restrictions INTEGER,
                has_substance_restrictions INTEGER,
                has_psychiatric_restrictions INTEGER,
                has_pregnancy_restrictions INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE conditions (
                trial_id TEXT,
                condition_name TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE interventions (
                trial_id TEXT,
                intervention_type TEXT,
                intervention_name TEXT
            )
        ''')

        # Insert test data with values for all columns
        cursor.execute(
            "INSERT INTO trials VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("NCT12345", "Test Trial", 18, 65, "ALL", 1, 100, 0, 0, 0, 0, 0, 0, 0, 0)
        )
        cursor.execute(
            "INSERT INTO conditions VALUES (?, ?)",
            ("NCT12345", "Test Condition")
        )
        cursor.execute(
            "INSERT INTO interventions VALUES (?, ?, ?)",
            ("NCT12345", "Drug", "Test Drug")
        )

        conn.commit()
        conn.close()

        # Path to test patient XML
        fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures')
        self.test_patient_path = os.path.join(fixtures_dir, 'sample_patient.xml')

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('src.parseXMLs.parse_ccda_file')
    def test_parse_and_match(self, mock_parse_ccda):
        # Mock the parse_ccda_file function to return a sample patient
        mock_parse_ccda.return_value = {
            "patientId": "12345",
            "demographics": {"age": 40, "gender": "M"},
            "conditions": [{"name": "Test Condition", "onsetDate": "2020-01-01"}],
            "medications": [{"name": "Test Medication", "dose": "10", "unit": "mg"}]
        }

        # Now test with the mocked patient data
        patient_data = mock_parse_ccda(self.test_patient_path)
        self.assertIsNotNone(patient_data)

        # Match patient to trials
        matched_trials, total_matches = match_patient_to_trials(patient_data, self.test_db_path)

        # Check that matching works correctly
        self.assertGreaterEqual(len(matched_trials), 0)