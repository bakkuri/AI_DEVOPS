"""
Authentication Module

Handles JWT token generation, password hashing, and auth validation.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import bcrypt
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class AuthError(Exception):
    """Base exception for auth operations."""
    pass


class InvalidCredentialsError(AuthError):
    """Raised when credentials are invalid."""
    pass


class TokenError(AuthError):
    """Raised when token operations fail."""
    pass


class AuthService:
    """Handles JWT tokens, password hashing, and authentication."""
    
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-in-production')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', '24'))
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password to verify
            password_hash: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False
    
    @staticmethod
    def create_token(user_id: int, email: str) -> str:
        """
        Create a JWT token for a user.
        
        Args:
            user_id: User ID
            email: User email
            
        Returns:
            JWT token string
            
        Raises:
            TokenError: If token creation fails
        """
        try:
            payload = {
                'user_id': user_id,
                'email': email,
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(hours=AuthService.JWT_EXPIRATION_HOURS)
            }
            
            token = jwt.encode(
                payload,
                AuthService.JWT_SECRET,
                algorithm=AuthService.JWT_ALGORITHM
            )
            
            logger.info(f"JWT token created for user {user_id}")
            return token
        
        except Exception as e:
            error_msg = f"Failed to create JWT token: {str(e)}"
            logger.error(error_msg)
            raise TokenError(error_msg)
    
    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            TokenError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                AuthService.JWT_SECRET,
                algorithms=[AuthService.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise TokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise TokenError(f"Invalid token: {str(e)}")
        except Exception as e:
            raise TokenError(f"Token verification failed: {str(e)}")
