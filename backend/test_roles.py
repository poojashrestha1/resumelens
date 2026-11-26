from fastapi.testclient import TestClient
from app.main import app
from app import storage
##
def _login(client,email,password):
    res=client.post('/api/auth/login',json={'email':email,'password':password})
    assert res.status_code==200,res.text
    return {'Authorization':'Bearer '+res.json()['access_token']}

def test_hr_can_manage_jobs_but_cannot_apply():
    storage.init()
    with TestClient(app) as client:
        hr=_login(client,'hr@demo.example.com','hr12345678')
        applicant=_login(client,'applicant@demo.example.com','applicant123')
        response=client.post('/api/staff/jobs',headers=hr,json={
            'title':'Site Reliability Engineer','department':'Engineering','location':'Remote',
            'type':'Full-time','description':'Build infrastructure automation','active':True})
        assert response.status_code==201,response.text
        job=response.json()
        assert client.post('/api/staff/jobs',headers=applicant,json={
            'title':'Not Allowed','department':'Engineering','location':'Remote','description':'No access'}).status_code==403
        assert client.post('/api/applications',headers=hr,data={
            'job_id':job['id'],'details':'{"name":"Recruiter","email":"hr@demo.example.com","phone":"5551234567","address":"Example City"}'},files={'resume':('resume.pdf',b'%PDF-1.4\n','application/pdf')}).status_code==403
        assert client.delete('/api/staff/jobs/'+job['id'],headers=hr).status_code==200
        assert all(j['id']!=job['id'] for j in client.get('/api/jobs').json())
        assert any(j['id']==job['id'] for j in client.get('/api/staff/jobs',headers=hr).json())

def test_staff_only_search_and_aws_info():
    storage.init()
    with TestClient(app) as client:
        hr=_login(client,'hr@demo.example.com','hr12345678')
        applicant=_login(client,'applicant@demo.example.com','applicant123')
        assert client.get('/api/staff/applications?q=Python',headers=hr).status_code==200
        assert client.get('/api/staff/applications?q=Python',headers=applicant).status_code==403
        assert client.get('/api/staff/aws-resources',headers=hr).status_code==200
