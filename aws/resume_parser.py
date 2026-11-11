"""Resume extraction from Textract LINE blocks with column-aware reading order.

Records evidence; never turns projects or extracurriculars into paid work.
"""
import re

HEADINGS = {
    'skills': r'(?:technical\s+)?skills?|technical\s+proficienc(?:y|ies)|technologies|tools\s*(?:&|and)\s*technologies|core\s+competencies',
    'education': r'education|academic\s+(?:background|qualifications)|qualifications',
    'experience': r'(?:professional|work|employment|relevant)\s+(?:experience|history)|experience|employment\s+history|work\s+history|career\s+history',
    'volunteer_experience': r'volunteer(?:ing)?(?:\s+experience|\s+work)?|community\s+(?:service|involvement|engagement)|extracurricular\s+activities',
    'projects': r'(?:academic|selected|technical|personal)?\s*projects?',
    'leadership': r'leadership(?:\s+(?:experience|activities))?|activities|student\s+organizations?',
}
SECTION_RE = re.compile(r'^\s*(?:\d+[.)]\s*)?(?:' + '|'.join(f'(?P<{k}>{p})' for k,p in HEADINGS.items()) + r')\s*[:\-–—]?\s*(.*)$', re.I)
STOP_RE = re.compile(r'^(?:certifications?|licenses?|awards?|publications?|references?|professional summary|profile|contact|interests?|languages?|relevant courses)\s*[:\-–—]?$', re.I)
SKILL_PATTERNS = {
    'AWS':r'\b(?:AWS|Amazon Web Services)\b', 'Azure':r'\bAzure\b', 'Google Cloud':r'\b(?:GCP|Google Cloud)\b',
    'Python':r'\bPython\b', 'Pandas':r'\bPandas\b', 'scikit-learn':r'\bscikit[ -]learn\b',
    'NumPy':r'\bNumPy\b', 'Java':r'\bJava\b(?!Script)', 'JavaScript':r'\bJavaScript\b',
    'TypeScript':r'\bTypeScript\b', 'React':r'\bReact(?:\.js)?\b', 'FastAPI':r'\bFastAPI\b',
    'SQL':r'\bSQL\b', 'PostgreSQL':r'\bPostgreSQL\b', 'MySQL':r'\bMySQL\b',
    'DynamoDB':r'\bDynamoDB\b', 'Terraform':r'\bTerraform\b', 'Docker':r'\bDocker\b',
    'Kubernetes':r'\bKubernetes\b|\bK8s\b', 'Linux':r'\bLinux\b', 'Git':r'\bGit\b',
    'GitHub Actions':r'\bGitHub Actions\b', 'C++':r'(?<!\w)C\+\+(?!\w)', 'C#':r'(?<!\w)C#(?!\w)',
    'HTML':r'\bHTML\b', 'CSS':r'\bCSS\b', 'Machine Learning':r'\bmachine learning\b',
    'PyTorch':r'\bPyTorch\b', 'TensorFlow':r'\bTensorFlow\b',
    'Excel':r'\bExcel\b', 'Google Sheets':r'\bGoogle\s+Sheets\b',
    'Matplotlib':r'\bMatplotlib\b', 'Tableau':r'\bTableau\b',
    'Regression Modeling':r'\b(?:linear|logistic)\s+regressions?\b',
}
DEGREE_RE = re.compile(r'\b(?:bachelor|master|b\.?s\.?|m\.?s\.?|b\.?tech|m\.?tech|ph\.?d\.?|doctorate|diploma|associate|university|college|institute)\b', re.I)
OUTREACH_RE = re.compile(r'\b(?:community outreach|volunteer(?:ed|ing)?|pro bono|charity|nonprofit|community service|mentored|tutored)\b', re.I)


