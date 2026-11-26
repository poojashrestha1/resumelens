# ResumeLens
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_mode: str = 'local'
    aws_region: str = 'us-east-1'
    s3_bucket: str = ''
    applications_table: str = 'careerflow-applications'
    jobs_table: str = 'careerflow-jobs'
    cognito_pool_id: str = ''
    cognito_client_id: str = ''
    cors_origins: str = 'http://localhost:5173'
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

settings = Settings()
