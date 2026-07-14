# End-to-End Integration Guide

This guide covers the complete flow of the AI Cloud Cost Detective application, from authentication through analysis and reporting.

## Architecture Overview

The application follows this request flow:

1. **Step ①**: User Authentication (JWT-based signup/login)
2. **Step ③**: AWS Resource Discovery via AWS CLI
3. **Step ④**: WebSocket Progress Tracking
4. **Step ⑤**: AI-Powered Cost Analysis via OpenAI
5. **Step ⑥**: Results Storage in PostgreSQL
6. **Step ⑦**: History Retrieval and Report Display

## Backend Integration Points

### 1. Authentication Endpoints

#### POST `/api/auth/signup`
Creates a new user account with JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "email": "user@example.com"
}
```

#### POST `/api/auth/login`
Authenticates user credentials and returns JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "email": "user@example.com"
}
```

#### GET `/api/auth/me`
Returns authenticated user information.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "created_at": "2024-01-15T10:30:00"
}
```

### 2. Resource Analysis Endpoints

#### GET `/api/resource-groups`
Fetches list of AWS Resource Groups (requires AWS CLI authentication).

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "resource_groups": ["group-1", "group-2"],
  "total_groups": 2
}
```

#### POST `/api/analyze`
Starts cost analysis for a resource group.

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request:**
```json
{
  "resource_group": "group-1"
}
```

**Response:**
```json
{
  "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
  "resource_group": "group-1",
  "total_resources": 15,
  "resources": [
    {
      "resource_type": "AWS::EC2::Instance",
      "name": "web-server-1",
      "region": "us-east-1",
      "sku": "t3.large",
      "tags": {"Name": "web-server-1"},
      "arn": "arn:aws:ec2:..."
    }
  ],
  "analysis": {
    "summary": "Found 3 cost optimization opportunities...",
    "total_estimated_savings": "$2,400/year",
    "issues": [
      {
        "title": "Over-provisioned EC2 Instance",
        "description": "Instance is running at 15% CPU utilization consistently...",
        "severity": "high",
        "resource_name": "web-server-1",
        "resource_type": "AWS::EC2::Instance",
        "estimated_savings": "$800/year",
        "fix_command": "aws ec2 stop-instances --instance-ids i-xxxxx"
      }
    ],
    "recommendations": [
      "Consider using Reserved Instances for steady-state workloads",
      "Review IAM policies to ensure least privilege"
    ]
  }
}
```

### 3. WebSocket Progress Tracking

#### WS `/ws/progress/{analysis_id}`
Real-time progress tracking during analysis.

**Example JavaScript:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/progress/550e8400-e29b-41d4-a716-446655440000');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data = {
  //   "type": "progress|completed|error",
  //   "message": "Listing AWS Resource Groups...",
  //   "timestamp": "2024-01-15T10:35:25.123456"
  // }
  console.log(data.message);
};

ws.onclose = () => {
  console.log('Analysis complete');
};
```

**Progress Message Sequence:**
1. "Listing AWS Resource Groups..."
2. "Scanning AWS resources in 'group-name'..."
3. "Analyzing costs with AI..."
4. "Storing results..."
5. "Analysis complete" (type: "completed")

### 4. History and Analysis Retrieval

#### GET `/api/history`
Fetches all analysis records for the authenticated user.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "total": 2,
  "analyses": [
    {
      "id": 1,
      "resource_group": "group-1",
      "resources_scanned": 15,
      "issues_found": 3,
      "estimated_savings": "$2,400/year",
      "status": "completed",
      "created_at": "2024-01-15T10:35:00"
    }
  ]
}
```

#### GET `/api/analysis/{analysis_db_id}`
Fetches full details of a specific analysis.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
Same as POST `/api/analyze` response with full analysis details.

## Frontend Integration Flow

### Authentication Flow
1. User navigates to `http://localhost:5173/login`
2. Clicks "Sign up" or enters credentials
3. Frontend calls `POST /api/auth/signup` or `POST /api/auth/login`
4. Response includes `access_token` which is stored in `localStorage`
5. All subsequent API requests include header: `Authorization: Bearer {token}`
6. User redirected to `/dashboard`

### Analysis Flow
1. Dashboard component fetches resource groups with JWT: `GET /api/resource-groups`
2. User selects group from dropdown menu
3. User clicks "Run Analysis"
4. Frontend calls `POST /api/analyze` with JWT token
5. Response includes `analysis_id` and initial resource list
6. WebSocket connects to `ws://localhost:8000/ws/progress/{analysis_id}`
7. Messages streamed in real-time as analysis progresses:
   - AWS CLI execution
   - Resource scanning
   - OpenAI analysis
   - Database storage
8. On completion, user is redirected to `/report/{analysis_id}` with full results
9. Report displays:
   - Summary with estimated savings
   - Detailed issues with severity badges
   - Copyable AWS CLI fix commands
   - General recommendations
   - Resources scanned table

### History Flow
1. User navigates to `/history`
2. Frontend calls `GET /api/history` with JWT
3. Table displays past analyses with status badges
4. User clicks "View Report →" for any analysis
5. Frontend calls `GET /api/analysis/{database_id}` with JWT
6. User is navigated to `/report/{analysis_uuid}` with full data
7. Report page displays the same details as live analysis

## JWT Token Management

### Token Storage
- Stored in `localStorage` as `access_token` key
- Persists across browser sessions
- Cleared on logout via `localStorage.removeItem('access_token')`

