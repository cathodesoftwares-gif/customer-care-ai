"""
Text-to-SQL Lambda Handler

Main Lambda function that:
1. Receives natural language questions
2. Retrieves relevant schema context
3. Generates SQL using Bedrock
4. Validates and executes the query
5. Returns natural language response
"""

import json
import logging
import os
from typing import Any

from common.bedrock_client import BedrockClient
from common.db_connector import DatabaseConnector
from common.sql_validator import SQLValidator, SQLValidationError
from prompts.sql_generation import get_sample_schema, get_few_shot_examples

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for text-to-SQL queries.

    Expected event structure:
    {
        "question": "Where is my order #12345?",
        "tenant_id": "tenant-uuid",
        "customer_context": {
            "email": "customer@example.com",
            "customer_id": "customer-uuid"
        },
        "secret_arn": "arn:aws:secretsmanager:...",  # Optional for testing
        "schema_override": "..."  # Optional for testing
    }

    Returns:
    {
        "statusCode": 200,
        "body": {
            "response": "Your order #12345 shipped on Dec 5th...",
            "sql": "SELECT ... (for debugging)",
            "success": true
        }
    }
    """
    try:
        # Parse input
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", event)

        question = body.get("question")
        tenant_id = body.get("tenant_id")
        customer_context = body.get("customer_context", {})
        secret_arn = body.get("secret_arn")
        schema_override = body.get("schema_override")

        # Validate required fields
        if not question:
            return _error_response(400, "Missing required field: question")

        if not tenant_id:
            return _error_response(400, "Missing required field: tenant_id")

        logger.info(f"Processing query for tenant {tenant_id}: {question[:100]}...")

        # Initialize clients
        bedrock = BedrockClient()
        db = DatabaseConnector()
        validator = SQLValidator()

        # Get schema context
        if schema_override:
            # Use provided schema (for testing)
            schema_context = schema_override
            schema_dict = None
        elif secret_arn:
            # Fetch live schema from database
            schema_dict = db.get_schema(secret_arn)
            schema_context = db.format_schema_for_prompt(schema_dict)
        else:
            # Use sample schema (for demo/testing)
            schema_context = get_sample_schema()
            schema_dict = None

        # Add few-shot examples to schema context
        full_context = f"{schema_context}\n\n{get_few_shot_examples()}"

        # Generate SQL
        logger.info("Generating SQL with Bedrock...")
        sql_result = bedrock.generate_sql(
            question=question,
            schema_context=full_context,
            customer_context=customer_context,
        )

        generated_sql = sql_result["sql"]
        explanation = sql_result["explanation"]

        logger.info(f"Generated SQL: {generated_sql}")

        # Validate SQL
        validator_with_schema = SQLValidator(
            allowed_tables=set(schema_dict.keys()) if schema_dict else None
        )
        is_valid, error_msg = validator_with_schema.validate(generated_sql, schema_dict)

        if not is_valid:
            logger.warning(f"SQL validation failed: {error_msg}")
            return _error_response(400, f"Generated query failed validation: {error_msg}")

        # Sanitize and add limit
        safe_sql = validator.sanitize(generated_sql)
        safe_sql = validator.add_limit_if_missing(safe_sql)

        # Execute query (if we have database credentials)
        if secret_arn:
            logger.info("Executing query...")
            try:
                results = db.execute_query(secret_arn, safe_sql)
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                return _escalation_response(
                    "I encountered an issue retrieving your information. "
                    "Let me connect you with a support agent who can help."
                )
        else:
            # Demo mode - return mock results
            results = _get_mock_results(question)

        # Generate natural language response
        logger.info("Generating response...")
        response_text = bedrock.generate_response(
            question=question,
            query_results=results,
            sql_explanation=explanation,
        )

        # Check if we need to escalate (no results or unclear)
        if not results:
            return _escalation_response(
                "I couldn't find any information matching your query. "
                "Let me connect you with a support agent who can investigate further."
            )

        return _success_response({
            "response": response_text,
            "sql": safe_sql if os.environ.get("DEBUG") else None,
            "success": True,
            "result_count": len(results),
        })

    except SQLValidationError as e:
        logger.error(f"SQL validation error: {e}")
        return _error_response(400, str(e))

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return _escalation_response(
            "I'm having trouble processing your request. "
            "Let me connect you with a support agent."
        )


def _success_response(data: dict) -> dict:
    """Return a successful API response."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(data),
    }


def _error_response(status_code: int, message: str) -> dict:
    """Return an error API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({
            "success": False,
            "error": message,
        }),
    }


def _escalation_response(message: str) -> dict:
    """Return a response indicating escalation to human agent is needed."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({
            "success": True,
            "response": message,
            "escalate": True,
            "escalation_reason": "Unable to answer query automatically",
        }),
    }


def _get_mock_results(question: str) -> list[dict]:
    """Return mock results for demo/testing purposes."""
    question_lower = question.lower()

    if "order" in question_lower and ("12345" in question or "status" in question_lower):
        return [{
            "order_id": 12345,
            "status": "shipped",
            "tracking_number": "1Z999AA10123456784",
            "shipped_date": "2024-12-05",
            "estimated_delivery": "2024-12-10",
        }]

    if "history" in question_lower or "orders" in question_lower:
        return [
            {"order_id": 12345, "total": 129.99, "status": "shipped", "created_at": "2024-12-01"},
            {"order_id": 12340, "total": 59.99, "status": "delivered", "created_at": "2024-11-15"},
            {"order_id": 12332, "total": 89.99, "status": "delivered", "created_at": "2024-10-28"},
        ]

    return [{"message": "Demo mode - no real database connected"}]
