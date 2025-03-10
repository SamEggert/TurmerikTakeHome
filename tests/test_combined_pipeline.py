import unittest
import os
import sys
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

# Add the root directory to sys.path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.combined_pipeline import process_single_patient, run_pipeline

class TestCombinedPipeline(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()

        # Create directories and test files
        self.trials_json_path = os.path.join(self.test_dir, "test_trials.json")
        self.sqlite_db_path = os.path.join(self.test_dir, "test.db")
        self.chroma_db_path = os.path.join(self.test_dir, "test_chroma")
        self.output_dir = os.path.join(self.test_dir, "output")
        self.patient_dir = os.path.join(self.test_dir, "patients")

        # Create directories
        os.makedirs(self.chroma_db_path, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.patient_dir, exist_ok=True)

        # Create a sample patient XML file
        self.patient_file = os.path.join(self.patient_dir, "test_patient.xml")
        with open(self.patient_file, 'w') as f:
            f.write('''<?xml version="1.0" encoding="UTF-8"?>
            <ClinicalDocument xmlns="urn:hl7-org:v3">
              <recordTarget>
                <patientRole>
                  <id extension="12345" />
                  <patient>
                    <administrativeGenderCode code="M" />
                    <birthTime value="19800101" />
                  </patient>
                </patientRole>
              </recordTarget>
            </ClinicalDocument>''')

        # Create a sample trials JSON file
        with open(self.trials_json_path, 'w') as f:
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

        # Create a second patient file for multi-patient tests
        self.patient_file2 = os.path.join(self.patient_dir, "test_patient2.xml")
        shutil.copy(self.patient_file, self.patient_file2)

    def tearDown(self):
        # Clean up test directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('src.combined_pipeline.parse_ccda_file')
    @patch('src.combined_pipeline.match_and_rank_trials')
    @patch('src.combined_pipeline.evaluate_patient_eligibility')
    @patch('src.combined_pipeline.generate_output')
    def test_process_single_patient(self, mock_generate_output, mock_evaluate_eligibility,
                                  mock_match_and_rank, mock_parse_ccda):
        """Test the process_single_patient function with mocked dependencies"""

        # Set up mock returns
        mock_parse_ccda.return_value = {
            "patientId": "12345",
            "demographics": {"age": 40, "gender": "M"},
            "conditions": [{"name": "Test Condition", "onsetDate": "2020-01-01"}],
            "medications": [{"name": "Test Medication", "dose": "10", "unit": "mg"}],
            "key_clinical_info": {
                "demographic_summary": "Age: 40; Gender: Male",
                "condition_summary": "Test Condition",
                "medication_summary": "Test Medication 10 mg",
                "semantic_search_query": "40-year-old male with Test Condition"
            }
        }

        # Mock match_and_rank_trials to create output files
        def fake_match_and_rank(file_path, db_path, chroma_path, output_path, top_k):
            # Create the files that would normally be created
            with open(output_path, 'w') as f:
                f.write("Mock trial ranking results")

            json_output = os.path.splitext(output_path)[0] + ".json"
            with open(json_output, 'w') as f:
                json.dump({
                    "patient": {"patientId": "12345"},
                    "matched_trials": [{"trial_id": "NCT12345", "trial_title": "Test Trial"}],
                    "total_matches": 1
                }, f)

        mock_match_and_rank.side_effect = fake_match_and_rank

        # Mock evaluate_patient_eligibility
        mock_evaluate_eligibility.return_value = {
            "patient_id": "12345",
            "evaluation_date": "2023-01-01",
            "trials_evaluated": 1,
            "results": [
                {
                    "trial_id": "NCT12345",
                    "trial_title": "Test Trial",
                    "semantic_score": 0.9,
                    "evaluation": [
                        {
                            "criterion": "Patient must be between 18 and 65 years of age",
                            "is_met": True,
                            "confidence": "high",
                            "rationale": "Patient is 40 years old and meets this criterion."
                        }
                    ]
                }
            ]
        }

        # Mock generate_output
        mock_generate_output.return_value = {
            "patient_id": "12345",
            "json_path": os.path.join(self.output_dir, "results.json"),
            "excel_path": os.path.join(self.output_dir, "results.xlsx"),
            "simple_json_path": os.path.join(self.output_dir, "simple.json"),
            "simple_excel_path": os.path.join(self.output_dir, "simple.xlsx")
        }

        # Run the function
        result = process_single_patient(
            patient_file_path=self.patient_file,
            trials_json_path=self.trials_json_path,
            sqlite_db_path=self.sqlite_db_path,
            chroma_db_path=self.chroma_db_path,
            output_dir=self.output_dir,
            model_name="mock-model"
        )

        # Check the result
        self.assertIsNotNone(result)
        self.assertEqual(result["patient_name"], "test_patient")
        self.assertEqual(result["patient_id"], "12345")

        # Verify all mocked functions were called
        mock_parse_ccda.assert_called_once()
        mock_match_and_rank.assert_called_once()
        mock_evaluate_eligibility.assert_called_once()
        mock_generate_output.assert_called_once()

    @patch('src.combined_pipeline.process_json_file')
    @patch('src.combined_pipeline.create_corpus_db')
    @patch('src.combined_pipeline.process_single_patient')
    def test_run_pipeline_single_patient(self, mock_process_single_patient,
                                      mock_create_corpus_db, mock_process_json_file):
        """Test the run_pipeline function with a single patient"""

        # Set up mock returns
        mock_process_json_file.return_value = (1, 1)  # Total trials, processed trials

        # Mock the process_single_patient function
        mock_process_single_patient.return_value = {
            "patient_name": "test_patient",
            "patient_id": "12345",
            "eligibility_results": os.path.join(self.output_dir, "eligibility_results.json"),
            "output_files": {
                "json_path": os.path.join(self.output_dir, "results.json"),
                "excel_path": os.path.join(self.output_dir, "results.xlsx"),
                "simple_json_path": os.path.join(self.output_dir, "simple.json"),
                "simple_excel_path": os.path.join(self.output_dir, "simple.xlsx")
            }
        }

        # Run the pipeline with a single patient
        result = run_pipeline(
            patient_path=self.patient_file,
            trials_json_path=self.trials_json_path,
            sqlite_db_path=self.sqlite_db_path,
            chroma_db_path=self.chroma_db_path,
            output_dir=self.output_dir,
            sample_size=10,
            batch_size=5,
            top_k=5,
            model_name="mock-model"
        )

        # Check results
        self.assertIsNotNone(result)
        self.assertEqual(result["patient_name"], "test_patient")
        self.assertEqual(result["patient_id"], "12345")
        self.assertEqual(result["simple_json"], os.path.join(self.output_dir, "simple.json"))
        self.assertEqual(result["simple_excel"], os.path.join(self.output_dir, "simple.xlsx"))

        # Verify functions were called
        mock_process_json_file.assert_called_once()
        mock_create_corpus_db.assert_called_once()
        mock_process_single_patient.assert_called_once_with(
            patient_file_path=self.patient_file,
            trials_json_path=self.trials_json_path,
            sqlite_db_path=self.sqlite_db_path,
            chroma_db_path=self.chroma_db_path,
            output_dir=self.output_dir,
            sample_size=10,
            batch_size=5,
            top_k=5,
            model_name="mock-model"
        )

    @patch('src.combined_pipeline.process_json_file')
    @patch('src.combined_pipeline.create_corpus_db')
    @patch('src.combined_pipeline.process_single_patient')
    @patch('src.combined_pipeline.generate_output')
    def test_run_pipeline_multiple_patients(self, mock_generate_output,
                                         mock_process_single_patient,
                                         mock_create_corpus_db,
                                         mock_process_json_file):
        """Test the run_pipeline function with multiple patients"""

        # Set up mock returns
        mock_process_json_file.return_value = (1, 1)  # Total trials, processed trials

        # Mock the process_single_patient function to return different values for each call
        patient_results = [
            {
                "patient_name": "test_patient",
                "patient_id": "12345",
                "eligibility_results": os.path.join(self.output_dir, "12345", "eligibility_results.json"),
                "output_files": {
                    "json_path": os.path.join(self.output_dir, "12345", "results.json"),
                    "excel_path": os.path.join(self.output_dir, "12345", "results.xlsx"),
                    "simple_json_path": os.path.join(self.output_dir, "12345", "simple.json"),
                    "simple_excel_path": os.path.join(self.output_dir, "12345", "simple.xlsx")
                }
            },
            {
                "patient_name": "test_patient2",
                "patient_id": "67890",
                "eligibility_results": os.path.join(self.output_dir, "67890", "eligibility_results.json"),
                "output_files": {
                    "json_path": os.path.join(self.output_dir, "67890", "results.json"),
                    "excel_path": os.path.join(self.output_dir, "67890", "results.xlsx"),
                    "simple_json_path": os.path.join(self.output_dir, "67890", "simple.json"),
                    "simple_excel_path": os.path.join(self.output_dir, "67890", "simple.xlsx")
                }
            }
        ]

        mock_process_single_patient.side_effect = patient_results

        # Mock the generate_output function for summary
        mock_generate_output.return_value = {
            "summary_spreadsheet": os.path.join(self.output_dir, "summary", "all_patients_summary.xlsx"),
            "simple_consolidated_json": os.path.join(self.output_dir, "summary", "all_patients_simple.json"),
            "simple_consolidated_excel": os.path.join(self.output_dir, "summary", "all_patients_simple.xlsx")
        }

        # Run the pipeline with a directory of patients
        result = run_pipeline(
            patient_path=self.patient_dir,
            trials_json_path=self.trials_json_path,
            sqlite_db_path=self.sqlite_db_path,
            chroma_db_path=self.chroma_db_path,
            output_dir=self.output_dir,
            sample_size=10,
            batch_size=5,
            top_k=5,
            model_name="mock-model"
        )

        # Check results
        self.assertIsNotNone(result)
        self.assertIn("patient_results", result)
        self.assertEqual(len(result["patient_results"]), 2)
        self.assertIn("summary_dir", result)
        self.assertEqual(result["simple_json"], os.path.join(self.output_dir, "summary", "all_patients_simple.json"))
        self.assertEqual(result["simple_excel"], os.path.join(self.output_dir, "summary", "all_patients_simple.xlsx"))

        # Verify functions were called
        mock_process_json_file.assert_called_once()
        mock_create_corpus_db.assert_called_once()
        self.assertEqual(mock_process_single_patient.call_count, 2)
        mock_generate_output.assert_called_once()

    @patch('src.combined_pipeline.process_json_file')
    @patch('src.combined_pipeline.create_corpus_db')
    @patch('src.combined_pipeline.process_single_patient')
    def test_run_pipeline_with_existing_db(self, mock_process_single_patient,
                                         mock_create_corpus_db,
                                         mock_process_json_file):
        """Test run_pipeline when databases already exist"""

        # Create mock existing databases
        open(self.sqlite_db_path, 'w').close()  # Create empty file
        os.makedirs(os.path.join(self.chroma_db_path, "dummy"), exist_ok=True)  # Create non-empty directory

        # Set up mock return for process_single_patient
        mock_process_single_patient.return_value = {
            "patient_name": "test_patient",
            "patient_id": "12345",
            "eligibility_results": os.path.join(self.output_dir, "eligibility_results.json"),
            "output_files": {
                "json_path": os.path.join(self.output_dir, "results.json"),
                "excel_path": os.path.join(self.output_dir, "results.xlsx"),
                "simple_json_path": os.path.join(self.output_dir, "simple.json"),
                "simple_excel_path": os.path.join(self.output_dir, "simple.xlsx")
            }
        }

        # Run the pipeline
        result = run_pipeline(
            patient_path=self.patient_file,
            trials_json_path=self.trials_json_path,
            sqlite_db_path=self.sqlite_db_path,
            chroma_db_path=self.chroma_db_path,
            output_dir=self.output_dir
        )

        # Check results
        self.assertIsNotNone(result)

        # Verify that database creation functions were not called
        mock_process_json_file.assert_not_called()
        mock_create_corpus_db.assert_not_called()

        # Verify that process_single_patient was called
        mock_process_single_patient.assert_called_once()

    @patch('src.combined_pipeline.parse_ccda_file')
    def test_process_single_patient_parse_error(self, mock_parse_ccda):
        """Test process_single_patient when there's an error parsing the patient file"""

        # Mock parse_ccda_file to return None (error)
        mock_parse_ccda.return_value = None

        # Run the function
        result = process_single_patient(
            patient_file_path=self.patient_file,
            trials_json_path=self.trials_json_path,
            sqlite_db_path=self.sqlite_db_path,
            chroma_db_path=self.chroma_db_path,
            output_dir=self.output_dir
        )

        # Check result is None due to parsing error
        self.assertIsNone(result)
        mock_parse_ccda.assert_called_once()

    def test_run_pipeline_invalid_paths(self):
        """Test run_pipeline with invalid file paths"""

        # Test with non-existent patient path
        result = run_pipeline(
            patient_path="/non/existent/path",
            trials_json_path=self.trials_json_path,
            sqlite_db_path=self.sqlite_db_path,
            chroma_db_path=self.chroma_db_path,
            output_dir=self.output_dir
        )
        self.assertIsNone(result)

        # Test with non-existent trials JSON
        result = run_pipeline(
            patient_path=self.patient_file,
            trials_json_path="/non/existent/trials.json",
            sqlite_db_path=self.sqlite_db_path,
            chroma_db_path=self.chroma_db_path,
            output_dir=self.output_dir
        )
        self.assertIsNone(result)