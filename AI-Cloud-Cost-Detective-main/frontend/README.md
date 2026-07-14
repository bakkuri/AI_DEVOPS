# Frontend - AI Cloud Cost Detective

React + Vite + TypeScript + Tailwind CSS

## Setup

```bash
cd frontend
npm install
npm run dev
```

Server will start on `http://localhost:5173`

## Build

```bash
npm run build
```

## Environment

The frontend connects to the backend at `http://localhost:8000` and proxies WebSocket connections automatically via Vite.

### Frontend Pages

- **Login** (`/login`) - Email/password authentication
- **Signup** (`/signup`) - Create new account
- **Dashboard** (`/dashboard`) - Select resource group and run analysis
- **Report** (`/report/:id`) - View analysis results with issues and recommendations
- **History** (`/history`) - View past analyses

### Authentication

JWT tokens are stored in localStorage and included in all API requests via `Authorization: Bearer <token>` header.
