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
]

def init():
    if settings.app_mode == 'local':
        with sqlite3.connect(DB) as db:
            db.execute('CREATE TABLE IF NOT EXISTS applications (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            if not db.execute('SELECT 1 FROM jobs LIMIT 1').fetchone():
                db.executemany('INSERT INTO jobs VALUES (?,?)', [(j['id'],json.dumps(j)) for j in SEED_JOBS])

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
