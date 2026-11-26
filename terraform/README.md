# Resume Lens — Terraform Infrastructure

Resume Lens (internal resource prefix: `careerflow`) uses Terraform to provision AWS infrastructure and GitHub Actions to automate deployment. This guide describes the existing configuration and safe maintenance procedures.

## 1. File structure

| File                       | Responsibility                                             |
| -------------------------- | ---------------------------------------------------------- |
| `main.tf`                  | AWS resources, permissions and service integrations        |
| `versions.tf`              | Terraform/provider requirements and S3 backend declaration |
| `variables.tf`             | Configurable deployment inputs                             |
| `outputs.tf`               | Resource identifiers and application endpoint              |
| `terraform.tfvars.example` | Example input values; replace placeholders before use      |
| `user_data.sh.tftpl`       | EC2 initialization template                                |
| `.terraform.lock.hcl`      | Provider dependency lock file; retain in version control   |

## 2. Infrastructure overview

| Component                                            | Purpose                                                                                     |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| VPC, public subnet, internet gateway and route table | Network connectivity (VPC `10.42.0.0/16`, subnet `10.42.1.0/24`)                            |
| Security group                                       | HTTP/HTTPS ingress from `my_cidr`; outbound connectivity                                    |
| EC2 and Elastic IP                                   | Ubuntu 24.04 application host and stable public IPv4 address                                |
| S3                                                   | Separate private resume and deployment release buckets with AES256 encryption               |
| DynamoDB                                             | On-demand applications and jobs tables, keyed by `id`                                       |
| Cognito                                              | Email-based authentication and explicit `admin` and `hr` groups                             |
| IAM                                                  | EC2 and Lambda service roles and access policies                                            |
| Lambda                                               | Python 3.12 resume parser; S3 object-created events filtered by `resumes/` and `.pdf`       |
| Textract and Comprehend                              | Document text extraction and language analysis permissions                                  |
| CloudWatch                                           | Lambda execution logs with seven-day retention                                              |
| Systems Manager                                      | Remote application installation on EC2                                                      |
| Route 53                                             | DNS A record when both domain inputs are set; existing record imported into Terraform state |

## 3. Configuration inputs

| Variable         | Default      | Purpose                          |
| ---------------- | ------------ | -------------------------------- |
| `aws_region`     | `us-east-1`  | AWS deployment region            |
| `project`        | `careerflow` | Resource naming prefix           |
| `instance_type`  | `t3.micro`   | EC2 instance size                |
| `domain_name`    | Empty        | Full DNS name for HTTPS          |
| `hosted_zone_id` | Empty        | Existing Route 53 hosted zone ID |
| `my_cidr`        | `0.0.0.0/0`  | Allowed web ingress CIDR         |

Both domain inputs must be supplied for Terraform to manage the DNS record and return an HTTPS site URL. The updated configuration sets `allow_overwrite = true` on the Route 53 A record and includes an import block targeting `aws_route53_record.web[0]` for the existing record. Preserve the import block and coordinate DNS or state changes with the team. The deployment workflow requires `DOMAIN_NAME` to equal `cloudlyspeaking.com`; `HOSTED_ZONE_ID` must also be configured for the HTTPS path. Verify TLS before entering credentials or uploading applicant data. The HTTP endpoint is intended for infrastructure smoke tests only.

## 4. Remote state management

The S3 backend is declared in `versions.tf` and configured during GitHub Actions initialization. The state key is `careerflow/app.tfstate`. The workflow enables encryption and S3 lockfile-based locking to coordinate concurrent Terraform operations. The bootstrap helper (`../scripts/bootstrap_github.py`) configures the state bucket with versioning, encryption and public access blocking, and creates a GitHub OIDC role.

GitHub Actions uses Terraform 1.10.5. The configuration declares Terraform >= 1.6.0, but the existing S3 lockfile workflow requires a version supporting `use_lockfile`; use 1.10.5 to match CI.

Do not rerun bootstrap or migrate state merely to validate documentation. Never commit state files, state backups, credentials or real applicant documents. State may contain sensitive information.

