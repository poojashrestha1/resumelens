# ResumeLens — ATS + editable application form (v4 extraction fixes included)

> A **university lab/demo**, not a production ATS. Contains personal résumé data: use fictitious/synthetic candidates while testing. Infrastructure creation has **not** been exercised against a live AWS account in this deliverable; review `terraform plan` before deploying.

## What is included

- Public React careers site, job listing, and **applicant-only** editable application form with optional PDF résumé autofill.
- Cognito applicant **sign-up**, email confirmation, sign-in, and **My Applications** history/status.
- Protected **HR dashboard**: candidates, extracted education, résumé PDF, review statuses.
- Protected **Admin dashboard**: recruit HR by email, enable/disable HR, post jobs.
- One EC2 instance (Ubuntu, Caddy, systemd, FastAPI, React static build), with no SSH port; SSM for deployment.
- VPC, public subnet, internet gateway, routes, security group, 16 GiB encrypted EBS, EIP.
- Cognito pool, admin/hr groups; 2 DynamoDB on-demand tables, private S3 résumé/release buckets.
- S3-event Lambda triggers **asynchronous Textract** for multipage PDFs, enriches using Comprehend, updates DynamoDB; CloudWatch Logs.
- GitHub Actions CI validation plus manual `deploy`/`destroy` pipeline using **OIDC** (no long-lived AWS credentials).
- Terraform S3 remote state bucket & GitHub role bootstrapped once outside the disposable application stack.

### Architecture

```text
Browser -- HTTPS / Caddy on EC2 -- React static files
          |                       \-- /api/* -> FastAPI (localhost:8000)
          |                                     | Cognito access JWT verified
          |                                     | DynamoDB: jobs / applications
          |                                     \ S3 private résumés
          |                                              |
          |                                          ObjectCreated
          |                                              v
          |                                Lambda -> Textract -> Comprehend
          |                                              |
          |                                         DynamoDB update
          \------ Cognito sign-up/auth via FastAPI --------+
```

**Do not treat this as a resume screening/hiring AI**: extracted education/skills are heuristic fields for HR review, not an automated qualification score.

## 0. Prerequisites

- AWS account with permission to create IAM, EC2, VPC, S3, DynamoDB, Lambda, Cognito, CloudWatch, EIP, Route 53 (optional).
- AWS CLI configured locally with credentials for a **dedicated sandbox AWS account**.
- Python 3.11+, Node.js 22+, Git, Terraform 1.10+, GitHub repo.
- **For publicly accessible login**: a DNS domain you own in an *existing* Route 53 hosted zone. Enter its ID and a record name (e.g. `careers.example.com`). Caddy obtains a free Let's Encrypt cert, so **ACM is not needed** and no paid ALB is provisioned. Route 53 hosted zone/domain may have separate costs.
- Without domain DNS, the site serves plain HTTP on the EC2 IP for infrastructure smoke tests **only**. **Do not use real passwords or real applicants over plain HTTP**. For a login demo without a domain, use the local SSM tunnel described below.
- Verify your region's instance quotas (t3.micro), Cognito, Comprehend, and Textract availability and any associated charges.

## 1. GitHub setup / one-time bootstrap

Upload the entire directory to a **private GitHub repository**. Set the default branch to `main` and enable protection/restricted writes to the `main` branch and GitHub workflow changes.

```bash
python3 -m pip install boto3
python3 scripts/bootstrap_github.py --repo YOUR_GITHUB_USERNAME/cloudpto --region us-east-1
```

The bootstrap creates persistent resources: an S3 Terraform state bucket (versioned, encrypted, private), a branch-scoped GitHub OIDC provider, and an IAM role. It prints the values to configure in **GitHub > Settings > Secrets and variables > Actions > Secrets**:

| Secret | Value |
|---|---|
| `AWS_ROLE_ARN` | Printed role ARN |
| `TF_STATE_BUCKET` | Printed state bucket |
| `AWS_REGION` | `us-east-1` |

In **Actions > Variables**, optionally create:

| Variable | Example |
|---|---|
| `DOMAIN_NAME` | `careers.example.com` (must be a DNS name in your existing hosted zone) |
| `HOSTED_ZONE_ID` | `Z123456789` |

**Security warning**: the starter GitHub Terraform role uses `AdministratorAccess` for ease of provisioning in a **dedicated throwaway lab account only**. This is powerful; do not add it to a shared, personal, or production account. Require approvals for manual destroy/deploy and narrow the IAM policy after the initial lab. It is deliberately restricted by OIDC trust to one repository and the `main` branch, but compromising that branch is still highly privileged.

