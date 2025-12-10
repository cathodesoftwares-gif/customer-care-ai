"""
SQL Validator for Query Safety

Validates and sanitizes SQL queries to ensure they are:
1. Read-only (SELECT statements only)
2. Free of SQL injection attempts
3. Valid against the known schema
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Only import sqlglot if available
try:
    import sqlglot
    from sqlglot import exp
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False
    logger.warning("sqlglot not available - using fallback validation")


class SQLValidationError(Exception):
    """Raised when SQL validation fails."""
    pass


class SQLValidator:
    """Validates SQL queries for safety and correctness."""

    # Dangerous SQL keywords that should never appear
    DANGEROUS_KEYWORDS = {
        "insert", "update", "delete", "drop", "truncate", "alter",
        "create", "replace", "grant", "revoke", "exec", "execute",
        "xp_", "sp_", "into outfile", "into dumpfile", "load_file",
    }

    # Patterns that indicate SQL injection attempts
    INJECTION_PATTERNS = [
        r";\s*--",                    # Statement termination with comment
        r";\s*(drop|delete|insert)",  # Statement chaining with dangerous ops
        r"union\s+all\s+select",      # UNION-based injection
        r"or\s+1\s*=\s*1",            # Boolean-based injection
        r"'\s*or\s+'",                # String-based injection
        r"sleep\s*\(",                # Time-based injection
        r"benchmark\s*\(",            # Time-based injection
        r"waitfor\s+delay",           # SQL Server time-based
    ]

    def __init__(self, allowed_tables: Optional[set[str]] = None):
        """
        Initialize the SQL validator.

        Args:
            allowed_tables: Optional set of table names that are allowed.
        """
        self.allowed_tables = allowed_tables
        self._injection_regex = re.compile(
            "|".join(self.INJECTION_PATTERNS),
            re.IGNORECASE
        )

    def validate(self, sql: str, schema: Optional[dict] = None) -> tuple[bool, str]:
        """
        Validate a SQL query for safety.

        Args:
            sql: The SQL query to validate.
            schema: Optional schema dict to validate table/column names.

        Returns:
            Tuple of (is_valid, error_message).
        """
        sql_lower = sql.lower().strip()

        # Check 1: Must start with SELECT
        if not sql_lower.startswith("select"):
            return False, "Query must be a SELECT statement"

        # Check 2: No dangerous keywords
        for keyword in self.DANGEROUS_KEYWORDS:
            # Use word boundary check to avoid false positives
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, sql_lower):
                return False, f"Query contains forbidden keyword: {keyword.upper()}"

        # Check 3: No injection patterns
        if self._injection_regex.search(sql_lower):
            return False, "Query contains potential SQL injection pattern"

        # Check 4: No multiple statements (semicolon followed by another statement)
        if ";" in sql:
            # Allow trailing semicolon, but not statement chaining
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            if len(statements) > 1:
                return False, "Multiple statements are not allowed"

        # Check 5: Use sqlglot for AST-level validation if available
        if SQLGLOT_AVAILABLE:
            return self._validate_with_sqlglot(sql, schema)

        # Check 6: Validate tables if schema provided (fallback)
        if schema and self.allowed_tables:
            tables_in_query = self._extract_table_names_regex(sql)
            invalid_tables = tables_in_query - self.allowed_tables
            if invalid_tables:
                return False, f"Query references unknown tables: {invalid_tables}"

        return True, ""

    def _validate_with_sqlglot(
        self,
        sql: str,
        schema: Optional[dict] = None,
    ) -> tuple[bool, str]:
        """
        Validate SQL using sqlglot's AST parser.

        Args:
            sql: The SQL query to validate.
            schema: Optional schema dict to validate table/column names.

        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            # Parse the SQL
            parsed = sqlglot.parse_one(sql, dialect="postgres")

            # Check that it's a SELECT statement
            if not isinstance(parsed, exp.Select):
                return False, "Query must be a SELECT statement"

            # Check for subqueries with dangerous operations
            for node in parsed.walk():
                if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop)):
                    return False, "Query contains forbidden operation in subquery"

            # Validate table names if schema provided
            if schema:
                tables_in_query = set()
                for table in parsed.find_all(exp.Table):
                    tables_in_query.add(table.name.lower())

                allowed = {t.lower() for t in schema.keys()}
                invalid = tables_in_query - allowed
                if invalid:
                    return False, f"Query references unknown tables: {invalid}"

            return True, ""

        except sqlglot.errors.ParseError as e:
            return False, f"SQL syntax error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error in sqlglot validation: {e}")
            # Fall back to basic validation (already passed)
            return True, ""

    def _extract_table_names_regex(self, sql: str) -> set[str]:
        """
        Extract table names using regex (fallback method).

        Args:
            sql: The SQL query.

        Returns:
            Set of table names found in the query.
        """
        # Match FROM and JOIN clauses
        pattern = r"(?:from|join)\s+([a-z_][a-z0-9_]*)"
        matches = re.findall(pattern, sql.lower())
        return set(matches)

    def sanitize(self, sql: str) -> str:
        """
        Sanitize a SQL query by removing potentially dangerous elements.

        Args:
            sql: The SQL query to sanitize.

        Returns:
            Sanitized SQL query.
        """
        # Remove comments
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)

        # Remove trailing semicolons and extra whitespace
        sql = sql.strip().rstrip(";")

        # Normalize whitespace
        sql = re.sub(r"\s+", " ", sql)

        return sql

    def add_limit_if_missing(self, sql: str, default_limit: int = 100) -> str:
        """
        Add a LIMIT clause if one is not present.

        Args:
            sql: The SQL query.
            default_limit: Default number of rows to limit to.

        Returns:
            SQL query with LIMIT clause.
        """
        if "limit" not in sql.lower():
            sql = sql.rstrip(";")
            sql = f"{sql} LIMIT {default_limit}"
        return sql
