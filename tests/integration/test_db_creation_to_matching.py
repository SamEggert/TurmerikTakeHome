# tests/integration/test_db_creation_to_matching.py (revised version)
import unittest
import os
import tempfile
import json
import shutil
from unittest.mock import patch
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

        # Create test directory structure
        os.makedirs(self.test_chroma_path, exist_ok=True)

        # Create minimal test JSON with clinical trial data
        with open(self.test_json_path, 'w') as f:
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

        # Path to test patient XML
        fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures')
        self.test_patient_path = os.path.join(fixtures_dir, 'sample_patient.xml')

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('chromadb.PersistentClient')
    @patch('chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_end_to_end_matching(self, mock_embedding_function, mock_client):
        # Skip test if sample patient file doesn't exist
        if not os.path.exists(self.test_patient_path):
            self.skipTest("Sample patient XML not found - skipping test")
            return

        # Mock ChromaDB components
        mock_collection = unittest.mock.MagicMock()
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "ids": [["NCT12345"]],
            "distances": [[0.1]],
            "metadatas": [[{"trial_id": "NCT12345"}]],
            "documents": [["Trial text 1"]]
        }
        mock_client_instance = unittest.mock.MagicMock()
        mock_client_instance.get_or_create_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        # Mock embedding function
        mock_embedding_function_instance = unittest.mock.MagicMock()
        mock_embedding_function.return_value = mock_embedding_function_instance

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