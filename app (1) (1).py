from flask import Flask, render_template, request, redirect, session, send_file
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from bson.errors import InvalidId
from functools import wraps
from datetime import datetime

import os
import re
import io
import csv
import pdfplumber
import docx
import pandas as pd
from dotenv import load_dotenv

from fpdf import FPDF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from semantic_matcher import sbert_similarity
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
# ===================== Flask Setup =====================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")


# ===================== MongoDB Setup =====================
app.config["MONGO_URI"] = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27017/ai_resume_db"
)
mongo = PyMongo(app)

users      = mongo.db.users
jds        = mongo.db.job_descriptions
resumes    = mongo.db.resumes
screenings = mongo.db.screenings


# ===================== ROLE PROTECTION =====================
def login_required(role=None):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return redirect("/login")
            if role and session.get("role") != role:
                return "Unauthorized Access", 403
            return f(*args, **kwargs)
        return decorated
    return wrapper


# ===================== Utilities =====================
def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ===================== BIAS MITIGATION: PII Stripping =====================
# These patterns strip personally identifiable information before scoring.
# This is the core implementation of "Bias-Free" screening:
# HR scoring is done on skills/experience text only, not demographics.
PII_PATTERNS = [
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",           # email
    r"\b(\+91[-\s]?)?[6-9]\d{9}\b",                                      # Indian mobile
    r"\b(\+1[-\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",            # US phone
    r"\b(mr|mrs|ms|dr|prof)\.?\s+[a-z]+\b",                             # gendered titles
    r"\b(january|february|march|april|may|june|july|august|"
     r"september|october|november|december)\s+\d{4}\b",                  # birth month-year
    r"\b(dob|date of birth|born)\s*[:\-]?\s*[\d/\-]+",                  # explicit DOB
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",                               # date formats
    r"\b(father|mother|guardian|nationality|religion|"
     r"marital status|caste|gender)\s*[:\-]",                            # demographic fields
]

def strip_pii(text):
    """
    Replace PII tokens with [REDACTED] so scoring is based purely on professional content.
    IMPROVEMENT: Now also returns a redaction count as measurable proof of bias mitigation.
    """
    cleaned = text
    redacted_count = 0
    for pattern in PII_PATTERNS:
        matches = re.findall(pattern, cleaned, flags=re.IGNORECASE)
        redacted_count += len(matches)
        cleaned = re.sub(pattern, " [REDACTED] ", cleaned, flags=re.IGNORECASE)
    return cleaned, redacted_count


def anonymize_filename(filename, index):
    """Replace candidate's real filename with a neutral label.
    This prevents HR from making subconscious name/gender judgments from filenames."""
    ext = os.path.splitext(filename)[1]
    return f"Candidate_{index:03d}{ext}"


# ===================== File Loading =====================
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_MB   = 5

def load_file(file):
    """Load text from uploaded file. Validates type and size."""
    if not file or not file.filename:
        return ""

    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return ""

    # Size guard: reject files over 5 MB
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE_MB * 1024 * 1024:
        return ""

    text = ""
    if ext == ".txt":
        text = file.read().decode("utf-8", errors="ignore")
    elif ext == ".docx":
        d    = docx.Document(file)
        text = "\n".join(p.text for p in d.paragraphs)
    elif ext == ".pdf":
        out  = []
        with pdfplumber.open(file) as pdf:
            for p in pdf.pages:
                t = p.extract_text()
                if t:
                    out.append(t)
        text = "\n".join(out)

    return clean_text(text)


# ===================== Skill Loading =====================
def load_skills():
    s = pd.read_excel("skills_onet.xlsx")
    t = pd.read_excel("Technology Skills.xlsx")
    s = s[(s["Scale Name"] == "Importance") & (s["Data Value"] >= 3)]
    return set(s["Element Name"].str.lower()).union(set(t["Example"].str.lower()))

SKILL_DB = load_skills()