The S3 state bucket and GitHub IAM role remain after `terraform destroy`. This is intentional to allow a fresh deployment on presentation day. Delete those bootstrap resources separately when done with the entire project; avoid deleting the state bucket first.

### Note on CI validation

CI checks Python syntax, builds React, and checks Terraform format. CI normalizes Terraform formatting before running its format check. You should also run `terraform fmt -recursive` locally and commit the resulting file formatting.

## 2. Deploy all disposable AWS resources

Go to your GitHub repo > **Actions > AWS Lab Deploy or Destroy > Run workflow > deploy**.

This workflow:
1. Authenticates to AWS using short-lived GitHub OIDC credentials.
2. Initializes Terraform in your persistent S3 backend, validates, and applies the stack.
3. Installs dependencies/builds the React frontend in GitHub Actions.
4. Uploads a release tarball to the private releases bucket.
5. Uses **AWS Systems Manager Run Command (SSM)** to configure FastAPI + React on EC2.

When complete, note the **site URL** and **Cognito pool ID** from the workflow output. To view outputs yourself locally:

```bash
cd terraform
terraform init -backend-config="bucket=YOUR_STATE_BUCKET" -backend-config="key=careerflow/app.tfstate" -backend-config="region=us-east-1" -backend-config="encrypt=true" -backend-config="use_lockfile=true"
terraform output
```

**Important:** Terraform can take a few minutes to provision; an EC2 instance may take longer to finish its user-data and show as Online in SSM. If deployment fails after an apply, rerun `deploy` to retry; Terraform will reuse its existing resources. Look at the SSM Run Command result and EC2 `/var/log/cloud-init-output.log` if necessary.

## 3. Bootstrap the first admin (after EVERY fresh destroy/redeploy)

Run **locally** with your AWS CLI credentials, not as a GitHub Actions secret:

```bash
python3 scripts/bootstrap_admin.py --pool YOUR_COGNITO_POOL_ID --email admin@example.com --region us-east-1
```

Enter a strong password when prompted; the password is not stored in Terraform, GitHub or source code. Then open `https://YOUR_DOMAIN/login` and sign in as admin.

The admin creates an HR user from **Manage recruiters**. Cognito emails that user a temporary password; the first sign-in prompts for a new permanent password. Applicants independently create their accounts, confirm the emailed code, sign in, and apply.

**Cognito mail note:** Cognito's default email sender has sending limits. Use a real, accessible email address during tests. If an invitation or confirmation email is not delivered, verify Cognito account/region email configuration and quotas. Admin invitation issues do not affect applicant résumé processing.

## 4. GitHub updates and CI/CD

- Every push to `main` or PR runs `Validate` (frontend build + backend syntax + Terraform format).
- To update the running site, run **AWS Lab Deploy or Destroy -> deploy** again. This packages the latest code, uses Terraform to apply any infrastructure changes, and deploys the new backend/frontend via SSM. No SSH or API credentials are stored in GitHub.
- You can add an automatic `push` trigger to the deployment workflow once you are happy with infrastructure creation costs. It is deliberately **manual** to prevent an unexpected AWS bill each time you push.

## 5. Destroy after practice / recreate for presentation

**WARNING: destructive.** `destroy` permanently deletes application records, résumé PDFs, Cognito accounts, jobs, the EC2 instance, EBS volume, EIP, and Lambda logs in this lab. Terraform also deletes sample job records. **Do not store real user data.** S3 release/resume buckets use `force_destroy=true` to enable teardown. If you need to retain results, take a deliberate protected backup before destroying; protect candidate PII.

In Actions, choose **AWS Lab Deploy or Destroy -> destroy**. The Terraform state bucket and GitHub OIDC role stay, so redeploy later by choosing `deploy` and running `bootstrap_admin.py` again.

After destruction, check AWS Billing / Cost Explorer. **Costs may remain** for the state bucket (and its old versions), registered domain/hosted zone, service usage, retained snapshots or other external resources. Also note that Route 53 hosted zones created outside this Terraform stack are not deleted by this stack.

### Optional private localhost tunnel (no domain)

For private smoke testing without domain:

```bash
aws ssm start-session --target INSTANCE_ID --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["80"],"localPortNumber":["8080"]}'
```

