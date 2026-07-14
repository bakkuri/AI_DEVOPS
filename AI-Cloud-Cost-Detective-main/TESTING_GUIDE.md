# End-to-End Testing Guide

Complete testing workflow for the AI Cloud Cost Detective application from signup to history retrieval.

## Prerequisites

Before starting, ensure:

```bash
# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
```

## Test Part 1: Backend Setup and Health Check

### 1.1 Configure Environment Variables

Create `/backend/.env` with:
```bash
OPENAI_API_KEY=sk-your-key-here
DATABASE_URL=postgresql://your_user:your_password@localhost:5432/ai_cost_detective
JWT_SECRET=your-super-secret-key-min-32-chars-long-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

### 1.2 Setup PostgreSQL Database

```bash
# Create database
psql -U postgres -c "CREATE DATABASE ai_cost_detective;"

# Verify connection
psql -U postgres -d ai_cost_detective -c "SELECT 1;"
```

### 1.3 Start Backend Server

```bash
cd backend
python main.py
```

Expected output:
```
INFO:__main__:Starting AI Cloud Cost Detective API server...
INFO:uvicorn.server:Uvicorn running on http://0.0.0.0:8000
```

### 1.4 Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"ok"}
```

## Test Part 2: Frontend Setup

### 2.1 Start Frontend Development Server

```bash
cd frontend
npm run dev
```

Expected output:
```
  VITE v5.0.6  ready in XX ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### 2.2 Open Browser

Navigate to: `http://localhost:5173`

Should redirect to `/login`

## Test Part 3: Authentication Flow

### 3.1 Signup Test

**Steps:**
1. Click "Sign up" link
2. Enter email: `test@example.com`
3. Enter password: `TestPassword123`
4. Confirm password: `TestPassword123`
5. Click "Sign up" button

**Expected Results:**
- No validation errors appear
- Form submission succeeds
- Redirected to Dashboard (`/dashboard`)
- Browser DevTools → Application → localStorage contains `access_token`

**Verify JWT token:**
```bash
# In browser console:
localStorage.getItem('access_token')
# Should return: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Backend logs:**
```
INFO:__main__:Processing signup for email: test@example.com
INFO:__main__:User created successfully: test@example.com
INFO:__main__:Created user with email: test@example.com
```

### 3.2 Logout and Login Test

**Steps:**
1. Click "Logout" in navbar
2. Verify redirected to login page
3. Verify `access_token` removed from localStorage
4. Click "Log in" 
5. Enter email: `test@example.com`
6. Enter password: `TestPassword123`
7. Click "Log in" button

**Expected Results:**
- Login succeeds
- New token stored in localStorage
- Redirected to Dashboard
- Token is different from previous one (new `iat` timestamp)

### 3.3 Password Validation Test

**Steps:**
1. Go to signup page
2. Try password shorter than 6 characters: `test`
3. Verify error: "Password must be at least 6 characters"
4. Try mismatched passwords: `TestPassword123` vs `DifferentPassword123`
5. Verify error: "Passwords do not match"

**Expected Results:**
- Client-side validation prevents form submission
- Errors display in red boxes
- Backend never receives invalid requests

### 3.4 Invalid Login Test

**Steps:**
1. Go to login page
2. Enter email: `nonexistent@example.com`
3. Enter password: `SomePassword123`
4. Click "Log in"

**Expected Results:**
- Error displays: "Invalid email or password"
- Not redirected to dashboard
- Token not stored in localStorage

## Test Part 4: AWS Integration

### 4.1 AWS CLI Verification

```bash
# Verify AWS CLI is installed
aws --version
# Expected: aws-cli/2.x.x