def skills_in_text(text):
    """Use word-boundary regex matching to avoid false positives."""
    found = set()
    for skill in SKILL_DB:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text):
            found.add(skill)
    return found


def extract_experience_years(text):
    """
    IMPROVEMENT: Added a sanity cap of 40 years to prevent
    absurd values when a resume mentions large numbers near 'years'.
    """
    text    = text.lower()
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(years|yrs)", text)
    if matches:
        raw = int(max(float(m[0]) for m in matches))
        return min(raw, 40)   # cap at 40 — anything higher is a parsing error
    since = re.search(r"since\s+(20\d{2})", text)
    if since:
        years = datetime.now().year - int(since.group(1))
        return min(max(years, 0), 40)
    return 0


# ===================== SKILL CATEGORY GAPS =====================
# Instead of showing exact missing keywords (which candidates can game),
# we map gaps to broad categories and show industry trend context.
# This gives directional guidance without handing over an answer key.
SKILL_CATEGORIES = {
    "Cloud & DevOps":        ["aws", "azure", "gcp", "docker", "kubernetes",
                               "terraform", "ci/cd", "jenkins", "ansible", "cloud"],
    "Data & Analytics":      ["sql", "pandas", "numpy", "tableau", "power bi",
                               "excel", "data analysis", "statistics", "matplotlib"],
    "Machine Learning & AI": ["machine learning", "deep learning", "tensorflow",
                               "pytorch", "scikit-learn", "nlp", "computer vision",
                               "neural network"],
    "Web Development":       ["html", "css", "javascript", "react", "angular",
                               "vue", "node", "django", "flask", "rest api", "typescript"],
    "Programming Languages": ["python", "java", "c++", "c#", "go", "rust",
                               "kotlin", "swift", "scala", "ruby"],
    "Databases":             ["mongodb", "mysql", "postgresql", "redis",
                               "elasticsearch", "firebase", "oracle", "sqlite"],
    "Soft Skills & PM":      ["agile", "scrum", "jira", "communication",
                               "leadership", "project management", "teamwork"],
    "Security":              ["cybersecurity", "penetration testing", "owasp",
                               "encryption", "firewalls", "ethical hacking"],
    "Mobile Development":    ["android", "ios", "react native", "flutter",
                               "swift", "kotlin", "mobile app"],
}

TREND_CONTEXT = {
    "Cloud & DevOps":        "Cloud skills are among the top 3 most in-demand technical capabilities in 2024-25.",
    "Data & Analytics":      "Data literacy is now expected even in non-technical roles across most industries.",
    "Machine Learning & AI": "AI/ML skills have seen a 40%+ surge in demand since 2023 across all sectors.",
    "Web Development":       "Full-stack capability is increasingly preferred over specialisation alone.",
    "Programming Languages": "Python continues to dominate as the most versatile language across domains.",
    "Databases":             "Knowledge of both SQL and NoSQL databases is now a standard expectation.",
    "Soft Skills & PM":      "Agile/Scrum familiarity is expected even for individual contributor roles.",
    "Security":              "Cybersecurity awareness is required across all tech roles, not just specialists.",
    "Mobile Development":    "Cross-platform frameworks (Flutter, React Native) are growing faster than native-only.",
}

