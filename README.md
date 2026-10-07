# TalentIQ

A Flask-based resume screening and candidate evaluation project for matching applicant resumes against job descriptions using keyword similarity and semantic similarity.

## 📌 Project Overview

This project is a web application built for two main user types:

- HR users can upload job descriptions, select active openings, upload multiple candidate resumes, and review screening results.
- Candidate users can select a job, upload or build a resume, and check how closely their profile matches the selected role.

The application reads resumes from PDF, DOCX, or TXT files, cleans the text, extracts relevant skills and experience details, compares them against a job description, and shows a match score and a shortlist/rejection result.

The project is intended as a student mini-project and is based on a local Flask application with MongoDB storage.

## 🎯 Problem Statement

Hiring teams often need to review a large number of resumes manually. This process is time-consuming and can make it difficult to compare a candidate's skills against a job requirement consistently.

At the same time, candidates may not know whether their resume is aligned with the role they are applying for, or which skills they are missing. The project addresses this by giving both sides a simple screening workflow: HR can assess large sets of resumes quickly, and candidates can see a match result and skill-gap hints.

## 💡 Proposed Solution

The application stores job descriptions and screening data in MongoDB and uses Flask routes to manage both HR and candidate workflows.

For each resume, the system:

- reads text from an uploaded file,
- removes common personal identifiers before scoring,
- extracts skills and experience-related text,
- compares the resume with the selected job description,
- calculates a match score,
- displays matched skills and missing skill categories,
- decides whether the resume should be shortlisted or rejected based on the configured rules.

This is a practical project workflow for automated resume screening rather than a full production recruitment system.

## ✨ Features

### Candidate-side features

- Resume upload in PDF, DOCX, or TXT format
- Resume creation through a built-in form
- Resume preview before scoring
- Match score result for the selected job
- Display of matched skills and missing skill categories
- Skill-gap guidance based on the missing areas from the job description
- Download of a generated PDF resume for built resumes
- Login/signup with candidate or HR role selection

### HR-side features

- Upload and manage job descriptions
- Set minimum score, minimum experience, and mandatory skills for each job
- Activate or deactivate job listings
- Upload multiple candidate resumes for screening
- View shortlisted and rejected candidates
- See scoring breakdown and rejection reasons
- Export shortlisted results as CSV
- Review recent screening history

## 🧠 How the System Works

### Candidate workflow

1. The candidate signs up or logs in.
2. The candidate selects an active job opening from the dashboard.
3. The candidate either:
   - uploads an existing resume file, or
   - fills the resume builder form with summary, skills, experience, projects, education, and certifications.
4. The application stores the resume content in session data and in MongoDB.
5. The candidate clicks the check-match option.
6. The project extracts text from the uploaded file or composes text from the resume form fields.
7. The resume text is cleaned and compared with the selected job description.
8. The result page shows:
   - final match score,
   - semantic score,
   - keyword score,
   - matched skills,
   - category-based skill gaps,
   - a notice indicating that personal identifiers were stripped before scoring.

### HR workflow

1. HR signs up or logs in with the HR role.
2. HR uploads a job description file (PDF or DOCX) and provides a job title, minimum score, minimum experience, and optional mandatory skills.
3. The job description is stored in MongoDB and appears in the HR dashboard.
4. HR selects an active job and uploads candidate resumes.
5. For each resume file, the backend:
   - reads the text,
   - cleans the text,
   - removes known personal identifiers,
   - extracts skills and experience,
   - compares resume and job description,
   - applies the minimum score and other filters.
6. The results page shows shortlisted candidates and rejected candidates.
7. HR can export the shortlist as CSV and review prior screening history.

## 🔬 Matching / Resume Processing

### 1. File loading and text extraction

The application accepts `.pdf`, `.docx`, and `.txt` files. In `app.py`, `load_file()` checks the extension and file size before reading the file.

Implementation details:

- `.txt`: read as UTF-8 text
- `.docx`: uses `docx.Document(file)` and reads paragraph text
- `.pdf`: uses `pdfplumber.open(file)` and extracts text from each page

The extracted text is normalized with `clean_text()`, which converts to lowercase and removes non-alphanumeric characters, leaving a simpler text representation.

### 2. Skill extraction

The app loads skill words from Excel files at startup:

- `skills_onet.xlsx`
- `Technology Skills.xlsx`

This is done in `load_skills()`:

- reads both Excel files with `pandas.read_excel()`
- filters the O*NET Excel file where `Scale Name == "Importance"` and `Data Value >= 3`
- combines the resulting skill names with example technology skills
- stores them in a set called `SKILL_DB`

Then `skills_in_text(text)` checks which skills appear in a resume or job description using regex word-boundary matching.

### 3. Experience extraction

The function `extract_experience_years(text)` searches the text for patterns like:

- `3 years`
- `5 yrs`
- `2+ years`
- `since 2019`

It converts the match into an integer and caps the result at 40 years to avoid unrealistic values.

