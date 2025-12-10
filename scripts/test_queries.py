#!/usr/bin/env python3
"""
Interactive Test Script for Text-to-SQL Engine

Run this script to test the Text-to-SQL functionality interactively.
Works in demo mode (no database) or with a local PostgreSQL instance.
"""

import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "layers", "common", "python"
))

# Try to import the Lambda handler
try:
    from functions.text_to_sql.app import lambda_handler
    from functions.text_to_sql.prompts.sql_generation import get_sample_schema
    HANDLER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import Lambda handler: {e}")
    print("Running in schema-only mode.\n")
    HANDLER_AVAILABLE = False
    from functions.text_to_sql.prompts.sql_generation import get_sample_schema


def test_with_mock():
    """Run interactive tests using mock data (no AWS required)."""
    print("=" * 60)
    print("Customer Care AI - Text-to-SQL Interactive Test")
    print("=" * 60)
    print("\nRunning in DEMO MODE (no AWS credentials required)")
    print("Using mock database responses.\n")

    # Show the schema being used
    print("Sample Database Schema:")
    print("-" * 40)
    schema = get_sample_schema()
    for line in schema.split("\n")[:20]:
        print(f"  {line}")
    print("  ... (truncated)")
    print("-" * 40)

    # Sample queries to test
    sample_queries = [
        "Where is my order #12345?",
        "Show me my order history",
        "What products did I buy?",
        "When will my order arrive?",
    ]

    print("\nSample queries you can try:")
    for i, q in enumerate(sample_queries, 1):
        print(f"  {i}. {q}")
    print()

    while True:
        try:
            question = input("\nEnter your question (or 'quit' to exit): ").strip()

            if question.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            if not question:
                continue

            # Create test event
            event = {
                "question": question,
                "tenant_id": "test-tenant",
                "customer_context": {
                    "email": "john@example.com",
                    "customer_id": "1",
                },
            }

            print("\n" + "-" * 40)
            print("Processing query...")

            if HANDLER_AVAILABLE:
                # Call the Lambda handler
                result = lambda_handler(event, None)
                body = json.loads(result["body"]) if isinstance(result.get("body"), str) else result

                print(f"\nStatus: {result.get('statusCode', 'N/A')}")

                if body.get("sql"):
                    print(f"\nGenerated SQL:")
                    print(f"  {body['sql']}")

                print(f"\nResponse:")
                print(f"  {body.get('response', body.get('error', 'No response'))}")

                if body.get("escalate"):
                    print(f"\n⚠️  Escalation triggered: {body.get('escalation_reason', 'Unknown')}")
            else:
                print("(Handler not available - showing mock response)")
                print(f"\nYour question: {question}")
                print("Mock response: I would process this query and return results.")

            print("-" * 40)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()


def test_sql_validator():
    """Test the SQL validator with various inputs."""
    print("\n" + "=" * 60)
    print("Testing SQL Validator")
    print("=" * 60)

    try:
        from common.sql_validator import SQLValidator

        validator = SQLValidator()

        test_cases = [
            ("SELECT * FROM orders WHERE id = 1", True, "Basic SELECT"),
            ("SELECT * FROM orders; DROP TABLE orders;", False, "SQL injection - DROP"),
            ("INSERT INTO orders VALUES (1, 2)", False, "INSERT not allowed"),
            ("SELECT * FROM orders WHERE status = 'shipped'", True, "SELECT with condition"),
            ("SELECT * FROM orders WHERE 1=1 OR 1=1", False, "Boolean injection"),
        ]

        for sql, should_pass, description in test_cases:
            is_valid, error = validator.validate(sql)
            status = "✅" if is_valid == should_pass else "❌"
            print(f"\n{status} {description}")
            print(f"   SQL: {sql[:50]}...")
            print(f"   Valid: {is_valid}, Expected: {should_pass}")
            if error:
                print(f"   Error: {error}")

    except ImportError as e:
        print(f"Could not import SQLValidator: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--validator":
        test_sql_validator()
    else:
        test_with_mock()
