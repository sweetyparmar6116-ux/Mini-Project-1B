# TalentIQ

TalentIQ is a web-based resume screening and candidate evaluation system developed as a college mini-project to compare candidate resumes with job descriptions using keyword similarity and semantic similarity.

## 📌 Project Overview

This project is built for two main user groups:

- HR users can upload job descriptions, review active openings, upload multiple candidate resumes, and assess screening results.
- Candidate users can select a job, upload an existing resume or build one using the in-app form, and view how closely their profile matches the selected role.

The application reads resumes from PDF, DOCX, and TXT files, cleans the extracted text, extracts relevant skill and experience information, compares the resume with a job description, and shows a match score along with shortlist or rejection decisions.

The project is implemented as a local Flask application that stores its data in MongoDB.

## 🎯 Problem Statement

Manual resume screening is time-consuming and difficult to manage when a large number of applications need to be reviewed. HR teams often need to compare candidate profiles against job requirements without a consistent evaluation method.

At the same time, candidates may not understand whether their resume matches the role they are applying for, or which skills they may need to strengthen. The project addresses this by giving both sides a simple workflow: HR can screen multiple resumes quickly, and candidates can check how closely their profile aligns with a selected job description.

## 💡 Proposed Solution

The application stores job descriptions and screening records in MongoDB and uses Flask routes to manage both HR and candidate workflows.

For each resume, the system:

- reads text from an uploaded file,
- cleans the text,
- removes common personal identifiers before scoring,
- extracts skills and experience-related information,
- compares the resume with the selected job description,
- calculates a match score,
- displays matched skills and skill-gap categories,
- decides whether the candidate should be shortlisted or rejected based on the configured rules.

This is a practical academic project for automated resume screening rather than a production recruitment system.

## ✨ Features

### Candidate-side features

- Resume upload in PDF, DOCX, or TXT format
- Resume creation using an in-app form
- Resume preview before scoring
- Match score for the selected job
- Display of matched skills and missing skill categories
- Skill-gap guidance based on missing areas from the job description
- Download of a generated PDF resume for built resumes
- Signup and login for candidate and HR roles

### HR-side features

- Upload and manage job descriptions
- Set minimum score, minimum experience, and mandatory skills for each job
- Activate or deactivate job listings
- Upload multiple candidate resumes for screening
- View shortlisted and rejected candidates
- Review scoring breakdown and rejection reasons
- Export shortlisted results as CSV
- Review recent screening history

## 🧠 How the System Works

### Candidate workflow

1. The candidate signs up or logs in.
2. The candidate selects an active job opening from the dashboard.
3. The candidate either uploads an existing resume or fills the resume builder form with summary, skills, experience, projects, education, and certifications.
4. The application stores the resume content in session data and in MongoDB.
5. The candidate clicks the option to check the match score.
6. The project extracts text from the uploaded file or composes text from the resume form fields.
7. The resume text is cleaned and compared with the selected job description.
8. The result page displays:
   - final match score,
   - semantic score,
   - keyword score,
   - matched skills,
   - category-based skill gaps,
   - a notice indicating that personal identifiers were removed before scoring.

### HR workflow

1. HR signs up or logs in with the HR role.
2. HR uploads a job description file (PDF or DOCX) and provides a job title, minimum score, minimum experience, and optional mandatory skills.
3. The job description is stored in MongoDB and appears in the HR dashboard.
4. HR selects an active job and uploads candidate resumes.
5. For each resume file, the backend:
   - reads the text,
   - cleans the text,
   - removes personal identifiers,
   - extracts skills and experience,
   - compares the resume and job description,
   - applies the minimum score and other filters.
6. The results page shows shortlisted and rejected candidates.
7. HR can export the shortlist as a CSV and review prior screening history.

## 🔬 Matching / Resume Processing

### 1. File loading and text extraction

The application accepts `.pdf`, `.docx`, and `.txt` files. In `app.py`, the `load_file()` function checks the extension and file size before reading the file.

Implementation details:

- `.txt`: read as UTF-8 text
- `.docx`: uses `docx.Document(file)` and reads paragraph text
- `.pdf`: uses `pdfplumber.open(file)` and extracts text from each page