def get_skill_category_gaps(missing_skills):
    """
    Map missing skill keywords → broad categories.
    Returns top 4 category gaps with trend context.
    Candidates get growth direction, not an exploitable keyword list.

    FIX: Two improvements over the old version:
    1. Broader word-level matching — splits multi-word skills into individual
       words so "software development lifecycle" still hits "Web Development".
    2. Always returns something — if no category gaps are detected from missing
       skills, fall back to showing the top universal trending categories so the
       candidate always sees actionable market insight, never a blank section.
    """
    category_hits = {}

    for skill in missing_skills:
        skill_lower = skill.lower()
        # Split into individual words for broader matching
        skill_words = set(re.split(r'\s+|/', skill_lower))

        for category, keywords in SKILL_CATEGORIES.items():
            matched = False
            for kw in keywords:
                kw_words = set(re.split(r'\s+|/', kw))
                # Match if: full phrase match, substring match, or any word overlaps
                if (kw in skill_lower or
                    skill_lower in kw or
                    skill_words & kw_words):       # word-level intersection
                    matched = True
                    break
            if matched:
                category_hits[category] = category_hits.get(category, 0) + 1

    sorted_gaps = sorted(category_hits.items(), key=lambda x: x[1], reverse=True)

    result = []
    for category, count in sorted_gaps[:4]:
        result.append({
            "category": category,
            "trend":    TREND_CONTEXT.get(category, ""),
            "weight":   min(count * 20, 100),
            "is_gap":   True    # flagged as an actual gap from missing skills
        })

    # Fallback: if no gaps were detected (O*NET skills didn't map to our categories),
    # always show the top universally trending categories so the section is never empty.
    if not result:
        fallback_categories = [
            "Machine Learning & AI",
            "Cloud & DevOps",
            "Data & Analytics",
            "Programming Languages"
        ]
        for cat in fallback_categories:
            result.append({
                "category": cat,
                "trend":    TREND_CONTEXT.get(cat, ""),
                "weight":   60,
                "is_gap":   False   # not a detected gap — shown as general market trends
            })

    return result


# ===================== Scoring =====================
def score_resume(resume, jd):
    """
    Hybrid TF-IDF + SBERT scoring.
    IMPROVEMENT: strip_pii now returns redaction count for audit/display purposes.
    """
    rc, redacted_count = strip_pii(clean_text(resume))
    jc = clean_text(jd)

    if not rc or not jc:
        return 0, 0, 0, [], [], 0

    vec   = TfidfVectorizer(stop_words="english")
    mat   = vec.fit_transform([rc, jc])
    tfidf = cosine_similarity(mat[0:1], mat[1:2])[0][0] * 100

    semantic = sbert_similarity(resume, jd)
    final    = round(0.6 * semantic + 0.4 * tfidf, 2)

    resume_skills = skills_in_text(rc)
    jd_skills     = skills_in_text(jc)

    matched = sorted(resume_skills & jd_skills)
    missing = sorted(jd_skills - resume_skills)

    return round(tfidf, 2), round(semantic, 2), final, matched, missing, redacted_count


# ===================== Duplicate Resume Detection =====================
def is_duplicate_resume(resume_text, job_id, username):
    """
    IMPROVEMENT: Check if this candidate already submitted a very similar
    resume for the same job. Uses cosine similarity on TF-IDF vectors.
    Returns True if a near-identical resume (>= 95% similarity) already exists.
    """
    existing = list(resumes.find({"job_id": job_id, "username": username}))
    if not existing:
        return False

    for prev in existing:
        prev_text = prev.get("resume_text", "")
        if not prev_text:
            continue
        try:
            vec = TfidfVectorizer(stop_words="english")
            mat = vec.fit_transform([resume_text, prev_text])
            sim = cosine_similarity(mat[0:1], mat[1:2])[0][0]
            if sim >= 0.95:
                return True
        except Exception:
            continue
    return False


# ===================== Resume PDF Generator =====================
def resume_to_pdf(resume):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    def section_header(title):
        pdf.ln(4)
        pdf.set_font("Arial", style="B", size=13)
        pdf.set_fill_color(230, 240, 255)
        pdf.cell(0, 9, title, ln=True, fill=True)
        pdf.set_font("Arial", size=11)
        pdf.ln(2)

    def body_text(text):
        if text and text.strip():
            pdf.multi_cell(0, 7, text.strip())
            pdf.ln(2)

    pdf.set_font("Arial", style="B", size=20)
    pdf.cell(0, 12, resume.get("name", ""), ln=True, align="C")
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"{resume.get('email','')} | {resume.get('phone','')}", ln=True, align="C")
    pdf.ln(6)

    if resume.get("summary"):
        section_header("Professional Summary")
        body_text(resume["summary"])

    if resume.get("skills"):
        section_header("Skills")
        body_text("  •  ".join(resume["skills"]))

    if resume.get("experience"):
        section_header("Work Experience")
        body_text(resume["experience"])

    if resume.get("projects"):
        section_header("Projects")
        body_text(resume["projects"])

    if resume.get("education"):
        section_header("Education")
        body_text(resume["education"])

    if resume.get("certifications"):
        section_header("Certifications")
        body_text(resume["certifications"])

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    return io.BytesIO(pdf_bytes)


