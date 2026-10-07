# TalentIQ

TalentIQ is a web-based resume screening and candidate evaluation system developed as a college mini-project. It compares candidate resumes with job descriptions using keyword-based and semantic similarity techniques.

## 📌 Project Overview

TalentIQ provides two workflows:

- **HR:** Upload job descriptions, configure screening criteria, upload candidate resumes, and review screening results.
- **Candidates:** Select a job, upload an existing resume or create one using the resume builder, and view how closely their profile matches the selected role.

The application supports PDF, DOCX, and TXT resumes. It extracts and processes resume text, identifies relevant skills and experience, compares the resume with the selected job description, and generates a match score.

The application is implemented using **Flask** with **MongoDB** as the database.

## 🎯 Problem Statement

Manual resume screening can be time-consuming when HR teams need to review multiple applications. Candidates may also find it difficult to understand how well their qualifications match a particular job.

TalentIQ addresses these problems by providing an automated screening workflow that compares resumes with job requirements and presents the results in an easy-to-understand format.

## 💡 Proposed Solution

For each resume, the system:

1. Extracts text from the uploaded file.
2. Cleans and normalizes the extracted text.
3. Removes selected personal identifiers before scoring.
4. Extracts skills and experience-related information.
5. Compares the resume with the selected job description.
6. Calculates keyword and semantic similarity scores.
7. Generates a final match score.
8. Applies the configured screening criteria.
9. Displays matched skills, skill-gap categories, and the final screening decision.

The project is intended as an academic implementation of automated resume screening rather than a production recruitment system.

## ✨ Features

### Candidate Features

- Upload resumes in PDF, DOCX, or TXT format
- Create resumes using an in-app resume builder
- Preview a created resume
- Check resume match score against a selected job
- View semantic and keyword matching scores
- View matched skills
- View skill-gap categories
- Download generated PDF resumes
- Candidate signup and login

### HR Features

- Upload and manage job descriptions
- Set minimum match score
- Set minimum experience requirement
- Specify mandatory skills
- Activate or deactivate job listings
- Upload multiple candidate resumes
- View shortlisted and rejected candidates
- View scoring breakdown and rejection reasons
- Export shortlisted candidates as CSV
- Review previous screening results

## 🧠 How the System Works

### Candidate Workflow

1. Candidate signs up or logs in.
2. Candidate selects an active job opening.
3. Candidate uploads an existing resume or creates one using the resume builder.
4. Resume information is processed by the application.
5. Personal identifiers are removed before scoring.
6. Resume content is compared with the selected job description.
7. TF-IDF and semantic similarity scores are calculated.
8. The final match score is displayed along with matched skills and skill-gap categories.

### HR Workflow

1. HR signs up or logs in.
2. HR creates a job opening by uploading a job description.
3. Screening criteria such as minimum score, experience, and mandatory skills can be configured.
4. HR selects an active job opening.
5. Candidate resumes are uploaded for screening.
6. Each resume is processed and compared with the job description.
7. Candidates are shortlisted or rejected according to the configured criteria.
8. HR can review results and export shortlisted candidates as CSV.

## 🔬 Resume Processing and Matching

### 1. Resume Text Extraction

The application supports:

- **PDF** — text extracted using `pdfplumber`
- **DOCX** — text extracted using `python-docx`
- **TXT** — read as UTF-8 text

The extracted content is cleaned and normalized before matching.

### 2. Skill Extraction

The project uses two Excel files as skill sources:

- `skills_onet.xlsx`
- `Technology Skills.xlsx`

The application loads the skill information using `pandas` and creates a skill database.

Skills are then detected in resumes and job descriptions using text matching.

### 3. Experience Extraction

The application identifies experience information from resume text using patterns such as:

- `3 years`
- `5 yrs`
- `2+ years`
- `since 2019`

The extracted experience value is capped at 40 years to avoid unrealistic values caused by parsing errors.

### 4. TF-IDF Matching

The project uses `TfidfVectorizer` and cosine similarity from **scikit-learn**.

TF-IDF measures the importance of words in the resume and job description and compares their similarity.

This helps identify overlap between the candidate's resume and the job requirements.

### 5. Semantic Matching

The project also uses **SentenceTransformer** with the:

```text
all-MiniLM-L6-v2
```

model.

The resume and job description are converted into embeddings, and cosine similarity is used to compare their semantic meaning.

This allows the system to identify similarity beyond exact keyword matches.

### 6. Final Match Score

The final score is calculated using:

```text
Final Score = 0.6 × Semantic Score + 0.4 × TF-IDF Score
```

