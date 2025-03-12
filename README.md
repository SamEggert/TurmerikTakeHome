# Clinical Trial Matcher (TurmerikAI Take Home)

A system for matching patients to actively recruiting clinical trials based on their CCDA (Consolidated Clinical Document Architecture) records.

## Overview

This pipeline automates the process of matching patients to clinical trials by:

1. Scraping actively recruiting trials from ClinicalTrials.gov
2. Creating a SQLite database for demographic filtering (age, gender)
3. Building a ChromaDB vector database for semantic search
4. Using LLM (GPT-4o-mini) to evaluate patient eligibility based on conditions and medications
5. Generating comprehensive output in JSON and Excel formats

## Prerequisites

* Python 3.7+
* OpenAI API key

## Setup Instructions

### 1. Clone the Repository

```bash
git clone git clone https://github.com/SamEggert/TurmerikTakeHome.git
cd TurmerikTakeHome
```

### 2. Create a Virtual Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up OpenAI API Access

Create a `.env` file in the project root directory with your OpenAI API key:

```
OPENAI_API_KEY=your_openai_api_key_here
```

### 5. Download and Organize Data

#### Patient Data (CCDA Records)

1. Download the synthetic patient data from: [Synthea Sample Data - CCDA](https://synthetichealth.github.io/synthea-sample-data/downloads/latest/synthea_sample_data_ccda_latest.zip)
2. Extract the ZIP file
3. Move the extracted folder (`synthea_sample_data_ccda_latest`) to the `data/` directory in the project

> **Note** : You can also use your own patient data in CCDA XML format.

#### 6. Verify Directory Structure

Your project directory should look like this:

```
TurmerikTakeHome/
├── data/
│   ├── synthea_sample_data_ccda_latest/   # Patient CCDA XML files
├── src/                                   # Source code directory
├── .env                                   # OpenAI API key
├── requirements.txt
└── README.md
```

## Running the Pipeline

1. Navigate to the source directory:

```bash
cd src
```

2. Run the main pipeline script:

```bash
python combined_pipeline.py
```

3. The results will be available in the `data/results` directory, with both JSON and Excel format outputs.

## Command-Line Options

The pipeline supports various command-line arguments for customization:

```bash
python combined_pipeline.py [OPTIONS]
```

| Option                     | Description                                       | Default                                      |
| -------------------------- | ------------------------------------------------- | -------------------------------------------- |
| `--patient`or `-p`     | Path to a patient CCDA XML file or directory      | `../data/synthea_sample_data_ccda_latest/` |
| `--trials-json`or `-j` | Path to the clinical trials JSON file             | `../data/ctg-studies.json`                 |
| `--sqlite-db`or `-s`   | Path to the SQLite database                       | `../data/clinical_trials.db`               |
| `--chroma-db`or `-c`   | Path to the ChromaDB directory                    | `../data/chroma_db`                        |
| `--output-dir`or `-o`  | Directory to store output files                   | `../data/results`                          |
| `--sample-size`          | Number of trials to sample from JSON              | `500`                                      |
| `--batch-size`or `-b`  | Number of trials to process in each batch         | `100`                                      |
| `--top-k`or `-k`       | Number of top trials to evaluate for eligibility  | `10`                                       |
| `--model`or `-m`       | LLM model to use for eligibility evaluation       | `gpt-4o-mini`                              |
| `--max-patients`         | Maximum number of patients to process (0 for all) | `1`                                        |
| `--no-scrape`            | Skip scraping trials from ClinicalTrials.gov      | Scraping enabled by default                  |
| `--force-scrape`         | Force re-scraping even if trials JSON exists      | False                                        |

### Examples

Process a specific patient file:

```bash
python combined_pipeline.py --patient ../data/synthea_sample_data_ccda_latest/specific_patient.xml
```

Process more patients and trials:

```bash
python combined_pipeline.py --max-patients 5 --sample-size 1000 --top-k 20
```

Use an existing trials JSON file without scraping:

```bash
python combined_pipeline.py --no-scrape --trials-json ../data/my_trials.json
```

## Output Files

The pipeline generates several output files:

* **JSON format** : Detailed eligibility results for each patient
* **Excel files** : Formatted eligibility reports
* **Simple format files** : Condensed results focusing on matched trials only
* `patient_[ID]_simple_eligibility_[DATE].json`
* `patient_[ID]_simple_eligibility_[DATE].xlsx`

For multiple patients, additional summary files are generated:

* `all_patients_simple_[DATE].json`
* `all_patients_simple_[DATE].xlsx`

## Troubleshooting

* **OpenAI API Errors** : Ensure your API key is correctly set in the `.env` file
* **Memory Issues** : Reduce `--sample-size` or `--batch-size` if encountering memory problems
* **Missing Libraries** : Verify all dependencies are installed with `pip install -r requirements.txt`
* **Run Time:** for default settings, the entire pipeline takes about 6 minutes to run. Adding more patients or trials will likely take longer.

## Sample Excel and JSON Output (50 patients, 10,000 trials, took 2 hours)

[https://drive.google.com/drive/folders/12_qzbUu4XScOX9lQsA69i3ZIj4fRbiI6?usp=drive_link](https://drive.google.com/drive/folders/12_qzbUu4XScOX9lQsA69i3ZIj4fRbiI6?usp=drive_link)
