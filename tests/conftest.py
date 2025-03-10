# tests/conftest.py
import os
import pytest
import tempfile
import shutil
import json
import sqlite3
from unittest.mock import patch

# Path to fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')

@pytest.fixture
def sample_patient_path():
    return os.path.join(FIXTURES_DIR, 'sample_patient.xml')

@pytest.fixture
def sample_trials_json_path():
    return os.path.join(FIXTURES_DIR, 'sample_trials.json')

@pytest.fixture
def temp_test_dir():
    test_dir = tempfile.mkdtemp()
    yield test_dir
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

@pytest.fixture
def test_db_path(temp_test_dir, sample_trials_json_path):
    db_path = os.path.join(temp_test_dir, 'test.db')
    # Create and populate test database
    from src.createCorpusDB import process_json_file
    process_json_file(sample_trials_json_path, db_path)
    return db_path

@pytest.fixture
def mock_llm():
    with patch('langchain_openai.ChatOpenAI') as mock:
        from tests.mocks.mock_llm import MockChatOpenAI
        mock.return_value = MockChatOpenAI()
        yield mock

@pytest.fixture
def mock_chroma():
    with patch('chromadb.PersistentClient') as mock:
        from tests.mocks.mock_chroma import MockChromaClient
        mock.return_value = MockChromaClient(path='mock_path')
        yield mock