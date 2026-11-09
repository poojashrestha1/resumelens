import io, os, re, time, uuid, hmac
from datetime import datetime,timezone
from pathlib import Path
from typing import Annotated
import boto3, fitz, jwt
from botocore.exceptions import ClientError
from fastapi import FastAPI,Depends,File,Form,UploadFile,HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,EmailStr,Field
from .config import settings
from . import storage
from .auth import client, verified_user, staff, admin

app=FastAPI(title='CareerFlow API',version='2.0')
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(',')],allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Authorization','Content-Type'])
MAX_PDF=5*1024*1024

def now():return datetime.now(timezone.utc).isoformat()

def fail_aws(exc):
    code=exc.response.get('Error',{}).get('Code','Authentication error')
    raise HTTPException(400,code)

@app.on_event('startup')
def start():
    storage.init()
    if settings.app_mode=='aws' and not all([settings.s3_bucket,settings.cognito_pool_id,settings.cognito_client_id]):raise RuntimeError('AWS configuration missing')

@app.get('/api/health')
def health():return {'ok':True,'mode':settings.app_mode}

class AuthForm(BaseModel):
    email:EmailStr
    password:str=Field(min_length=8)
class ConfirmForm(BaseModel):
    email:EmailStr
    code:str
class ChallengeForm(BaseModel):
    email:EmailStr
    password:str=Field(min_length=8)
    session:str

@app.post('/api/auth/signup')
def signup(form:AuthForm):
    if settings.app_mode=='local':raise HTTPException(400,'Use demo login locally; Cognito signup is AWS-only')
    try:
        client().sign_up(ClientId=settings.cognito_client_id,Username=form.email.lower(),Password=form.password,UserAttributes=[{'Name':'email','Value':form.email.lower()}])
        return {'message':'Check email for a confirmation code'}
    except ClientError as e:fail_aws(e)

@app.post('/api/auth/confirm')
def confirm(form:ConfirmForm):
    if settings.app_mode=='local':return {'message':'Local demo'}
    try:
        client().confirm_sign_up(ClientId=settings.cognito_client_id,Username=form.email.lower(),ConfirmationCode=form.code)
        return {'message':'Email verified; you can sign in'}
    except ClientError as e:fail_aws(e)

@app.post('/api/auth/login')
def login(form:AuthForm):
    if settings.app_mode=='local':
        demo={'admin@demo.example.com':('admin12345','admin'),'hr@demo.example.com':('hr12345678','hr'),'applicant@demo.example.com':('applicant123','applicant')}
        stored=demo.get(form.email.lower())
        if not stored or not hmac.compare_digest(stored[0],form.password):raise HTTPException(401,'Invalid demo login')
        token=jwt.encode({'sub':form.email.lower(),'role':stored[1],'exp':int(time.time())+3600,'aud':'careerflow-local'},'local-only-development-key',algorithm='HS256')
        return {'access_token':token,'role':stored[1]}
    try:
        result=client().initiate_auth(ClientId=settings.cognito_client_id,AuthFlow='USER_PASSWORD_AUTH',AuthParameters={'USERNAME':form.email.lower(),'PASSWORD':form.password})
        if result.get('ChallengeName')=='NEW_PASSWORD_REQUIRED':return {'challenge':'NEW_PASSWORD_REQUIRED','session':result['Session']}
        return {'access_token':result['AuthenticationResult']['AccessToken'],'id_token':result['AuthenticationResult']['IdToken']}
    except ClientError as e:fail_aws(e)

@app.post('/api/auth/challenge')
def challenge(form:ChallengeForm):
    if settings.app_mode=='local':raise HTTPException(400,'Only available in AWS mode')
    try:
        response=client().respond_to_auth_challenge(ClientId=settings.cognito_client_id,ChallengeName='NEW_PASSWORD_REQUIRED',Session=form.session,ChallengeResponses={'USERNAME':form.email.lower(),'NEW_PASSWORD':form.password})
        return {'access_token':response['AuthenticationResult']['AccessToken'],'id_token':response['AuthenticationResult']['IdToken']}
    except ClientError as e:fail_aws(e)

@app.get('/api/me')
def me(user=Depends(verified_user)):
    return user

@app.get('/api/jobs')
def jobs():return sorted([j for j in storage.all_items('jobs') if j.get('active',True)],key=lambda j:j['title'])

@app.get('/api/staff/jobs')
def staff_jobs(_=Depends(staff)):
    return sorted(storage.all_items('jobs'),key=lambda j:j.get('title',''))


class JobForm(BaseModel):
    title:str=Field(min_length=3,max_length=100)
    department:str=Field(min_length=2,max_length=100)
    location:str=Field(min_length=2,max_length=100)
    type:str='Full-time'
    description:str=Field(min_length=5,max_length=2000)
    active:bool=True

@app.post('/api/staff/jobs',status_code=201)
def create_job(form:JobForm,_=Depends(staff)):
    job={'id':str(uuid.uuid4()),**form.model_dump()};storage.put('jobs',job);return job

