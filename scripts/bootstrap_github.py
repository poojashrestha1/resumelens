"""ONE-TIME setup. Creates persistent state bucket and a branch-restricted GitHub OIDC role.
WARNING: CI role has AdministratorAccess. Use only in a dedicated disposable AWS lab account.
This bootstrap is outside Terraform so `terraform destroy` does not remove its own state/identity.
"""
import argparse,boto3,json,sys
from botocore.exceptions import ClientError
p=argparse.ArgumentParser()
p.add_argument('--repo',required=True,help='owner/repository')
p.add_argument('--region',default='us-east-1')
p.add_argument('--branch',default='main')
a=p.parse_args()
if len(a.repo.split('/'))!=2:sys.exit('repo must look like owner/repo')
s3=boto3.client('s3',region_name=a.region);iam=boto3.client('iam');sts=boto3.client('sts')
account=sts.get_caller_identity()['Account'];bucket=f'careerflow-tfstate-{account}-{a.region}'
try:
    kwargs={'Bucket':bucket}
    if a.region!='us-east-1':kwargs['CreateBucketConfiguration']={'LocationConstraint':a.region}
    s3.create_bucket(**kwargs)
except ClientError as e:
    if e.response['Error']['Code'] not in ('BucketAlreadyOwnedByYou','BucketAlreadyExists'):raise
s3.put_public_access_block(Bucket=bucket,PublicAccessBlockConfiguration={k:True for k in ['BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets']})
s3.put_bucket_versioning(Bucket=bucket,VersioningConfiguration={'Status':'Enabled'})
s3.put_bucket_encryption(Bucket=bucket,ServerSideEncryptionConfiguration={'Rules':[{'ApplyServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]})
provider_arn=f'arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com'
try:iam.get_open_id_connect_provider(OpenIDConnectProviderArn=provider_arn)
except iam.exceptions.NoSuchEntityException:
    iam.create_open_id_connect_provider(Url='https://token.actions.githubusercontent.com',ClientIDList=['sts.amazonaws.com'])
trust={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Federated':provider_arn},'Action':'sts:AssumeRoleWithWebIdentity','Condition':{'StringEquals':{'token.actions.githubusercontent.com:aud':'sts.amazonaws.com','token.actions.githubusercontent.com:sub':f'repo:{a.repo}:ref:refs/heads/{a.branch}'}}}]}
role='careerflow-github-terraform-lab'
try:iam.create_role(RoleName=role,AssumeRolePolicyDocument=json.dumps(trust),Description='Lab-only GitHub OIDC Terraform role; branch restricted')
except iam.exceptions.EntityAlreadyExistsException:iam.update_assume_role_policy(RoleName=role,PolicyDocument=json.dumps(trust))
iam.attach_role_policy(RoleName=role,PolicyArn='arn:aws:iam::aws:policy/AdministratorAccess')
print('\nGitHub Repository > Settings > Secrets and variables > Actions > Secrets:')
print(f' AWS_ROLE_ARN = arn:aws:iam::{account}:role/{role}')
print(f' TF_STATE_BUCKET = {bucket}')
print(' AWS_REGION = '+a.region)
print('\nSECURITY: This role can administer the AWS account. Use a dedicated lab account; protect main and workflow files.')