The extracted text is normalized with `clean_text()`, which converts it to lowercase and removes non-alphanumeric characters to simplify the content before comparison.

### 2. Skill extraction

The project loads skill words from Excel files at startup:

- `skills_onet.xlsx`
- `Technology Skills.xlsx`

This is done in `load_skills()`:

- reads both Excel files using `pandas.read_excel()`
- filters the O*NET data where `Scale Name == "Importance"` and `Data Value >= 3`
- combines the resulting skill names with example technology skills
- stores them in a set called `SKILL_DB`

The function `skills_in_text(text)` checks which skills appear in a resume or job description using regex word-boundary matching.

### 3. Experience extraction

The function `extract_experience_years(text)` searches for patterns such as:

- `3 years`
- `5 yrs`
- `2+ years`
- `since 2019`

It converts the extracted value into an integer and caps the result at 40 years to avoid unrealistic values.

### 4. TF-IDF matching

The project uses scikit-learn's `TfidfVectorizer` and `cosine_similarity`.

In `score_resume(resume, jd)`, both the cleaned resume and the cleaned job description are transformed with TF-IDF, and cosine similarity is computed between them. The result is converted to a percentage and stored as `tfidf`.

This part captures keyword overlap and term importance in the resume and job description.

### 5. Semantic matching

The project also uses a sentence-transformers model:

- `SentenceTransformer("all-MiniLM-L6-v2")`
- defined in `semantic_matcher.py`

The function `sbert_similarity(text1, text2)`:

- encodes both strings into embeddings,
- computes cosine similarity using `util.cos_sim`,
- returns a score in the range 0–100.

This allows the project to compare the semantic meaning of the resume and the job description beyond exact word matches.

### 6. Final matching formula

The final score in `score_resume()` is calculated as:

```python
final = round(0.6 * semantic + 0.4 * tfidf, 2)
```

This exact formula appears in the source code. The semantic score is weighted more heavily than the TF-IDF score.

### 7. PII stripping and privacy-related screening

The project includes `PII_PATTERNS` and a `strip_pii()` function in `app.py`.

It removes patterns such as:

- email addresses
- phone numbers
- gendered titles such as Mr., Ms., and Dr.
- date patterns and DOB-like entries
- selected demographic fields including nationality, religion, marital status, caste, and gender

The cleaned text is then used for scoring. The code also tracks a `redacted_count` and passes it to the result pages, so the interface can show how many personal identifiers were removed before evaluation.

This is a real feature in the project and should be described as a bias-mitigation step rather than a production security feature.

### 8. Skill-gap analysis

The project does not simply print a raw list of missing keywords. Instead, it maps missing skills to category groups using `get_skill_category_gaps(missing_skills)`.

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

In `hr_analyze()`, each candidate result is evaluated against the job settings:

- minimum score threshold
- minimum experience threshold
- mandatory skills list

If a candidate fails any of these conditions, a rejection reason is added.

### 10. Duplicate resume detection

