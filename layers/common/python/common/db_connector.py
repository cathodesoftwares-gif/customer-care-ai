"""
Database Connector for Multi-Tenant Database Access

Provides secure, read-only connections to client databases (PostgreSQL)
and S3-based data sources (CSV files) with schema inference.
"""

import json
import logging
import os
from contextlib import contextmanager
from io import StringIO
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
    logger.warning("psycopg2 not available - PostgreSQL connectivity disabled")

# Only import pandas if available
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not available - S3/CSV connectivity disabled")


class DatabaseConnector:
    """Manages data connections for tenant databases (PostgreSQL or S3/CSV)."""


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

    # =========================================================================
    # S3/CSV Data Source Methods
    # =========================================================================

    def get_schema_from_s3(
        self,
        bucket: str,
        prefix: str,
        sample_rows: int = 5,
    ) -> dict:
        """
        Extract schema from CSV files in an S3 bucket.

        Each CSV file is treated as a table. Column names come from headers,
        and data types are inferred from sample data.

        Args:
            bucket: S3 bucket name
            prefix: S3 prefix (folder) containing CSV files
            sample_rows: Number of rows to sample for type inference

        Returns:
            Schema dict with table names, columns, types, and sample data
        """
        if not PANDAS_AVAILABLE:
            raise RuntimeError("pandas is required for S3/CSV schema extraction")

        s3 = boto3.client("s3", region_name=self.region)
        schema: dict = {}

        # List CSV files in the prefix
        csv_files = self._list_csv_files(s3, bucket, prefix)
        logger.info(f"Found {len(csv_files)} CSV files in s3://{bucket}/{prefix}")

        for csv_key in csv_files:
            table_name = self._csv_key_to_table_name(csv_key)
            logger.info(f"Processing table: {table_name} from {csv_key}")

            # Read CSV from S3
            df = self._read_csv_from_s3(s3, bucket, csv_key)

            if df is not None and not df.empty:
                schema[table_name] = {
                    "source_file": csv_key,
                    "row_count": len(df),
                    "columns": self._infer_columns_from_dataframe(df),
                    "sample_data": df.head(sample_rows).to_dict(orient="records"),
                }

        # Detect relationships between tables
        schema = self._detect_relationships(schema)

        return schema

    def _list_csv_files(self, s3, bucket: str, prefix: str) -> list[str]:
        """List all CSV files in an S3 prefix."""
        csv_files = []
        paginator = s3.get_paginator("list_objects_v2")

        # Ensure prefix ends with /
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.lower().endswith(".csv"):
                    csv_files.append(key)

        return csv_files

    def _csv_key_to_table_name(self, csv_key: str) -> str:
        """Convert CSV S3 key to table name."""
        # Extract filename without extension
        filename = csv_key.split("/")[-1]
        table_name = filename.rsplit(".", 1)[0]
        # Clean up: lowercase, replace spaces/hyphens with underscores
        table_name = table_name.lower().replace(" ", "_").replace("-", "_")
        return table_name

    def _read_csv_from_s3(self, s3, bucket: str, key: str) -> Optional[Any]:
        """Read a CSV file from S3 into a pandas DataFrame."""
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            csv_content = response["Body"].read().decode("utf-8")
            df = pd.read_csv(StringIO(csv_content))
            return df
        except Exception as e:
            logger.error(f"Error reading CSV from s3://{bucket}/{key}: {e}")
            return None

    def _infer_columns_from_dataframe(self, df: Any) -> list[dict]:
        """Infer column metadata from a pandas DataFrame."""
        columns = []

        for col_name in df.columns:
            col_data = df[col_name]

            # Infer type
            inferred_type = self._infer_column_type(col_data)

            # Check for nulls
            has_nulls = col_data.isna().any()

            # Get sample value
            sample_value = None
            non_null = col_data.dropna()
            if len(non_null) > 0:
                sample_value = str(non_null.iloc[0])

            # Detect if likely primary key
            is_primary_key = self._is_likely_primary_key(col_name, col_data)

            columns.append({
                "name": col_name,
                "type": inferred_type,
                "nullable": bool(has_nulls),
                "primary_key": is_primary_key,
                "sample_value": sample_value,
            })

        return columns

    def _infer_column_type(self, series: Any) -> str:
        """Infer SQL-like type from pandas series."""
        dtype = series.dtype

        # Check pandas dtype
        if pd.api.types.is_integer_dtype(dtype):
            return "integer"
        elif pd.api.types.is_float_dtype(dtype):
            return "decimal"
        elif pd.api.types.is_bool_dtype(dtype):
            return "boolean"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return "timestamp"

        # For object dtype, try to infer from values
        if dtype == "object":
            # Sample non-null values
            sample = series.dropna().head(10)
            if len(sample) == 0:
                return "text"

            # Try to detect date/datetime patterns
            try:
                pd.to_datetime(sample, format="%Y-%m-%d", errors="raise")
                return "date"
            except (ValueError, TypeError):
                pass

            try:
                pd.to_datetime(sample, errors="raise")
                return "timestamp"
            except (ValueError, TypeError):
                pass

            # Check if looks like numeric
            try:
                pd.to_numeric(sample, errors="raise")
                return "decimal"
            except (ValueError, TypeError):
                pass

            # Check average string length for varchar vs text
            avg_len = sample.str.len().mean()
            if avg_len < 100:
                return "varchar"
            else:
                return "text"

        return "text"

    def _is_likely_primary_key(self, col_name: str, series: Any) -> bool:
        """Guess if a column is likely a primary key."""
        col_lower = col_name.lower()

        # Check common primary key patterns
        if col_lower == "id":
            return True
        if col_lower.endswith("_id") and col_lower == series.name.lower():
            # Only if it's the first id-like column
            return series.is_unique and not series.isna().any()

        return False

    def _detect_relationships(self, schema: dict) -> dict:
        """Detect foreign key relationships between tables based on naming."""
        table_names = set(schema.keys())

        for table_name, table_info in schema.items():
            relationships = []

            for col in table_info["columns"]:
                col_name = col["name"].lower()

                # Check for foreign key pattern: {other_table}_id
                if col_name.endswith("_id") and col_name != "id":
                    # Extract potential referenced table
                    ref_table = col_name[:-3]  # Remove "_id"

                    if ref_table in table_names or f"{ref_table}s" in table_names:
                        actual_ref = ref_table if ref_table in table_names else f"{ref_table}s"
                        relationships.append({
                            "column": col["name"],
                            "references_table": actual_ref,
                            "references_column": "id",
                        })

            if relationships:
                table_info["relationships"] = relationships

        return schema

    def get_sample_data_from_s3(
        self,
        bucket: str,
        prefix: str,
        table_name: str,
        limit: int = 5,
    ) -> list[dict]:
        """Get sample rows from a specific table/CSV file."""
        if not PANDAS_AVAILABLE:
            raise RuntimeError("pandas is required for S3/CSV access")

        s3 = boto3.client("s3", region_name=self.region)
        csv_files = self._list_csv_files(s3, bucket, prefix)

        # Find the matching CSV file
        for csv_key in csv_files:
            if self._csv_key_to_table_name(csv_key) == table_name:
                df = self._read_csv_from_s3(s3, bucket, csv_key)
                if df is not None:
                    return df.head(limit).to_dict(orient="records")

        return []
