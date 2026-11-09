data "aws_caller_identity" "current" {
}
data "aws_availability_zones" "available" {
  state = "available"
}
data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}
resource "random_id" "suffix" {
  byte_length = 4
}
locals {
  prefix    = "${var.project}-${random_id.suffix.hex}"
  use_https = var.domain_name != "" && var.hosted_zone_id != ""
}

resource "aws_vpc" "main" {
  cidr_block = "10.42.0.0/16"
  enable_dns_support = true
  enable_dns_hostnames = true
  tags = { Name = "${local.prefix}-vpc" }
}
resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id
  availability_zone = data.aws_availability_zones.available.names[0]
  cidr_block = "10.42.1.0/24"
  map_public_ip_on_launch = true
  tags = { Name = "${local.prefix}-public" }
}
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags = { Name = "${local.prefix}-igw" }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
   gateway_id = aws_internet_gateway.main.id
  }
}
resource "aws_route_table_association" "public" {
  subnet_id = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}
resource "aws_security_group" "web" {
  name_prefix = "${local.prefix}-web-"
  vpc_id = aws_vpc.main.id
  ingress {
    description = "HTTP for Caddy ACME or initial checks"
   from_port = 80
   to_port = 80
   protocol = "tcp"
   cidr_blocks = [var.my_cidr]
  }
  ingress {
    description = "HTTPS"
   from_port = 443
   to_port = 443
   protocol = "tcp"
   cidr_blocks = [var.my_cidr]
  }
  egress {
    from_port = 0
   to_port = 0
   protocol = "-1"
   cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_s3_bucket" "resumes" {
  bucket = "${local.prefix}-resumes"
   force_destroy = true
  }
resource "aws_s3_bucket_public_access_block" "resumes" {
  bucket = aws_s3_bucket.resumes.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "resumes" {
  bucket = aws_s3_bucket.resumes.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket" "releases" {
  bucket = "${local.prefix}-releases"
   force_destroy = true
  }
resource "aws_s3_bucket_public_access_block" "releases" {
  bucket = aws_s3_bucket.releases.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "releases" {
  bucket = aws_s3_bucket.releases.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_dynamodb_table" "applications" {
  name = "${local.prefix}-applications"
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "id"
  attribute {
    name = "id"
   type = "S"
  }
}
resource "aws_dynamodb_table" "jobs" {
  name = "${local.prefix}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "id"
  attribute {
    name = "id"
   type = "S"
  }
}
resource "aws_dynamodb_table_item" "sample_jobs" {
  for_each = {
    "cloud-engineer" = { title="Cloud Engineer", department="Infrastructure", location="Hybrid", description="Develop AWS cloud infrastructure using Terraform and Python." }
    "devops-engineer" = { title="DevOps Engineer", department="Platform", location="Remote", description="Build CI/CD pipelines, Docker workflows, and observability." }
    "frontend-engineer" = { title="Frontend Engineer", department="Engineering", location="Remote", description="Build accessible web applications with React." }
  }
  table_name = aws_dynamodb_table.jobs.name
  hash_key = aws_dynamodb_table.jobs.hash_key
  item = jsonencode({
    id = { S = each.key }
    title = { S = each.value.title }
    department = { S = each.value.department }
    location = { S = each.value.location }
    description = { S = each.value.description }
    type = { S = "Full-time" }
    active = { BOOL = true }
  })
}

resource "aws_cognito_user_pool" "users" {
  name = "${local.prefix}-users"
  username_attributes = ["email"]
  auto_verified_attributes = ["email"]
  password_policy {
    minimum_length = 10
   require_lowercase = true
   require_uppercase = true
   require_numbers = true
   require_symbols = false
  }
  admin_create_user_config {
    allow_admin_create_user_only = false
  }
  account_recovery_setting {
    recovery_mechanism {
      name = "verified_email"
      priority = 1
    }
  }
  lifecycle {
    prevent_destroy = false
  }
}
resource "aws_cognito_user_pool_client" "web" {
  name = "${local.prefix}-web"
  user_pool_id = aws_cognito_user_pool.users.id
  generate_secret = false
  explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH","ALLOW_REFRESH_TOKEN_AUTH","ALLOW_USER_SRP_AUTH"]
  prevent_user_existence_errors = "ENABLED"
}
resource "aws_cognito_user_group" "admin" {
  user_pool_id = aws_cognito_user_pool.users.id
   name = "admin"
   precedence = 0
  }
resource "aws_cognito_user_group" "hr" {
  user_pool_id = aws_cognito_user_pool.users.id
   name = "hr"
   precedence = 1
  }

resource "aws_iam_role" "ec2" {
  name = "${local.prefix}-ec2-role"
  assume_role_policy = jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Principal={Service="ec2.amazonaws.com"},Action="sts:AssumeRole"}]})
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy" "app" {
  role = aws_iam_role.ec2.id
  policy = jsonencode({Version="2012-10-17",Statement=[
    {Effect="Allow",Action=["s3:PutObject","s3:GetObject"],Resource=["${aws_s3_bucket.resumes.arn}/resumes/*","${aws_s3_bucket.releases.arn}/*"]},
    {Effect="Allow",Action=["dynamodb:PutItem","dynamodb:GetItem","dynamodb:Scan","dynamodb:UpdateItem","dynamodb:DeleteItem"],Resource=[aws_dynamodb_table.applications.arn,aws_dynamodb_table.jobs.arn]},
    {Effect="Allow",Action=["cognito-idp:AdminCreateUser","cognito-idp:AdminAddUserToGroup","cognito-idp:ListUsersInGroup","cognito-idp:AdminListGroupsForUser","cognito-idp:AdminDisableUser","cognito-idp:AdminEnableUser"],Resource=aws_cognito_user_pool.users.arn}
  ]})
}
resource "aws_iam_instance_profile" "ec2" {
  name = "${local.prefix}-profile"
   role = aws_iam_role.ec2.name
  }

