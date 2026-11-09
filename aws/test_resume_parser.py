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