### 4. TF-IDF matching

The project uses scikit-learn's `TfidfVectorizer` and `cosine_similarity`.

In `score_resume(resume, jd)`: 

- both the cleaned resume and cleaned job description are transformed with TF-IDF,
- cosine similarity is computed between them,
- the result is converted to a percentage and stored as `tfidf`.

This part captures keyword overlap and term importance.

### 5. Semantic matching

The project also uses a sentence-transformers model:

- `SentenceTransformer("all-MiniLM-L6-v2")`
- defined in `semantic_matcher.py`

The function `sbert_similarity(text1, text2)`:

- encodes both strings into embeddings,
- computes cosine similarity using `util.cos_sim`,
- returns a score in the range 0–100.

This allows a broader semantic comparison beyond exact words.

### 6. Final matching formula

The final score in `score_resume()` is calculated as:

```python
final = round(0.6 * semantic + 0.4 * tfidf, 2)
```

This exact formula is present in the source code. The implementation uses the semantic score with a higher weight than the TF-IDF score.

### 7. PII stripping and privacy-related screening

The application includes `PII_PATTERNS` and a `strip_pii()` function in `app.py`.

It removes patterns such as:

- email addresses
- phone numbers
- gendered titles like Mr./Ms./Dr.
- date patterns and dob-looking entries
- selected demographic fields like nationality, religion, marital status, caste, and gender

The stripped text is then used when scoring. The code also tracks a `redacted_count` and passes it to the results pages, so the UI shows how many personal identifiers were removed before evaluation.

This is a real feature in the project and should be described as a bias-mitigation step rather than as a production security feature.

### 8. Skill-gap analysis

The project does not simply print missing keywords. Instead, it maps missing skills to categories using `get_skill_category_gaps(missing_skills)`.

Examples of categories in the code include:

- Cloud & DevOps
- Data & Analytics
- Machine Learning & AI
- Web Development
- Programming Languages
- Databases
- Soft Skills & PM
- Security
- Mobile Development

The function groups missing skill terms into these categories and adds trend text from `TREND_CONTEXT` such as cloud, AI/ML, and data-related insights.

### 9. Mandatory filters and rejection logic

In `hr_analyze()`, each candidate's result is evaluated against the job settings:

- minimum score threshold
- minimum experience threshold
- mandatory skills list

If a candidate fails any of these conditions, a rejection reason is added.

### 10. Duplicate resume detection

The project includes `is_duplicate_resume(resume_text, job_id, username)`. It compares a new resume against earlier resumes already uploaded for the same job and user using TF-IDF cosine similarity. If the similarity is greater than or equal to `0.95`, the project treats it as a duplicate and blocks the submission.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core backend language for processing, scoring, and application logic |
| Flask | Web framework for routing, templates, and request handling |
| Flask-PyMongo | MongoDB integration with Flask |
| MongoDB | Database for users, job descriptions, resumes, and screening records |
| pandas | Reads Excel data files for skill matching |
| scikit-learn | Uses TF-IDF vectorizer and cosine similarity for keyword-based matching |
| sentence-transformers | Loads the `all-MiniLM-L6-v2` model for semantic similarity |
| pdfplumber | Extracts text from PDF resume files |
| python-docx | Reads text from DOCX resume files |
| FPDF | Generates PDF output for built resumes |
| python-dotenv | Loads environment variables from a `.env` file |
| Werkzeug | Password hashing and verification |
| HTML/CSS | User interface pages for candidate and HR dashboards |
| Jinja2 | Template rendering in Flask pages |
| Excel files (`.xlsx`) | Dataset sources for skills and technology keywords |

## 📂 Project Structure

```text
Mini-Project-1B/
├── .env.example
├── .gitignore
├── README.md
├── Technology Skills.xlsx
├── app.py
├── candidate_create.html
├── candidate_dashboard.html
├── candidate_preview.html
├── candidate_result.html
├── candidate_upload.html
├── hr_dashboard.html
├── hr_results.html
├── index.html
├── login.html
├── no_jd.html
├── requirements.txt
├── resumer_parser.py
├── semantic_matcher.py
├── signup.html
├── skills_onet.xlsx
└── .pyc files (generated at runtime and not shown here)
```

### Important files

- `app.py`: Main Flask application. Contains routes for login, signup, HR, candidate dashboards, resume processing, scoring logic, skill extraction, filtering, and result generation.
- `semantic_matcher.py`: Defines the SBERT similarity function and loads the sentence-transformers model.
- `resumer_parser.py`: Utility for extracting text from PDF/DOCX files using `pdfplumber` and `python-docx`.
- `candidate_*.html`: Pages for candidate login flow, resume upload, preview, and reporting.
- `hr_*.html`: Pages for HR job management, candidate screening, and result display.
- `index.html`: Homepage and landing page.
- `login.html` and `signup.html`: Authentication pages.
- `skills_onet.xlsx` and `Technology Skills.xlsx`: Skill datasets used to build the skill database.
- `.env.example`: Environment variable template.
- `requirements.txt`: Minimal Python dependency file included in the repository; it does not cover all packages used by the app.

