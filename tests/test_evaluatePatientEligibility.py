import unittest
import os
import sys
import json
from unittest.mock import patch, MagicMock
import tempfile

# Add the root directory to sys.path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.evaluatePatientEligibility import (
    evaluate_patient_eligibility,
    extract_inclusion_criteria,
    format_inclusion_criteria,
    save_eligibility_results
)

class TestEvaluatePatientEligibility(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()

        # Sample patient data
        self.patient_data = {
            "patientId": "TEST-123",
            "demographics": {"age": 45, "gender": "M"},
            "conditions": [{"name": "Hypertension", "onsetDate": "2020-01-01"}],
            "medications": [{"name": "Lisinopril", "dose": "10", "unit": "mg"}],
            "key_clinical_info": {
                "demographic_summary": "Age: 45; Gender: Male",
                "condition_summary": "Hypertension (onset: 2020-01-01)",
                "medication_summary": "Lisinopril 10 mg",
                "semantic_search_query": "45-year-old male with Hypertension"
            }
        }

        # Sample trials JSON file
        self.trials_json = os.path.join(self.test_dir, "sample_trials.json")
        with open(self.trials_json, 'w') as f:
            json.dump({
                "patient": {
                    "patientId": "TEST-123",
                    "key_clinical_info": {
                        "demographic_summary": "Age: 45; Gender: Male",
                        "condition_summary": "Hypertension (onset: 2020-01-01)"
                    }
                },
                "matched_trials": [
                    {
                        "trial_id": "NCT12345",
                        "trial_title": "Test Hypertension Study",
                        "semantic_score": 0.9,
                        "minimum_age": 18,
                        "maximum_age": 65,
                        "sex": "ALL",
                        "conditions": ["Hypertension"]
                    }
                ],
                "total_matches": 1
            }, f)

        # Output file path for test
        self.output_path = os.path.join(self.test_dir, "eligibility_results.json")

    def tearDown(self):
        # Clean up test files
        for file in [self.trials_json, self.output_path]:
            if os.path.exists(file):
                os.remove(file)
        os.rmdir(self.test_dir)

    def test_extract_inclusion_criteria(self):
        """Test extraction of inclusion criteria from trial data"""
        # Sample trial data
        trial = {
            "trial_id": "NCT12345",
            "trial_title": "Test Trial",
            "minimum_age": 18,
            "maximum_age": 65,
            "sex": "MALE",
            "conditions": ["Hypertension", "Diabetes"],
            "interventions": [{"intervention": "Drug: Medication A"}]
        }

        criteria = extract_inclusion_criteria(trial, self.trials_json)

        # Check the extracted criteria
        self.assertTrue(any("between 18 and 65" in c for c in criteria))
        self.assertTrue(any("must be male" in c.lower() for c in criteria))
        self.assertTrue(any("Hypertension" in c for c in criteria))
        self.assertTrue(len(criteria) >= 3)  # At least the criteria we expect

    def test_format_inclusion_criteria(self):
        """Test formatting of inclusion criteria"""
        criteria = [
            "Patient must be between 18 and 65 years of age",
            "Patient must be male",
            "Patient must have hypertension"
        ]

        formatted = format_inclusion_criteria(criteria)

        # Check formatting
        self.assertIn("1. Patient must be between 18 and 65 years of age", formatted)
        self.assertIn("2. Patient must be male", formatted)
        self.assertIn("3. Patient must have hypertension", formatted)

        # Test with empty criteria
        empty_formatted = format_inclusion_criteria([])
        self.assertEqual(empty_formatted, "No specific inclusion criteria found for this trial.")

    def test_save_eligibility_results(self):
        """Test saving eligibility results to JSON file"""
        results = {
            "patient_id": "TEST-123",
            "evaluation_date": "2023-01-01",
            "trials_evaluated": 1,
            "results": [
                {
                    "trial_id": "NCT12345",
                    "trial_title": "Test Trial",
                    "evaluation": [
                        {
                            "criterion": "Test criterion",
                            "is_met": True,
                            "confidence": "high",
                            "rationale": "Test rationale"
                        }
                    ]
                }
            ]
        }

        save_eligibility_results(results, self.output_path)

        # Verify file was created and contains the correct data
        self.assertTrue(os.path.exists(self.output_path))
        with open(self.output_path, 'r') as f:
            loaded_results = json.load(f)
            self.assertEqual(loaded_results, results)

    @patch('src.evaluatePatientEligibility.ChatOpenAI')
    def test_evaluate_patient_eligibility(self, mock_chat_openai):
        """Test the main evaluate_patient_eligibility function with mocked LLM"""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.content = """```json
        [
            {
                "criterion": "Patient must be between 18 and 65 years of age",
                "medications_and_supplements": ["Lisinopril 10 mg"],
                "rationale": "Patient is 45 years old and meets this criterion.",
                "is_met": true,
                "confidence": "high"
            }
        ]
        ```"""

        # Configure the mock to return our response
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_instance

        # Execute the function with our test data
        result = evaluate_patient_eligibility(
            patient_data=self.patient_data,
            trials_json_path=self.trials_json,
            model_name="test-model",
            top_k=1
        )

        # Check the results
        self.assertEqual(result["patient_id"], "TEST-123")
        self.assertEqual(result["trials_evaluated"], 1)
        self.assertEqual(len(result["results"]), 1)

        # Check that the evaluation was extracted correctly
        trial_result = result["results"][0]
        self.assertEqual(trial_result["trial_id"], "NCT12345")
        self.assertEqual(len(trial_result["evaluation"]), 1)

        criterion = trial_result["evaluation"][0]
        self.assertEqual(criterion["criterion"], "Patient must be between 18 and 65 years of age")
        self.assertTrue(criterion["is_met"])
        self.assertEqual(criterion["confidence"], "high")

        # Verify LLM was called with appropriate messages
        mock_instance.invoke.assert_called_once()

    @patch('src.evaluatePatientEligibility.ChatOpenAI')
    def test_evaluate_patient_eligibility_json_error(self, mock_chat_openai):
        """Test handling of invalid JSON response from LLM"""
        # Set up mock with invalid JSON
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON"

        mock_instance = MagicMock()
        mock_instance.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_instance

        # Execute the function
        result = evaluate_patient_eligibility(
            patient_data=self.patient_data,
            trials_json_path=self.trials_json,
            model_name="test-model",
            top_k=1
        )

        # Verify error handling
        self.assertEqual(result["trials_evaluated"], 1)
        self.assertEqual(len(result["results"]), 1)
        self.assertIn("raw_response", result["results"][0])
        self.assertIn("error", result["results"][0])
        self.assertEqual(result["results"][0]["error"], "Failed to parse JSON response")

    @patch('src.evaluatePatientEligibility.ChatOpenAI')
    def test_evaluate_patient_eligibility_api_error(self, mock_chat_openai):
        """Test handling of API errors"""
        # Set up mock to raise an exception
        mock_instance = MagicMock()
        mock_instance.invoke.side_effect = Exception("API Error")
        mock_chat_openai.return_value = mock_instance

        # Execute the function
        result = evaluate_patient_eligibility(
            patient_data=self.patient_data,
            trials_json_path=self.trials_json,
            model_name="test-model",
            top_k=1
        )

        # Verify error handling
        self.assertEqual(result["trials_evaluated"], 1)
        self.assertEqual(len(result["results"]), 1)
        self.assertIn("error", result["results"][0])
        self.assertEqual(result["results"][0]["error"], "API Error")