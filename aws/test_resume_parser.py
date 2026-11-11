from resume_parser import parse_resume

def test_multisection_resume():
    text='''Asha Shrestha
SKILLS
Python, AWS, Terraform, Docker, Kubernetes
EDUCATION
Master of Science in Computer Science
University of Central Missouri
PROFESSIONAL EXPERIENCE
DevOps Engineer | 2022 - 2025
Developed CI/CD with AWS
VOLUNTEER EXPERIENCE
AWS Community Leader | 2023 - Present'''
    result=parse_resume(text)
    assert {'AWS','Python','Terraform','Docker','Kubernetes'}<=set(result['skills'])
    assert 'Master' in result['education']
    assert 'DevOps Engineer' in result['experience']
    assert 'AWS Community Leader' in result['volunteer_experience']
    assert 'AWS Community Leader' not in result['experience']
    assert result['processing_status']=='completed'

def test_missing_section_requires_review():
    result=parse_resume('Jane Doe\nPython AWS\nBSc University of Example')
    assert result['processing_status']=='review_required'
    assert result['experience']==''
    assert result['resume_text']

def test_section_heading_with_inline_content():
    result=parse_resume('Jaya Shrestha\nSKILLS: SQL, Python\nEDUCATION: BSc IT\nExperience\nSoftware Engineer 2023\nVolunteer Work\nTutored students')
    assert 'SQL' in result['skills']
    assert 'BSc IT' in result['education']
    assert 'Tutored students' in result['volunteer_experience']

def test_two_column_resume_pdf_real():
    """Regression test for the user-supplied student résumé with two columns."""
    from pathlib import Path
    import fitz
    root=Path(__file__).resolve().parents[1]
    fixture=root/'fixtures'/'two_column_student_resume.pdf'
    with fitz.open(fixture) as doc:
        blocks=[]
        for page_no,page in enumerate(doc,1):
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines',[]):
                    txt=''.join(span['text'] for span in line['spans']).strip()
                    if txt:
                        blocks.append({'BlockType':'LINE','Page':page_no,'Text':txt,
                            'Geometry':{'BoundingBox':{'Top':line['bbox'][1]/page.rect.height,'Left':line['bbox'][0]/page.rect.width}}})
        result=parse_resume('\n'.join(page.get_text() for page in doc),blocks)
    assert result['detected_name']=='JANEE ZEDA'
    assert 'Mathematics' in result['education']
    assert 'University of Alaska' in result['education']
    assert {'SQL','Python','Pandas','scikit-learn','Matplotlib','Tableau'}<=set(result['skills'])
    assert 'Fantasy Football Modeling' in result['projects']
    assert 'Movie Recommendation Engine' in result['projects']
    assert 'Market Analysis' in result['projects']
    assert 'Basketball Intramural Team' not in result['projects']
    assert 'Basketball Intramural Team' in result['leadership']
    assert result['experience']==''
    assert 'community outreach' in result['volunteer_experience']
    assert result['processing_status']=='completed'
