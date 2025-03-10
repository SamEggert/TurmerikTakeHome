# tests/integration/test_db_creation_to_matching.py
import unittest
import os
import tempfile
import json
import shutil
from src.createCorpusDB import process_json_file
from src.createVectorDB import create_corpus_db
from src.findTrialsByChroma import match_and_rank_trials
from src.parseXMLs import register_namespaces

class TestDBCreationToMatching(unittest.TestCase):
    def setUp(self):
        register_namespaces()
        # Set up test paths
        self.test_dir = tempfile.mkdtemp()
        self.test_json_path = os.path.join(self.test_dir, "sample_trials.json")
        self.test_db_path = os.path.join(self.test_dir, "test.db")
        self.test_chroma_path = os.path.join(self.test_dir, "test_chroma")
        self.test_output_path = os.path.join(self.test_dir, "test_output.txt")

        # Create test JSON with clinical trial data
        # Include trial data that would match the test patient
        # ...

        # Path to test patient XML
        self.test_patient_path = os.path.join('tests', 'fixtures', 'sample_patient.xml')

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_end_to_end_matching(self):
        # Process JSON to create SQLite database
        total, processed = process_json_file(self.test_json_path, self.test_db_path)
        self.assertEqual(processed, total)

        # Create vector database
        create_corpus_db(self.test_db_path, self.test_chroma_path, batch_size=1)

        # Match and rank trials
        match_and_rank_trials(
            file_path=self.test_patient_path,
            db_path=self.test_db_path,
            chroma_path=self.test_chroma_path,
            output_path=self.test_output_path,
            top_k=5
        )

        # Check that output file was created
        self.assertTrue(os.path.exists(self.test_output_path))

        # Check content of output file to ensure matching worked
        with open(self.test_output_path, 'r') as f:
            content = f.read()
            self.assertIn("RANKED MATCHING TRIALS", content)