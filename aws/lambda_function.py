"""S3 upload -> Textract asynchronous PDF extraction -> Comprehend -> DynamoDB.
Simple demo implementation polls for up to 4 minutes; for production switch to SNS/SQS completion.
"""
import os,re,json,time,urllib.parse
import boto3
from botocore.exceptions import ClientError

REGION=os.environ['AWS_REGION'];BUCKET=os.environ['S3_BUCKET'];TABLE=os.environ['APPLICATIONS_TABLE']
textract=boto3.client('textract',region_name=REGION)
comprehend=boto3.client('comprehend',region_name=REGION)
table=boto3.resource('dynamodb',region_name=REGION).Table(TABLE)
SKILLS=['Python','Java','JavaScript','React','FastAPI','AWS','Terraform','Docker','Kubernetes','SQL','Linux','Git','CI/CD']

def detect_text(bucket,key):
    job=textract.start_document_text_detection(DocumentLocation={'S3Object':{'Bucket':bucket,'Name':key}})['JobId']
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        result=textract.get_document_text_detection(JobId=job)
        if result['JobStatus']=='SUCCEEDED':break
        if result['JobStatus']=='FAILED':raise RuntimeError('Textract job failed')
        time.sleep(4)
    else:raise TimeoutError('Textract processing timeout')
    lines=[]
    while True:
        lines += [b['Text'] for b in result.get('Blocks',[]) if b.get('BlockType')=='LINE']
        if not result.get('NextToken'):break
        result=textract.get_document_text_detection(JobId=job,NextToken=result['NextToken'])
    return '\n'.join(lines)

def education(text):
    lines=[re.sub(r'\s+',' ',s).strip()[:180] for s in text.splitlines()]
    return ' · '.join(s for s in lines if re.search(r'\b(bachelor|master|university|college|degree|education|btech|mtech|phd)\b',s,re.I))[:500] or 'Needs manual review'

def handler(event,context):
    for rec in event.get('Records',[]):
        key=urllib.parse.unquote_plus(rec['s3']['object']['key']);bucket=rec['s3']['bucket']['name']
        if bucket!=BUCKET or not re.fullmatch(r'resumes/[0-9a-f-]{36}\.pdf',key):continue
        app_id=key.split('/')[-1][:-4]
        try:
            full_text=detect_text(bucket,key)
            if not full_text.strip():raise ValueError('No text found')
            sample=full_text.encode('utf-8')[:4900].decode('utf-8','ignore')
            entities=comprehend.detect_entities(Text=sample,LanguageCode='en').get('Entities',[])
            phrases=comprehend.detect_key_phrases(Text=sample,LanguageCode='en').get('KeyPhrases',[])
            people=[e['Text'] for e in entities if e.get('Type')=='PERSON' and e.get('Score',0)>=0.8]
            skills=[s for s in SKILLS if re.search(r'(?<!\w)'+re.escape(s)+r'(?!\w)',full_text,re.I)]
            table.update_item(Key={'id':app_id},ConditionExpression='attribute_exists(id)',UpdateExpression='SET education=:e, skills=:s, experience=:x, processing_status=:p, processing_error=:err, detected_name=:n',ExpressionAttributeValues={':e':education(full_text),':s':json.dumps(skills),':x':' · '.join(x['Text'] for x in phrases[:6]),':p':'completed',':err':'',':n':people[0] if people else ''})
        except Exception as exc:
            table.update_item(Key={'id':app_id},ConditionExpression='attribute_exists(id)',UpdateExpression='SET processing_status=:p, processing_error=:e',ExpressionAttributeValues={':p':'review_required',':e':type(exc).__name__})
            raise
    return {'ok':True}
