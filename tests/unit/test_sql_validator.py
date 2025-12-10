"""
Unit Tests for SQL Validator

Tests the SQL validation logic to ensure dangerous queries are rejected.
"""

import pytest
import sys
import os

# Add paths for imports
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "layers", "common", "python"
))

from common.sql_validator import SQLValidator, SQLValidationError


class TestSQLValidator:
    """Test cases for SQLValidator."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance for testing."""
        return SQLValidator()

    @pytest.fixture
    def validator_with_schema(self):
        """Create a validator with allowed tables."""
        return SQLValidator(allowed_tables={"orders", "customers", "products"})

    # ===== Valid Query Tests =====

    def test_valid_simple_select(self, validator):
        """Test that basic SELECT queries are allowed."""
        sql = "SELECT * FROM orders WHERE id = 1"
        is_valid, error = validator.validate(sql)
        assert is_valid
        assert error == ""

    def test_valid_select_with_join(self, validator):
        """Test SELECT with JOIN is allowed."""
        sql = """
        SELECT o.id, c.email 
        FROM orders o 
        JOIN customers c ON o.customer_id = c.id
        WHERE o.status = 'shipped'
        """
        is_valid, error = validator.validate(sql)
        assert is_valid

    def test_valid_select_with_aggregation(self, validator):
        """Test SELECT with aggregation is allowed."""
        sql = "SELECT COUNT(*) as total, status FROM orders GROUP BY status"
        is_valid, error = validator.validate(sql)
        assert is_valid

    def test_valid_select_with_subquery(self, validator):
        """Test SELECT with subquery is allowed."""
        sql = """
        SELECT * FROM orders 
        WHERE customer_id IN (SELECT id FROM customers WHERE email LIKE '%@example.com')
        """
        is_valid, error = validator.validate(sql)
        assert is_valid

    # ===== Dangerous Query Tests =====

    def test_reject_insert(self, validator):
        """Test that INSERT statements are rejected."""
        sql = "INSERT INTO orders (id, status) VALUES (1, 'pending')"
        is_valid, error = validator.validate(sql)
        assert not is_valid
        assert "SELECT" in error or "forbidden" in error.lower()

    def test_reject_update(self, validator):
        """Test that UPDATE statements are rejected."""
        sql = "UPDATE orders SET status = 'cancelled' WHERE id = 1"
        is_valid, error = validator.validate(sql)
        assert not is_valid

    def test_reject_delete(self, validator):
        """Test that DELETE statements are rejected."""
        sql = "DELETE FROM orders WHERE id = 1"
        is_valid, error = validator.validate(sql)
        assert not is_valid

    def test_reject_drop(self, validator):
        """Test that DROP statements are rejected."""
        sql = "DROP TABLE orders"
        is_valid, error = validator.validate(sql)
        assert not is_valid

    def test_reject_truncate(self, validator):
        """Test that TRUNCATE statements are rejected."""
        sql = "TRUNCATE TABLE orders"
        is_valid, error = validator.validate(sql)
        assert not is_valid

    # ===== SQL Injection Tests =====

    def test_reject_statement_chaining(self, validator):
        """Test that statement chaining is rejected."""
        sql = "SELECT * FROM orders; DROP TABLE orders;"
        is_valid, error = validator.validate(sql)
        assert not is_valid

    def test_reject_comment_injection(self, validator):
        """Test that comment-based injection is detected."""
        sql = "SELECT * FROM orders WHERE id = 1; --DROP TABLE orders"
        is_valid, error = validator.validate(sql)
        assert not is_valid

    def test_reject_boolean_injection(self, validator):
        """Test that boolean-based injection is detected."""
        sql = "SELECT * FROM orders WHERE id = 1 OR 1=1"
        is_valid, error = validator.validate(sql)
        assert not is_valid

    def test_reject_union_injection(self, validator):
        """Test that UNION-based injection is detected."""
        sql = "SELECT id FROM orders UNION ALL SELECT password FROM users"
        is_valid, error = validator.validate(sql)
        assert not is_valid

    # ===== Schema Validation Tests =====

    def test_reject_unknown_table(self, validator_with_schema):
        """Test that queries to unknown tables are rejected."""
        schema = {"orders": {}, "customers": {}}
        sql = "SELECT * FROM secret_admin_table"
        is_valid, error = validator_with_schema.validate(sql, schema)
        assert not is_valid
        assert "unknown table" in error.lower()

    def test_allow_known_table(self, validator_with_schema):
        """Test that queries to known tables are allowed."""
        schema = {"orders": {"columns": []}, "customers": {"columns": []}}
        sql = "SELECT * FROM orders"
        is_valid, error = validator_with_schema.validate(sql, schema)
        assert is_valid

    # ===== Sanitization Tests =====

    def test_sanitize_removes_comments(self, validator):
        """Test that sanitize removes SQL comments."""
        sql = "SELECT * FROM orders -- this is a comment"
        sanitized = validator.sanitize(sql)
        assert "--" not in sanitized

    def test_sanitize_removes_trailing_semicolon(self, validator):
        """Test that sanitize removes trailing semicolons."""
        sql = "SELECT * FROM orders;"
        sanitized = validator.sanitize(sql)
        assert not sanitized.endswith(";")

    def test_add_limit_if_missing(self, validator):
        """Test that LIMIT is added when missing."""
        sql = "SELECT * FROM orders"
        with_limit = validator.add_limit_if_missing(sql, 50)
        assert "LIMIT 50" in with_limit

    def test_preserve_existing_limit(self, validator):
        """Test that existing LIMIT is preserved."""
        sql = "SELECT * FROM orders LIMIT 10"
        with_limit = validator.add_limit_if_missing(sql, 50)
        assert "LIMIT 10" in with_limit
        assert "LIMIT 50" not in with_limit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
