"""
CSV Query Engine

Enables SQL-like queries on CSV data using pandas and pandasql.
Supports both local files and S3-hosted CSVs.
"""

import logging
import os
from io import StringIO
from typing import Any, Optional

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Check for pandas availability
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not available - CSV Query Engine disabled")

# Check for pandasql availability
try:
    from pandasql import sqldf
    PANDASQL_AVAILABLE = True
except ImportError:
    PANDASQL_AVAILABLE = False
    logger.warning("pandasql not available - SQL queries will use pandas fallback")


class CSVQueryEngine:
    """
    Query engine for CSV data.
    
    Loads CSV files from local paths or S3, extracts schema,
    and executes SQL queries using pandasql.
    """
    
    def __init__(self, region: Optional[str] = None):
        """
        Initialize the CSV Query Engine.
        
        Args:
            region: AWS region for S3 access.
        """
        if not PANDAS_AVAILABLE:
            raise RuntimeError("pandas is required for CSV Query Engine")
        
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._dataframes: dict[str, pd.DataFrame] = {}
    
    def load_from_local(self, path: str, table_name: Optional[str] = None) -> pd.DataFrame:
        """
        Load a CSV file from local filesystem.
        
        Args:
            path: Path to the CSV file.
            table_name: Optional name for the table. Defaults to filename without extension.
            
        Returns:
            Loaded DataFrame.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"CSV file not found: {path}")
        
        df = pd.read_csv(path)
        
        # Derive table name from filename if not provided
        if table_name is None:
            table_name = os.path.splitext(os.path.basename(path))[0].lower()
        
        # Normalize column names (lowercase, replace spaces with underscores)
        df.columns = [col.lower().replace(" ", "_") for col in df.columns]
        
        self._dataframes[table_name] = df
        logger.info(f"Loaded table '{table_name}' with {len(df)} rows and {len(df.columns)} columns")
        
        return df
    
    def load_from_s3(
        self, 
        bucket: str, 
        key: str, 
        table_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load a CSV file from S3.
        
        Args:
            bucket: S3 bucket name.
            key: S3 object key (path to the CSV file).
            table_name: Optional name for the table.
            
        Returns:
            Loaded DataFrame.
        """
        s3 = boto3.client("s3", region_name=self.region)
        
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            csv_content = response["Body"].read().decode("utf-8")
            df = pd.read_csv(StringIO(csv_content))
        except Exception as e:
            logger.error(f"Error reading CSV from s3://{bucket}/{key}: {e}")
            raise
        
        # Derive table name from key if not provided
        if table_name is None:
            filename = key.split("/")[-1]
            table_name = os.path.splitext(filename)[0].lower()
        
        # Normalize column names
        df.columns = [col.lower().replace(" ", "_") for col in df.columns]
        
        self._dataframes[table_name] = df
        logger.info(f"Loaded table '{table_name}' from S3 with {len(df)} rows")
        
        return df
    
    def get_schema(self, table_name: Optional[str] = None) -> dict:
        """
        Get schema information for loaded tables.
        
        Args:
            table_name: Specific table to get schema for. If None, returns all tables.
            
        Returns:
            Schema dictionary with column names, types, and sample values.
        """
        if table_name:
            if table_name not in self._dataframes:
                raise ValueError(f"Table '{table_name}' not loaded")
            dataframes = {table_name: self._dataframes[table_name]}
        else:
            dataframes = self._dataframes
        
        schema = {}
        for name, df in dataframes.items():
            columns = []
            for col in df.columns:
                col_info = {
                    "name": col,
                    "type": self._infer_type(df[col]),
                    "nullable": df[col].isnull().any(),
                    "sample_values": df[col].dropna().head(3).tolist(),
                }
                columns.append(col_info)
            
            schema[name] = {
                "columns": columns,
                "row_count": len(df),
                "sample_data": df.head(3).to_dict(orient="records"),
            }
        
        return schema
    
    def format_schema_for_prompt(self, table_name: Optional[str] = None) -> str:
        """
        Format schema as a string suitable for LLM prompts.
        
        Args:
            table_name: Specific table to format. If None, formats all tables.
            
        Returns:
            Formatted schema string.
        """
        schema = self.get_schema(table_name)
        lines = ["DATABASE SCHEMA:"]
        
        for table, info in schema.items():
            lines.append(f"\nTABLE: {table} ({info['row_count']} rows)")
            for col in info["columns"]:
                nullable = "NULL" if col["nullable"] else "NOT NULL"
                samples = ", ".join(str(v) for v in col["sample_values"][:2])
                lines.append(f"  - {col['name']}: {col['type']} {nullable} (e.g., {samples})")
        
        return "\n".join(lines)
    
    def execute_query(self, sql: str, limit: int = 100) -> list[dict]:
        """
        Execute a SQL query against loaded CSV data.
        
        Args:
            sql: SQL query string.
            limit: Maximum number of rows to return.
            
        Returns:
            List of dictionaries representing query results.
        """
        if not self._dataframes:
            raise ValueError("No CSV data loaded. Call load_from_local or load_from_s3 first.")
        
        # Add LIMIT if not present
        sql_upper = sql.upper()
        if "LIMIT" not in sql_upper:
            sql = f"{sql.rstrip(';')} LIMIT {limit}"
        
        if PANDASQL_AVAILABLE:
            return self._execute_with_pandasql(sql)
        else:
            return self._execute_with_pandas_fallback(sql)
    
    def _execute_with_pandasql(self, sql: str) -> list[dict]:
        """Execute SQL using pandasql."""
        try:
            # Create a local environment with all loaded DataFrames
            env = self._dataframes.copy()
            
            # pandasql's sqldf function uses a lambda to access local variables
            result_df = sqldf(sql, env)
            
            if result_df is None or result_df.empty:
                return []
            
            return result_df.to_dict(orient="records")
            
        except Exception as e:
            logger.error(f"pandasql query failed: {e}")
            raise ValueError(f"Query execution failed: {str(e)}")
    
    def _execute_with_pandas_fallback(self, sql: str) -> list[dict]:
        """
        Basic fallback for simple SELECT queries without pandasql.
        
        Only supports very simple queries like SELECT * FROM table LIMIT n.
        """
        sql_upper = sql.upper()
        
        # Very basic parsing - only for fallback
        if "SELECT" not in sql_upper or "FROM" not in sql_upper:
            raise ValueError("Fallback only supports SELECT ... FROM ... queries")
        
        # Extract table name (very simple parsing)
        from_idx = sql_upper.index("FROM")
        after_from = sql[from_idx + 4:].strip()
        
        # Get first word after FROM
        table_name = after_from.split()[0].lower().rstrip(";")
        
        if table_name not in self._dataframes:
            raise ValueError(f"Table '{table_name}' not found")
        
        df = self._dataframes[table_name]
        
        # Handle LIMIT
        limit = 100
        if "LIMIT" in sql_upper:
            limit_idx = sql_upper.index("LIMIT")
            limit_str = sql[limit_idx + 5:].strip().split()[0].rstrip(";")
            try:
                limit = int(limit_str)
            except ValueError:
                pass
        
        return df.head(limit).to_dict(orient="records")
    
    def _infer_type(self, series: pd.Series) -> str:
        """Infer SQL-like type from pandas series."""
        dtype = series.dtype
        
        if pd.api.types.is_integer_dtype(dtype):
            return "INTEGER"
        elif pd.api.types.is_float_dtype(dtype):
            return "FLOAT"
        elif pd.api.types.is_bool_dtype(dtype):
            return "BOOLEAN"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return "TIMESTAMP"
        else:
            # Check if it might be a date column
            if series.name and any(d in str(series.name).lower() for d in ["date", "time", "created", "updated"]):
                return "DATE"
            return "TEXT"
    
    def get_table_names(self) -> list[str]:
        """Return list of loaded table names."""
        return list(self._dataframes.keys())
    
    def get_dataframe(self, table_name: str) -> pd.DataFrame:
        """Get the raw DataFrame for a table."""
        if table_name not in self._dataframes:
            raise ValueError(f"Table '{table_name}' not loaded")
        return self._dataframes[table_name]
    
    def get_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        return len(self.get_dataframe(table_name))
