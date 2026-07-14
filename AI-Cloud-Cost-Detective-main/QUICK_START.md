# Quick Start Guide

Get the AI Cloud Cost Detective running in 5 minutes.

## Step 1: Prerequisites (5 minutes)

### Install Required Software

**macOS:**
```bash
# Install Homebrew packages
brew install python@3.11 node postgresql

# Start PostgreSQL
brew services start postgresql

# Verify installations
python3 --version   # Should be 3.11+
node --version      # Should be 16+
psql --version      # Should be 14+
aws --version       # Should be 2.x
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3.11 nodejs postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
- Download Python 3.11+ from python.org
- Download Node.js 16+ from nodejs.org
- Download PostgreSQL from postgresql.org
- Download AWS CLI from aws.amazon.com
- Run all installers and follow prompts

### Configure AWS CLI

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter default region (e.g., us-east-1)
# Enter default output format: json
```

Verify:
```bash
aws sts get-caller-identity
```

## Step 2: Backend Setup (2 minutes)

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cat > .env << EOF
OPENAI_API_KEY=sk-your-api-key-here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_cost_detective
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
EOF

# Create database
createdb ai_cost_detective

# Start backend server
python3 main.py
```

Expected output:
```
INFO:__main__:Starting AI Cloud Cost Detective API server...
INFO:uvicorn.server:Uvicorn running on http://0.0.0.0:8000
```

## Step 3: Frontend Setup (2 minutes)

In a **new terminal**:

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Expected output:
```
  VITE v5.0.6  ready in XX ms

  ➜  Local:   http://localhost:5173/
```

## Step 4: Test the Application (30 seconds)

1. Open browser: `http://localhost:5173`
2. Click "Sign up"
3. Enter any email and password
4. Select resource group from dropdown
5. Click "Run Analysis"
6. Watch live progress tracking
7. View report with findings

## Key Environment Variables

Create `backend/.env`:

```bash
# Required: OpenAI API Key
# Get from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...

# Required: PostgreSQL Connection
# Format: postgresql://username:password@host:port/database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_cost_detective

# Required: JWT Secret (run: python3 -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET=your-secret-here

# Optional: JWT Configuration (defaults provided)
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

## Troubleshooting

### Backend fails to start
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql  # Linux
brew services list  # macOS

# Create database if missing
createdb ai_cost_detective

# Install missing dependencies
pip install -r requirements.txt --upgrade
```

### Frontend can't connect to backend
```bash
# Check backend is running on port 8000
curl http://localhost:8000/health

# Check Vite proxy is configured correctly
cat frontend/vite.config.ts | grep proxy
```

### "AWS CLI not found" error
```bash
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure
```

### "Database not configured" error
```bash
# Set DATABASE_URL and restart backend
echo "DATABASE_URL=postgresql://..." >> backend/.env
python main.py
```

## What Gets Created

After running the application:

**Database Tables:**
- `users` - Stores account information with password hashes
- `analyses` - Stores analysis history with full results

**Storage:**
- Browser localStorage - Stores JWT authentication token
- PostgreSQL database - Stores persistent user and analysis data

**API Endpoints:**
- `GET /health` - Server health check
- `POST /api/auth/signup` - Create account
- `POST /api/auth/login` - Login to account
- `GET /api/resource-groups` - List AWS resource groups
- `POST /api/analyze` - Start analysis
- `GET /api/history` - Get past analyses
- `GET /api/analysis/{id}` - Get specific analysis details
- `WS /ws/progress/{id}` - WebSocket progress streaming

## Next Steps

1. **Run Tests**: See [TESTING_GUIDE.md](TESTING_GUIDE.md)
2. **Understanding Integration**: See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
3. **Production Deployment**: See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md#production-deployment)
4. **Troubleshooting**: See [TESTING_GUIDE.md](TESTING_GUIDE.md#troubleshooting-guide)

## Common Commands

```bash
# Backend
cd backend && source venv/bin/activate && python main.py

# Frontend
cd frontend && npm run dev

# Run tests
cd frontend && npm test

# Build for production
cd frontend && npm run build

# Database
psql -U postgres -d ai_cost_detective
SELECT * FROM users;
SELECT * FROM analyses;

# Check logs
# Backend: stdout in terminal where you ran `python main.py`
# Frontend: browser DevTools Console
```

## File Structure

```
AI-Cloud-Cost-Detective-main/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── aws_scanner.py          # AWS CLI integration
│   ├── ai_analyzer.py          # OpenAI integration
│   ├── auth.py                 # JWT authentication
│   ├── db.py                   # PostgreSQL database
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # Environment variables
├── frontend/
│   ├── src/
│   │   ├── api.ts              # API client
│   │   ├── auth.ts             # Auth helpers
│   │   ├── App.tsx             # Main app
│   │   ├── pages/              # Page components
│   │   └── components/         # UI components
│   ├── package.json            # Node dependencies
│   ├── vite.config.ts          # Vite configuration
│   └── tailwind.config.js      # Tailwind CSS configuration
├── INTEGRATION_GUIDE.md        # API documentation
├── TESTING_GUIDE.md            # Testing procedures
└── README.md                   # Project overview
```

## Support

- Check logs in terminal where backend/frontend are running
- Review error messages in browser DevTools Console
- Check database directly: `psql -d ai_cost_detective`
- Verify AWS CLI: `aws sts get-caller-identity`
- Verify API: `curl http://localhost:8000/health`

