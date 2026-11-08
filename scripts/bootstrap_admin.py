"""Run after every fresh terraform apply. Creates the first administrator securely."""
import argparse,getpass,boto3
p=argparse.ArgumentParser()
p.add_argument('--pool',required=True)
p.add_argument('--email',required=True)
p.add_argument('--region',default='us-east-1')
a=p.parse_args();c=boto3.client('cognito-idp',region_name=a.region)
password=getpass.getpass('Choose strong admin password (10+ chars, upper/lower/digit): ')
if len(password)<10:raise SystemExit('Password too short')
try:
    c.admin_create_user(UserPoolId=a.pool,Username=a.email.lower(),MessageAction='SUPPRESS',UserAttributes=[{'Name':'email','Value':a.email.lower()},{'Name':'email_verified','Value':'true'}])
except c.exceptions.UsernameExistsException:pass
c.admin_set_user_password(UserPoolId=a.pool,Username=a.email.lower(),Password=password,Permanent=True)
c.admin_add_user_to_group(UserPoolId=a.pool,Username=a.email.lower(),GroupName='admin')
print('Admin account ready; password was not saved to a file.')