# Verify AWS credentials are configured
aws sts get-caller-identity
# Expected: {"UserId": "...", "Account": "123456789012", "Arn": "arn:aws:iam::..."}
```

### 4.2 Resource Groups Fetch

**Manual API Test:**
```bash
# Get auth token from browser localStorage
TOKEN="eyJhbGciOijQ8..."

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/resource-groups
```

Expected response:
```json
{
  "resource_groups": ["my-group-1", "my-group-2"],
  "total_groups": 2
}
```

**Frontend Test:**
1. Dashboard page should display dropdown with resource group names
2. If dropdown is empty, check:
   - AWS credentials: `aws sts get-caller-identity`
   - Backend logs for errors starting with "AWSCliNotFound" or "AWSAuthenticationError"

### 4.3 AWS CLI Error Handling

**Test Missing AWS CLI:**
1. Temporarily rename AWS CLI: `mv /usr/local/bin/aws /usr/local/bin/aws.bak`
2. Refresh dashboard
3. Error should appear: "AWS CLI not found. Please install AWS CLI v2."
4. Restore AWS: `mv /usr/local/bin/aws.bak /usr/local/bin/aws`

**Test Missing AWS Credentials:**
1. Run: `unset AWS_ACCESS_KEY_ID; unset AWS_SECRET_ACCESS_KEY`
2. Create resource group with invalid credentials or delete `~/.aws/credentials`
3. Run analysis
4. Error should appear: "Unable to locate credentials"

## Test Part 5: Analysis Workflow

### 5.1 Single Resource Group Analysis

**Steps:**
1. Login to dashboard
2. Select first resource group from dropdown
3. Click "Run Analysis" button
4. Watch WebSocket progress messages:
   - "Listing AWS Resource Groups..."
   - "Scanning AWS resources in 'group-name'..."
   - "Analyzing costs with AI..."
   - "Storing results..."
   - "Analysis complete"

**Expected Results:**
- Analysis takes 10-30 seconds (depends on number of resources)
- Progress messages appear in real-time
- Redirected to Report page after completion
- Report displays all discovered resources

**ProgressTracker Component Checks:**
- Each message shows with timestamp
- Completed messages show with ✓ icon (green)
- Messages are scrollable if many results
- Spinning indicator visible during progress

### 5.2 Report Display

**Expected Report Sections:**

1. **Header:**
   - Title: "Analysis Report"
   - Resource Group name
   - Analysis UUID

2. **Estimated Savings (if analysis completed):**
   - Green box with savings amount
   - Number of issues found

3. **Analysis Summary:**
   - 2-3 paragraph summary of findings

4. **Issues Found:**
   - For each issue:
     - Title (e.g., "Over-provisioned EC2 Instance")
     - Severity badge (red=high, yellow=medium, blue=low)
     - Resource name and type
     - Description
     - Estimated individual savings
     - **Fix Command** in copyable code block
     - Copy button

5. **General Recommendations:**
   - List of strategic recommendations

6. **Resources Scanned:**
   - Table with 200+ resources scrollable
   - Columns: Name, Type, Region

7. **Action Buttons:**
   - "← Back to Dashboard"
   - "View History →"

### 5.3 Copy Fix Command Test

**Steps:**
1. On Report page, locate first issue with `fix_command`
2. Click "📋 Copy Command" button
3. Paste in terminal: `Ctrl+V` or `Cmd+V`
4. Verify full AWS CLI command appears

**Example Fix Command:**
```bash
aws ec2 stop-instances --instance-ids i-0123456789abcdef0
```

### 5.4 Multiple Resource Groups

**Steps:**
1. Return to dashboard
2. Select different resource group
3. Click "Run Analysis"
4. Complete analysis
5. View report

**Expected Results:**
- Different resources appear for different groups
- Different analysis results based on resources
- Each analysis gets unique UUID

## Test Part 6: History and Database

### 6.1 History Page Display

**Steps:**
1. Complete 2-3 analyses first (different resource groups)
2. Logout and login to verify persistence
3. Click "View History" from dashboard

**Expected Results:**
- Table shows all past analyses
- Columns: Resource Group, Date, Resources, Issues Found, Est. Savings, Status, Action
- Status badges:
  - Green "completed" for finished analyses
  - Blue "in_progress" for ongoing analyses
  - Red "failed" for errors
- Dates formatted as: "1/15/2024, 3:45:30 PM"
- Most recent analyses appear first
- "Run Your First Analysis" button appears if empty

### 6.2 View Past Analysis

**Steps:**
1. On History page, click "View Report →" for any analysis
2. Page shows loading indicator briefly
3. Redirected to `/report/{analysis_id}`
4. Full analysis details load from database

**Expected Results:**
- Report displays with resources from database
- Analysis results include previously calculated issues
- All fix commands present
- Same content as when initially viewed

### 6.3 Database Verification

```bash
# Connect to database
psql -U postgres -d ai_cost_detective

# Check users table
SELECT id, email, created_at FROM users;
# Should show: test@example.com

# Check analyses table
SELECT id, user_id, resource_group, status, created_at FROM analyses ORDER BY created_at DESC;
# Should show completed and in_progress analyses

