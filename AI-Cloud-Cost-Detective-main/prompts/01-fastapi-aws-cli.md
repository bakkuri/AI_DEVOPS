# Prompt 1: FastAPI Backend + AWS CLI

Create a Python FastAPI backend in a `backend/` folder for the AI Cloud Cost Detective project.

## What to build

- A FastAPI server with a `POST /api/analyze` endpoint that accepts `{ "resource_group": "<name>" }`.
- A `GET /api/resource-groups` endpoint that returns the list of AWS Resource Groups.
- Use Python's `subprocess` module to run AWS CLI commands:
  - `aws resource-groups list-groups --output json` to list all resource groups.
  - `aws resource-groups list-group-resources --group-name <name> --output json` to fetch all resources in the selected group.
  - Optionally use `aws resourcegroupstaggingapi get-resources --resource-arn-list <arns> --output json` to enrich resources with tags.
- Parse the AWS CLI JSON output and return a structured response with:
  - **resource_type** — e.g. `AWS::EC2::Instance`, `AWS::RDS::DBInstance`
  - **name** — from the `Name` tag when present, otherwise the last segment of the resource ARN
  - **region** — parsed from the resource ARN
  - **sku** — size/type where applicable (e.g. EC2 instance type, RDS instance class); use type-specific `describe-*` calls only when needed
  - **tags** — key/value pairs from the Resource Groups Tagging API
- Add error handling for:
  - AWS CLI not installed (`aws` command not found)
  - Not authenticated or missing credentials (failed `aws sts get-caller-identity` or credential errors from AWS CLI)
  - Invalid or non-existent resource group
- Enable CORS for `http://localhost:5173`.
- Include a `requirements.txt` with `fastapi`, `uvicorn`.

## Project structure

```
backend/
├── main.py
├── aws_scanner.py
├── requirements.txt
```

Refer to `Architecture.MD` and `RequestFlow.MD`. This covers step ③ of the request flow.
