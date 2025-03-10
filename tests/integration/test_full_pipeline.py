# tests/integration/test_full_pipeline.py
import unittest
import os
import tempfile
import shutil
import json
import sys
from unittest.mock import patch, MagicMock

# Add the root directory to sys.path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class TestFullPipeline(unittest.TestCase):
    def setUp(self):
        # Set up test paths
        self.test_dir = tempfile.mkdtemp()
        self.test_json_path = os.path.join(self.test_dir, "sample_trials.json")
        self.test_db_path = os.path.join(self.test_dir, "test.db")
        self.test_chroma_path = os.path.join(self.test_dir, "test_chroma")
        self.test_output_dir = os.path.join(self.test_dir, "test_output")

        # Create directories
        os.makedirs(self.test_chroma_path, exist_ok=True)
        os.makedirs(self.test_output_dir, exist_ok=True)

        # Create a minimal test JSON with clinical trial data
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

        # Create a fake patient XML file
        self.test_patient_path = os.path.join(self.test_dir, "test_patient.xml")
        with open(self.test_patient_path, 'w') as f:
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

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @unittest.skip("Requires full environment including LLM API")
    def test_full_pipeline(self):
        # This test would run the full pipeline but is skipped
        pass

    @patch('src.parseXMLs.parse_ccda_file')
    @patch('src.createCorpusDB.process_json_file')
    @patch('src.createVectorDB.create_corpus_db')
    @patch('src.findTrialsByChroma.match_and_rank_trials')
    @patch('src.evaluatePatientEligibility.evaluate_patient_eligibility')
    @patch('src.generateOutput.generate_output')
    def test_full_pipeline_with_mocks(
        self,
        mock_generate_output,
        mock_evaluate_eligibility,
        mock_match_and_rank,
        mock_create_corpus_db,
        mock_process_json,
        mock_parse_ccda
    ):
        # Import here to avoid circular imports
        from src.combined_pipeline import process_single_patient

        patient_output_dir = os.path.join(self.test_output_dir, "12345")
        os.makedirs(patient_output_dir, exist_ok=True)


        # Set up all the mocks

        # Mock patient data
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

        # Mock process_json_file to return success
        mock_process_json.return_value = (1, 1)

        # Mock create_corpus_db to do nothing
        mock_create_corpus_db.return_value = None

        # Mock match_and_rank_trials to save a file
        def fake_match(file_path, db_path, chroma_path, output_path, top_k):
            # Create the output files that would normally be created
            with open(output_path, 'w') as f:
                f.write("Mock ranking results")

            json_output = os.path.splitext(output_path)[0] + ".json"
            with open(json_output, 'w') as f:
                json.dump({
                    "patient": {"patientId": "12345"},
                    "matched_trials": [{"trial_id": "NCT12345", "trial_title": "Test Trial"}],
                    "total_matches": 1
                }, f)

        mock_match_and_rank.side_effect = fake_match

        # Mock evaluate_patient_eligibility to return results
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

        # Mock generate_output to return paths
        eligibility_dir = os.path.join(self.test_output_dir, "12345")
        os.makedirs(eligibility_dir, exist_ok=True)

        mock_generate_output.return_value = {
            "patient_id": "12345",
            "json_path": os.path.join(eligibility_dir, "results.json"),
            "excel_path": os.path.join(eligibility_dir, "results.xlsx"),
            "simple_json_path": os.path.join(eligibility_dir, "simple.json"),
            "simple_excel_path": os.path.join(eligibility_dir, "simple.xlsx")
        }

        # Now call process_single_patient and check the results
        result = process_single_patient(
            patient_file_path=self.test_patient_path,
            trials_json_path=self.test_json_path,
            sqlite_db_path=self.test_db_path,
            chroma_db_path=self.test_chroma_path,
            output_dir=self.test_output_dir,
            model_name="mock-model"
        )

        # Verify that we got a result
        self.assertIsNotNone(result)
        self.assertIn("patient_name", result)
        self.assertEqual(result["patient_name"], "test_patient")