## ⚙️ Installation and Setup

### Prerequisites

- Python installed on the system
- MongoDB running locally or available via a MongoDB URI
- pip package manager
- Git for cloning the repository

### Python version

The repository does not explicitly declare a required Python version in a config file. The code is written in Python and imports modern packages, so Python 3.9+ is a reasonable environment for running it.

### Required packages

The repository does not provide a complete dependency list covering every imported package. Based on the source code, the app imports and uses:

```bash
pip install flask flask-pymongo python-dotenv scikit-learn sentence-transformers pdfplumber python-docx fpdf pandas werkzeug
```

The project also includes a `requirements.txt` file, but it currently only contains:

```txt
python-dotenv
```

This means the full dependency setup is not fully captured in the repository file.

### Environment variables

The project uses the variables shown in `.env.example`:

```env
MONGO_URI=mongodb://localhost:27017/ai_resume_db
SECRET_KEY=change-this-for-local-development
FLASK_DEBUG=0
```

Create a local `.env` file in the project root if you want to override these values.

### Database setup

The app uses MongoDB and connects with:

```python
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/ai_resume_db")
```

So a local MongoDB instance at `mongodb://localhost:27017` is the default expectation.

### Local setup steps

```bash
git clone https://github.com/sweetyparmar6116-ux/Mini-Project-1B.git
cd Mini-Project-1B
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install flask flask-pymongo python-dotenv scikit-learn sentence-transformers pdfplumber python-docx fpdf pandas werkzeug
cp .env.example .env
```

Then edit `.env` if needed before running the application.

## ▶️ Running the Application

The application entry point is:

```bash
python app.py
```

This is the main Flask file. In `app.py`, the application runs with:

```python
if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        port=5000
    )
```

So the app starts on port `5000` by default.

Open the app in the browser at:

```text
http://localhost:5000
```

## 📊 Example Workflow

Example:

```text
Input:
  HR uploads a job description and candidate uploads a PDF resume.

Processing:
  - file text is extracted
  - text is cleaned
  - PII is stripped
  - skills are compared against the job description
  - experience is extracted
  - keyword and semantic similarity are calculated

Matching:
  - TF-IDF score is computed from resume vs. JD
  - SBERT semantic score is computed
  - final score = 0.6 * semantic + 0.4 * tfidf

Result:
  - candidate is shortlisted or rejected
  - matched skills and skill-gap categories are shown
  - HR receives a ranked list or a rejected list
```

This is an actual representation of the repository workflow.

## 📸 Screenshots

No screenshots are included in the repository. The following files can be used as placeholders for future screenshots:

```text
screenshots/
├── home.png
├── login.png
├── signup.png
├── candidate-dashboard.png
├── candidate-upload.png
├── candidate-preview.png
├── candidate-results.png
├── hr-dashboard.png
├── hr-results.png
└── results-export.png
```

These names correspond to actual screens present in the project.

## 🧪 Testing

The repository does not include an automated testing suite such as `pytest` or a `tests/` folder.

At the moment, the project appears to rely on manual use of the Flask app and browser-based verification for functionality. There is no repository evidence of a formal automated test run.

## ⚠️ Limitations

This project has several practical limitations based on the code:

- It depends on the quality of PDF and DOCX text extraction.
- The skill database is based on Excel files and is not a large enterprise-grade hiring dataset.
- The matching logic uses a fixed approach and does not provide deep explainability for each score element beyond matched and missing skill groups.
- The application is a local Flask project with MongoDB as the data store, not a cloud-hosted or production-ready system.
- The user interface is designed for demonstration and educational use rather than large-scale recruitment operations.
- Some matching features depend on the quality of the resume text and the dataset used to detect skills.

## 🚀 Future Enhancements

The following features are realistic future improvements and are not currently implemented as part of the repository:

- Improved resume parsing for more complex document layouts
- Larger and more detailed skill datasets
- Better ranking explanations for each candidate score
- Role-based permissions with stronger authentication controls
- Cloud deployment for MongoDB and the application
- More advanced candidate analytics and dashboard reporting
- Better authentication flows and account recovery
- Formal automated test suite with model validation
- Improved candidate recommendation and job matching across multiple roles

## 👥 Project Team

```text
- [Name 1]
- [Name 2]
- [Name 3]
```

## 📄 License

No license has currently been specified for this project.

## Final Notes

This project is a working mini-project that demonstrates:

- job description upload,
- candidate resume upload and creation,
- text extraction,
- resume-to-job matching,
- skill extraction,
- shortlisting and rejection logic,
- MongoDB-backed storage,
- HR dashboard workflows.

It is a practical academic project and should be described as such rather than as a production-ready or enterprise product.
