"""DynamoDB or SQLite for demo. No credentials stored in application tables."""
import json, sqlite3
from pathlib import Path
import boto3
from .config import settings

DATA = Path(__file__).resolve().parents[1] / 'data'
DATA.mkdir(exist_ok=True)
DB = DATA / 'careerflow.sqlite3'
SEED_JOBS = [
 {'id':'cloud-engineer','title':'Cloud Engineer','department':'Infrastructure','location':'Hybrid','type':'Full-time','description':'Design reliable cloud platforms and automate deployments.','active':True},
 {'id':'frontend-engineer','title':'Frontend Engineer','department':'Engineering','location':'Remote','type':'Full-time','description':'Build accessible React experiences.','active':True},
 {'id':'devops-engineer','title':'DevOps Engineer','department':'Platform','location':'Hybrid','type':'Full-time','description':'Build CI/CD pipelines and infrastructure as code.','active':True},
 {'id':'data-engineer','title':'Data Engineer','department':'Data','location':'Remote','type':'Full-time','description':'Build and maintain scalable data pipelines and ETL workflows using tools like Apache Spark, Airflow, and AWS Glue. Collaborate with analysts and scientists to ensure reliable data availability across the organization.','active':True},
 {'id':'ml-engineer','title':'Machine Learning Engineer','department':'AI & ML','location':'Remote','type':'Full-time','description':'Design, train, and deploy machine learning models into production. Work closely with data scientists to productionize experiments, optimize model performance, and integrate predictions into core product features.','active':True},
 {'id':'backend-engineer','title':'Backend Engineer','department':'Engineering','location':'Hybrid','type':'Full-time','description':'Develop and maintain high-performance REST and GraphQL APIs using Python or Node.js. Own service reliability, write thorough tests, and collaborate with frontend and platform teams to deliver robust features.','active':True},
 {'id':'product-manager','title':'Product Manager','department':'Product','location':'On-site','type':'Full-time','description':'Define product vision and roadmap by synthesizing customer feedback, market research, and business goals. Partner with engineering, design, and stakeholders to prioritize features and drive successful product launches.','active':True},
 {'id':'ux-designer','title':'UX Designer','department':'Design','location':'Remote','type':'Full-time','description':'Conduct user research, create wireframes and prototypes, and deliver polished UI designs. Collaborate with product and engineering to ensure a consistent, accessible, and delightful user experience across all surfaces.','active':True},
 {'id':'security-engineer','title':'Security Engineer','department':'Security','location':'Hybrid','type':'Full-time','description':'Identify and remediate vulnerabilities across infrastructure and application layers. Lead threat modeling, security reviews, and incident response. Champion secure-by-default practices and compliance across engineering teams.','active':True},
 {'id':'site-reliability-engineer','title':'Site Reliability Engineer','department':'Platform','location':'Remote','type':'Full-time','description':'Ensure platform uptime and performance through observability, on-call rotations, and reliability engineering. Drive SLO/SLA definitions, automate toil, and partner with development teams to build resilient, self-healing systems.','active':True},
 {'id':'technical-writer','title':'Technical Writer','department':'Engineering','location':'Remote','type':'Full-time','description':'Create clear, accurate, and developer-friendly documentation including API references, integration guides, and internal runbooks. Work with engineers and product managers to keep documentation up to date with every release.','active':True},
 {'id':'qa-engineer','title':'QA Engineer','department':'Engineering','location':'Hybrid','type':'Full-time','description':'Design and execute manual and automated test plans to ensure product quality. Build end-to-end test suites using tools like Playwright or Cypress, triage bugs, and work with developers to maintain a high release confidence bar.','active':True},
 {'id':'data-analyst','title':'Data Analyst','department':'Data','location':'Remote','type':'Full-time','description':'Translate business questions into data queries, dashboards, and actionable insights using SQL, Python, and BI tools like Tableau or Looker. Partner with product and operations teams to drive data-informed decision making.','active':True},
]

def init():
    if settings.app_mode == 'local':
        with sqlite3.connect(DB) as db:
            db.execute('CREATE TABLE IF NOT EXISTS applications (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            existing={row[0] for row in db.execute('SELECT id FROM jobs')}
            new_jobs=[(j['id'],json.dumps(j)) for j in SEED_JOBS if j['id'] not in existing]
            if new_jobs:
                db.executemany('INSERT INTO jobs VALUES (?,?)', new_jobs)

def table(kind):
    name = settings.applications_table if kind == 'applications' else settings.jobs_table
    return boto3.resource('dynamodb',region_name=settings.aws_region).Table(name)

def put(kind, item):
    if settings.app_mode == 'aws': table(kind).put_item(Item=item)
    else:
        with sqlite3.connect(DB) as db:db.execute(f'INSERT OR REPLACE INTO {kind} VALUES (?,?)',(item['id'],json.dumps(item)))

def get(kind, key):
    if settings.app_mode == 'aws':return table(kind).get_item(Key={'id':key}).get('Item')
    with sqlite3.connect(DB) as db:
        row=db.execute(f'SELECT data FROM {kind} WHERE id=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None

def all_items(kind):
    if settings.app_mode == 'aws':
        results=[]; params={}
        while True:
            page=table(kind).scan(**params);results+=page.get('Items',[])
            if 'LastEvaluatedKey' not in page:break
            params['ExclusiveStartKey']=page['LastEvaluatedKey']
        return results
    with sqlite3.connect(DB) as db:return [json.loads(row[0]) for row in db.execute(f'SELECT data FROM {kind}')]

def patch(kind,key,updates):
    if settings.app_mode == 'aws':
        names={f'#k{i}':k for i,k in enumerate(updates)}
        values={f':v{i}':v for i,v in enumerate(updates.values())}
        expr=', '.join(f'#k{i}=:v{i}' for i in range(len(updates)))
        table(kind).update_item(Key={'id':key},UpdateExpression='SET '+expr,ExpressionAttributeNames=names,ExpressionAttributeValues=values,ConditionExpression='attribute_exists(id)')
    else:
        item=get(kind,key)
        if not item:raise KeyError(key)
        item.update(updates);put(kind,item)

def delete(kind,key):
    if settings.app_mode=='aws':table(kind).delete_item(Key={'id':key})
    else:
        with sqlite3.connect(DB) as db:db.execute(f'DELETE FROM {kind} WHERE id=?',(key,))