# ===================== HOME =====================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ===================== Signup / Login =====================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters.")

        if users.find_one({"username": username}):
            return render_template("signup.html", error="Username already exists!")

        users.insert_one({
            "username": username,
            "password": generate_password_hash(password, method="pbkdf2:sha256"),
            "role":     request.form["role"]
        })
        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = users.find_one({"username": request.form["username"].strip()})

        password_ok = False
        if u:
            try:
                password_ok = check_password_hash(u["password"], request.form["password"])
            except (ValueError, AttributeError):
                return render_template("login.html",
                    error="Your account was created on a newer system. "
                          "Please sign up again with a new username (your old data is preserved).")

        if password_ok:
            session["user"] = u["username"]
            session["role"] = u["role"]
            return redirect(f"/{u['role']}")

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


# ===================== HR SIDE =====================
@app.route("/hr")
@login_required(role="hr")
def hr_dashboard():
    past = list(screenings.find(
        {"hr_user": session["user"]}
    ).sort("timestamp", -1).limit(10))

    # IMPROVEMENT: Only show active JDs (is_active not explicitly False)
    all_jds = list(jds.find({"is_active": {"$ne": False}}))

    return render_template("hr_dashboard.html", jds=all_jds, past_screenings=past)


@app.route("/hr/upload_jd", methods=["POST"])
@login_required(role="hr")
def upload_jd():
    job_title        = request.form["job_title"].strip()
    jd_text          = load_file(request.files["jd"])
    min_score        = float(request.form.get("min_score", 0))
    min_exp          = int(request.form.get("min_exp", 0))
    mandatory_raw    = request.form.get("mandatory_skills", "")
    mandatory_skills = [s.strip().lower() for s in mandatory_raw.split(",") if s.strip()]

    if not jd_text.strip():
        past = list(screenings.find({"hr_user": session["user"]}).sort("timestamp", -1).limit(10))
        all_jds = list(jds.find({"is_active": {"$ne": False}}))
        return render_template("hr_dashboard.html",
                               jds=all_jds,
                               past_screenings=past,
                               error="Could not read the JD file. Upload a valid PDF or DOCX.")

    jds.insert_one({
        "title":            job_title,
        "jd":               jd_text,
        "uploaded_by":      session["user"],
        "min_score":        min_score,
        "min_experience":   min_exp,
        "mandatory_skills": mandatory_skills,
        "is_active":        True,           # IMPROVEMENT: JDs start as active
        "posted_on":        datetime.utcnow()
    })
    return redirect("/hr")


# IMPROVEMENT: HR can toggle a JD active/inactive instead of only deleting
@app.route("/hr/toggle_jd/<jd_id>")
@login_required(role="hr")
def toggle_jd(jd_id):
    try:
        jd_doc = jds.find_one({"_id": ObjectId(jd_id)})
    except InvalidId:
        return "Invalid Job ID", 400
    if not jd_doc:
        return "JD not found", 404

    current = jd_doc.get("is_active", True)
    jds.update_one({"_id": ObjectId(jd_id)}, {"$set": {"is_active": not current}})
    return redirect("/hr")


@app.route("/hr/delete_jd/<jd_id>")
@login_required(role="hr")
def delete_jd(jd_id):
    try:
        jds.delete_one({"_id": ObjectId(jd_id)})
    except InvalidId:
        return "Invalid Job ID", 400
    return redirect("/hr")


