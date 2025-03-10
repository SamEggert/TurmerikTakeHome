# tests/mocks/mock_chroma.py
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
        return len(self.ids)

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