# Check detailed analysis
SELECT analysis_result FROM analyses WHERE id = 1;
# Should show JSONB with full analysis data
```

## Test Part 7: Error Scenarios

### 7.1 Missing Database Configuration

**Steps:**
1. Unset `DATABASE_URL` from `.env`
2. Restart backend
3. Try to login (should work - no DB needed)
4. Try to run analysis

**Expected Results:**
- Database endpoints show: "Database is not configured"
- `/api/history` returns 503
- Analysis doesn't store in DB but still returns results
- Progress messages show normally

### 7.2 Missing OpenAI API Key

**Steps:**
1. Unset `OPENAI_API_KEY` from `.env`
2. Restart backend
3. Run analysis on resource group

**Expected Results:**
- Resource scanning completes normally ✓
- AI analysis step shows: "OpenAI not configured"
- Report shows resources but no issues/recommendations
- Still redirects to report page with partial data

### 7.3 Invalid JWT Token

**Steps:**
1. Open browser DevTools → Console
2. Modify token: `localStorage.setItem('access_token', 'invalid.token.here')`
3. Refresh page or navigate to `/dashboard`

**Expected Results:**
- Redirected to login page
- Token removed from localStorage
- Error message: "Invalid or expired token"

### 7.4 Network Error During Analysis

**Steps:**
1. Start analysis
2. While in progress, disconnect network (DevTools → Network → Offline)
3. Wait for WebSocket error

**Expected Results:**
- WebSocket disconnects gracefully
- Error message appears: "Connection error during analysis"
- Analyze button becomes enabled again
- Can retry analysis after reconnecting

## Test Part 8: Authorization Tests

### 8.1 JWT in Headers

**Steps:**
1. Open browser DevTools → Network tab
2. Trigger API call (e.g., click "Run Analysis")
3. Inspect request headers

**Expected Results:**
- Authorization header present: `Bearer eyJ...`
- Header format correct: "Bearer {token}"
- Present on: `/api/analyze`, `/api/history`, `/api/analysis/*`
- NOT present on: `/api/auth/signup`, `/api/auth/login`

### 8.2 Unauthorized Access

**Steps:**
```bash
# Try accessing protected endpoint without authorization
curl http://localhost:8000/api/history
```

**Expected Results:**
```json
{
  "detail": {
    "error": "Authorization header missing",
    "code": "MISSING_AUTH"
  }
}
```

HTTP Status: 401

### 8.3 User Isolation

**Steps:**
1. User A: Create account with email `user-a@example.com`
2. User A: Run 2 analyses
3. Logout
4. User B: Create account with email `user-b@example.com`
5. User B: Go to `/history`
6. Inspect database

**Expected Results:**
- User B only sees analyses created by User B (none if first time)
- User A's analyses not visible to User B
- Database has separate records for each user with correct `user_id` foreign key

## Test Part 9: Performance Tests

### 9.1 Large Resource Group

**Test with resource group containing 100+ resources:**

**Expected Results:**
- Scanning completes within 30-60 seconds
- Progress messages stream in real-time
- Database stores results without timeout
- Report page loads with scrollable table of 100+ resources

### 9.2 Pagination Test

```bash
# Check if history respects limit=50
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/history?limit=50"
```

**Expected Results:**
- Returns max 50 analyses even if user has 100+
- Newest analyses appear first (ORDER BY created_at DESC)

## Test Part 10: UI/UX Verification

### 10.1 Responsive Design

1. Test on desktop browser (1920x1080)
2. Resize to mobile (375x667)
3. Check Reports for mobile:
   - Tables should wrap/scroll
   - buttons should be touch-friendly
   - Text should be readable

### 10.2 Dark Theme

- Verify all text is readable on dark background
- Ensure error messages are visible (red on dark gray)
- Buttons have good contrast and hover states

### 10.3 Loading States

1. Slow network simulation (DevTools → Network → Slow 3G)
2. Analyze and watch UI:
   - Button changes to "Analyzing..." state
   - Progress tracker shows messages
   - No duplicate submissions possible

## Troubleshooting Guide

### Backend won't start
```bash
# Check Python version
python --version  # Should be 3.10+

# Check pip packages
pip list | grep fastapi

# Verify dependencies
pip install -r requirements.txt --upgrade
```

### Frontend won't start
```bash
# Check Node version
node --version  # Should be 16+

# Clear cache
rm -rf node_modules package-lock.json
npm install
```

### Database connection fails
```bash
# Check PostgreSQL is running
ps aux | grep postgres

# Test connection directly
psql -U postgres -d ai_cost_detective

# Check .env format (no spaces around =)
cat backend/.env
```

### JWT token keeps expiring
- Check system time is correct: `date`
- Verify JWT_EXPIRATION_HOURS is set in .env
- Check token wasn't manually corrupted

### WebSocket fails but API works
- Check Vite proxy config in `frontend/vite.config.ts`
- Verify `/ws` is mapped to `ws://localhost:8000`
- Check backend WebSocket is actually running

## Automated Testing (Optional)

Run backend tests:
```bash
cd backend
python -m pytest tests/ -v
```

Run frontend tests:
```bash
cd frontend
npm test
```

## Success Criteria

All tests pass when you can:

✅ Create account with email/password
✅ Login with valid credentials
✅ Logout successfully
✅ Fetch AWS resource groups
✅ Run analysis with real-time progress
✅ View analysis report with issues and fix commands
✅ Copy fix commands to clipboard
✅ See all past analyses in history
✅ View any past analysis with full details
✅ Receive proper error messages for failures
✅ Handle network disconnections gracefully
✅ Can't access other user's analyses
✅ Database stores all data correctly
✅ JWT token is sent with all protected requests

