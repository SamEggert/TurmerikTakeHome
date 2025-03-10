# tests/mocks/mock_llm.py
class MockChatOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def invoke(self, messages):
        # Simulate a response from the model
        return MockResponse("This is a mock LLM response that would evaluate patient eligibility.\n\n```json\n[{\"criterion\": \"Patient must be between 18 and 65 years of age\", \"medications_and_supplements\": [\"Medication A\", \"Medication B\"], \"rationale\": \"Patient is 45 years old and meets this criterion.\", \"is_met\": true, \"confidence\": \"high\"}]\n```")

class MockResponse:
    def __init__(self, content):
        self.content = content