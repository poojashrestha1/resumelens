"""S3 PDF -> Textract OCR -> section-aware parsing -> Comprehend enrichment -> DynamoDB.

Textract is the OCR layer, not a structured CV parser. Incomplete extraction is
marked review_required rather than publishing invented values.
"""
import json, os, re, time, urllib.parse
import boto3
from resume_parser import parse_resume

REGION=os.environ.get('AWS_REGION_NAME',os.environ.get('AWS_REGION','us-east-1'))
BUCKET=os.environ['S3_BUCKET']; TABLE=os.environ['APPLICATIONS_TABLE']
textract=boto3.client('textract',region_name=REGION)
comprehend=boto3.client('comprehend',region_name=REGION)
table=boto3.resource('dynamodb',region_name=REGION).Table(TABLE)


def detect_text(bucket,key):
    job_id=textract.start_document_text_detection(DocumentLocation={'S3Object':{'Bucket':bucket,'Name':key}})['JobId']
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        page=textract.get_document_text_detection(JobId=job_id)
        status=page['JobStatus']
        if status=='SUCCEEDED':break
        if status in ('FAILED','PARTIAL_SUCCESS'):
            raise RuntimeError('Textract returned '+status)
        time.sleep(4)
    else:raise TimeoutError('Textract processing exceeded 240 seconds')
    lines=[]; token=None
    while True:
        kwargs={'JobId':job_id}
        if token:kwargs['NextToken']=token
        result=textract.get_document_text_detection(**kwargs)
        for block in result.get('Blocks',[]):
            if block.get('BlockType')=='LINE' and block.get('Text'):
                lines.append((block.get('Page',1),block['Text']))
        token=result.get('NextToken')
        if not token:break
    return '\n'.join(t for _,t in lines)


def enrich(text):
    """Best-effort NER only; do not let service failure discard a valid CV."""
    try:
        # Comprehend accepts <= 5 KB per request, UTF-8 boundaries matter.
        sample=text.encode('utf-8')[:4500].decode('utf-8','ignore')
        return [{'text':e['Text'],'type':e['Type'],'score':round(float(e['Score']),3)}
                for e in comprehend.detect_entities(Text=sample,LanguageCode='en').get('Entities',[])
                if e.get('Score',0)>=0.85][:40]
    except Exception:
        return []


def handler(event,context):
    for record in event.get('Records',[]):
        key=urllib.parse.unquote_plus(record['s3']['object']['key'])
        bucket=record['s3']['bucket']['name']
        if bucket!=BUCKET or not re.fullmatch(r'resumes/[0-9a-f-]{36}\.pdf',key):continue
        app_id=key.rsplit('/',1)[-1][:-4]
        started=time.monotonic()
        try:
            text=detect_text(bucket,key)
            if len(text.strip())<30:raise ValueError('Textract returned insufficient text')
            parsed=parse_resume(text)
            parsed['comprehend_entities']=enrich(text)
            parsed['processing_duration_ms']=int((time.monotonic()-started)*1000)
            parsed['processing_error']=''
            values={':'+k:v for k,v in parsed.items()}
            names={'#'+k:k for k in parsed}
            expression='SET '+', '.join('#'+k+'=:'+k for k in parsed)
            table.update_item(Key={'id':app_id},ConditionExpression='attribute_exists(id)',UpdateExpression=expression,ExpressionAttributeNames=names,ExpressionAttributeValues=values)
        except Exception as exc:
            table.update_item(Key={'id':app_id},ConditionExpression='attribute_exists(id)',UpdateExpression='SET processing_status=:p, processing_error=:e',ExpressionAttributeValues={':p':'review_required',':e':type(exc).__name__+': '+str(exc)[:180]})
            # Intentional: preserve review_required status for HR and surface errors in CloudWatch.
            raise
    return {'ok':True}
