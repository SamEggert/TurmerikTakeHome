import unittest
import os
import sys
import json
import pandas as pd
from unittest.mock import patch, MagicMock
import tempfile
from datetime import datetime

# Add the root directory to sys.path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.generateOutput import (
    load_eligibility_results,
    format_simple_results,
    format_results_for_output,
    save_json_output,
    create_dataframes,
    create_simple_dataframe,
    process_single_eligibility_file,
    generate_output
)

class TestGenerateOutput(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()

        # Create a sample eligibility results file
        self.sample_results = {
            "patient_id": "TEST-123",
            "evaluation_date": "2023-01-01",
            "trials_evaluated": 2,
            "results": [
                {
                    "trial_id": "NCT12345",
                    "trial_title": "Test Trial 1",
                    "semantic_score": 0.9,
                    "evaluation": [
                        {
                            "criterion": "Patient must be between 18 and 65 years of age",
                            "medications_and_supplements": ["Medication A"],
                            "rationale": "Patient is 45 years old and meets this criterion.",
                            "is_met": True,
                            "confidence": "high"
                        },
                        {
                            "criterion": "Patient must have hypertension",
                            "medications_and_supplements": [],
                            "rationale": "Patient has hypertension diagnosis.",
                            "is_met": True,
                            "confidence": "high"
                        }
                    ]
                },
                {
                    "trial_id": "NCT67890",
                    "trial_title": "Test Trial 2",
                    "semantic_score": 0.8,
                    "evaluation": [
                        {
                            "criterion": "Patient must be between 18 and 65 years of age",
                            "medications_and_supplements": ["Medication A"],
                            "rationale": "Patient is 45 years old and meets this criterion.",
                            "is_met": True,
                            "confidence": "high"
                        },
                        {
                            "criterion": "Patient must have diabetes",
                            "medications_and_supplements": [],
                            "rationale": "Patient does not have diabetes diagnosis.",
                            "is_met": False,
                            "confidence": "high"
                        }
                    ]
                }
            ]
        }

        self.eligibility_file = os.path.join(self.test_dir, "sample_eligibility.json")
        with open(self.eligibility_file, 'w') as f:
            json.dump(self.sample_results, f, indent=2)

        # Create a directory to save output files
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        # Clean up test files
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_load_eligibility_results(self):
        """Test loading eligibility results from JSON file"""
        loaded_results = load_eligibility_results(self.eligibility_file)

        # Verify the results were loaded correctly
        self.assertEqual(loaded_results["patient_id"], "TEST-123")
        self.assertEqual(loaded_results["trials_evaluated"], 2)
        self.assertEqual(len(loaded_results["results"]), 2)

        # Test loading non-existent file
        non_existent_file = os.path.join(self.test_dir, "non_existent.json")
        self.assertIsNone(load_eligibility_results(non_existent_file))

    def test_format_simple_results(self):
        """Test formatting results into simplified format"""
        simple_results = format_simple_results(self.sample_results)

        # Check the simplified format
        self.assertEqual(simple_results["patientId"], "TEST-123")

        # Only the first trial should be eligible (all criteria met)
        self.assertEqual(len(simple_results["eligibleTrials"]), 1)
        self.assertEqual(simple_results["eligibleTrials"][0]["trialId"], "NCT12345")
        self.assertEqual(len(simple_results["eligibleTrials"][0]["eligibilityCriteriaMet"]), 2)

    def test_format_results_for_output(self):
        """Test formatting results for detailed output"""
        formatted_results = format_results_for_output(self.sample_results)

        # Check the general structure
        self.assertEqual(formatted_results["patient_id"], "TEST-123")
        self.assertEqual(formatted_results["evaluation_date"], "2023-01-01")
        self.assertEqual(formatted_results["total_trials_evaluated"], 2)

        # Check trial categorization
        self.assertEqual(len(formatted_results["eligible_trials"]), 1)
        self.assertEqual(len(formatted_results["ineligible_trials"]), 1)
        self.assertEqual(len(formatted_results["indeterminate_trials"]), 0)

        # Check details of eligible trial
        eligible_trial = formatted_results["eligible_trials"][0]
        self.assertEqual(eligible_trial["trial_id"], "NCT12345")
        self.assertEqual(len(eligible_trial["criteria_summary"]), 2)
        self.assertTrue(all(c["is_met"] for c in eligible_trial["criteria_summary"]))

        # Check details of ineligible trial
        ineligible_trial = formatted_results["ineligible_trials"][0]
        self.assertEqual(ineligible_trial["trial_id"], "NCT67890")
        self.assertEqual(len(ineligible_trial["criteria_summary"]), 2)
        self.assertFalse(all(c["is_met"] for c in ineligible_trial["criteria_summary"]))

    def test_save_json_output(self):
        """Test saving formatted results to JSON file"""
        formatted_results = format_results_for_output(self.sample_results)
        json_path = save_json_output(formatted_results, self.output_dir)

        # Verify the file was created
        self.assertIsNotNone(json_path)
        self.assertTrue(os.path.exists(json_path))

        # Load and verify the saved content
        with open(json_path, 'r') as f:
            saved_results = json.load(f)
            self.assertEqual(saved_results["patient_id"], "TEST-123")
            self.assertEqual(len(saved_results["eligible_trials"]), 1)

    def test_create_simple_dataframe(self):
        """Test creating a simple DataFrame for Excel output"""
        simple_results = format_simple_results(self.sample_results)
        df = create_simple_dataframe(simple_results)

        # Check the DataFrame structure
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(df.shape[0], 1)  # One eligible trial
        self.assertIn("Patient ID", df.columns)
        self.assertIn("Trial ID", df.columns)
        self.assertIn("Trial Name", df.columns)
        self.assertIn("Eligibility Criteria Met", df.columns)

        # Check the content
        self.assertEqual(df.iloc[0]["Patient ID"], "TEST-123")
        self.assertEqual(df.iloc[0]["Trial ID"], "NCT12345")

    def test_create_dataframes(self):
        """Test creating DataFrames for detailed Excel output"""
        formatted_results = format_results_for_output(self.sample_results)
        summary_df, eligible_df, ineligible_df, criteria_df = create_dataframes(formatted_results)

        # Check the summary DataFrame
        self.assertEqual(summary_df.shape[0], 1)
        self.assertEqual(summary_df.iloc[0]["Patient ID"], "TEST-123")
        self.assertEqual(summary_df.iloc[0]["Eligible Trials"], 1)
        self.assertEqual(summary_df.iloc[0]["Ineligible Trials"], 1)

        # Check the eligible trials DataFrame
        self.assertEqual(eligible_df.shape[0], 1)
        self.assertEqual(eligible_df.iloc[0]["Trial ID"], "NCT12345")
        self.assertEqual(eligible_df.iloc[0]["Number of Criteria"], 2)

        # Check the ineligible trials DataFrame
        self.assertEqual(ineligible_df.shape[0], 1)
        self.assertEqual(ineligible_df.iloc[0]["Trial ID"], "NCT67890")
        self.assertEqual(ineligible_df.iloc[0]["Unmet Criteria"], 1)

        # Check the criteria details DataFrame
        self.assertEqual(criteria_df.shape[0], 2)  # Two criteria for the eligible trial

    @patch('src.generateOutput.save_excel_output')
    def test_process_single_eligibility_file(self, mock_save_excel):
        """Test processing a single eligibility file"""
        # Configure mock
        mock_save_excel.return_value = os.path.join(self.output_dir, "test_excel.xlsx")

        # Process the file
        result = process_single_eligibility_file(self.eligibility_file, self.output_dir)

        # Check the result structure
        self.assertEqual(result["patient_id"], "TEST-123")
        self.assertIn("json_path", result)
        self.assertIn("simple_json_path", result)
        self.assertIn("excel_path", result)
        self.assertIn("simple_excel_path", result)
        self.assertIn("formatted_results", result)
        self.assertIn("simple_results", result)

        # Verify files were created
        self.assertTrue(os.path.exists(result["json_path"]))
        self.assertTrue(os.path.exists(result["simple_json_path"]))

        # Check the content of simple JSON
        with open(result["simple_json_path"], 'r') as f:
            simple_data = json.load(f)
            self.assertEqual(simple_data["patientId"], "TEST-123")
            self.assertEqual(len(simple_data["eligibleTrials"]), 1)

    @patch('src.generateOutput.process_single_eligibility_file')
    def test_generate_output_single_file(self, mock_process):
        """Test generate_output function with a single file"""
        # Configure mock
        mock_process.return_value = {
            "patient_id": "TEST-123",
            "json_path": "test_path.json",
            "excel_path": "test_path.xlsx",
            "simple_json_path": "simple_test_path.json",
            "simple_excel_path": "simple_test_path.xlsx"
        }

        # Test the function
        result = generate_output(self.eligibility_file, self.output_dir)

        # Verify the result
        self.assertEqual(result["patient_id"], "TEST-123")
        self.assertEqual(result["json_path"], "test_path.json")
        self.assertEqual(result["excel_path"], "test_path.xlsx")
        self.assertEqual(result["simple_json_path"], "simple_test_path.json")
        self.assertEqual(result["simple_excel_path"], "simple_test_path.xlsx")

        # Verify process_single_eligibility_file was called once
        mock_process.assert_called_once_with(self.eligibility_file, self.output_dir)

    @patch('src.generateOutput.process_single_eligibility_file')
    @patch('src.generateOutput.create_consolidated_json')
    @patch('src.generateOutput.create_comprehensive_excel')
    @patch('src.generateOutput.create_summary_spreadsheet')
    @patch('glob.glob')
    def test_generate_output_directory(self, mock_glob, mock_summary, mock_excel, mock_json, mock_process):
        """Test generate_output function with a directory of files"""
        # Configure mocks
        mock_glob.return_value = [self.eligibility_file, self.eligibility_file + "2"]

        test_output = {
            "patient_id": "TEST-123",
            "json_path": "test_path.json",
            "excel_path": "test_path.xlsx",
            "simple_json_path": "simple_test_path.json",
            "simple_excel_path": "simple_test_path.xlsx",
            "formatted_results": format_results_for_output(self.sample_results),
            "simple_results": format_simple_results(self.sample_results)
        }
        mock_process.return_value = test_output

        mock_json.return_value = "consolidated.json"
        mock_excel.return_value = "comprehensive.xlsx"
        mock_summary.return_value = "summary.xlsx"

        # Create a test directory
        test_dir = os.path.join(self.test_dir, "eligibility_dir")
        os.makedirs(test_dir, exist_ok=True)

        # Test the function
        result = generate_output(test_dir, self.output_dir)

        # Verify the result structure for multiple patients
        self.assertIn("individual_outputs", result)
        self.assertEqual(len(result["individual_outputs"]), 2)
        self.assertEqual(result["summary_spreadsheet"], "summary.xlsx")
        self.assertEqual(result["consolidated_json"], "consolidated.json")
        self.assertEqual(result["comprehensive_excel"], "comprehensive.xlsx")
        self.assertIn("simple_consolidated_json", result)
        self.assertIn("simple_consolidated_excel", result)

        # Verify that create_summary_spreadsheet was called
        mock_summary.assert_called_once()

        # Verify that create_consolidated_json and create_comprehensive_excel were called
        mock_json.assert_called_once()
        mock_excel.assert_called_once()

if __name__ == '__main__':
    unittest.main()