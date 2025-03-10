
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


## Environment and Pipeline Setup

### 1. Create a Virtual Environment and Install Dependencies

Ensure you have Python 3.7+ installed. Then, create a virtual environment and install the required packages. For example:

```bash
# Create and activate a virtual environment (Linux/macOS)
python -m venv venv
source venv/bin/activate

# On Windows:
# python -m venv venv
# venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```


### 2. Set Up the `.env` File for OpenAI API Access

This project uses the OpenAI API (via Langchain's `ChatOpenAI`) to evaluate patient eligibility. To enable API calls, create a `.env` file in your project root with your OpenAI API key. For example:

```dotenv
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Organize Your Data

Make sure your data is organized as follows:

```python
project-root/
├── data/
│   ├── synthea_sample_data_ccda_latest/   # Extracted patient CCDA XML files
│   └── ctg-studies.json                    # Clinical trials JSON file
├── src/                                   # Source code directory
└── README.md
```


### 4. Running the Pipeline

Once the environment is set up and the data is organized, follow these steps to run the full pipeline:

1. Navigate to the `src` Directory:
2. ```bash
   cd src
   ```


2. Run the Combined Pipeline:

Execute the `combined_pipeline.py` script to process the data and generate outputs. For example:

```bash
python combined_pipeline.py
```


This command performs the following steps:

* **Data Preparation:**

  Parses and imports trial data from `ctg-studies.json` into a SQLite database and creates a vector database using ChromaDB.
* **Patient Processing:**

  Reads the CCDA files from the Synthea dataset, extracts key clinical details, and generates semantic search queries.
* **Matching and Ranking:**

  Matches each patient to eligible clinical trials based on demographic filters and semantic similarity.
* **Eligibility Evaluation:**

  Uses the OpenAI API to evaluate whether the patient meets the inclusion criteria for each trial.
* **Output Generation:**

  Produces both JSON and Excel files summarizing eligible trials for each patient.


### 5. Command-Line Options

`combined_pipeline.py` supports various command-line arguments to customize the pipeline. Some of the options include:

* `--patient` or `-p`: Path to a single patient CCDA XML file or a directory containing multiple patient files.
* `--trials-json` or `-j`: Path to the clinical trials JSON file.
* `--sqlite-db` or `-s`: Path for the SQLite database (it will be created if it does not exist).
* `--chroma-db` or `-c`: Path for the ChromaDB vector database.
* `--output-dir` or `-o`: Directory to store output files.
* `--sample-size`, `--batch-size`, `--top-k`, and `--model`: Additional parameters for sampling and eligibility evaluation.
