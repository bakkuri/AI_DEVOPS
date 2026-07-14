# Prompt 1: FastAPI Backend + AWS CLI

Create a Python FastAPI backend in a `backend/` folder for the AI Cloud Cost Detective project.

## What to build

- A FastAPI server with a `POST /api/analyze` endpoint that accepts `{ "resource_group": "<name>" }`.
- A `GET /api/resource-groups` endpoint that returns the list of AWS resource groups.
- Use Python's `subprocess` module to run AWS CLI commands:
  - `az group list` to list all resource groups.
  - `az resource list --resource-group <name> -o json` to fetch all resources in the selected group.
- Parse the AWS CLI JSON output and return a structured response with resource type, name, location, SKU, and tags.
- Add error handling for AWS CLI not installed, not logged in, or invalid resource group.
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
