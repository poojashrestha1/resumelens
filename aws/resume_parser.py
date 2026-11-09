"""Deterministic résumé section parser. Never invents missing candidate information.

Textract performs OCR; this module recognizes headings/lines and records evidence.
Comprehend is optional enrichment, not a substitute for section extraction.
"""
import re

HEADINGS = {
    'skills': r'(?:technical\s+)?skills?|technical\s+proficienc(?:y|ies)|technologies|tools\s*(?:&|and)\s*technologies|core\s+competencies',
    'education': r'education|academic\s+(?:background|qualifications)|qualifications',
    'experience': r'(?:professional|work|employment|relevant)\s+(?:experience|history)|experience|employment\s+history|work\s+history|career\s+history',
    'volunteer_experience': r'volunteer(?:ing)?(?:\s+experience|\s+work)?|community\s+(?:service|involvement|engagement)|extracurricular\s+activities',
}
STOP_RE = re.compile(r'^(?:projects?|certifications?|licenses?|awards?|publications?|references?|professional summary|profile|contact|interests?|languages?)\s*[:\-–—]?$', re.I)
SECTION_RE = re.compile(r'^\s*(?:\d+[.)]\s*)?(?:' + '|'.join(f'(?P<{k}>{p})' for k,p in HEADINGS.items()) + r')\s*[:\-–—]?\s*(.*)$', re.I)
SKILL_PATTERNS = {
    'AWS':r'\b(?:AWS|Amazon Web Services)\b', 'Azure':r'\b(?:Azure|Microsoft Azure)\b',
    'Google Cloud':r'\b(?:GCP|Google Cloud(?: Platform)?)\b',
    'Python':r'\bPython\b', 'Java':r'\bJava\b(?!Script)', 'JavaScript':r'\bJavaScript\b',
    'TypeScript':r'\bTypeScript\b', 'React':r'\bReact(?:\.js)?\b',
    'FastAPI':r'\bFastAPI\b', 'Node.js':r'\bNode(?:\.js|JS)\b',
    'SQL':r'\bSQL\b', 'PostgreSQL':r'\bPostgreSQL\b', 'MySQL':r'\bMySQL\b',
    'DynamoDB':r'\bDynamoDB\b', 'Terraform':r'\bTerraform\b',
    'Docker':r'\bDocker\b', 'Kubernetes':r'\bKubernetes\b|\bK8s\b',
    'Linux':r'\bLinux\b', 'Git':r'\bGit\b', 'GitHub Actions':r'\bGitHub Actions\b',
    'CI/CD':r'\bCI\s*/\s*CD\b|\bcontinuous (?:integration|delivery|deployment)\b',
    'C++':r'(?<!\w)C\+\+(?!\w)', 'C#':r'(?<!\w)C#(?!\w)',
    'HTML':r'\bHTML\b', 'CSS':r'\bCSS\b', 'Machine Learning':r'\bmachine learning\b',
    'PyTorch':r'\bPyTorch\b', 'TensorFlow':r'\bTensorFlow\b',
}
DEGREE_RE = re.compile(r'\b(bachelor|master|b\.?s\.?\b|m\.?s\.?\b|b\.?tech\b|m\.?tech\b|ph\.?d\.?\b|doctorate|diploma|associate(?:\'s)?|university|college|institute|school of)\b', re.I)
DATE_RE = re.compile(r'\b(?:19|20)\d{2}\b|\b(?:present|current)\b', re.I)


def parse_resume(text):
    lines=[re.sub(r'[\t\u00a0]+',' ',x).strip() for x in text.replace('\r','\n').split('\n')]
    lines=[x for x in lines if x]
    sections={k:[] for k in HEADINGS}
    current=None
    headings_found=set()
    for line in lines:
        # Heading is anchored and short; do not treat 'Experience with Python' as heading.
        match=SECTION_RE.match(line) if len(line)<=90 else None
        if match:
            current=next((k for k in HEADINGS if match.group(k) is not None),None)
            headings_found.add(current)
            trailer=match.group(match.lastindex).strip(' :-–—') if match.lastindex else ''
            if trailer:sections[current].append(trailer)
            continue
        if STOP_RE.match(line):
            current=None
            continue
        if current:sections[current].append(line)
    skills=[name for name,pat in SKILL_PATTERNS.items() if re.search(pat,text,re.I)]
    edu=sections['education'][:14]
    if not edu:
        edu=[line for line in lines if DEGREE_RE.search(line)][:6]
    experience=sections['experience'][:24]
    volunteers=sections['volunteer_experience'][:16]
    # Deliberately return empty values when sections are absent: no fabricated experience.
    detected_name=''
    for line in lines[:6]:
        if len(line)<65 and re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{3,60}",line) and not re.search(r'\b(resume|curriculum vitae|professional|engineer|developer|email|contact|profile)\b',line,re.I):
            detected_name=line
            break
    fields={
        'detected_name':detected_name,
        'skills':skills,
        'education':'\n'.join(edu)[:1600],
        'experience':'\n'.join(experience)[:2500],
        'volunteer_experience':'\n'.join(volunteers)[:1600],
        'resume_text':text[:85000],
        'section_evidence':sorted(headings_found),
    }
    missing=[key for key in ('education','experience') if not fields[key]]
    fields['processing_status']='review_required' if missing else 'completed'
    fields['processing_warning']=('Missing or unrecognized sections: '+', '.join(missing)) if missing else ''
    return fields