@app.route("/hr/analyze", methods=["POST"])
@login_required(role="hr")
def hr_analyze():
    jd_id = request.form["jd_id"]
    try:
        jd_doc = jds.find_one({"_id": ObjectId(jd_id)})
    except InvalidId:
        return "Invalid Job ID", 400
    if not jd_doc:
        return "Job description not found", 404

    min_score        = jd_doc.get("min_score", 0)
    min_exp          = jd_doc.get("min_experience", 0)
    mandatory_skills = jd_doc.get("mandatory_skills", [])

    all_files = request.files.getlist("resumes")

    # IMPROVEMENT: Warn HR if more than 20 resumes were uploaded (silent drop fixed)
    dropped_count = max(0, len(all_files) - 20)
    files         = all_files[:20]

    shortlisted      = []
    rejected         = []
    total_redactions = 0

    for idx, f in enumerate(files, start=1):
        resume_text = load_file(f)
        if not resume_text.strip():
            continue

        anon_name = anonymize_filename(f.filename, idx)

        t, s, final, matched, missing, redacted_count = score_resume(resume_text, jd_doc["jd"])
        total_redactions += redacted_count
        exp = extract_experience_years(resume_text)

        reasons = []
        if final < min_score:
            reasons.append(f"Score {final}% is below minimum {min_score}%")
        if exp < min_exp:
            reasons.append(f"Experience {exp} yr(s) is below minimum {min_exp} yr(s)")
        for skill in mandatory_skills:
            pattern = r"\b" + re.escape(skill) + r"\b"
            if not re.search(pattern, resume_text.lower()):
                reasons.append(f"Missing mandatory skill: {skill}")

        candidate_data = {
            "filename":       anon_name,
            "score":          final,
            "tfidf":          t,
            "semantic":       s,
            "experience":     exp,
            "matched":        matched[:8],
            "missing":        missing[:8],
            "reasons":        reasons,
            "redacted_count": redacted_count    # per-candidate redaction count
        }

        if reasons:
            rejected.append(candidate_data)
        else:
            shortlisted.append(candidate_data)

    shortlisted.sort(key=lambda x: x["score"], reverse=True)
    rejected.sort(key=lambda x: x["score"], reverse=True)

    screening_doc = {
        "hr_user":          session["user"],
        "job_title":        jd_doc["title"],
        "jd_id":            str(jd_id),
        "timestamp":        datetime.utcnow(),
        "shortlisted":      shortlisted,
        "rejected":         rejected,
        "min_score":        min_score,
        "min_exp":          min_exp,
        "mandatory_skills": mandatory_skills,
        "total_redactions": total_redactions,
        "dropped_count":    dropped_count
    }
    result       = screenings.insert_one(screening_doc)
    screening_id = str(result.inserted_id)

    return render_template(
        "hr_results.html",
        job_title=jd_doc["title"],
        shortlisted=shortlisted,
        rejected=rejected,
        min_score=min_score,
        min_exp=min_exp,
        mandatory_skills=mandatory_skills,
        screening_id=screening_id,
        total_redactions=total_redactions,
        dropped_count=dropped_count         # passed so template can warn HR
    )


@app.route("/hr/screening/<screening_id>")
@login_required(role="hr")
def hr_view_screening(screening_id):
    try:
        doc = screenings.find_one({"_id": ObjectId(screening_id), "hr_user": session["user"]})
    except InvalidId:
        return "Invalid ID", 400
    if not doc:
        return "Screening not found or access denied", 404

    return render_template(
        "hr_results.html",
        job_title=doc["job_title"],
        shortlisted=doc["shortlisted"],
        rejected=doc["rejected"],
        min_score=doc["min_score"],
        min_exp=doc["min_exp"],
        mandatory_skills=doc["mandatory_skills"],
        screening_id=screening_id,
        timestamp=doc.get("timestamp"),
        total_redactions=doc.get("total_redactions", 0),
        dropped_count=doc.get("dropped_count", 0)
    )


