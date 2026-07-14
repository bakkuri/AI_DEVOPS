"""
Database Module

Handles PostgreSQL connection pool, table initialization, and database queries.
Uses asyncpg for async database operations compatible with FastAPI.
"""

import logging
import os
import asyncpg
import json
import urllib.parse
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class PostgresDatabase:
    """Manages PostgreSQL connection pool and database operations."""
    
    def __init__(self):
        """Initialize database connection parameters."""
        self.database_url = os.getenv('DATABASE_URL')
        self.pool = None
        
        if not self.database_url:
            logger.warning("DATABASE_URL not set. Database features will be unavailable.")
    
    async def connect(self):
        """
        Create the connection pool.
        
        Raises:
            Exception: If DATABASE_URL is not configured
        """
        if not self.database_url:
            raise Exception(
                "DATABASE_URL environment variable is not set. "
                "Please configure it in .env file."
            )
        
        try:
            logger.info("Connecting to PostgreSQL database...")

            # Support AWS RDS IAM authentication when enabled via USE_RDS_IAM
            use_rds_iam = os.getenv('USE_RDS_IAM', 'false').lower() == 'true'
            if use_rds_iam:
                region = os.getenv('AWS_REGION', 'us-east-1')
                # Parse components from DATABASE_URL (host, port, dbname, user)
                parsed = urllib.parse.urlparse(self.database_url)
                host = parsed.hostname or os.getenv('DB_HOST')
                port = parsed.port or int(os.getenv('DB_PORT', 5432))
                database = (parsed.path or '').lstrip('/') or os.getenv('DB_NAME')
                user = parsed.username or os.getenv('DB_USER')

                if not all([host, port, database, user]):
                    raise Exception("DATABASE_URL is missing components required for RDS IAM auth."
                                    " Provide a full DATABASE_URL or set DB_HOST/DB_PORT/DB_NAME/DB_USER.")

                try:
                    import boto3
                    # generate the IAM auth token
                    client = boto3.client('rds', region_name=region)
                    auth_token = client.generate_db_auth_token(DBHostname=host, Port=port, DBUsername=user)
                except Exception as be:
                    logger.error(f"Failed to generate RDS IAM auth token: {be}")
                    raise

                self.pool = await asyncpg.create_pool(
                    user=user,
                    password=auth_token,
                    database=database,
                    host=host,
                    port=port,
                    min_size=5,
                    max_size=20,
                    command_timeout=60,
                    ssl='require',
                )
            else:
                self.pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=5,
                    max_size=20,
                    command_timeout=60
                )

            logger.info("Database connection pool created successfully")
            await self._initialize_schema()
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise
    
    async def disconnect(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def _initialize_schema(self):
        """Create tables if they don't exist."""
        async with self.pool.acquire() as conn:
            # Create users table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            ''')
            
            # Create analyses table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS analyses (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    resource_group VARCHAR(255) NOT NULL,
                    resources_scanned INT DEFAULT 0,
                    issues_found INT DEFAULT 0,
                    estimated_savings VARCHAR(255),
                    analysis_result JSONB,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    
                    CONSTRAINT fk_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id);
                CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at);
                CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);
            ''')
            
            logger.info("Database schema initialized successfully")
    
    async def create_user(self, email: str, password_hash: str) -> int:
        """
        Create a new user.
        
        Args:
            email: User email address
            password_hash: Hashed password
            
        Returns:
            User ID
            
        Raises:
            asyncpg.UniqueViolationError: If email already exists
        """
        async with self.pool.acquire() as conn:
            user_id = await conn.fetchval(
                '''
                INSERT INTO users (email, password_hash)
                VALUES ($1, $2)
                RETURNING id
                ''',
                email, password_hash
            )
            logger.info(f"Created user with email: {email}")
            return user_id
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email.
        
        Args:
            email: User email address
            
        Returns:
            User record or None
        """
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT id, email, password_hash, created_at FROM users WHERE email = $1',
                email
            )
            return dict(user) if user else None
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User record or None
        """
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT id, email, created_at FROM users WHERE id = $1',
                user_id
            )
            return dict(user) if user else None
    
    async def create_analysis(self, user_id: int, resource_group: str) -> int:
        """
        Create a new analysis record.
        
        Args:
            user_id: ID of the user performing the analysis
            resource_group: Name of the AWS resource group
            
        Returns:
            Analysis ID
        """
        async with self.pool.acquire() as conn:
            analysis_id = await conn.fetchval(
                '''
                INSERT INTO analyses (user_id, resource_group, status)
                VALUES ($1, $2, $3)
                RETURNING id
                ''',
                user_id, resource_group, 'in_progress'
            )
            logger.info(f"Created analysis record: ID={analysis_id}")
            return analysis_id
    
    async def update_analysis(
        self,
        analysis_id: int,
        resources_scanned: int,
        issues_found: int,
        estimated_savings: str,
        analysis_result: Dict[str, Any],
        status: str = 'completed'
    ):
        """
        Update analysis record with results.
        
        Args:
            analysis_id: Analysis ID
            resources_scanned: Number of resources scanned
            issues_found: Number of issues found
            estimated_savings: Total estimated savings
            analysis_result: Full analysis result as dict
            status: Analysis status (completed, failed, etc.)
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                UPDATE analyses
                SET resources_scanned = $2,
                    issues_found = $3,
                    estimated_savings = $4,
                    analysis_result = $5,
                    status = $6,
                    updated_at = NOW()
                WHERE id = $1
                ''',
                analysis_id,
                resources_scanned,
                issues_found,
                estimated_savings,
                json.dumps(analysis_result),
                status
            )
            logger.info(f"Updated analysis record: ID={analysis_id}, status={status}")
    
    async def get_analysis(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        """
        Get analysis record by ID.
        
        Args:
            analysis_id: Analysis ID
            
        Returns:
            Analysis record or None
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                '''
                SELECT id, user_id, resource_group, resources_scanned, issues_found,
                       estimated_savings, analysis_result, status, created_at, updated_at
                FROM analyses
                WHERE id = $1
                ''',
                analysis_id
            )
            if record:
                result = dict(record)
                # Parse JSONB if stored as string
                analysis_result = result.get('analysis_result')
                if isinstance(analysis_result, str):
                    try:
                        result['analysis_result'] = json.loads(analysis_result)
                    except json.JSONDecodeError:
                        logger.warning("Analysis result is stored as invalid JSON string; treating as empty result")
                        result['analysis_result'] = {}
                return result
            return None
    
    async def get_user_analyses(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get analysis history for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of records to return
            
        Returns:
            List of analysis records ordered by creation date (newest first)
        """
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                '''
                SELECT id, resource_group, resources_scanned, issues_found,
                       estimated_savings, status, created_at, updated_at
                FROM analyses
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                ''',
                user_id, limit
            )
            result = []
            for record in records:
                item = dict(record)
                result.append(item)
            return result
    
    async def search_analyses(
        self,
        user_id: int,
        resource_group: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search analyses with optional filters.
        
        Args:
            user_id: User ID
            resource_group: Filter by resource group name (optional)
            status: Filter by status (optional)
            limit: Maximum number of records to return
            
        Returns:
            List of filtered analysis records
        """
        query = '''
            SELECT id, resource_group, resources_scanned, issues_found,
                   estimated_savings, status, created_at, updated_at
            FROM analyses
            WHERE user_id = $1
        '''
        params = [user_id]
        
        if resource_group:
            params.append(f"%{resource_group}%")
            query += f" AND resource_group ILIKE ${len(params)}"
        
        if status:
            params.append(status)
            query += f" AND status = ${len(params)}"
        
        query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)
        
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, *params)
            result = []
            for record in records:
                item = dict(record)
                result.append(item)
            return result


# Global database instance
class SqliteDatabase:
    """Lightweight SQLite-based database for local testing.

    This implements the same methods used by the PostgresDatabase but
    stores data in a local SQLite file (or in-memory) to allow running
    integration tests without an external Postgres server.
    """
    def __init__(self):
        self.database_url = os.getenv('TEST_SQLITE_DB_PATH', ':memory:')
        self.pool = None
        self._conn = None

    async def connect(self):
        """Open SQLite connection and initialize schema."""
        import aiosqlite
        logger.info("Connecting to SQLite test database (%s)...", self.database_url)
        self._conn = await aiosqlite.connect(self.database_url)
        await self._initialize_schema()
        logger.info("SQLite test database ready")

    async def disconnect(self):
        if self._conn:
            await self._conn.close()
            logger.info("SQLite test database closed")

    async def _initialize_schema(self):
        cur = await self._conn.cursor()
        await cur.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                resource_group TEXT NOT NULL,
                resources_scanned INTEGER DEFAULT 0,
                issues_found INTEGER DEFAULT 0,
                estimated_savings TEXT,
                analysis_result TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        ''')
        await self._conn.commit()
        await cur.close()

    async def create_user(self, email: str, password_hash: str) -> int:
        cur = await self._conn.execute(
            'INSERT INTO users (email, password_hash) VALUES (?, ?)',
            (email, password_hash)
        )
        await self._conn.commit()
        return cur.lastrowid

    async def get_user_by_email(self, email: str):
        cur = await self._conn.execute('SELECT id, email, password_hash, created_at FROM users WHERE email = ?', (email,))
        row = await cur.fetchone()
        await cur.close()
        return dict(row) if row else None

    async def get_user_by_id(self, user_id: int):
        cur = await self._conn.execute('SELECT id, email, created_at FROM users WHERE id = ?', (user_id,))
        row = await cur.fetchone()
        await cur.close()
        return dict(row) if row else None

    async def create_analysis(self, user_id: int, resource_group: str) -> int:
        cur = await self._conn.execute(
            'INSERT INTO analyses (user_id, resource_group, status) VALUES (?, ?, ?)',
            (user_id, resource_group, 'in_progress')
        )
        await self._conn.commit()
        return cur.lastrowid

    async def update_analysis(self, analysis_id: int, resources_scanned: int, issues_found: int, estimated_savings: str, analysis_result: Dict[str, Any], status: str = 'completed'):
        await self._conn.execute(
            '''
            UPDATE analyses
            SET resources_scanned = ?, issues_found = ?, estimated_savings = ?, analysis_result = ?, status = ?, updated_at = datetime('now')
            WHERE id = ?
            ''',
            (resources_scanned, issues_found, estimated_savings, json.dumps(analysis_result), status, analysis_id)
        )
        await self._conn.commit()

    async def get_analysis(self, analysis_id: int):
        cur = await self._conn.execute('SELECT id, user_id, resource_group, resources_scanned, issues_found, estimated_savings, analysis_result, status, created_at, updated_at FROM analyses WHERE id = ?', (analysis_id,))
        row = await cur.fetchone()
        await cur.close()
        if row:
            result = dict(row)
            if result.get('analysis_result'):
                result['analysis_result'] = json.loads(result['analysis_result'])
            return result
        return None

    async def get_user_analyses(self, user_id: int, limit: int = 50):
        cur = await self._conn.execute('SELECT id, resource_group, resources_scanned, issues_found, estimated_savings, status, created_at, updated_at FROM analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT ?', (user_id, limit))
        rows = await cur.fetchall()
        await cur.close()
        result = [dict(r) for r in rows]
        return result

    async def search_analyses(self, user_id: int, resource_group: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
        query = 'SELECT id, resource_group, resources_scanned, issues_found, estimated_savings, status, created_at, updated_at FROM analyses WHERE user_id = ?'
        params = [user_id]
        if resource_group:
            query += ' AND resource_group LIKE ?'
            params.append(f"%{resource_group}%")
        if status:
            query += ' AND status = ?'
            params.append(status)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        cur = await self._conn.execute(query, tuple(params))
        rows = await cur.fetchall()
        await cur.close()
        return [dict(r) for r in rows]


# Choose which database backend to use based on env var
USE_TEST_DB = os.getenv('USE_TEST_DB', 'false').lower() == 'true'
if USE_TEST_DB:
    db = SqliteDatabase()
else:
    db = PostgresDatabase()
