# tests/conftest.py
import os
import pytest
import tempfile
import shutil
import json
import sqlite3
from unittest.mock import patch

# Path to fixtures - using absolute path based on this file's location
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')

@pytest.fixture
def sample_patient_path():
    patient_path = os.path.join(FIXTURES_DIR, 'sample_patient.xml')
    if not os.path.exists(patient_path):
        pytest.skip(f"Sample patient file not found at {patient_path}")
    return patient_path

@pytest.fixture
def sample_trials_json_path():
    trials_path = os.path.join(FIXTURES_DIR, 'sample_trials.json')
    if not os.path.exists(trials_path):
        pytest.skip(f"Sample trials file not found at {trials_path}")
    return trials_path

@pytest.fixture
def temp_test_dir():
    test_dir = tempfile.mkdtemp()
    yield test_dir
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

@pytest.fixture
def test_db_path(temp_test_dir):
    """Create a test database with minimal structure"""
    db_path = os.path.join(temp_test_dir, 'test.db')

    # Create minimal database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create necessary tables
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

    # Add test data
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
        ("NCT12345", "Test Inclusion Criterion")
    )

    conn.commit()
    conn.close()

    return db_path

@pytest.fixture
def mock_llm():
    with patch('src.evaluatePatientEligibility.ChatOpenAI') as mock:
        # Create a mock LLM that returns a valid response
        class MockChatOpenAI:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def invoke(self, messages):
                # Return a mock response with correct structure
                class MockResponse:
                    def __init__(self, content):
                        self.content = content

                return MockResponse("""```json
                [
                    {
                        "criterion": "Patient must be between 18 and 65 years of age",
                        "medications_and_supplements": ["Medication A", "Medication B"],
                        "rationale": "Patient is 45 years old and meets this criterion.",
                        "is_met": true,
                        "confidence": "high"
                    }
                ]
                ```""")

        mock.return_value = MockChatOpenAI()
        yield mock

@pytest.fixture
def mock_chroma():
    with patch('chromadb.PersistentClient') as mock:
        # Create a mock Chroma client
        class MockChromaCollection:
            def __init__(self, name):
                self.name = name
                self.documents = []
                self.metadatas = []
                self.ids = []

            def add(self, documents, metadatas, ids):
                self.documents.extend(documents)
                self.metadatas.extend(metadatas)
                self.ids.extend(ids)
                return {"count": len(documents)}

            def query(self, query_texts, where=None, n_results=10):
                # Return mock search results
                return {
                    "ids": [["NCT12345", "NCT67890"]],
                    "distances": [[0.1, 0.2]],
                    "metadatas": [[{"trial_id": "NCT12345"}, {"trial_id": "NCT67890"}]],
                    "documents": [["Trial text 1", "Trial text 2"]]
                }

            def count(self):
                return len(self.ids) or 1  # Return at least 1

        class MockChromaClient:
            def __init__(self, path):
                self.path = path
                self.collections = {"clinical_trials": MockChromaCollection("clinical_trials")}

            def get_or_create_collection(self, name, embedding_function=None):
                if name in self.collections:
                    return self.collections[name]
                self.collections[name] = MockChromaCollection(name)
                return self.collections[name]

            def list_collections(self):
                return list(self.collections.keys())

        mock.return_value = MockChromaClient(path='mock_path')
        yield mock

@pytest.fixture
def mock_embedding_function():
    with patch('chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction') as mock:
        # Create a mock embedding function that returns fixed embeddings
        mock.return_value = lambda texts: [[0.1] * 10 for _ in range(len(texts) if isinstance(texts, list) else 1)]
        yield mock