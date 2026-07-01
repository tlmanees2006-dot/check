"""
extractors/resume_extractor.py
Extracts a candidate profile from a resume PDF/DOCX using text extraction +
section-header heuristics (no ML/NLP model - kept explainable, per design doc
scope decision).
"""
import re
import os


def _read_pdf_text(path):
    import pdfplumber
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
    return text


def _read_docx_text(path):
    import docx
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


SECTION_HEADERS = ["SUMMARY", "EXPERIENCE", "EDUCATION", "SKILLS"]


def _split_sections(text):
    sections = {}
    current = "HEADER"
    sections[current] = []
    for line in text.split("\n"):
        stripped = line.strip()
        upper = stripped.upper()
        if upper in SECTION_HEADERS:
            current = upper
            sections[current] = []
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


EMAIL_RE = re.compile(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-]{8,}\d)")
DATE_RANGE_RE = re.compile(
    r"([A-Za-z]+\s+\d{4}|\d{1,2}/\d{4})\s*[-–—]\s*(Present|Current|[A-Za-z]+\s+\d{4}|\d{1,2}/\d{4})",
    re.IGNORECASE,
)


def extract(path):
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            text = _read_pdf_text(path)
        elif ext == ".docx":
            text = _read_docx_text(path)
        else:
            print(f"[WARN] Unsupported resume format for '{path}'")
            return []
    except Exception as e:
        print(f"[WARN] Failed to read resume '{path}': {e}")
        return []

    if not text.strip():
        print(f"[WARN] Resume '{path}' produced no extractable text (possibly scanned/garbled).")
        return []

    lines = [l for l in text.split("\n") if l.strip()]
    name = lines[0].strip() if lines else None
    headline = lines[1].strip() if len(lines) > 1 else None

    email_match = EMAIL_RE.search(text)
    raw_email = email_match.group(0) if email_match else None

    phone_match = PHONE_RE.search(text)
    raw_phone = phone_match.group(0) if phone_match else None

    sections = _split_sections(text)

    # Experience entries: lines containing a date range are treated as job headers
    experience_entries = []
    exp_text = sections.get("EXPERIENCE", "")
    for line in exp_text.split("\n"):
        dr = DATE_RANGE_RE.search(line)
        if dr:
            before_dates = line[:dr.start()].strip(" -—–\u2014")
            company_title = before_dates.split("—") if "—" in before_dates else before_dates.split("-")
            company = company_title[0].strip() if company_title else before_dates
            title = company_title[1].strip() if len(company_title) > 1 else None
            experience_entries.append({
                "raw_company": company,
                "raw_title": title,
                "raw_start": dr.group(1),
                "raw_end": dr.group(2),
            })

    skills_text = sections.get("SKILLS", "")
    raw_skills = [s.strip() for s in re.split(r",|\u2022", skills_text) if s.strip()]

    education_text = sections.get("EDUCATION", "")

    record = {
        "_source_type": "resume",
        "_source_file": path,
        "raw_name": name,
        "raw_headline": headline,
        "raw_email": raw_email,
        "raw_phone": raw_phone,
        "raw_experience": experience_entries,
        "raw_education_text": education_text,
        "raw_skills": raw_skills,
        "raw_summary": sections.get("SUMMARY", ""),
        "raw_full_text": text,
    }
    return [record]