Install AWS's Session Manager plugin locally. Open `http://localhost:8080` while tunnel is running, not the public EC2 IP. HTTP is transported inside the authenticated SSM session for this tunnel. Browser authentication still uses the local-origin web app and same-origin API.

## 6. Local development (no AWS)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:5173`. In **local** mode, Cognito registration and HR invitations are disabled. Demo logins (only for localhost):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@demo.example.com` | `admin12345` |
| HR | `hr@demo.example.com` | `hr12345678` |
| Applicant | `applicant@demo.example.com` | `applicant123` |

Local storage uses SQLite and reads embedded PDF text with PyMuPDF. AWS uses Textract to support scanned and multi-page PDFs.

## Security and cost notes

- Cognito access tokens are validated on FastAPI using the user pool's JWKS, and **role checks run on the backend**. HR accounts can only be created by admins. Applicants can only view their own applications and PDFs.
- The UI stores access tokens in `sessionStorage` for this lab; improve token lifecycle, CSP, XSS defenses, rate limiting, audit logs, and session revocation for production.
- Applicant emails are verified by Cognito, but resume education extraction is heuristic and requires human review. The browser cannot claim HR rights by changing its state.
- App uses 1 public EC2 with IAM instance profile (no embedded AWS keys), S3 encryption/block-public-access, and no inbound SSH. **Caddy handles HTTPS with a domain**. IAM Lambda policies scope résumé bucket and DynamoDB, while Textract/Comprehend APIs require `*` resource permissions in this demo.
- Use 5 MB PDFs, at most 25 pages. Textract async start + polling in a 300-second Lambda is intentionally simplified: **it can incur charges while waiting and time out**. A production architecture should use Textract completion SNS/SQS callbacks, DLQ retries, idempotency, and longer retention policies. Failed parsing sets `review_required`; Lambda raises to make errors visible in CloudWatch.
- DynamoDB `scan` is fine for a small class presentation but not a production applicant database: use GSIs, Query, pagination, user-level tenancy, and stricter authorization boundaries at scale.
- No NAT gateway, load balancer, ECR, or Elastic Beanstalk resources are provisioned to limit recurring cost. Terraform does not create ACM certificate because this no-ALB plan terminates TLS using Caddy/Let's Encrypt instead. AWS services still incur charges; price depends on region/usage.

## Directory guide

```text
backend/app/          FastAPI, Cognito JWT validation, DynamoDB/SQLite storage
frontend/src/         React interface (3 roles)
aws/lambda_function.py S3 / Textract / Comprehend enrichment
terraform/            All disposable AWS resources (Terraform)
scripts/              AWS bootstrap and EC2 deployment scripts
.github/workflows/    CI validation + manual deploy/destroy
```

## V3 ATS improvements (2026-11-09)

- **HR and Admin** can create, edit and archive jobs using `/api/staff/jobs`; `/api/staff/jobs` returns active and archived. Archiving preserves past applications. Only Admin can invite/manage HR.
- **Applicant-only** application submission is enforced in FastAPI (`403` for HR/Admin). The React careers page hides Apply for signed-in HR/Admin.
- Staff application table displays **Name, Skills, Education, Experience, Volunteer Experience, Position, Status, extraction review, CV**. Keyword matching checks these fields **and full OCR text**.
- **Résumé extraction** now uses Textract as OCR, a deterministic section-aware parser for CV fields, and Comprehend only for optional entity enrichment. Missing education or experience produces `review_required`, never fabricated information. AWS extraction duration, recognized headings, error and warning are stored for review.
- **AWS Processing** tab explains services and shows **recorded app processing counts**, not unverified AWS service-health claims.
- The starter project uses DynamoDB Scan for small test datasets (limit 250 returned records). Full-text search at scale requires OpenSearch or a separate index.

**Accuracy limitations:** Scanned, multi-column, image-heavy, unusual, and non-English PDFs may be misread by Textract or the heading rules. Test varied real and synthetic CVs and review flagged results. No parser can guarantee correct extraction of every résumé. Human review is required for consequential hiring decisions.

### Local tests

```bash
python -m pip install -r backend/requirements.txt
PYTHONPATH=aws python -m pytest aws/test_resume_parser.py -q
cd backend && python -m pytest test_smoke.py test_roles.py -q
```

### Updating the already deployed project

