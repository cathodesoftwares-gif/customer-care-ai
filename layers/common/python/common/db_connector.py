"""
Database Connector for Multi-Tenant Database Access

Provides secure, read-only connections to client databases
with connection pooling and secrets management.
"""

import json
import logging
import os
from contextlib import contextmanager
from typing import Any, Generator, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Only import psycopg2 if available (in Lambda with layer)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not available - database connectivity disabled")


class DatabaseConnector:
    """Manages database connections for tenant databases."""

    def __init__(self, region: Optional[str] = None):
        """
        Initialize the database connector.

        Args:
            region: AWS region for Secrets Manager. Defaults to environment variable.
        """
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.secrets_client = boto3.client("secretsmanager", region_name=self.region)
        self._connections: dict = {}

    def get_credentials(self, secret_arn: str) -> dict:
        """
        Retrieve database credentials from AWS Secrets Manager.

        Args:
            secret_arn: ARN of the secret containing database credentials.

        Returns:
            dict with host, port, database, username, password.
        """
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            secret_string = response.get("SecretString")

            if secret_string:
                return json.loads(secret_string)
            else:
                raise ValueError("Secret does not contain a string value")

        except ClientError as e:
            logger.error(f"Error retrieving secret {secret_arn}: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing secret JSON: {e}")
            raise

    @contextmanager
    def get_connection(
        self,
        secret_arn: str,
        read_only: bool = True,
    ) -> Generator[Any, None, None]:
        """
        Get a database connection for the specified tenant.

        Args:
            secret_arn: ARN of the secret containing database credentials.
            read_only: If True, set the transaction to read-only mode.

        Yields:
            A database connection object.
        """
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("psycopg2 is not available")

        credentials = self.get_credentials(secret_arn)
        connection = None

        try:
            connection = psycopg2.connect(
                host=credentials["host"],
                port=credentials.get("port", 5432),
                database=credentials["database"],
                user=credentials["username"],
                password=credentials["password"],
                connect_timeout=10,
                options="-c statement_timeout=30000",  # 30 second timeout
            )

            if read_only:
                connection.set_session(readonly=True)

            yield connection

        except psycopg2.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if connection:
                connection.close()

    def execute_query(
        self,
        secret_arn: str,
        query: str,
        params: Optional[tuple] = None,
        max_rows: int = 100,
    ) -> list[dict]:
        """
        Execute a read-only query and return results as dictionaries.

        Args:
            secret_arn: ARN of the secret containing database credentials.
            query: SQL query to execute (must be SELECT).
            params: Optional tuple of query parameters.
            max_rows: Maximum number of rows to return.

        Returns:
            List of dictionaries representing the query results.
        """
        with self.get_connection(secret_arn, read_only=True) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    cursor.execute(query, params)
                    results = cursor.fetchmany(max_rows)
                    return [dict(row) for row in results]
                except psycopg2.Error as e:
                    logger.error(f"Query execution error: {e}")
                    raise

    def get_schema(self, secret_arn: str) -> dict:
        """
        Retrieve the database schema for a tenant.

        Args:
            secret_arn: ARN of the secret containing database credentials.

        Returns:
            dict with table names as keys and column info as values.
        """
        schema_query = """
        SELECT 
            t.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            (
                SELECT 
                    tc.constraint_type 
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = t.table_name 
                    AND kcu.column_name = c.column_name
                    AND tc.constraint_type = 'PRIMARY KEY'
                LIMIT 1
            ) as is_primary_key
        FROM information_schema.tables t
        JOIN information_schema.columns c 
            ON t.table_name = c.table_name 
            AND t.table_schema = c.table_schema
        WHERE t.table_schema = 'public'
            AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name, c.ordinal_position;
        """

        results = self.execute_query(secret_arn, schema_query, max_rows=1000)

        # Organize by table
        schema: dict = {}
        for row in results:
            table_name = row["table_name"]
            if table_name not in schema:
                schema[table_name] = {"columns": []}

            schema[table_name]["columns"].append({
                "name": row["column_name"],
                "type": row["data_type"],
                "nullable": row["is_nullable"] == "YES",
                "default": row["column_default"],
                "primary_key": row["is_primary_key"] == "PRIMARY KEY",
            })

        return schema

    def format_schema_for_prompt(self, schema: dict) -> str:
        """
        Format the schema dictionary as a string for LLM prompts.

        Args:
            schema: Schema dictionary from get_schema().

        Returns:
            Formatted string representation of the schema.
        """
        lines = []
        for table_name, table_info in schema.items():
            lines.append(f"TABLE: {table_name}")
            for col in table_info["columns"]:
                pk_marker = " (PK)" if col["primary_key"] else ""
                null_marker = " NULL" if col["nullable"] else " NOT NULL"
                lines.append(f"  - {col['name']}: {col['type']}{pk_marker}{null_marker}")
            lines.append("")

        return "\n".join(lines)