@app.patch('/api/staff/jobs/{job_id}')
def edit_job(job_id:str,form:JobForm,_=Depends(staff)):
    if not storage.get('jobs',job_id):raise HTTPException(404,'Job not found')
    storage.patch('jobs',job_id,form.model_dump());return storage.get('jobs',job_id)

@app.delete('/api/staff/jobs/{job_id}')
def archive_job(job_id:str,_=Depends(staff)):
    if not storage.get('jobs',job_id):raise HTTPException(404,'Job not found')
    # Retain applications and audit records; do not hard-delete positions.
    storage.patch('jobs',job_id,{'active':False,'archived_at':now()})
    return {'message':'Position archived'}

class RecruiterForm(BaseModel):
    email:EmailStr

@app.get('/api/admin/recruiters')
def recruiters(_=Depends(admin)):
    if settings.app_mode=='local':return [{'email':'hr@demo.example.com','enabled':True}]
    # Small demo pool; pagination for accounts at larger scale.
    members=[];token=None
    while True:
        args={'UserPoolId':settings.cognito_pool_id,'GroupName':'hr','Limit':60}
        if token:args['NextToken']=token
        res=client().list_users_in_group(**args)
        for u in res.get('Users',[]):
            attrs={a['Name']:a['Value'] for a in u.get('Attributes',[])}
            members.append({'email':attrs.get('email',u['Username']),'enabled':u['Enabled'],'username':u['Username']})
        token=res.get('NextToken')
        if not token:break
    return members

@app.post('/api/admin/recruiters',status_code=201)
def add_recruiter(form:RecruiterForm,_=Depends(admin)):
    if settings.app_mode=='local':raise HTTPException(400,'Recruiter invitations require Cognito in AWS mode')
    email=form.email.lower()
    try:
        client().admin_create_user(UserPoolId=settings.cognito_pool_id,Username=email,UserAttributes=[{'Name':'email','Value':email},{'Name':'email_verified','Value':'true'}],DesiredDeliveryMediums=['EMAIL'])
        client().admin_add_user_to_group(UserPoolId=settings.cognito_pool_id,Username=email,GroupName='hr')
        return {'message':'Recruiter invitation created; temporary password sent via email'}
    except ClientError as e:fail_aws(e)

@app.post('/api/admin/recruiters/{username}/disable')
def disable_recruiter(username:str,_=Depends(admin)):
    if settings.app_mode=='local':raise HTTPException(400,'Requires AWS mode')
    # Restrict operation to users currently in hr group (never disable admin by this route).
    member=client().admin_list_groups_for_user(UserPoolId=settings.cognito_pool_id,Username=username)
    if 'hr' not in [g['GroupName'] for g in member['Groups']]:raise HTTPException(403,'Not an HR user')
    client().admin_disable_user(UserPoolId=settings.cognito_pool_id,Username=username)
    return {'message':'Recruiter disabled'}

@app.post('/api/admin/recruiters/{username}/enable')
def enable_recruiter(username:str,_=Depends(admin)):
    if settings.app_mode=='local':raise HTTPException(400,'Requires AWS mode')
    member=client().admin_list_groups_for_user(UserPoolId=settings.cognito_pool_id,Username=username)
    if 'hr' not in [g['GroupName'] for g in member['Groups']]:raise HTTPException(403,'Not an HR user')
    client().admin_enable_user(UserPoolId=settings.cognito_pool_id,Username=username)
    return {'message':'Recruiter enabled'}

def education(text):
    result=[re.sub(r'\s+',' ',x).strip()[:180] for x in text.splitlines() if re.search(r'\b(bachelor|master|university|college|degree|education|btech|mtech|phd)\b',x,re.I)]
    return ' · '.join(result[:3]) or 'Needs manual review'

@app.post('/api/applications',status_code=201)
async def submit(job_id:Annotated[str,Form()],name:Annotated[str,Form()],phone:Annotated[str,Form()],resume:Annotated[UploadFile,File()],user=Depends(verified_user)):
    if user['role']!='applicant':raise HTTPException(403,'Applicant account required')
    job=storage.get('jobs',job_id)
    if not job or not job.get('active',True):raise HTTPException(404,'Job not available')
    if not 2<=len(name.strip())<=120 or len(phone)>40:raise HTTPException(422,'Invalid application details')
    data=await resume.read(MAX_PDF+1)
    if len(data)>MAX_PDF:raise HTTPException(413,'PDF must be at most 5 MB')
    if not data.startswith(b'%PDF-'):raise HTTPException(415,'PDF required')
    try:
        with fitz.open(stream=data,filetype='pdf') as doc:
            if doc.needs_pass or not 1<=len(doc)<=25:raise ValueError('Invalid page count or encrypted file')
            text='\n'.join(page.get_text() for page in doc) if settings.app_mode=='local' else ''
    except Exception:raise HTTPException(415,'Unreadable or password-protected PDF')
    user_sub=user['sub'];app_id=str(uuid.uuid4());key=f'resumes/{app_id}.pdf'
    # Store applicant subject, not email supplied by browser.
    record={'id':app_id,'applicant_sub':user_sub,'name':name.strip(),'phone':phone.strip(),'position':job['title'],'job_id':job_id,'education':education(text) if settings.app_mode=='local' else 'Pending extraction','skills':[],'experience':'','volunteer_experience':'','resume_text':'','processing_warning':'','section_evidence':[],'resume_key':key,'processing_status':'processing' if settings.app_mode=='aws' else 'review_required','review_status':'applied','created_at':now(),'processing_error':''}
    if settings.app_mode=='local' and text.strip():
        # Shared parser matches production Lambda behavior in offline demonstrations.
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'aws'))
        from resume_parser import parse_resume
        record.update(parse_resume(text))
    storage.put('applications',record)
    try:
        if settings.app_mode=='aws':
            boto3.client('s3',region_name=settings.aws_region).put_object(Bucket=settings.s3_bucket,Key=key,Body=data,ContentType='application/pdf',ServerSideEncryption='AES256')
        else:
            folder=storage.DATA/'resumes';folder.mkdir(exist_ok=True);(folder/f'{app_id}.pdf').write_bytes(data)
    except Exception:
        storage.patch('applications',app_id,{'processing_status':'upload_failed'})
        raise HTTPException(502,'Resume upload failed')
    return {'id':app_id,'message':'Application submitted'}