Replace the source files in your cloned GitHub project with the files from this ZIP, then commit and push to `main`. Run the existing GitHub Actions **AWS Lab Deploy or Destroy** workflow with `action=deploy` (do not select `destroy`). Terraform updates the Lambda ZIP and the application package is redeployed to EC2. Because the Lambda archive now contains the parser as well as the handler, changing these source files updates the Lambda code on the next Terraform apply. Verify the GitHub Action plan carefully for unwanted resource replacement, especially EC2 and Cognito. Never run destroy to update code: destroy deletes user pools and data.

Use only sample résumés until the application has HTTPS and is evaluated for privacy/security. S3 documents may contain personal data; avoid exposing raw extracted text beyond authorized staff.

## v4 extraction update — two-column resumes

- `aws/resume_parser.py` now accepts Textract `LINE` blocks with bounding boxes, preserving reading order separately for columns. Falls back to plain text when layout information is unavailable.
- `aws/lambda_function.py` passes Textract blocks into the parser and still retains Comprehend enrichment.
- `backend/app/main.py` builds equivalent geometry from PyMuPDF in local mode.
- Projects and leadership are captured separately from paid employment; outreach can be shown for HR review without assuming the activity was a formal volunteer job.
- `fixtures/two_column_student_resume.pdf` is a regression sample, and `aws/test_resume_parser.py` includes its extraction assertions.
- Run `python -m pytest -q aws/test_resume_parser.py backend/test_roles.py backend/test_smoke.py` locally.
- For deployment, copy the updated source into the original repository and run the existing GitHub Actions deploy workflow. Avoid deploying Terraform changes blindly; check the plan first.
- Live AWS Textract accuracy has not been validated by these local tests. Compare actual Lambda output and PDF before claiming end-to-end success.
- Previously submitted resumes are not automatically reprocessed; submit a fresh sample PDF after deployment.


## v5 update — apply once over your working v2 repository

The full ZIP bundles v3 role/job-management features, the v4 column-aware PDF résumé parser,
and the v5 applicant form. It is NOT necessary to deploy v3 or v4 first.

### Applicant workflow
1. Sign in as Applicant; select a job and choose **Apply**.
2. Optionally upload a résumé (PDF up to 5MB). The backend first uses PyMuPDF; if the file
   has no readable text and is a single page in AWS mode, it tries synchronous Textract.
   Scanned multipage PDFs require manual entry during preview. Never promise a 1–2 second SLA.
3. Review/edit full name, email, address, contact number, skills, education, work experience,
   projects, volunteering, leadership, and cover letter (text or optional PDF attachment).
4. Submit. Confirmed form values are saved separately and Lambda never overwrites them.
5. Uploaded PDFs trigger the existing S3→Lambda→Textract→Comprehend workflow, which adds
   raw OCR text for HR keyword search and processing metrics. OCR may continue after submission.

### Installation
Copy the contents of this ZIP into the root of the original repository, **not the folder itself**.
Preserve `.git`, local `.env` files, and any customized `scripts/install_on_ec2.sh` file if you
have changes beyond the bundled health-check version. Do not copy local SQLite test data.

Changes of particular importance:
- `backend/app/main.py`: `/api/applications/prefill` and editable submitted JSON in multipart form
- `frontend/src/main.jsx`, `frontend/src/style.css`: expanded application and dashboards
- `aws/resume_parser.py`, `aws/lambda_function.py`: column-aware parsing, verified-data protection
- `terraform/main.tf`: EC2 `textract:DetectDocumentText`, S3 cover-letter prefix, Lambda `dynamodb:GetItem`
- `backend/test_application_v5.py`, `aws/test_resume_parser.py`, `fixtures/`: regression tests
- `.github/workflows/aws-lab.yml`: packages shared Python parser in EC2 release

Run `PYTHONPATH=backend pytest -q aws/test_resume_parser.py backend/test_roles.py backend/test_smoke.py backend/test_application_v5.py`
and `cd frontend && npm install && npm run build`. The latter was not run in this packaging
session because npm dependencies were not available offline.

**Review Terraform plan before applying.** Avoid destroy; that can delete users/jobs/applications.
Use only test PDFs and HTTPS or localhost SSM tunneling until HTTPS is configured.

### Limitations
- For text-based PDFs, fast preview is a *target*, not a guaranteed 2-second result.
- For scanned single-page PDFs in AWS, synchronous Textract response time is variable;
  for scanned multi-page preview, the form remains manually editable.
- There is no full DOCX support in this package.
- Keyword searching via DynamoDB Scan is intended only for a small teaching dataset.
- The résumé parser is heuristic and requires applicant correction and human HR review.
- AWS live OCR processing and the frontend production build still need verification.
