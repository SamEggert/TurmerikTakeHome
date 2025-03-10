
# TumerikTakeHome

This repository contains instructions for obtaining and organizing both patient and trial data.

## Data Sources

### 1. Patient Data: Synthetic CCDA Records

- **Source:** [Synthea Sample Data - CCDA](https://synthetichealth.github.io/synthea-sample-data/downloads/latest/synthea_sample_data_ccda_latest.zip)
- **Description:** 100 Sample Synthetic Patient Records in CCDA (XML) format (~7 MB)

### 2. Trial Data: Actively Recruiting Clinical Trials

- **Source:** [ClinicalTrials.gov Expert Search](https://clinicaltrials.gov/expert-search?term=AREA%5BLocationStatus%5DCOVERAGE%5BFullMatch%5DRECRUITING)
- **Download Instructions:**
  1. Navigate to the link above.
  2. Click the **Download** button (located under the search results).
  3. Under **What would you like to download?**, select:
     - **File format:** JSON
     - **Results to Download:** ALL
     - **Data Fields:** Custom set (choose only the following fields):
       - **protocolSection (18)** – Protocol Section
         - **identificationModule (18):**
           - `nctId` – NCT Number
           - `briefTitle` – Brief Title
       - **descriptionModule (1):**
         - `briefSummary`
       - **conditionsModule (1):**
         - `conditions` – Condition/Disease
       - **designModule (2):**
         - `phases` – Study Phase
         - **enrollmentInfo (1):**
           - `count` – Enrollment
       - **armsInterventionsModule (2):**
         - **interventions (2):**
           - `type` – Intervention/Treatment Type
           - `name` – Intervention Name
       - **eligibilityModule (10):**
         - `eligibilityCriteria`
         - `healthyVolunteers`
         - `sex`
         - `genderBased`
         - `genderDescription`
         - `minimumAge`
         - `maximumAge`
         - `stdAges`
         - `studyPopulation`
         - `samplingMethod`
- **Result:** The downloaded file should be named `ctg-studies.json`.

## Directory Structure

Organize your project files in the following structure:

```python
project-root/
├── data/
│   ├── synthea_sample_data_ccda_latest/   # Extracted patient data files
│   ├── synthea_sample_data_ccda_latest.zip
│   └── ctg-studies.json                    # Trial data file
└── README.md

```


## Instructions

1. **Download Patient Data:**

   - Download the Synthea sample data (CCDA format) from the [link](https://synthetichealth.github.io/synthea-sample-data/downloads/latest/synthea_sample_data_ccda_latest.zip).
   - Extract the downloaded ZIP file. The resulting folder should be named `synthea_sample_data_ccda_latest`.
2. **Download Trial Data:**

   - Follow the instructions in the **Trial Data** section.
   - After downloading, ensure the file is named `ctg-studies.json`.
3. **Organize Files:**

   - Create a directory named `data` in the project root.
   - Move both the extracted Synthea sample data folder and the `ctg-studies.json` file into the `data` directory.

Happy coding!