## 5. CI/CD workflow

The repository has two existing workflows:

- `.github/workflows/ci.yml` (`Validate`): runs Python syntax checks, React build and Terraform formatting on pull requests and pushes to `main`. It formats before checking formatting, so it does not independently enforce the original committed formatting.
- `.github/workflows/aws-lab.yml` (`AWS Lab Deploy or Destroy`): manually dispatched, restricted to `main`, and serialized using the `careerflow-terraform` concurrency group.

The deployment workflow uses GitHub OIDC to assume an AWS role, initializes remote state, validates Terraform, checks the required domain, provisions resources, builds React, uploads a release archive to S3 and installs the application through Systems Manager. It reports the deployed site URL. The deploy workflow checks the domain name but does not itself verify a successful TLS handshake. The destroy option removes application resources and can delete candidate data; it is not a validation operation.

### GitHub configuration

| Type     | Name              | Purpose                                            |
| -------- | ----------------- | -------------------------------------------------- |
| Secret   | `AWS_ROLE_ARN`    | OIDC role to assume                                |
| Secret   | `AWS_REGION`      | AWS region                                         |
| Secret   | `TF_STATE_BUCKET` | Existing remote state bucket                       |
| Variable | `DOMAIN_NAME`     | Required by deploy workflow: `cloudlyspeaking.com` |
| Variable | `HOSTED_ZONE_ID`  | Existing hosted zone ID for DNS and HTTPS          |

The bootstrap script attaches AdministratorAccess to its lab deployment role. Use a dedicated lab account and protect `main` and workflow files. A production deployment should use a separately reviewed least-privilege role.

## 6. Safe local validation

From the repository root, use Terraform 1.10.5:

```bash
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false -input=false
terraform -chdir=terraform validate
```

Use a fresh checkout for backend-free initialization. Provider downloads require network access. Validation checks configuration syntax and consistency, not live AWS permissions or deployed resource health. Formatting checks may fail if existing files are not formatted; formatting can be handled in a separate reviewed commit. None of these commands applies or destroys AWS resources.

For documentation-only changes, inspect the Git diff and do not manually dispatch the deployment workflow. Review current workflow triggers before pushing because they may differ from this documented snapshot.

## 7. Terraform outputs

| Output               | Purpose                               |
| -------------------- | ------------------------------------- |
| `instance_id`        | EC2 instance identifier for SSM       |
| `public_ip`          | Elastic IP address                    |
| `site_url`           | Application endpoint                  |
| `release_bucket`     | Deployment artifact bucket            |
| `resume_bucket`      | Applicant document bucket             |
| `cognito_pool_id`    | Cognito user pool identifier          |
| `cognito_client_id`  | Cognito application client identifier |
| `applications_table` | Applications table name               |
| `jobs_table`         | Jobs table name                       |
| `lambda_name`        | Resume processing function name       |

## 8. Troubleshooting and operational safety

| Symptom                           | Check                                                                                               |
| --------------------------------- | --------------------------------------------------------------------------------------------------- |
| Remote state initialization fails | Confirm the configured bucket, region, OIDC role and state permissions                              |
| State lock error                  | Check for an active deployment; do not force-unlock an active operation                             |
| SSM installation fails            | Review workflow logs, instance connectivity and SSM command output                                  |
| Site unavailable                  | Check EC2 status, security group, Caddy and application service                                     |
| TLS connection fails              | Verify the required domain, hosted zone, DNS record and certificate configuration before signing in |
| Resume processing fails           | Check the S3 prefix/suffix filter, Lambda permissions and CloudWatch logs                           |

Avoid changing resource addresses, backend settings, provider versions or EC2 user data without reviewing the resulting plan. The existing EC2 configuration can replace the instance when user data changes. Both application buckets use `force_destroy = true`; destroying infrastructure may delete stored documents and deployment artifacts.

## 9. Maintenance checklist

- Review changes on a feature branch.
- Keep comments consistent with actual resource behavior.
- Run non-deployment validation and review the diff.
- Obtain team review before merging infrastructure changes.
- Never run apply or destroy for documentation-only maintenance.