@app.get('/api/me/applications')
def my_applications(user=Depends(verified_user)):
    return sorted([a for a in storage.all_items('applications') if a.get('applicant_sub')==user['sub']],key=lambda x:x['created_at'],reverse=True)

@app.get('/api/staff/applications')
def staff_applications(q:str='',job_id:str='',_ = Depends(staff)):
    # Small teaching/demo dataset only: DynamoDB Scan isn't a scalable search engine.
    # Matches raw Textract text AND parsed fields; cap query length for safety.
    if len(q)>150:raise HTTPException(422,'Query too long')
    needle=q.strip().casefold()
    results=[]
    for item in storage.all_items('applications'):
        if job_id and item.get('job_id')!=job_id:continue
        if needle:
            searchable=' '.join(str(item.get(k,'')) for k in ('name','position','skills','education','experience','volunteer_experience','resume_text'))
            if needle not in searchable.casefold():continue
        results.append(item)
    return sorted(results,key=lambda x:x.get('created_at',''),reverse=True)[:250]


@app.get('/api/staff/aws-resources')
def aws_resources(_=Depends(staff)):
    # Configuration and observed application states, not a live AWS Health assertion.
    records=storage.all_items('applications')
    state_counts={status:sum(a.get('processing_status')==status for a in records)
                  for status in ('processing','completed','review_required','upload_failed')}
    return {'region':settings.aws_region,'app_mode':settings.app_mode,
            'processing_counts':state_counts,
            'services':[
                {'name':'Amazon EC2 + Caddy','purpose':'Hosts React frontend and FastAPI API'},
                {'name':'Amazon Cognito','purpose':'Authenticates users and assigns Admin/HR groups'},
                {'name':'Amazon S3','purpose':'Stores original private PDF résumés','resource':settings.s3_bucket},
                {'name':'AWS Lambda','purpose':'Processes uploaded documents asynchronously'},
                {'name':'Amazon Textract','purpose':'OCR extraction of printed résumé text'},
                {'name':'Amazon Comprehend','purpose':'Optional named entity enrichment; does not determine experience'},
                {'name':'Amazon DynamoDB','purpose':'Stores job and candidate records','resource':settings.applications_table},
                {'name':'Amazon CloudWatch','purpose':'Captures Lambda and application operational logs'}]}

class Review(BaseModel):
    status:str

@app.patch('/api/staff/applications/{application_id}/status')
def review_status(application_id:str,body:Review,_=Depends(staff)):
    if body.status not in ('applied','in_review','interview','rejected','offer'):raise HTTPException(422,'Invalid status')
    if not storage.get('applications',application_id):raise HTTPException(404,'Application not found')
    storage.patch('applications',application_id,{'review_status':body.status});return {'status':body.status}

@app.get('/api/applications/{application_id}/resume')
def resume(application_id:str,user=Depends(verified_user)):
    record=storage.get('applications',application_id)
    if not record:raise HTTPException(404,'Not found')
    if user['role'] not in ('hr','admin') and record['applicant_sub']!=user['sub']:raise HTTPException(403,'Not allowed')
    if settings.app_mode=='aws':
        try:
            obj=boto3.client('s3',region_name=settings.aws_region).get_object(Bucket=settings.s3_bucket,Key=record['resume_key'])
            return StreamingResponse(obj['Body'].iter_chunks(chunk_size=65536),media_type='application/pdf',headers={'Content-Disposition':'inline; filename="resume.pdf"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
        except ClientError:raise HTTPException(404,'Resume missing')
    path=storage.DATA/'resumes'/f'{application_id}.pdf'
    if not path.exists():raise HTTPException(404,'Resume missing')
    return StreamingResponse(io.BytesIO(path.read_bytes()),media_type='application/pdf',headers={'Content-Disposition':'inline; filename="resume.pdf"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
