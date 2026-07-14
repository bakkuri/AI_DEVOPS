"""
AI Cloud Cost Detective - FastAPI Backend

Provides endpoints for AWS resource analysis and cost detection.
Steps of the request flow:
  - Step ①: Authentication (signup/login with JWT)
  - Step ③: Fetches resources using AWS CLI
  - Step ④: WebSocket progress tracking
  - Step ⑤: Performs AI-powered cost analysis
  - Step ⑥: Stores results in PostgreSQL
"""

import logging
import asyncio
import uuid
import json
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from contextlib import asynccontextmanager

from aws_scanner import (
    AWSScanner,
    AWSCliNotFoundError,
    AWSAuthenticationError,
    AWSResourceGroupError,
    Resource
)
from ai_analyzer import (
    AIAnalyzer,
    AIAnalyzerError,
    OpenAIConfigError,
    OpenAIAPIError,
    CostAnalysis,
    CostIssue
)
from auth import (
    AuthService,
    InvalidCredentialsError,
    TokenError
)
from db import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# WebSocket connection manager for progress tracking
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, analysis_id: str, websocket: WebSocket):
        """Connect a WebSocket client to an analysis."""
        await websocket.accept()
        if analysis_id not in self.active_connections:
            self.active_connections[analysis_id] = set()
        self.active_connections[analysis_id].add(websocket)
        logger.info(f"WebSocket connected for analysis {analysis_id}")
    
    def disconnect(self, analysis_id: str, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        if analysis_id in self.active_connections:
            self.active_connections[analysis_id].discard(websocket)
            if not self.active_connections[analysis_id]:
                del self.active_connections[analysis_id]
            logger.info(f"WebSocket disconnected for analysis {analysis_id}")
    
    async def broadcast(self, analysis_id: str, message: str, status: str = "progress"):
        """Send a message to all connected clients for an analysis."""
        if analysis_id not in self.active_connections:
            return
        
        payload = {
            "type": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        for connection in list(self.active_connections[analysis_id]):
            try:
                await connection.send_json(payload)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {str(e)}")
                self.active_connections[analysis_id].discard(connection)

manager = ConnectionManager()

# Dependency function to get current user from JWT token
async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Extract and verify JWT token from Authorization header.
    
    Args:
        authorization: Authorization header value ("Bearer <token>")
        
    Returns:
        Decoded token payload with user_id and email
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authorization header missing",
                "code": "MISSING_AUTH"
            }
        )
    
    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise TokenError("Invalid authorization header format")
        
        token = parts[1]
        payload = AuthService.verify_token(token)
        return payload
    
    except TokenError as e:
        logger.warning(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": str(e),
                "code": "INVALID_TOKEN"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected auth error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authentication failed",
                "code": "AUTH_ERROR"
            }
        )

# Lifespan context manager for app startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app startup and shutdown events."""
    # Startup
    try:
        await db.connect()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Failed to connect to database during startup: {str(e)}")
        logger.warning("Running in read-only mode without database features")
    
    yield
    
    # Shutdown
    await db.disconnect()
    logger.info("Application shutdown complete")

