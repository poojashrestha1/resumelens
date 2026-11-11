import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app import storage

PDF=Path(__file__).resolve().parents[1]/'fixtures'/'two_column_student_resume.pdf'

def headers(client,email='applicant@demo.example.com',password='applicant123'):
    response=client.post('/api/auth/login',json={'email':email,'password':password})
    assert response.status_code==200
    return {'Authorization':'Bearer '+response.json()['access_token']}

def test_prefill_two_column_and_corrections_are_authoritative():
    with TestClient(app) as client:
        auth=headers(client)
        data=PDF.read_bytes()
        r=client.post('/api/applications/prefill',headers=auth,files={'resume':('sample.pdf',data,'application/pdf')})
        assert r.status_code==200,r.text
        extracted=r.json()
        assert extracted['detected_name']=='JANEE ZEDA'
        assert 'University of Alaska' in extracted['education']
        assert 'Basketball Intramural Team' in extracted['leadership']
        assert extracted['experience']==''
        assert extracted['extraction_method']=='direct_pdf'
        details={'name':'Janee Zeda','email':'janee@example.com','phone':'555 0100','address':'Anchorage, AK',
                 'skills':['SQL','Python'],'education':'B.S., Mathematics and Economics',
                 'experience':'Confirmed: no formal employment','volunteer_experience':'Community outreach',
                 'cover_letter':'Please consider my application'}
        submit=client.post('/api/applications',headers=auth,data={'job_id':'cloud-engineer','details':json.dumps(details)},files={'resume':('sample.pdf',data,'application/pdf')})
        assert submit.status_code==201,submit.text
        app_id=submit.json()['id']
        record=storage.get('applications',app_id)
        assert record['experience']=='Confirmed: no formal employment'
        assert record['name']=='Janee Zeda'
        assert record['applicant_verified'] is True
        assert client.get('/api/applications/'+app_id+'/resume',headers=auth).status_code==200

def test_hr_cannot_prefill():
    with TestClient(app) as client:
        hr=headers(client,'hr@demo.example.com','hr12345678')
        r=client.post('/api/applications/prefill',headers=hr,files={'resume':('sample.pdf',PDF.read_bytes(),'application/pdf')})
        assert r.status_code==403

def test_manual_application_without_resume():
    with TestClient(app) as client:
        applicant=headers(client)
        details={'name':'Manual Candidate','email':'manual@example.com','phone':'5550102','address':'Kansas City',
                 'education':'MS Computer Science'}
        r=client.post('/api/applications',headers=applicant,data={'job_id':'devops-engineer','details':json.dumps(details)})
        assert r.status_code==201,r.text
        assert client.get('/api/applications/'+r.json()['id']+'/resume',headers=applicant).status_code==404