### Token Format
```json
{
  "user_id": 1,
  "email": "user@example.com",
  "iat": 1705320953,
  "exp": 1705407353
}
```

### Token Expiration
- Default: 24 hours
- Configurable via `JWT_EXPIRATION_HOURS` in `.env`
- Expired tokens return 401 error from backend
- Frontend handles 401 by redirecting to `/login`

## Error Handling

### Frontend Error Display
- HTTP errors display in red boxes with error messages
- Network errors (WebSocket disconnect) show progress interruption
- Authentication errors redirect to login page
- 503 errors indicate database is not configured

### Backend Error Responses
All errors follow this format:
```json
{
  "detail": {
    "error": "Descriptive error message",
    "code": "ERROR_CODE"
  }
}
```

Common error codes:
- `MISSING_AUTH`: Authorization header missing
- `INVALID_TOKEN`: JWT token is invalid or expired
- `AWS_CLI_NOT_FOUND`: AWS CLI is not installed
- `AWS_AUTHENTICATION_FAILED`: AWS credentials are not configured
- `AWS_OPERATION_FAILED`: AWS CLI command failed
- `DB_NOT_CONFIGURED`: Database URL is not set
- `ANALYSIS_NOT_FOUND`: Analysis database record not found

## Environment Configuration

### Backend `.env` Requirements
```bash
# OpenAI API Configuration
OPENAI_API_KEY=sk-...

# PostgreSQL Database
DATABASE_URL=postgresql://user:password@localhost:5432/ai_cost_detective

# JWT Configuration
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

### AWS CLI Configuration
Required for resource group scanning:
```bash
aws configure
# Enter AWS Access Key ID
# Enter AWS Secret Access Key
# Enter default region (e.g., us-east-1)
```

## Testing the Complete Flow

### 1. Setup
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### 2. Authentication Test
1. Open `http://localhost:5173`
2. Click "Sign up"
3. Enter email: `test@example.com`, password: `TestPass123`
4. Verify redirect to dashboard
5. Check browser DevTools → Application → localStorage for `access_token`

### 3. Resource Group Test
1. On Dashboard, verify dropdown shows AWS resource groups
2. If empty, check:
   - AWS credentials are configured: `aws sts get-caller-identity`
   - Backend logs for AWS CLI errors

### 4. Analysis Test
1. Select a resource group
2. Click "Run Analysis"
3. Watch WebSocket progress messages stream in real-time
4. After completion, verify report displays issues and recommendations

### 5. History Test
1. Click "View History" from dashboard
2. Verify past analyses appear in table
3. Click "View Report" on an analysis
4. Verify full analysis data loads from database

### 6. JWT Authentication Test
1. Open browser DevTools → Network tab
2. Every API request to protected endpoints shows:
   - Header: `Authorization: Bearer eyJ...`
3. Try manually deleting `access_token` from localStorage
4. Refresh page - should redirect to login

## Database Schema

### Users Table
```sql
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### Analyses Table
```sql
CREATE TABLE analyses (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  resource_group VARCHAR(255) NOT NULL,
  resources_scanned INT DEFAULT 0,
  issues_found INT DEFAULT 0,
  estimated_savings VARCHAR(255),
  analysis_result JSONB,
  status VARCHAR(50) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

## Troubleshooting

### "Database is not configured" Error
- Verify `DATABASE_URL` is set in `.env`
- Ensure PostgreSQL is running: `psql -c "SELECT 1"`
- Check connection string format: `postgresql://user:password@host:port/database`

### "AWS CLI not found" Error
- Install AWS CLI: `brew install awscli2` (macOS) or `pip install awscli`
- Verify installation: `aws --version`
- Configure credentials: `aws configure`

### "OpenAI API error" Messages
- Verify `OPENAI_API_KEY` is set in `.env`
- Check API key is valid: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`
- Ensure account has API credits available

### WebSocket Connection Fails
- Check backend is running: `curl http://localhost:8000/health`
- Verify Vite proxy is configured in `frontend/vite.config.ts`
- Check browser console for WebSocket error messages

### Blank Report Page
- Verify location state was passed from Dashboard or History
- Check browser console for JavaScript errors
- Ensure `analysis_id` param matches route parameter

## Production Deployment

### Security Considerations
1. Use HTTPS in production (update `frontend/src/api.ts` to use `https://`)
2. Set strong `JWT_SECRET` (minimum 32 characters)
3. Enable CORS only for your domain
4. Use managed database service (RDS)
5. Store secrets in environment variables, never commit to git
6. Enable email verification before allowing analysis
7. Implement rate limiting on `/api/analyze` endpoint

### Scaling Considerations
1. Run backend behind load balancer
2. Use connection pool with higher `max_size` for database
3. Implement Redis for session caching
4. Queue long-running analyses with Celery/RQ
5. Cache resource group list with TTL
6. Implement pagination for large history lists (currently fixed at 50)

## API Reference Summary

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | No | Server health check |
| `/api/auth/signup` | POST | No | Create new user |
| `/api/auth/login` | POST | No | Authenticate user |
| `/api/auth/me` | GET | Yes | Get current user info |
| `/api/auth-check` | GET | No | Check AWS auth status |
| `/api/resource-groups` | GET | - | List AWS resource groups |
| `/api/analyze` | POST | - | Start resource analysis |
| `/api/analysis/{id}` | GET | Yes | Get analysis details |
| `/api/history` | GET | Yes | Get user's analyses |
| `/ws/progress/{id}` | WS | No | Stream progress updates |

Legend: 
- Auth: Yes = Required
- Auth: No = Not required
- Auth: - = Optional

