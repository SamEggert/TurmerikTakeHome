# tests/test_createVectorDB.py (revised version)
import unittest
import os
import tempfile
import sqlite3
import shutil
from unittest.mock import patch, MagicMock
from src.createVectorDB import create_corpus_db

class TestCreateVectorDB(unittest.TestCase):
    def setUp(self):
        # Set up a test database with minimal data
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test.db")
        self.test_chroma_path = os.path.join(self.test_dir, "test_chroma")
        os.makedirs(self.test_chroma_path, exist_ok=True)

        # Create a minimal test database
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE trials (
                trial_id TEXT PRIMARY KEY,
                trial_title TEXT,
                minimum_age INTEGER,
                maximum_age INTEGER,
                sex TEXT,
                accepts_healthy_volunteers INTEGER,
                participant_count INTEGER
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
        cursor.execute('''
            CREATE TABLE inclusion_criteria (
                trial_id TEXT,
                criterion TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE exclusion_criteria (
                trial_id TEXT,
                criterion TEXT
            )
        ''')

        # Insert test data
        cursor.execute(
            "INSERT INTO trials VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("NCT12345", "Test Trial", 18, 65, "ALL", 1, 100)
        )
        cursor.execute(
            "INSERT INTO conditions VALUES (?, ?)",
            ("NCT12345", "Test Condition")
        )
        cursor.execute(
            "INSERT INTO interventions VALUES (?, ?, ?)",
            ("NCT12345", "Drug", "Test Drug")
        )
        cursor.execute(
            "INSERT INTO inclusion_criteria VALUES (?, ?)",
            ("NCT12345", "Test Inclusion")
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('chromadb.PersistentClient')
    @patch('chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_create_corpus_db(self, mock_embedding_function, mock_client):
        # Mock ChromaDB Collection
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1

        # Mock ChromaDB Client
        mock_client_instance = MagicMock()
        mock_client_instance.get_or_create_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        # Mock embedding function
        mock_embedding_function_instance = MagicMock()
        mock_embedding_function.return_value = mock_embedding_function_instance

        # Run function
        create_corpus_db(self.test_db_path, self.test_chroma_path, batch_size=1)

        # Check that the collection was created and documents were added
        mock_client.assert_called_once_with(path=self.test_chroma_path)
        mock_client_instance.get_or_create_collection.assert_called_once()
        mock_collection.add.assert_called_once()