resource "aws_iam_role" "lambda" {
  name = "${local.prefix}-lambda-role"
  assume_role_policy = jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Principal={Service="lambda.amazonaws.com"},Action="sts:AssumeRole"}]})
}
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
resource "aws_iam_role_policy" "lambda" {
  role = aws_iam_role.lambda.id
  policy = jsonencode({Version="2012-10-17",Statement=[
    {Effect="Allow",Action=["s3:GetObject"],Resource=["${aws_s3_bucket.resumes.arn}/resumes/*"]},
    {Effect="Allow",Action=["dynamodb:UpdateItem"],Resource=[aws_dynamodb_table.applications.arn]},
    {Effect="Allow",Action=["textract:StartDocumentTextDetection","textract:GetDocumentTextDetection","comprehend:DetectEntities","comprehend:DetectKeyPhrases"],Resource="*"}
  ]})
}

data "archive_file" "lambda" {
  type = "zip"
  source_dir = "${path.module}/../aws"
  output_path = "${path.module}/lambda-package.zip"
}
resource "aws_lambda_function" "resume" {
  function_name = "${local.prefix}-resume-parser"
  role = aws_iam_role.lambda.arn
  filename = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  runtime = "python3.12"
  handler = "lambda_function.handler"
  timeout = 300
  memory_size = 256
  environment {
    variables = { AWS_REGION_NAME = var.aws_region, S3_BUCKET = aws_s3_bucket.resumes.bucket, APPLICATIONS_TABLE = aws_dynamodb_table.applications.name }
  }
  depends_on = [aws_iam_role_policy.lambda,aws_iam_role_policy_attachment.lambda_logs]
}
resource "aws_cloudwatch_log_group" "resume" {
  name = "/aws/lambda/${aws_lambda_function.resume.function_name}"
  retention_in_days = 7
}
resource "aws_lambda_permission" "allow_s3" {
  statement_id = "AllowS3ObjectCreated"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.resume.function_name
  principal = "s3.amazonaws.com"
  source_arn = aws_s3_bucket.resumes.arn
  source_account = data.aws_caller_identity.current.account_id
}
resource "aws_s3_bucket_notification" "resume" {
  bucket = aws_s3_bucket.resumes.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.resume.arn
   events = ["s3:ObjectCreated:*"]
   filter_prefix = "resumes/"
   filter_suffix = ".pdf"
  }
  depends_on = [aws_lambda_permission.allow_s3]
}

resource "aws_instance" "web" {
  ami = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type = var.instance_type
  subnet_id = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id]
  iam_instance_profile = aws_iam_instance_profile.ec2.name
  associate_public_ip_address = true
  user_data = templatefile("${path.module}/user_data.sh.tftpl",{
    bucket=aws_s3_bucket.resumes.bucket, releases=aws_s3_bucket.releases.bucket,
    applications=aws_dynamodb_table.applications.name, jobs=aws_dynamodb_table.jobs.name,
    pool=aws_cognito_user_pool.users.id, client=aws_cognito_user_pool_client.web.id,
    region=var.aws_region, domain=var.domain_name
  })
  user_data_replace_on_change = true
  root_block_device {
    volume_size = 16
   volume_type = "gp3"
   encrypted = true
  }
  metadata_options {
    http_tokens = "required"
  }
  tags = { Name = "${local.prefix}-ec2"
   Project = var.project }
  depends_on = [aws_iam_role_policy.app,aws_iam_role_policy_attachment.ssm]
}
resource "aws_eip" "web" {
  domain = "vpc"
  instance = aws_instance.web.id
  depends_on = [aws_internet_gateway.main]
}
resource "aws_route53_record" "web" {
  count = local.use_https ? 1 : 0
  zone_id = var.hosted_zone_id
  name = var.domain_name
  type = "A"
  ttl = 60
  records = [aws_eip.web.public_ip]
}
