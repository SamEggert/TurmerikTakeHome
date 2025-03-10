# tests/integration/test_full_pipeline.py
import unittest
import os
import tempfile
import shutil
import json
from src.combined_pipeline import process_single_patient

class TestFullPipeline(unittest.TestCase):
    def setUp(self):
        # Set up test paths
        self.test_dir = tempfile.mkdtemp()
        self.test_json_path = os.path.join(self.test_dir, "sample_trials.json")
        self.test_db_path = os.path.join(self.test_dir, "test.db")
        self.test_chroma_path = os.path.join(self.test_dir, "test_chroma")
        self.test_output_dir = os.path.join(self.test_dir, "test_output")

        # Create test JSON with clinical trial data
        # ...

        # Path to test patient XML
        self.test_patient_path = os.path.join('tests', 'fixtures', 'sample_patient.xml')

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @unittest.skip("Requires full environment including LLM API")  # Skip for CI/CD
    def test_full_pipeline(self):
        # Run the full pipeline for a single patient
        result = process_single_patient(
            patient_file_path=self.test_patient_path,
            trials_json_path=self.test_json_path,
            sqlite_db_path=self.test_db_path,
            chroma_db_path=self.test_chroma_path,
            output_dir=self.test_output_dir,
            model_name="gpt-4o-mini"  # Use actual model or mock
        )

        # Check that pipeline ran successfully
        self.assertIsNotNone(result)
        self.assertIn("patient_name", result)
        self.assertIn("eligibility_results", result)

        # Check that output files exist
        self.assertTrue(os.path.exists(result["eligibility_results"]))
        self.assertTrue(os.path.exists(result["output_files"]["json_path"]))
        self.assertTrue(os.path.exists(result["output_files"]["excel_path"]))