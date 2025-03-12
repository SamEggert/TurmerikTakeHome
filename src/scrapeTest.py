import requests
import json
import time
import os
from urllib.parse import quote

class ClinicalTrialsDownloader:
    def __init__(self, base_url="https://clinicaltrials.gov", output_file="../data/ctg-studies.json"):
        self.base_url = base_url
        self.output_file = output_file
        self.api_endpoint = "/api/v2/studies"
        self.all_studies = []

    def download_studies(self, fields=None, max_retries=3, retry_delay=5):
        """
        Download all actively recruiting clinical trials

        Args:
            fields: List of fields to include in the response. If None, all fields will be included.
            max_retries: Maximum number of retries for API calls
            retry_delay: Delay in seconds between retries
        """
        query_term = "AREA[LocationStatus]COVERAGE[FullMatch]RECRUITING"
        page_size = 1000  # Maximum allowed by API
        page_token = None
        total_retrieved = 0

        # Check if API is ready before starting
        self._check_api_status()

        print(f"Starting download of actively recruiting clinical trials...")

        while True:
            params = {
                "query.term": query_term,
                "pageSize": page_size
            }

            # Add page token for pagination if we have one
            if page_token:
                params["pageToken"] = page_token

            # Add fields if specified
            if fields:
                params["fields"] = ",".join(fields)

            # Make API request with retries
            response = None
            for attempt in range(max_retries):
                try:
                    url = f"{self.base_url}{self.api_endpoint}"
                    print(f"Making request to: {url} (Page token: {page_token})")
                    response = requests.get(url, params=params)
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException as e:
                    print(f"Attempt {attempt+1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        print(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        print("Maximum retries reached. Exiting.")
                        raise

            # Parse response
            data = response.json()
            studies = data.get("studies", [])
            total_studies = data.get("totalCount", 0)

            if studies:
                self.all_studies.extend(studies)
                total_retrieved += len(studies)
                print(f"Retrieved {total_retrieved} of {total_studies} studies")

                # Check if we have more pages
                page_token = data.get("nextPageToken")
                if not page_token:
                    print("No more pages to retrieve.")
                    break
            else:
                print("No studies found in the response.")
                break

        # Save all studies to file
        self._save_to_file()
        print(f"Download completed. Total studies retrieved: {total_retrieved}")
        print(f"The data has been saved to {self.output_file}")
        print(f"You can now process it with your database script using:")
        print(f"python process_trials.py --input {self.output_file} --output ../data/clinical_trials.db --sample 5000")
        return self.all_studies

    def _check_api_status(self):
        """Check API version and status before starting download"""
        try:
            version_url = f"{self.base_url}/api/v2/version"
            response = requests.get(version_url)
            response.raise_for_status()
            version_data = response.json()
            print(f"API Version: {version_data.get('apiVersion')}")
            print(f"Data Timestamp: {version_data.get('dataTimestamp')}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to check API status: {e}")
            print("Continuing with download anyway...")

    def _save_to_file(self):
        """Save all retrieved studies to a JSON file in the same format as the website download"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)

            # Save directly as an array of studies, not inside a "studies" object
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.all_studies, f, indent=2)
            print(f"Successfully saved {len(self.all_studies)} studies to {self.output_file}")
        except Exception as e:
            print(f"Error saving to file: {e}")
            # Save to backup file
            backup_file = f"backup_{int(time.time())}.json"
            print(f"Attempting to save to backup file: {backup_file}")
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.all_studies, f, indent=2)

def main():
    """Main function to download clinical trials data"""
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Download actively recruiting clinical trials from ClinicalTrials.gov")
    parser.add_argument("--output", "-o", type=str, default="../data/ctg-studies.json",
                        help="Output file path (default: ../data/ctg-studies.json)")
    args = parser.parse_args()

    # Define the specific fields you want to download (matching your requirements)
    fields = [
        "protocolSection.identificationModule.nctId",
        "protocolSection.identificationModule.briefTitle",
        "protocolSection.descriptionModule.briefSummary",
        "protocolSection.conditionsModule.conditions",
        "protocolSection.designModule.phases",
        "protocolSection.designModule.enrollmentInfo.count",
        "protocolSection.armsInterventionsModule.interventions.type",
        "protocolSection.armsInterventionsModule.interventions.name",
        "protocolSection.eligibilityModule.eligibilityCriteria",
        "protocolSection.eligibilityModule.healthyVolunteers",
        "protocolSection.eligibilityModule.sex",
        "protocolSection.eligibilityModule.genderBased",
        "protocolSection.eligibilityModule.genderDescription",
        "protocolSection.eligibilityModule.minimumAge",
        "protocolSection.eligibilityModule.maximumAge",
        "protocolSection.eligibilityModule.stdAges",
        "protocolSection.eligibilityModule.studyPopulation",
        "protocolSection.eligibilityModule.samplingMethod"
    ]

    # Create downloader instance and start download
    downloader = ClinicalTrialsDownloader(output_file=args.output)
    downloader.download_studies(fields=fields)

if __name__ == "__main__":
    main()