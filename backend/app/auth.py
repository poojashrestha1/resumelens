"""Cognito access token verification; dev-mode auth is explicitly localhost-only."""
import os, time
from functools import lru_cache
from typing import Annotated
import boto3, jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings

bearer=HTTPBearer(auto_error=False)

def client():return boto3.client('cognito-idp',region_name=settings.aws_region)

@lru_cache(maxsize=1)
def jwks():
    return PyJWKClient(f'https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_pool_id}/.well-known/jwks.json')

def verified_user(creds:Annotated[HTTPAuthorizationCredentials | None,Depends(bearer)]):
    if not creds:raise HTTPException(401,'Please sign in')
    token=creds.credentials
    if settings.app_mode=='local':
        try:
            value=jwt.decode(token,'local-only-development-key',algorithms=['HS256'],audience='careerflow-local')
            if value['exp']<time.time():raise ValueError()
            return value
        except Exception:raise HTTPException(401,'Invalid session')
    try:
        key=jwks().get_signing_key_from_jwt(token).key
        claims=jwt.decode(token,key,algorithms=['RS256'],issuer=f'https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_pool_id}',options={'verify_aud':False})
        if claims.get('token_use')!='access' or claims.get('client_id')!=settings.cognito_client_id:raise ValueError()
        return {'sub':claims['sub'],'role':next((r for r in ['admin','hr'] if r in claims.get('cognito:groups',[])),'applicant')}
    except Exception:raise HTTPException(401,'Invalid or expired Cognito access token')

def staff(user=Depends(verified_user)):
    if user['role'] not in ('hr','admin'):raise HTTPException(403,'HR access required')
    return user

def admin(user=Depends(verified_user)):
    if user['role']!='admin':raise HTTPException(403,'Admin access required')
    return user
