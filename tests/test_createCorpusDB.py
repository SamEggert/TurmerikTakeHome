# tests/test_createCorpusDB.py
import unittest
import sqlite3
import os
import tempfile
import json
from src.createCorpusDB import parse_clinical_trial_eligibility, process_json_file

class TestCreateCorpusDB(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        # Create a small sample JSON for tests
        self.sample_json = os.path.join(self.test_dir, "sample_trials.json")
        with open(self.sample_json, 'w') as f:
            json.dump([{
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT12345", "briefTitle": "Test Trial"},
                    "eligibilityModule": {
                        "sex": "ALL",
                        "minimumAge": "18 Years",
                        "maximumAge": "65 Years",
                        "eligibilityCriteria": "Inclusion Criteria:\n* Test Inclusion\n\nExclusion Criteria:\n* Test Exclusion"
                    },
                    "conditionsModule": {"conditions": ["Test Condition"]},
                    "armsInterventionsModule": {"interventions": [{"type": "Drug", "name": "Test Drug"}]},
                    "designModule": {"enrollmentInfo": {"count": 100}}
                }
            }], f)
        # Create test database path
        self.test_db = os.path.join(self.test_dir, "test.db")

    def tearDown(self):
        # Clean up test files
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        if os.path.exists(self.sample_json):
            os.remove(self.sample_json)
        os.rmdir(self.test_dir)

    def test_parse_clinical_trial_eligibility(self):
        with open(self.sample_json, 'r') as f:
            data = json.load(f)
        result = parse_clinical_trial_eligibility(data[0])
        self.assertEqual(result['trial_id'], 'NCT12345')
        self.assertEqual(result['structured_criteria']['minimum_age'], 18)
        self.assertEqual(len(result['inclusion_criteria']), 1)

    def test_process_json_file(self):
        total, processed = process_json_file(self.sample_json, self.test_db, 5)
        self.assertEqual(total, 1)
        self.assertEqual(processed, 1)

        # Verify database was created correctly
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trials")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 1)
        conn.close()