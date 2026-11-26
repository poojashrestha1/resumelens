# ResumeLens

A full-stack job application platform built with **React**, **FastAPI**, and **AWS**. Applicants can browse open positions and submit applications with résumé parsing. HR staff can review candidates, manage positions, and update application statuses. Admins manage the full platform including recruiter accounts.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [User Roles](#user-roles)
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [AWS Setup](#aws-setup)
- [Navigating the App](#navigating-the-app)
- [Project Structure](#project-structure)

---

## Features

- Browse open job positions publicly (no login required)
- Upload a PDF résumé for automatic field extraction (PyMuPDF + AWS Textract)
- Submit applications with personal info, skills, education, experience, and cover letter
- HR dashboard to review, filter, and update candidate statuses
- Admin panel to invite and manage HR recruiters via AWS Cognito
- AWS mode: DynamoDB, S3, Cognito, Lambda, Textract
- Local mode: SQLite + JWT (no AWS account needed)

---

## Architecture

```
Browser (React + Vite)
        │
        ▼
FastAPI (Python)  ──►  SQLite (local) or DynamoDB (AWS)
        │
        ▼
   S3 (résumé PDFs)
        │
        ▼
   Lambda ──► Textract (OCR for scanned PDFs)
```

---

## User Roles

| Role | What they can do |
|---|---|
| **Applicant** | Browse jobs, submit applications, view own application status |
| **HR / Recruiter** | View all applications, update review status, manage job positions |
| **Admin** | Everything HR can do + invite/disable recruiter accounts |

### Demo accounts (local mode only)

| Email | Password | Role |
|---|---|---|
| `admin@demo.example.com` | `admin12345` | Admin |
| `hr@demo.example.com` | `hr12345678` | HR |
| `applicant@demo.example.com` | `applicant123` | Applicant |

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **pip** and **npm**
- (AWS mode only) AWS account with appropriate permissions

---

## Local Setup

Local mode uses SQLite and demo JWT auth — no AWS account needed.

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd careerflow-v2
```

### 2. Backend

```bash
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# .env is pre-configured for local mode — no changes needed
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. You can explore the auto-generated docs at `http://localhost:8000/docs`.

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Set up environment
cp .env.example .env
# VITE_API_URL=http://localhost:8000 is already set
```

Start the frontend:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

---

## AWS Setup

### 1. Infrastructure (Terraform)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
aws_region    = "us-east-1"
project       = "careerflow-v2"
instance_type = "t3.micro"
domain_name   = "careers.example.com"   # recommended for HTTPS
hosted_zone_id = "Z1234567890ABC"        # your Route53 hosted zone
```

Deploy:

```bash
terraform init
terraform apply
```

This provisions: EC2, Cognito User Pool, S3 bucket, DynamoDB tables, Lambda, IAM roles, and Caddy for HTTPS.

### 2. Backend `.env` (AWS mode)

```env
APP_MODE=aws
AWS_REGION=us-east-1
S3_BUCKET=your-s3-bucket-name
APPLICATIONS_TABLE=your-dynamodb-applications-table
JOBS_TABLE=your-dynamodb-jobs-table
COGNITO_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=your-cognito-client-id
CORS_ORIGINS=https://careers.example.com
```

### 3. Bootstrap admin account

```bash
cd scripts
python3 bootstrap_admin.py
```

### 4. Deploy to EC2

```bash
bash scripts/install_on_ec2.sh
```

---

## Navigating the App

### Public — Careers page (`/`)

- View all open job positions
- Click **Apply** on any role to open the application form
- You must be signed in as an **applicant** to apply

### Application form

1. Optionally upload a PDF résumé — fields will be auto-filled
2. Review and correct all extracted fields
3. Fill in personal info: name, email, phone, address
4. Fill in qualifications: skills, education, experience, projects, volunteer experience, leadership
5. Optionally add a cover letter (text or PDF)
6. Click **Submit application**

### Applicant dashboard (`/dashboard`)

- View all your submitted applications
- See review status (Applied → In review → Interview → Offer / Not selected)
- Download your submitted résumé PDF

### HR dashboard (`/dashboard`)

- **Applications tab** — searchable, filterable table of all candidates
  - Filter by position, review status, and date
  - Update review status per candidate
  - View résumé and cover letter PDFs
  - Expand rows to read full field content
- **Manage positions tab** — create, edit, and archive job postings

### Admin dashboard (`/dashboard`)

- Everything HR can do, plus:
- **Manage recruiters tab** — invite new HR recruiters via email (AWS Cognito sends a temporary password), enable or disable existing recruiter accounts

---

## Project Structure

```
careerflow-v2/
├── backend/
│   ├── app/
│   │   ├── main.py        # All API routes
│   │   ├── auth.py        # JWT + Cognito auth
│   │   ├── storage.py     # SQLite / DynamoDB abstraction + seed jobs
│   │   └── config.py      # Environment settings
│   ├── data/              # SQLite database (local mode)
│   ├── .env               # Your local environment config
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.jsx       # Entire React app
│   │   └── style.css      # All styles
│   ├── .env               # VITE_API_URL
│   └── package.json
├── aws/
│   ├── lambda_function.py # Async résumé processing
│   └── resume_parser.py   # Text + Textract extraction
├── terraform/             # Full AWS infrastructure
├── scripts/               # Bootstrap and deployment helpers
└── README.md
```

---

## API Reference (key endpoints)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/jobs` | None | List active job positions |
| `POST` | `/api/auth/signup` | None | Create applicant account (AWS only) |
| `POST` | `/api/auth/login` | None | Sign in |
| `GET` | `/api/me` | Any | Get current user info |
| `POST` | `/api/applications` | Applicant | Submit an application |
| `GET` | `/api/me/applications` | Applicant | List own applications |
| `GET` | `/api/staff/applications` | HR/Admin | List all applications |
| `PATCH` | `/api/staff/applications/{id}/status` | HR/Admin | Update review status |
| `POST` | `/api/staff/jobs` | HR/Admin | Create a job position |
| `PATCH` | `/api/staff/jobs/{id}` | HR/Admin | Edit a job position |
| `DELETE` | `/api/staff/jobs/{id}` | HR/Admin | Archive a job position |
| `GET` | `/api/admin/recruiters` | Admin | List recruiters |
| `POST` | `/api/admin/recruiters` | Admin | Invite a recruiter |

Full interactive docs available at `http://localhost:8000/docs` when running locally.
 