The semantic score therefore contributes 60% and the TF-IDF score contributes 40% to the final result.

### 7. PII Removal

Before scoring, the application removes selected personal identifiers such as:

- Email addresses
- Phone numbers
- Gendered titles
- Date/DOB patterns
- Selected demographic information

The application also tracks the number of redactions.

This feature is intended as a **bias-mitigation step** so that selected personal information does not directly influence the matching process.

### 8. Skill-Gap Analysis

The application groups missing skills into broader categories instead of displaying only a raw list of missing keywords.

Examples include:

- Cloud & DevOps
- Data & Analytics
- Machine Learning & AI
- Web Development
- Programming Languages
- Databases
- Security
- Mobile Development
- Soft Skills & PM

### 9. Screening Filters

HR can configure:

- Minimum match score
- Minimum experience
- Mandatory skills

A candidate who fails one or more configured conditions can be rejected with a corresponding reason.

### 10. Duplicate Resume Detection

The application compares a newly submitted resume with previous resumes submitted for the same job and user.

TF-IDF cosine similarity is used for comparison. A similarity of **0.95 or higher** is treated as a duplicate.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend and application logic |
| Flask | Web framework |
| MongoDB | Database |
| Flask-PyMongo | Flask-MongoDB integration |
| pandas | Processing Excel skill data |
| scikit-learn | TF-IDF and cosine similarity |
| Sentence Transformers | Semantic similarity using SBERT |
| pdfplumber | PDF text extraction |
| python-docx | DOCX text extraction |
| FPDF | PDF resume generation |
| python-dotenv | Environment variable management |
| Werkzeug | Password hashing and verification |
| HTML/CSS | Web interface |
| Jinja2 | Flask template rendering |
| Excel | Skill datasets |

## 📂 Project Structure

```text
Mini-Project-1B/
├── .env.example
├── .gitignore
├── README.md
├── Technology Skills.xlsx
├── skills_onet.xlsx
├── app.py
├── resumer_parser.py
├── semantic_matcher.py
├── requirements.txt
│
├── index.html
├── login.html
├── signup.html
│
├── candidate_create.html
├── candidate_dashboard.html
├── candidate_preview.html
├── candidate_result.html
├── candidate_upload.html
│
├── hr_dashboard.html
├── hr_results.html
└── no_jd.html
```

### Important Files

| File | Purpose |
|---|---|
| `app.py` | Main Flask application and application routes |
| `semantic_matcher.py` | SentenceTransformer semantic similarity |
| `resumer_parser.py` | PDF and DOCX resume text extraction |
| `candidate_*.html` | Candidate-side pages |
| `hr_*.html` | HR-side pages |
| `login.html` | Login interface |
| `signup.html` | Registration interface |
| `skills_onet.xlsx` | O*NET-based skill data |
| `Technology Skills.xlsx` | Technology skill data |
| `.env.example` | Environment variable template |
| `requirements.txt` | Python dependencies |

## ⚙️ Installation and Setup

### Prerequisites

- Python 3.9 or later
- MongoDB
- Git
- pip

### 1. Clone the Repository

```bash
git clone https://github.com/sweetyparmar6116-ux/Mini-Project-1B.git
cd Mini-Project-1B
```

### 2. Create a Virtual Environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file based on `.env.example`.

Example:

```text
MONGO_URI=mongodb://localhost:27017/ai_resume_db
SECRET_KEY=change-this-for-local-development
FLASK_DEBUG=0
```

Use appropriate local values for your environment.

### 5. Start MongoDB

Make sure MongoDB is running and accessible using the configured `MONGO_URI`.

## ▶️ Running the Application

Run the Flask application:

```bash
python app.py
```

The application runs on port `5000` by default.

Open:

```text
http://localhost:5000
```

## 📊 Example Workflow

```text
Job Description + Resume
          ↓
    Text Extraction
          ↓
      Text Cleaning
          ↓
     PII Removal
          ↓
     Skill Extraction
          ↓
 ┌─────────────────────┐
 │ TF-IDF Similarity   │
 │ Semantic Similarity│
 └─────────────────────┘
          ↓
   Final Match Score
          ↓
 Screening Criteria
          ↓
 Shortlist / Rejection
          ↓
 Results & Skill Gaps
```
## 📌 Project Summary

TalentIQ demonstrates a practical approach to automated resume screening using **Flask, MongoDB, Python, TF-IDF, SentenceTransformer semantic similarity, and skill extraction**.

The project combines text extraction, skill identification, semantic comparison, and configurable screening criteria into a single web application for candidate and HR workflows.
