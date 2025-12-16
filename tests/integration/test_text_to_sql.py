"""
Integration Tests for Text-to-SQL Lambda

Tests the full Text-to-SQL pipeline including Bedrock integration.
Requires AWS credentials with Bedrock access.
"""

import pytest
import json
import os
import sys

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "layers", "common", "python"
))


# Skip all tests if AWS credentials not available
pytestmark = pytest.mark.skipif(
    os.environ.get("AWS_ACCESS_KEY_ID") is None,
    reason="AWS credentials required for integration tests"
)


class TestTextToSQLIntegration:
    """Integration tests for the Text-to-SQL Lambda function."""

    @pytest.fixture
    def sample_event(self):
        """Create a sample Lambda event."""
        return {
            "question": "Where is my order #12345?",
            "tenant_id": "test-tenant",
            "customer_context": {
                "email": "john@example.com",
                "customer_id": "1",
            },
        }

    def test_basic_query_demo_mode(self, sample_event):
        """Test basic query processing in demo mode."""
        from functions.text_to_sql.app import lambda_handler

        result = lambda_handler(sample_event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "response" in body
        assert body.get("success") is True

    def test_missing_question_returns_error(self):
        """Test that missing question returns 400 error."""
        from functions.text_to_sql.app import lambda_handler

        event = {
            "tenant_id": "test-tenant",
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "error" in body

    def test_missing_tenant_returns_error(self):
        """Test that missing tenant_id returns 400 error."""
        from functions.text_to_sql.app import lambda_handler

        event = {
            "question": "Where is my order?",
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "error" in body

    @pytest.mark.slow
    def test_sql_generation_with_bedrock(self, sample_event):
        """
        Test SQL generation using actual Bedrock API.
        
        This test requires:
        - AWS credentials with Bedrock access
        - DeepSeek R1 model available in the region
        """
        from common.bedrock_client import BedrockClient
        from functions.text_to_sql.prompts.sql_generation import get_sample_schema

        client = BedrockClient()
        schema = get_sample_schema()

        result = client.generate_sql(
            question=sample_event["question"],
            schema_context=schema,
            customer_context=sample_event["customer_context"],
        )

        assert "sql" in result
        assert "SELECT" in result["sql"].upper()
        # Should not contain dangerous operations
        assert "DROP" not in result["sql"].upper()
        assert "DELETE" not in result["sql"].upper()

    @pytest.mark.slow
    def test_response_generation_with_bedrock(self):
        """Test natural language response generation."""
        from common.bedrock_client import BedrockClient

        client = BedrockClient()

        mock_results = [
            {"order_id": 12345, "status": "shipped", "tracking_number": "1Z999AA1"}
        ]

        response = client.generate_response(
            question="Where is my order #12345?",
            query_results=mock_results,
            sql_explanation="Retrieved order status and tracking info",
        )

        assert isinstance(response, str)
        assert len(response) > 0
        # Should mention the order in some form
        assert "12345" in response or "shipped" in response.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
