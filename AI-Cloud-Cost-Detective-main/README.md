# AI Cloud Cost Detective

An AI-powered tool that investigates AWS cloud costs automatically. It scans resources in an AWS Resource Group, detects cost issues like over-provisioning and misconfigurations, and provides actionable suggestions with fixes.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite + TypeScript + Tailwind) |
| Backend | Python (FastAPI) |
| Auth | Custom JWT Auth (bcrypt + PyJWT) |
| Cloud Data | AWS CLI |
| Cloud | AWS |
| AI Analysis | OpenAI API |
| Database | Amazon RDS for PostgreSQL |
| Live Updates | FastAPI WebSocket |

## Architecture

```
                              ┌──────────────┐
                              │     USER     │
                              └──────┬───────┘
                                     │
                                     ▼
                           ┌───────────────────┐
                           │  REACT FRONTEND   │
                           └────────┬──────────┘
                                    :
                                    : Login / Signup
                                    ▼
                           ┌───────────────────┐
                           │  PYTHON BACKEND   │
                           │    (FastAPI)      │
                           │                   │
                           │  · Custom JWT Auth│
                           └───┬───────┬───┬───┘
                               :       :   :
                ┌──────────────┘       :   └──────────────┐
                :                      :                  :
                ▼                      ▼                  ▼
         ┌─────────────┐     ┌──────────────┐    ┌──────────────┐
         │  AWS CLI    │     │   FASTAPI    │    │   OPENAI     │
         │             │     │  WEBSOCKET   │    │    API       │
         │ resource-   │     │  (Progress)  │    │              │
         │ groups list │     └──────┬───────┘    │ Cost Analysis│
         └──────┬──────┘            :            └──────┬───────┘
                :                   : Live updates      :
                ▼                   ▼                   :
         ┌─────────────┐   ┌───────────────┐            :
         │    AWS      │   │    REACT      │            :
         │ (Resource   │   │  (Progress    │            :
         │   Group)    │   │   Tracker)    │            :
         └─────────────┘   └───────────────┘            :
                                                        ▼
                                                 ┌──────────────┐
                                                 │  Amazon RDS  │
                                                 │ (PostgreSQL) │
                                                 │              │
                                                 │ · users      │
                                                 │ · analyses   │
                                                 └──────┬───────┘
                                                        :
                                                        : Stored results
                                                        ▼
                                                 ┌───────────────┐
                                                 │    REACT      │
                                                 │ (Final Report │
                                                 │  + Suggestions│
                                                 │  + Fixes)     │
                                                 └───────────────┘
```

## Request Flow

```
①  User ─·─·─► React ─·─·─► FastAPI Auth ─·─·─► JWT (Amazon RDS PostgreSQL)

②  User selects AWS Resource Group ─·─·─► Python Backend

③  Python ─·─·─► AWS CLI ─·─·─► Fetches all resources in Resource Group

④  Python ─·─·─► FastAPI WebSocket ─·─·─► React (live progress)

⑤  Python ─·─·─► OpenAI API ─·─·─► Cost analysis

⑥  Python ─·─·─► Amazon RDS PostgreSQL ─·─·─► Stores analysis history

⑦  React ◄·─·─·─ Final report with suggestions & AWS CLI fixes
```

## What It Detects

- **Over-provisioned resources** — EC2, RDS, or ElastiCache instances sized larger than needed
- **Unused resources** — Unattached EBS volumes, unused Elastic IPs, idle ALB/NLB, stopped instances with attached storage
- **Misconfigurations** — Wrong instance types/families, missing Savings Plans or Reserved Instances, no auto-scaling
- **Storage & logging costs** — S3 buckets without lifecycle policies, excessive CloudWatch log retention

## Prerequisites

- AWS CLI installed and configured (`aws configure` or valid IAM credentials)
- An active AWS account with at least one AWS Resource Group
- An Amazon RDS for PostgreSQL instance
- An OpenAI API key
- Python 3.10+
- Node.js 18+

## How to Run

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## How It Works

1. User signs up / logs in via custom JWT auth (credentials stored in Amazon RDS PostgreSQL)
2. Selects an AWS Resource Group to analyze
3. Python backend fetches all resources using AWS CLI (`aws resource-groups list-group-resources`)
4. Live progress is streamed to the UI via FastAPI WebSocket
5. Resource data is sent to OpenAI API for cost analysis
6. Analysis results are stored in Amazon RDS PostgreSQL
7. Final report with cost breakdown, suggestions, and AWS CLI fix commands is displayed