# Initialize FastAPI app
app = FastAPI(
    title="AI Cloud Cost Detective API",
    description="AWS resource analysis and cost detection backend",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

# Request/Response Models
# ============================================================================

class SignupRequest(BaseModel):
    """Request model for user signup."""
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Response model for auth endpoints."""
    access_token: str
    token_type: str
    user_id: int
    email: str


class UserResponse(BaseModel):
    """Response model for user info."""
    id: int
    email: str
    created_at: datetime


class AnalyzeRequest(BaseModel):
    """Request model for resource analysis."""
    resource_group: str
    user_id: Optional[int] = None  # Optional, populated from JWT if not provided


class ResourceResponse(BaseModel):
    """Response model for a single AWS resource."""
    resource_type: str
    name: str
    region: str
    sku: str
    tags: Dict[str, str]
    arn: str


class CostIssueResponse(BaseModel):
    """Response model for a single cost issue identified by AI."""
    title: str
    description: str
    severity: str  # "high", "medium", "low"
    resource_name: str
    resource_type: str
    estimated_savings: str
    fix_command: Optional[str] = None


class CostAnalysisResponse(BaseModel):
    """Response model for AI cost analysis results."""
    summary: str
    total_estimated_savings: str
    issues: List[CostIssueResponse]
    recommendations: List[str]


class AnalyzeResponse(BaseModel):
    """Response model for analysis endpoint with both resources and AI analysis."""
    analysis_id: str
    resource_group: str
    resources: List[ResourceResponse]
    total_resources: int
    analysis: Optional[CostAnalysisResponse] = None


class ResourceGroupsResponse(BaseModel):
    """Response model for list resource groups endpoint."""
    resource_groups: List[str]
    total_groups: int


class AnalysisHistoryItem(BaseModel):
    """Single item in analysis history."""
    id: int
    resource_group: str
    resources_scanned: int
    issues_found: int
    estimated_savings: Optional[str]
    status: str
    created_at: datetime


class AnalysisHistoryResponse(BaseModel):
    """Response model for analysis history."""
    total: int
    analyses: List[AnalysisHistoryItem]


class ErrorResponse(BaseModel):
    """Response model for errors."""
    error: str
    code: str


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns: {"status": "ok"}
    """
    return {"status": "ok"}


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/api/auth/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    """
    User signup endpoint.
    
    Creates a new user account and returns a JWT token.
    
    Request Body:
        {
            "email": "user@example.com",
            "password": "securepassword"
        }
    
    Returns:
        AuthResponse with JWT token, user_id, and email
        
    HTTP Status:
        200: User created successfully
        400: Email already exists
        422: Invalid request (missing fields)
    """
    if not db.pool:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Database is not configured",
                "code": "DB_NOT_CONFIGURED"
            }
        )
    
    if not request.email or not request.password:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Email and password are required",
                "code": "INVALID_REQUEST"
            }
        )
    
    if len(request.password) < 6:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Password must be at least 6 characters",
                "code": "WEAK_PASSWORD"
            }
        )
    
    try:
        logger.info(f"Processing signup for email: {request.email}")
        
        # Hash password
        password_hash = AuthService.hash_password(request.password)
        
        # Create user in database
        user_id = await db.create_user(request.email, password_hash)
        
        # Generate JWT token
        token = AuthService.create_token(user_id, request.email)
        
        logger.info(f"User created successfully: {request.email}")
        
        return AuthResponse(
            access_token=token,
            token_type="bearer",
            user_id=user_id,
            email=request.email
        )
    
    except Exception as e:
        error_msg = str(e)
        
        # Check for unique constraint violation (email already exists)
        if "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            logger.warning(f"Signup failed: Email already exists: {request.email}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Email already registered",
                    "code": "EMAIL_EXISTS"
                }
            )
        
        logger.error(f"Signup error: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to create user",
                "code": "SIGNUP_ERROR"
            }
        )


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    User login endpoint.
    
    Authenticates user credentials and returns a JWT token.
    
    Request Body:
        {
            "email": "user@example.com",
            "password": "securepassword"
        }
    
    Returns:
        AuthResponse with JWT token, user_id, and email
        
    HTTP Status:
        200: Login successful
        401: Invalid credentials or user not found
        422: Invalid request (missing fields)
    """
    if not db.pool:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Database is not configured",
                "code": "DB_NOT_CONFIGURED"
            }
        )
    
    if not request.email or not request.password:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Email and password are required",
                "code": "INVALID_REQUEST"
            }
        )
    
    try:
        logger.info(f"Processing login for email: {request.email}")
        
        # Get user from database
        user = await db.get_user_by_email(request.email)
        
        if not user:
            logger.warning(f"Login failed: User not found: {request.email}")
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Invalid email or password",
                    "code": "INVALID_CREDENTIALS"
                }
            )
        
        # Verify password
        if not AuthService.verify_password(request.password, user['password_hash']):
            logger.warning(f"Login failed: Invalid password for: {request.email}")
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Invalid email or password",
                    "code": "INVALID_CREDENTIALS"
                }
            )
        
        # Generate JWT token
        token = AuthService.create_token(user['id'], user['email'])
        
        logger.info(f"User logged in successfully: {request.email}")
        
        return AuthResponse(
            access_token=token,
            token_type="bearer",
            user_id=user['id'],
            email=user['email']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Login failed",
                "code": "LOGIN_ERROR"
            }
        )


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get current user information.
    
    Requires: Authorization: Bearer <token> header
    
    Returns:
        UserResponse with user id, email, and created_at
        
    HTTP Status:
        200: User info returned
        401: Invalid or missing token
    """
    if not db.pool:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Database is not configured",
                "code": "DB_NOT_CONFIGURED"
            }
        )
    
    try:
        user_id = current_user.get('user_id')
        user = await db.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "User not found",
                    "code": "USER_NOT_FOUND"
                }
            )
        
        return UserResponse(
            id=user['id'],
            email=user['email'],
            created_at=user['created_at']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to get user info",
                "code": "USER_INFO_ERROR"
            }
        )