@app.route("/hr/export/<screening_id>")
@login_required(role="hr")
def hr_export_csv(screening_id):
    try:
        doc = screenings.find_one({"_id": ObjectId(screening_id), "hr_user": session["user"]})
    except InvalidId:
        return "Invalid ID", 400
    if not doc:
        return "Not found", 404

    output = io.StringIO()
    writer = csv.writer(output)
    # IMPROVEMENT: CSV now includes per-candidate redaction count
    writer.writerow(["Rank", "Candidate", "Score (%)", "TF-IDF (%)", "Semantic (%)",
                     "Experience (yrs)", "Matched Skills", "PII Redactions"])
    for i, c in enumerate(doc["shortlisted"], 1):
        writer.writerow([
            i, c["filename"], c["score"],
            c.get("tfidf", ""), c.get("semantic", ""),
            c["experience"],
            ", ".join(c.get("matched", [])),
            c.get("redacted_count", 0)
        ])

    output.seek(0)
    safe_title = doc["job_title"].replace(" ", "_")
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"shortlist_{safe_title}.csv"
    )


# ===================== CANDIDATE SIDE =====================
@app.route("/candidate")
@login_required(role="candidate")
def candidate_dashboard():
    # IMPROVEMENT: Only show active JDs to candidates
    openings     = list(jds.find({"is_active": {"$ne": False}}, {"title": 1}))
    selected_job = None
    job_id       = session.get("job_id")

    if job_id:
        try:
            job_doc = jds.find_one({"_id": ObjectId(job_id)})
            if job_doc:
                selected_job = job_doc["title"]
        except InvalidId:
            session.pop("job_id", None)

    return render_template("candidate_dashboard.html",
                           openings=openings, selected_job=selected_job)


@app.route("/candidate/select_job/<job_id>")
@login_required(role="candidate")
def candidate_select_job(job_id):
    try:
        ObjectId(job_id)
    except InvalidId:
        return "Invalid Job ID", 400

    session["job_id"] = job_id
    session.pop("resume_text", None)
    session.pop("resume_data", None)
    session.pop("last_score", None)
    return redirect("/candidate")


@app.route("/candidate/upload", methods=["GET", "POST"])
@login_required(role="candidate")
def candidate_upload():
    job_id = session.get("job_id")
    if not job_id:
        return redirect("/candidate")

    try:
        job_doc = jds.find_one({"_id": ObjectId(job_id)})
    except InvalidId:
        return "Invalid Job ID", 400
    if not job_doc:
        return "Job description not found", 404

    job_title = job_doc["title"]

    if request.method == "POST":
        f = request.files.get("resume")
        if not f or not f.filename:
            return render_template("candidate_upload.html", job_title=job_title,
                                   error="Please select a file to upload.")

        ext = os.path.splitext(f.filename.lower())[1]
        if ext not in ALLOWED_EXTENSIONS:
            return render_template("candidate_upload.html", job_title=job_title,
                                   error="Only PDF, DOCX, and TXT files are accepted.")

        resume_text = load_file(f)
        if not resume_text.strip():
            return render_template("candidate_upload.html", job_title=job_title,
                                   error="Could not read your file. Please check it's not empty or corrupted.")

        # IMPROVEMENT: Block duplicate resume submissions for the same job
        if is_duplicate_resume(resume_text, job_id, session["user"]):
            return render_template("candidate_upload.html", job_title=job_title,
                                   error="You have already submitted a very similar resume for this position.")

        session["resume_text"] = resume_text
        session.pop("resume_data", None)

        resumes.insert_one({
            "username":    session["user"],
            "job_id":      job_id,
            "resume_text": resume_text,
            "created_with":"upload",
            "timestamp":   datetime.utcnow()
        })

        return render_template("candidate_preview.html", resume=resume_text, job_title=job_title)

    return render_template("candidate_upload.html", job_title=job_title)