The project includes `is_duplicate_resume(resume_text, job_id, username)`. It compares a new resume against earlier resumes submitted for the same job and user using TF-IDF cosine similarity. If the similarity is greater than or equal to `0.95`, the application treats it as a duplicate and blocks the submission.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core backend language for application logic and resume processing |
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
| Jinja2 | Template rendering for Flask pages |
| Excel files (`.xlsx`) | Data sources for skill lookup and technology keyword matching |

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
└── .pyc files generated at runtime
```

### Important files

- `app.py`: Main Flask application. It includes routes for login, signup, HR workflows, candidate workflows, resume processing, scoring, filtering, and result generation.
- `semantic_matcher.py`: Defines the SBERT similarity function and loads the sentence-transformers model.
- `resumer_parser.py`: Utility for extracting text from PDF and DOCX files using `pdfplumber` and `python-docx`.
- `candidate_*.html`: Candidate pages for dashboard, upload, preview, and result display.
- `hr_*.html`: HR pages for job management, screening, and result display.
- `index.html`: Landing page for the application.
- `login.html` and `signup.html`: Authentication pages.
- `skills_onet.xlsx` and `Technology Skills.xlsx`: Skill datasets used to build the skill database.
- `.env.example`: Environment variable template.
- `requirements.txt`: Minimal dependency file included in the repository; it does not contain the full dependency list used by the project.

## ⚙️ Installation and Setup

### Prerequisites

- Python installed on the system
- MongoDB running locally or available through a valid connection URI
- pip package manager
- Git for cloning the repository

### Python version

The repository does not explicitly declare a required Python version. The code uses modern Python libraries and is generally compatible with Python 3.9+.

### Required packages

The repository does not provide a complete dependency list covering every imported package. Based on the source code, the application uses:

```bash
pip install flask flask-pymongo python-dotenv scikit-learn sentence-transformers pdfplumber python-docx fpdf pandas werkzeug
```

The project also includes a `requirements.txt` file, but it currently contains only:

```txt
python-dotenv
```

This means the full dependency setup is not completely captured in the repository file.

### Environment variables

The project uses the variables shown in `.env.example`:

```env
MONGO_URI=mongodb://localhost:27017/ai_resume_db
SECRET_KEY=change-this-for-local-development
FLASK_DEBUG=0
```

Create a local `.env` file in the project root if you want to override the default values.

### Database setup

The application uses MongoDB and connects with:

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

The entry point is the main Flask file:

```bash
python app.py
```

In `app.py`, the application starts with:

```python
if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        port=5000
    )
```

This means the application runs on port `5000` by default.

Open the application in a browser at:

```text
http://localhost:5000
```

## 📊 Example Workflow

```text
Input:
  HR uploads a job description and a candidate uploads a PDF resume.

Processing:
  - file text is extracted
  - text is cleaned
  - personal identifiers are removed
  - skills are compared against the job description
  - experience is extracted
  - TF-IDF and semantic similarity are computed

Matching:
  - TF-IDF score is computed for resume vs. JD
  - SBERT score is computed for semantic similarity
  - final score = 0.6 * semantic + 0.4 * tfidf

Result:
  - candidate is shortlisted or rejected
  - matched skills and skill-gap categories are shown
  - HR receives a ranked list or rejection list
```

This is an accurate representation of the project workflow implemented in the repository.

## 📸 Screenshots

No screenshots are included in the repository. The following names can be used as placeholders for future screenshots:

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

The repository does not include an automated testing suite such as `pytest` or a `tests/` directory.

At present, the project appears to rely on manual browser-based verification and local use of the Flask application. There is no repository evidence of a formal automated test run.

## ⚠️ Limitations

This project has several practical limitations based on the actual implementation:

- It depends on the quality of PDF and DOCX text extraction.
- The skill database is based on Excel files and is not a large enterprise-level dataset.
- The matching logic does not provide detailed explainability for each score component beyond matched and missing skill information.
- The application is a local Flask project with MongoDB, rather than a cloud-hosted or production-ready system.
- The user interface is intended for academic demonstration and local use rather than large-scale recruitment operations.
- Some matching results depend heavily on the quality of the resume text and the skill data used to detect keywords.

## 🚀 Future Enhancements

The following are realistic future improvements and are not currently implemented in the repository:

- Improved resume parsing for more complex document layouts
- Larger and more detailed skill datasets
- Better explanation of candidate scores and ranking logic
- Stronger role-based permissions and authentication controls
- Cloud deployment for MongoDB and the application
- More advanced candidate analytics and dashboard reporting
- Formal automated test suite for validation
- Improved recommendation logic for job matching across multiple roles

## 👥 Project Team

```text
- [Name 1]
- [Name 2]
- [Name 3]
```

## 📄 License

No license has currently been specified for this project.

## Final Notes

This project demonstrates a practical workflow for resume screening using Flask, MongoDB, and Python-based text processing. It is suitable for academic study and viva explanation because it shows how text extraction, skill matching, semantic comparison, and shortlist/rejection logic are implemented in a small web application.

It is a student mini-project and should be presented as such rather than as a production-ready or enterprise-level system.