# ============================================================================
# AWS & Analysis Endpoints
# ============================================================================

@app.get("/api/auth-check")
async def auth_check():
    """
    Check AWS authentication status.
    
    Returns:
        {"authenticated": true/false, "message": "..."}
        
    HTTP Status:
        200: Authentication status returned (check 'authenticated' field)
        500: AWS CLI not installed
    """
    try:
        AWSScanner.verify_aws_authentication()
        return {
            "authenticated": True,
            "message": "AWS credentials configured and valid"
        }
    except AWSCliNotFoundError as e:
        logger.error(f"AWS CLI not found: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "code": "AWS_CLI_NOT_FOUND"
            }
        )
    except AWSAuthenticationError as e:
        logger.warning(f"AWS authentication failed: {str(e)}")
        return {
            "authenticated": False,
            "message": str(e)
        }


@app.get("/api/resource-groups", response_model=ResourceGroupsResponse)
async def get_resource_groups():
    """
    Fetch list of all AWS Resource Groups.
    
    Returns:
        ResourceGroupsResponse with list of group names
        
    HTTP Status:
        200: Successfully returned resource groups
        500: AWS CLI not installed
        401: AWS authentication failed
        400: Other AWS operation failed
    """
    try:
        groups = AWSScanner.list_resource_groups()
        return ResourceGroupsResponse(
            resource_groups=groups,
            total_groups=len(groups)
        )
    
    except AWSCliNotFoundError as e:
        logger.error(f"AWS CLI not found: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "code": "AWS_CLI_NOT_FOUND"
            }
        )
    except AWSAuthenticationError as e:
        logger.error(f"AWS authentication failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": str(e),
                "code": "AWS_AUTHENTICATION_FAILED"
            }
        )
    except AWSResourceGroupError as e:
        logger.error(f"AWS operation failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": str(e),
                "code": "AWS_OPERATION_FAILED"
            }
        )
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR"
            }
        )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_resource_group(
    request: AnalyzeRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Analyze resources in a specific AWS Resource Group with AI-powered cost analysis.
    
    Optional: Include Authorization: Bearer <token> header to use authenticated user ID.
    
    This endpoint:
      1. Creates an analysis record and generates a unique analysis_id
      2. Broadcasts progress via WebSocket at ws://localhost:8000/ws/progress/{analysis_id}
      3. Fetches all resources in the AWS Resource Group (Step ③)
      4. Performs AI-powered cost analysis using OpenAI (Step ⑤)
      5. Stores results in PostgreSQL (Step ⑥)
    
    Request Body:
        {
            "resource_group": "<group-name>",
            "user_id": 1  (optional)
        }
    
    Returns:
        AnalyzeResponse with:
          - analysis_id for WebSocket progress tracking
          - List of discovered AWS resources
          - AI-powered cost analysis (if OpenAI API is configured)
        
    HTTP Status:
        200: Successfully analyzed resource group
        500: AWS CLI not installed or OpenAI API error
        401: AWS authentication failed
        400: Invalid resource group or other AWS operation failed
        422: Invalid request (missing resource_group field)
    """
    if not request.resource_group or not request.resource_group.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error": "resource_group is required and cannot be empty",
                "code": "INVALID_REQUEST"
            }
        )
    
    group_name = request.resource_group.strip()
    analysis_id = str(uuid.uuid4())
    
    # Extract user_id from JWT if provided, otherwise use request.user_id or default to 1
    user_id = request.user_id
    if not user_id and authorization:
        try:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                payload = AuthService.verify_token(token)
                user_id = payload.get('user_id')
        except Exception:
            pass  # Continue without auth if JWT is invalid
    if not user_id:
        user_id = 1
    
    logger.info(f"Starting analysis {analysis_id} for resource group: {group_name} (user: {user_id})")
    
    try:
        # Create analysis record in database
        db_analysis_id = None
        if db.pool:
            try:
                db_analysis_id = await db.create_analysis(user_id, group_name)
                logger.info(f"Created analysis record in DB: {db_analysis_id}")
            except Exception as e:
                logger.warning(f"Failed to create analysis record: {str(e)}")

        # Give the client a short window to connect to the WebSocket so it doesn't miss final broadcasts.
        # If no client connects within the timeout, proceed anyway.
        try:
            wait_seconds = 3
            interval = 0.1
            waited = 0.0
            while waited < wait_seconds:
                if analysis_id in manager.active_connections:
                    logger.info(f"Client connected for analysis {analysis_id} after {waited:.1f}s")
                    break
                await asyncio.sleep(interval)
                waited += interval
        except Exception:
            # Non-fatal if asyncio sleep or check fails
            pass
        
        # Step ③: Fetch AWS resources with progress tracking
        await manager.broadcast(analysis_id, "Listing AWS Resource Groups...")
        await manager.broadcast(analysis_id, f"Scanning AWS resources in '{group_name}'...")
        
        resources = AWSScanner.list_group_resources(group_name)
        
        resource_responses = [
            ResourceResponse(
                resource_type=r.resource_type,
                name=r.name,
                region=r.region,
                sku=r.sku,
                tags=r.tags,
                arn=r.arn
            )
            for r in resources
        ]
        
        # Step ⑤: Perform AI-powered cost analysis
        analysis_response = None
        analysis_data = None
        
        try:
            await manager.broadcast(analysis_id, "Analyzing costs with AI...")
            logger.info("Starting AI cost analysis")
            
            analyzer = AIAnalyzer()
            analysis = analyzer.analyze(resources)
            analysis_data = analysis
            
            # Convert analysis to response model
            issue_responses = [
                CostIssueResponse(
                    title=issue.title,
                    description=issue.description,
                    severity=issue.severity,
                    resource_name=issue.resource_name,
                    resource_type=issue.resource_type,
                    estimated_savings=issue.estimated_savings,
                    fix_command=issue.fix_command
                )
                for issue in analysis.issues
            ]
            
            analysis_response = CostAnalysisResponse(
                summary=analysis.summary,
                total_estimated_savings=analysis.total_estimated_savings,
                issues=issue_responses,
                recommendations=analysis.recommendations
            )
            
            logger.info(f"Cost analysis complete: {len(analysis.issues)} issues found")
        
        except OpenAIConfigError as e:
            logger.error(f"OpenAI not configured: {str(e)}")
            await manager.broadcast(analysis_id, f"AI analysis failed: OpenAI API key is not configured.", status="error")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "OpenAI API key is not configured. Set OPENAI_API_KEY in your environment.",
                    "code": "OPENAI_API_CONFIG_ERROR"
                }
            )
        except OpenAIAPIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            await manager.broadcast(analysis_id, f"AI analysis failed: {str(e)}", status="error")
            raise HTTPException(
                status_code=502,
                detail={
                    "error": str(e),
                    "code": "OPENAI_API_ERROR"
                }
            )
        except AIAnalyzerError as e:
            logger.error(f"AI analysis error: {str(e)}")
            await manager.broadcast(analysis_id, f"Analysis error: {str(e)}", status="error")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": str(e),
                    "code": "AI_ANALYSIS_ERROR"
                }
            )
        
        # Step ⑥: Store results in database
        if db.pool and db_analysis_id:
            try:
                await manager.broadcast(analysis_id, "Storing results...")
                
                issues_found = len(analysis_data.issues) if analysis_data else 0
                total_savings = analysis_data.total_estimated_savings if analysis_data else "Unknown"
                
                # Prepare analysis result for storage
                analysis_result = {
                    "analysis_id": analysis_id,
                    "summary": analysis_response.summary if analysis_response else "",
                    "total_estimated_savings": total_savings,
                    "resources": [
                        {
                            "resource_type": r.resource_type,
                            "name": r.name,
                            "region": r.region,
                            "sku": r.sku,
                            "tags": r.tags,
                            "arn": r.arn
                        }
                        for r in resource_responses
                    ],
                    "issues": [
                        {
                            "title": issue.title,
                            "description": issue.description,
                            "severity": issue.severity,
                            "resource_name": issue.resource_name,
                            "resource_type": issue.resource_type,
                            "estimated_savings": issue.estimated_savings,
                            "fix_command": issue.fix_command
                        }
                        for issue in (analysis_data.issues if analysis_data else [])
                    ],
                    "recommendations": analysis_data.recommendations if analysis_data else []
                }
                
                await db.update_analysis(
                    db_analysis_id,
                    resources_scanned=len(resources),
                    issues_found=issues_found,
                    estimated_savings=total_savings,
                    analysis_result=analysis_result,
                    status="completed"
                )
                logger.info(f"Stored analysis results in DB: {db_analysis_id}")
            except Exception as e:
                logger.error(f"Failed to store analysis results: {str(e)}")
        
        await manager.broadcast(analysis_id, "Analysis complete", status="completed")
        
        return AnalyzeResponse(
            analysis_id=analysis_id,
            resource_group=group_name,
            resources=resource_responses,
            total_resources=len(resource_responses),
            analysis=analysis_response
        )
    
    except AWSCliNotFoundError as e:
        logger.error(f"AWS CLI not found: {str(e)}")
        await manager.broadcast(analysis_id, str(e), status="error")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "code": "AWS_CLI_NOT_FOUND"
            }
        )
    except AWSAuthenticationError as e:
        logger.error(f"AWS authentication failed: {str(e)}")
        await manager.broadcast(analysis_id, str(e), status="error")
        raise HTTPException(
            status_code=401,
            detail={
                "error": str(e),
                "code": "AWS_AUTHENTICATION_FAILED"
            }
        )
    except AWSResourceGroupError as e:
        logger.error(f"AWS operation failed: {str(e)}")
        await manager.broadcast(analysis_id, str(e), status="error")
        raise HTTPException(
            status_code=400,
            detail={
                "error": str(e),
                "code": "AWS_OPERATION_FAILED"
            }
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.exception(f"Unexpected error analyzing resource group: {str(e)}")
        await manager.broadcast(analysis_id, str(e), status="error")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR"
            }
        )


@app.get("/api/history", response_model=AnalysisHistoryResponse)
async def get_analysis_history(authorization: Optional[str] = Header(None)):
    """
    Get analysis history for the authenticated user.
    
    Requires: Authorization: Bearer <token> header
    
    Returns:
        AnalysisHistoryResponse with list of past analyses
        
    HTTP Status:
        200: Successfully returned history
        401: Missing or invalid JWT token
        500: Database error
        503: Database not configured
    """
    if not db.pool:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Database is not configured",
                "code": "DB_NOT_CONFIGURED"
            }
        )
    
    # Extract user_id from JWT
    user_id = None
    if authorization:
        try:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                payload = AuthService.verify_token(token)
                user_id = payload.get('user_id')
        except Exception as e:
            logger.warning(f"Token verification failed: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Invalid or expired token",
                    "code": "INVALID_TOKEN"
                }
            )
    
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authorization header missing",
                "code": "MISSING_AUTH"
            }
        )
    
    try:
        logger.info(f"Fetching analysis history for user {user_id}")
        analyses = await db.get_user_analyses(user_id, limit=50)
        
        history_items = [
            AnalysisHistoryItem(
                id=a['id'],
                resource_group=a['resource_group'],
                resources_scanned=a['resources_scanned'],
                issues_found=a['issues_found'],
                estimated_savings=a['estimated_savings'],
                status=a['status'],
                created_at=a['created_at']
            )
            for a in analyses
        ]
        
        return AnalysisHistoryResponse(
            total=len(history_items),
            analyses=history_items
        )
    
    except Exception as e:
        logger.exception(f"Error fetching analysis history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to fetch analysis history",
                "code": "DB_ERROR"
            }
        )


@app.get("/api/analysis/{analysis_db_id}", response_model=AnalyzeResponse)
async def get_analysis_details(
    analysis_db_id: int,
    authorization: Optional[str] = Header(None)
):
    """
    Get details of a specific analysis by database ID.
    
    Requires: Authorization: Bearer <token> header
    
    Args:
        analysis_db_id: Database ID of the analysis (from history)
    
    Returns:
        AnalyzeResponse with full analysis details
        
    HTTP Status:
        200: Successfully returned analysis
        401: Missing or invalid JWT token
        404: Analysis not found
        500: Database error
        503: Database not configured
    """
    if not db.pool:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Database is not configured",
                "code": "DB_NOT_CONFIGURED"
            }
        )
    
    # Extract user_id from JWT for authorization check
    user_id = None
    if authorization:
        try:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                payload = AuthService.verify_token(token)
                user_id = payload.get('user_id')
        except Exception as e:
            logger.warning(f"Token verification failed: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Invalid or expired token",
                    "code": "INVALID_TOKEN"
                }
            )
    
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authorization header missing",
                "code": "MISSING_AUTH"
            }
        )
    
    try:
        logger.info(f"Fetching analysis details for DB ID {analysis_db_id} (user: {user_id})")
        
        # Get analysis from database
        async with db.pool.acquire() as conn:
            analysis = await conn.fetchrow(
                'SELECT id, user_id, resource_group, resources_scanned, issues_found, estimated_savings, analysis_result FROM analyses WHERE id = $1 AND user_id = $2',
                analysis_db_id, user_id
            )
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Analysis not found",
                    "code": "ANALYSIS_NOT_FOUND"
                }
            )
        
        analysis_dict = dict(analysis)
        analysis_result = analysis_dict.get('analysis_result') or {}
        if isinstance(analysis_result, str):
            try:
                analysis_result = json.loads(analysis_result)
            except json.JSONDecodeError:
                logger.warning("Analysis result is stored as invalid JSON string; treating as empty result")
                analysis_result = {}
        
        # Reconstruct AnalyzeResponse
        resources = [
            ResourceResponse(
                resource_type=r.get('resource_type', 'Unknown'),
                name=r.get('name', 'Unknown'),
                region=r.get('region', 'Unknown'),
                sku=r.get('sku', 'Unknown'),
                tags=r.get('tags', {}),
                arn=r.get('arn', '')
            )
            for r in analysis_result.get('resources', [])
        ] if isinstance(analysis_result, dict) and 'resources' in analysis_result else []
        
        # Build cost analysis response
        analysis_response = None
        if analysis_result.get('issues') or analysis_result.get('recommendations'):
            analysis_response = CostAnalysisResponse(
                summary=analysis_result.get('summary', ''),
                total_estimated_savings=analysis_result.get('total_estimated_savings', 'Unknown'),
                issues=[
                    CostIssueResponse(
                        title=issue.get('title', 'Unknown'),
                        description=issue.get('description', ''),
                        severity=issue.get('severity', 'medium'),
                        resource_name=issue.get('resource_name', ''),
                        resource_type=issue.get('resource_type', ''),
                        estimated_savings=issue.get('estimated_savings', '-'),
                        fix_command=issue.get('fix_command')
                    )
                    for issue in analysis_result.get('issues', [])
                ],
                recommendations=analysis_result.get('recommendations', [])
            )
        
        return AnalyzeResponse(
            analysis_id=analysis_result.get('analysis_id', str(analysis_dict.get('id'))),
            resource_group=analysis_dict.get('resource_group', ''),
            resources=resources,
            total_resources=analysis_dict.get('resources_scanned', 0),
            analysis=analysis_response
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching analysis details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to fetch analysis details",
                "code": "DB_ERROR"
            }
        )


@app.websocket("/ws/progress/{analysis_id}")
async def websocket_progress(websocket: WebSocket, analysis_id: str):
    """
    WebSocket endpoint for real-time progress tracking of analysis.
    
    URL: ws://localhost:8000/ws/progress/{analysis_id}
    
    The endpoint will broadcast progress messages to all connected clients as the analysis progresses.
    Messages are JSON objects with:
        {
            "type": "progress|completed|error",
            "message": "Status message",
            "timestamp": "ISO timestamp"
        }
    
    Example client code (JavaScript):
        const ws = new WebSocket('ws://localhost:8000/ws/progress/analysis-uuid');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data.message);
        };
    """
    try:
        await manager.connect(analysis_id, websocket)
        
        while True:
            # Keep connection open, allow client to ping/keep-alive
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from client on {analysis_id}: {data}")
            except WebSocketDisconnect:
                manager.disconnect(analysis_id, websocket)
                break
    
    except Exception as e:
        logger.error(f"WebSocket error for analysis {analysis_id}: {str(e)}")
        manager.disconnect(analysis_id, websocket)


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting AI Cloud Cost Detective API server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