def _lines_from_blocks(blocks):
    """Read PDF columns top-to-bottom instead of mixing by Y coordinate.

    Textract bounding boxes are page-relative. Only split when both columns
    contain section headings; otherwise retain conventional reading order.
    """
    by_page={}
    for b in blocks:
        if b.get('BlockType')!='LINE' or not b.get('Text','').strip(): continue
        bb=b.get('Geometry',{}).get('BoundingBox',{})
        by_page.setdefault(int(b.get('Page',1)),[]).append((float(bb.get('Top',0)),float(bb.get('Left',0)),b['Text'].strip()))
    output=[]
    for page in sorted(by_page):
        items=sorted(by_page[page],key=lambda row:(row[0],row[1]))
        heading_positions=[(y,x) for y,x,t in items if SECTION_RE.match(t) and len(t)<70]
        left_heads=[(y,x) for y,x in heading_positions if x<.56]
        right_heads=[(y,x) for y,x in heading_positions if x>=.56]
        if left_heads and right_heads:
            start=min(y for y,x in heading_positions)
            header=[r for r in items if r[0]<start-.008]
            body=[r for r in items if r[0]>=start-.008]
            # Center split .56 keeps wide lines in left column even when text
            # stretches past the halfway point. Left is the beginning coordinate.
            left=sorted((r for r in body if r[1]<.56),key=lambda r:(r[0],r[1]))
            right=sorted((r for r in body if r[1]>=.56),key=lambda r:(r[0],r[1]))
            output.extend(r[2] for r in header+left+right)
        else:
            output.extend(r[2] for r in items)
    return output


def parse_resume(text, blocks=None):
    if blocks:
        lines=_lines_from_blocks(blocks)
        text='\n'.join(lines)
    else:
        lines=text.replace('\r','\n').split('\n')
    lines=[re.sub(r'[\t\u00a0]+',' ',x).strip() for x in lines]
    lines=[x for x in lines if x]
    sections={k:[] for k in HEADINGS}
    headings_found=set();current=None;header=[]
    for line in lines:
        m=SECTION_RE.match(line) if len(line)<=90 else None
        if m:
            current=next((k for k in HEADINGS if m.group(k) is not None),None)
            headings_found.add(current)
            trail=m.group(m.lastindex).strip(' :-–—') if m.lastindex else ''
            if trail:sections[current].append(trail)
            continue
        if current=='projects' and re.search(r'\b(?:intramural|basketball|student association|student club)\b',line,re.I) and len(line)<100:
            current='leadership'
            headings_found.add('leadership')
        if STOP_RE.match(line): current=None;continue
        if current:sections[current].append(line)
        else:header.append(line)
    # Name is drawn from the first couple of header lines, not from project titles.
    name=''
    for line in lines[:5]:
        if len(line)<60 and re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{3,58}",line) and not re.search(r'\b(resume|curriculum vitae|professional|engineer|developer|analyst|email|contact|profile)\b',line,re.I):
            name=line;break
    skills=[name for name,pat in SKILL_PATTERNS.items() if re.search(pat,text,re.I)]
    # Skills should be grounded in section text wherever present; fallback to
    # the rest of the document for a résumé without a recognized heading.
    if sections['skills']:
        section_text='\n'.join(sections['skills'])
        skills=[name for name,pat in SKILL_PATTERNS.items() if re.search(pat,section_text,re.I)] or skills
    edu=sections['education'][:20]
    if not edu:edu=[x for x in lines if DEGREE_RE.search(x)][:8]
    volunteers=sections['volunteer_experience'][:20]
    warnings=[]
    if not volunteers:
        # Only quote actual community-service evidence, never imply that a
        # leadership post or extracurricular activity was an employment role.
        volunteers=[]
        for i,line in enumerate(lines):
            if OUTREACH_RE.search(line):
                # Keep the sentence together when a PDF wraps the activity.
                next_line=lines[i+1] if i+1<len(lines) else ''
                if next_line and line.rstrip().endswith(('-', 'at-risk', 'high', 'the', 'to', 'for')):
                    line+=' '+next_line
                volunteers.append(line)
                if len(volunteers)>=5:break
        if volunteers:warnings.append('Community involvement identified; verify whether it was volunteer service.')
    exp=sections['experience'][:35]
    # Empty experience is expected for entry-level résumés: not a parsing failure.
    if not exp:warnings.append('No formal employment experience listed.')
    missing=[]
    if not name:missing.append('name')
    if not edu or ('education' not in headings_found and not blocks):missing.append('education')
    if not skills:missing.append('skills')
    if missing:warnings.append('Missing or unrecognized fields: '+', '.join(missing))
    fields={
        'detected_name':name,'skills':skills,
        'education':'\n'.join(edu)[:1600],
        'experience':'\n'.join(exp)[:2500],
        'volunteer_experience':'\n'.join(volunteers)[:1600],
        'projects':'\n'.join(sections['projects'][:45])[:3500],
        'leadership':'\n'.join(sections['leadership'][:20])[:1600],
        'resume_text':text[:85000],
        'section_evidence':sorted(headings_found),
        'processing_status':'review_required' if missing else 'completed',
        'processing_warning':' '.join(warnings),
    }
    return fields