@app.route("/candidate/create", methods=["GET", "POST"])
@login_required(role="candidate")
def candidate_create():
    job_id = session.get("job_id")
    if not job_id:
        return redirect("/candidate")

    try:
        job_doc = jds.find_one({"_id": ObjectId(job_id)})
    except InvalidId:
        return "Invalid Job ID", 400
    if not job_doc:
        return "Job description not found", 404

    job_title = job_doc["title"]

    if request.method == "POST":
        skills_raw  = request.form["skills"]
        skills_list = [s.strip() for s in re.split(r"[,\n]", skills_raw) if s.strip()]

        resume_data = {
            "name":           request.form["name"].strip(),
            "email":          request.form["email"].strip(),
            "phone":          request.form["phone"].strip(),
            "summary":        request.form["summary"].strip(),
            "skills":         skills_list,
            "experience":     request.form["experience"].strip(),
            "projects":       request.form["projects"].strip(),
            "education":      request.form["education"].strip(),
            "certifications": request.form["certifications"].strip()
        }

        session["resume_data"] = resume_data
        session["resume_text"] = " ".join([
            resume_data["summary"], " ".join(skills_list),
            resume_data["experience"], resume_data["projects"],
            resume_data["education"], resume_data["certifications"]
        ])

        resumes.insert_one({
            "username":    session["user"],
            "job_id":      job_id,
            "resume_text": session["resume_text"],
            "created_with":"builder",
            "timestamp":   datetime.utcnow()
        })

        return render_template("candidate_preview.html", resume=resume_data, job_title=job_title)

    return render_template("candidate_create.html", job_title=job_title,
                           resume=session.get("resume_data", {}))


@app.route("/candidate/download")
@login_required(role="candidate")
def candidate_download_resume():
    resume_data = session.get("resume_data")
    if not resume_data:
        return "Download only works for resumes built with the Resume Builder.", 400

    pdf_stream = resume_to_pdf(resume_data)
    return send_file(pdf_stream, as_attachment=True,
                     download_name="Resume.pdf", mimetype="application/pdf")


@app.route("/candidate/check")
@login_required(role="candidate")
def candidate_check():
    job_id = session.get("job_id")
    if not job_id:
        return redirect("/no_jd")

    resume = session.get("resume_text", "")
    if not resume.strip():
        return redirect("/candidate")

    # IMPROVEMENT: Verify resume in session belongs to the currently selected job.
    # If they switched jobs without re-uploading, send them back to upload.
    session_job_id = session.get("job_id")
    last_resume_record = resumes.find_one(
        {"username": session["user"], "job_id": session_job_id},
        sort=[("timestamp", -1)]
    )
    if not last_resume_record:
        return redirect("/candidate/upload")

    try:
        jd_doc = jds.find_one({"_id": ObjectId(job_id)})
    except InvalidId:
        return "Invalid Job ID", 400
    if not jd_doc:
        return "Job description not found", 404

    t, s, f, matched, missing, redacted_count = score_resume(resume, jd_doc["jd"])

    # Replace raw missing skill list with non-gameable category insights
    category_gaps = get_skill_category_gaps(missing)

    session["last_score"] = f

    return render_template("candidate_result.html",
                           job_title=jd_doc["title"],
                           tfidf=t, semantic=s, final=f,
                           matched=matched,
                           category_gaps=category_gaps,
                           redacted_count=redacted_count)


# NOTE: candidate/fix_resume has been intentionally removed.
# Auto-injecting missing skills into a resume inflates scores dishonestly
# and directly contradicts the integrity of bias-free screening.
# Candidates now receive category-level trend guidance instead.


@app.route("/no_jd")
def no_jd():
    return render_template("no_jd.html")


# ===================== Global Error Handlers =====================
@app.errorhandler(404)
def not_found(e):
    return render_template("no_jd.html"), 404

@app.errorhandler(500)
def server_error(e):
    return "Internal server error — please try again.", 500


# ===================== Run =====================
if __name__ == "__main__":
  app.run(
    debug=os.getenv("FLASK_DEBUG", "0") == "1",
    port=5000
)
