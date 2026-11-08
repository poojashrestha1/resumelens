from fastapi.testclient import TestClient
from app.main import app
from app import storage

def test_health_and_sample_jobs():
    storage.init()
    with TestClient(app) as client:
        assert client.get('/api/health').status_code == 200
        assert len(client.get('/api/jobs').json()) >= 1

def test_no_anonymous_applications():
    with TestClient(app) as client:
        assert client.get('/api/me/applications').status_code in (401,403)
        assert client.get('/api/staff/applications').status_code in (401,403)
