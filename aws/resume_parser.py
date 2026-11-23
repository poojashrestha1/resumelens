"""Evidence-based résumé extraction from text or Amazon Textract LINE blocks.

Compatible with ResumeLens's existing parse_resume(text, blocks=None) interface.
Avoids inventing jobs, degrees, volunteer roles, and skills. Applicant review
remains essential: no rule-based parser can interpret every résumé perfectly.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

# Order is important: specific combinations precede broader headings.
_HEADING_VARIANTS: list[tuple[str, str]] = [
    ("volunteer_experience", r"volunteer(?:ing)?(?:\s+(?:experience|work|activities|history))?|community\s+(?:service|involvement|engagement|outreach)|service\s+activities|volunteer\s*(?:&|and)\s*community\s+service"),
    ("leadership", r"leadership(?:\s+(?:experience|activities|and\s+activities))?|(?:leadership\s*(?:&|and)\s*)?activities|extracurricular(?:\s+activities)?|student\s+organizations?|campus\s+involvement|clubs\s*(?:&|and)\s*organizations"),
    ("skills", r"(?:technical\s+|professional\s+|relevant\s+)?skills?|technical\s+proficienc(?:y|ies)|technologies|tools\s*(?:&|and)\s*technologies|core\s+competencies|areas\s+of\s+expertise|software\s*(?:&|and)\s*tools|competencies"),
    ("education", r"education(?:al\s+background)?|academic\s+(?:background|qualifications|history)|qualifications|degrees?"),
    ("experience", r"(?:professional|work|employment|relevant|industry)\s+(?:experience|history)|experience|employment\s+history|work\s+history|career\s+history|internships?"),
    ("projects", r"(?:(?:academic|selected|technical|personal|research|key)\s+)?projects?(?:\s*(?:&|and)\s*research)?"),
]
HEADINGS = dict(_HEADING_VARIANTS)

# Full-line headings, optionally containing an inline value after punctuation.
# Preserve name SECTION_RE for compatibility with any external imports.
SECTION_RE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?P<heading>" + "|".join(
        rf"(?:{p})" for _, p in _HEADING_VARIANTS
    ) + r")\s*(?:(?:[:\-–—])\s*(?P<trail>.*))?\s*$",
    re.I,
)
_STOP_HEADING_RE = re.compile(
    r"^(?:certifications?|licenses?|awards?(?:\s+and\s+honors)?|publications?|"
    r"references?|professional\s+summary|summary|profile|contact(?:\s+information)?|"
    r"interests?|languages?|relevant\s+courses|coursework|objective|"
    r"professional\s+memberships?|additional\s+information)\s*[:\-–—]?\s*$",
    re.I,
)

# Used only as a fallback when a proper SKILLS section is absent.
# Explicitly listed skills in a SKILLS section are *not* restricted to this list.
SKILL_PATTERNS = {
    "AWS": r"\b(?:AWS|Amazon Web Services)\b", "Azure": r"\bAzure\b",
    "Google Cloud": r"\b(?:GCP|Google Cloud)\b", "Python": r"\bPython\b",
    "Pandas": r"\bPandas\b", "scikit-learn": r"\bscikit[ -]learn\b",
    "NumPy": r"\bNumPy\b", "Java": r"\bJava\b(?!Script)",
    "JavaScript": r"\bJavaScript\b", "TypeScript": r"\bTypeScript\b",
    "React": r"\bReact(?:\.js)?\b", "FastAPI": r"\bFastAPI\b",
    "SQL": r"\bSQL\b", "PostgreSQL": r"\bPostgreSQL\b",
    "MySQL": r"\bMySQL\b", "DynamoDB": r"\bDynamoDB\b",
    "Terraform": r"\bTerraform\b", "Docker": r"\bDocker\b",
    "Kubernetes": r"\bKubernetes\b|\bK8s\b", "Linux": r"\bLinux\b",
    "Git": r"\bGit\b", "GitHub Actions": r"\bGitHub Actions\b",
    "C++": r"(?<!\w)C\+\+(?!\w)", "C#": r"(?<!\w)C#(?!\w)",
    "HTML": r"\bHTML\b", "CSS": r"\bCSS\b",
    "Machine Learning": r"\bmachine learning\b", "PyTorch": r"\bPyTorch\b",
    "TensorFlow": r"\bTensorFlow\b", "Excel": r"\bExcel\b",
    "Google Sheets": r"\bGoogle\s+Sheets\b", "Matplotlib": r"\bMatplotlib\b",
    "Tableau": r"\bTableau\b", "Regression Modeling": r"\b(?:linear|logistic)\s+regressions?\b",
    "Adobe Creative Suite": r"\bAdobe Creative Suite\b", "Figma": r"\bFigma\b",
    "Canva": r"\bCanva\b", "CRM": r"\bCRM\b",
    "POS Systems": r"\bPOS\s+(?:systems?|software)\b",
    "Customer Support": r"\bcustomer\s+(?:support|service)\b",
    "Inventory Control": r"\binventory\s+(?:control|management)\b",
    "Conflict Resolution": r"\bconflict\s+resolution\b",
    "Scheduling": r"\bscheduling\b", "Team Collaboration": r"\bteam\s+collaboration\b",
}
DEGREE_RE = re.compile(
    r"\b(?:bachelor(?:'s)?|master(?:'s)?|b\.?s\.?|b\.?a\.?|m\.?s\.?|m\.?a\.?|"
    r"b\.?tech|m\.?tech|ph\.?d\.?|doctorate|diploma|associate(?:'s)?|"
    r"university|college|institute|school of)\b", re.I,
)
OUTREACH_RE = re.compile(
    r"\b(?:community\s+outreach|volunteer(?:ed|ing|ism)?|pro\s+bono|charit(?:y|able)|"
    r"non[ -]?profit|community\s+service|food\s+pantry|food\s+bank|"
    r"mentored|tutored|fundrais(?:ed|ing)|donat(?:ed|ion)|"
    r"community\s+workshops?|underserved|at-risk)\b", re.I,
)

_BULLET_RE = re.compile(r"^\s*[•●▪■◦‣*]\s*|^\s*[-–]\s+")
_SPLIT_SKILLS_RE = re.compile(r"\s*(?:[,;|•●▪■◦‣]|\s+\u2022\s+)\s*")
_SKILL_LABEL_RE = re.compile(
    r"^(?:programming(?:\s+languages?)?|languages?|tools?|software|frameworks?|"
    r"libraries|platforms?|databases?|modeling|data\s+visualization|"
    r"technical|interpersonal|soft\s+skills|office|applications?|"
    r"other\s+skills|skills)\s*:\s*", re.I,
)


def _tidy(line: str) -> str:
    return re.sub(r"[\t\u00a0]+", " ", str(line)).strip()


def _heading(line: str) -> tuple[str | None, str]:
    """Recognize heading-only lines and short 'SKILLS: Python, SQL' entries.

    Avoid interpreting arbitrary prose starting with 'Experience' as a heading.
    """
    if len(line) > 110:
        return None, ""
    stripped = _tidy(line)
    # Match a heading with a boundary, not a prefix of ordinary text.
    for name, expression in _HEADING_VARIANTS:
        match = re.fullmatch(
            rf"(?:\d+[.)]\s*)?(?:{expression})\s*(?:(?:[:\-–—])\s*(.*))?",
            stripped,
            re.I,
        )
        if match:
            trail = (match.group(1) or "").strip()
            return name, trail
    return None, ""


def _lines_from_blocks(blocks: list[dict[str, Any]]) -> list[str]:
    """Read Textract LINE blocks in page order, respecting two-column pages.

    Textract coordinates are normalized 0..1. Splitting into columns is a
    conservative heuristic: it requires recognizable headings on *both* sides.
    """
    by_page: dict[int, list[tuple[float, float, float, str]]] = defaultdict(list)
    for block in blocks:
        if block.get("BlockType") != "LINE":
            continue
        value = _tidy(block.get("Text", ""))
        if not value:
            continue
        bb = block.get("Geometry", {}).get("BoundingBox", {})
        by_page[int(block.get("Page", 1))].append((
            float(bb.get("Top", 0)), float(bb.get("Left", 0)),
            float(bb.get("Width", 0)), value,
        ))

    output: list[str] = []
    for page in sorted(by_page):
        rows = sorted(by_page[page], key=lambda r: (r[0], r[1]))
        headings = sorted(
            (left, top) for top, left, width, value in rows
            if _heading(value)[0] and len(value) < 70
        )
        xs = sorted(set(round(x, 3) for x, _ in headings))
        if len(xs) < 2:
            output.extend(r[3] for r in rows)
            continue
        gap, at = max((xs[i + 1] - xs[i], i) for i in range(len(xs) - 1))
        split = (xs[at] + xs[at + 1]) / 2
        left_heads = [(x, y) for x, y in headings if x < split]
        right_heads = [(x, y) for x, y in headings if x >= split]
        if gap < 0.08 or not left_heads or not right_heads:
            output.extend(r[3] for r in rows)
            continue
        start = min(top for _, top in headings)
        header = [r for r in rows if r[0] < start - 0.008]
        body = [r for r in rows if r[0] >= start - 0.008]
        left = sorted((r for r in body if r[1] < split), key=lambda r: (r[0], r[1]))
        right = sorted((r for r in body if r[1] >= split), key=lambda r: (r[0], r[1]))
        output.extend(r[3] for r in header + left + right)
    return output


def _skills_from_section(lines: list[str]) -> list[str]:
    """Retain skills as explicitly written, including nontechnical skills."""
    skills: list[str] = []
    seen: set[str] = set()
    for original in lines:
        line = _BULLET_RE.sub("", _tidy(original))
        line = _SKILL_LABEL_RE.sub("", line)
        if not line or line.endswith(":"):
            continue
        # A single line may list several skills, or be one multiword skill.
        for item in _SPLIT_SKILLS_RE.split(line):
            item = item.strip(" \t-–—.:•")
            # Guard against accidentally treating long paragraphs as 'skills'.
            if not item or len(item) > 95 or len(item.split()) > 12:
                continue
            key = re.sub(r"\s+", " ", item.casefold())
            if key not in seen:
                skills.append(item)
                seen.add(key)
    return skills[:60]


def _volunteer_evidence(lines: list[str]) -> list[str]:
    """Return only sentences that explicitly suggest service; label for review."""
    results: list[str] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        if not OUTREACH_RE.search(line):
            continue
        if _heading(line)[0] or _STOP_HEADING_RE.fullmatch(line):
            continue
        candidate = line
        # If OCR broke a phrase in the middle, retain a little context.
        if i + 1 < len(lines) and re.search(r"(?:-|\b(?:the|for|to|and|at-risk|high))\s*$", line, re.I):
            next_line = lines[i + 1]
            if not _heading(next_line)[0] and len(next_line) < 130:
                candidate += " " + next_line
        key = candidate.casefold()
        if key not in seen:
            results.append(candidate)
            seen.add(key)
        if len(results) >= 8:
            break
    return results


def parse_resume(text: str, blocks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return the same dictionary fields expected by ResumeLens.

    Prefer Textract LINE geometry when supplied. Keep work and volunteering
    separate, do not infer paid experience from projects or extracurriculars.
    """
    if blocks:
        block_lines = _lines_from_blocks(blocks)
        lines = block_lines if block_lines else str(text or "").replace("\r", "\n").split("\n")
    else:
        lines = str(text or "").replace("\r", "\n").split("\n")
    lines = [clean for s in lines if (clean := _tidy(s))]
    cleaned_text = "\n".join(lines)

    sections: dict[str, list[str]] = {key: [] for key in HEADINGS}
    headings_found: set[str] = set()
    current: str | None = None
    for line in lines:
        heading, trail = _heading(line)
        if heading:
            current = heading
            headings_found.add(heading)
            if trail:
                sections[heading].append(trail)
            continue
        if _STOP_HEADING_RE.fullmatch(line):
            current = None
            continue
        # A new captain/club activity should not become a paid job or project.
        if current == "projects" and len(line) < 100 and re.search(
            r"\b(?:intramural|student\s+(?:club|association|society)|basketball\s+team)\b",
            line, re.I,
        ):
            current = "leadership"
            headings_found.add("leadership")
        if current:
            sections[current].append(line)

    detected_name = ""
    for line in lines[:7]:
        if (
            len(line) < 60
            and re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{3,58}", line)
            and not _heading(line)[0]
            and not _STOP_HEADING_RE.fullmatch(line)
            and not re.search(
                r"\b(?:resume|curriculum vitae|professional|engineer|developer|analyst|"
                r"email|contact|profile|customer service|customer support|associate|"
                r"specialist|manager|coordinator|university|college)\b",
                line, re.I,
            )
        ):
            detected_name = line
            break

    skills = _skills_from_section(sections["skills"])
    if not skills:
        # Dictionary-based fallback only when explicit skill lists don't help.
        skills = [key for key, pattern in SKILL_PATTERNS.items() if re.search(pattern, cleaned_text, re.I)]

    education = sections["education"][:20]
    if not education:
        education = [line for line in lines if DEGREE_RE.search(line)][:8]

    volunteers = sections["volunteer_experience"][:25]
    evidence_from_context = False
    if not volunteers:
        volunteers = _volunteer_evidence(lines)
        evidence_from_context = bool(volunteers)

    experience = sections["experience"][:35]
    missing: list[str] = []
    warnings: list[str] = []
    if not detected_name:
        missing.append("name")
    if not education:
        missing.append("education")
    if not skills:
        missing.append("skills")
    if not experience:
        warnings.append("No formal employment experience listed; this may be expected.")
    if evidence_from_context:
        warnings.append("Community involvement detected outside a dedicated volunteer section; applicant should verify classification.")
    if missing:
        warnings.append("Missing or unrecognized fields: " + ", ".join(missing))

    return {
        "detected_name": detected_name,
        "skills": skills,
        "education": "\n".join(education)[:1600],
        "experience": "\n".join(experience)[:2500],
        "volunteer_experience": "\n".join(volunteers)[:1600],
        "projects": "\n".join(sections["projects"][:45])[:3500],
        "leadership": "\n".join(sections["leadership"][:20])[:1600],
        "resume_text": cleaned_text[:85000],
        "section_evidence": sorted(headings_found),
        "processing_status": "review_required" if missing or evidence_from_context else "completed",
        "processing_warning": " ".join(warnings),
    }
