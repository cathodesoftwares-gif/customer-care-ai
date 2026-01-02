"""
Chat Handler Lambda

Orchestrates the conversation flow:
1. Manages conversation context
2. Validates customer identity
3. Routes to Text-to-SQL for data queries
4. Handles escalation to human agents
"""

import json
import logging
import os
from typing import Any, Optional

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for chat conversations.

    Expected event structure:
    {
        "message": "Where is my order?",
        "tenant_id": "tenant-uuid",
        "session_id": "session-uuid",
        "customer_context": {
            "email": "customer@example.com",
            "verified": true
        }
    }

    Returns:
    {
        "statusCode": 200,
        "body": {
            "response": "Your order shipped...",
            "session_id": "session-uuid",
            "requires_verification": false,
            "escalate": false
        }
    }
    """
    try:
        # Parse input
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", event)

        message = body.get("message")
        tenant_id = body.get("tenant_id")
        session_id = body.get("session_id")
        customer_context = body.get("customer_context", {})

        # Validate required fields
        if not message:
            return _error_response(400, "Missing required field: message")
        if not tenant_id:
            return _error_response(400, "Missing required field: tenant_id")

        logger.info(f"Chat message for tenant {tenant_id}, session {session_id}")

        # Check if customer verification is needed
        if not customer_context.get("verified"):
            return _verification_required_response(session_id)

        # Classify the message intent
        intent = _classify_intent(message)

        if intent == "data_query":
            # Route to Text-to-SQL Lambda
            response = _invoke_text_to_sql(
                question=message,
                tenant_id=tenant_id,
                customer_context=customer_context,
            )
            return _format_chat_response(response, session_id)

        elif intent == "greeting":
            return _success_response({
                "response": "Hello! I'm here to help you with questions about loan data. "
                           "You can ask me about loan statistics, credit scores, "
                           "or approval rates.",
                "session_id": session_id,
                "escalate": False,
            })

        elif intent == "human_request":
            return _escalation_response(
                "I'll connect you with a support agent right away. "
                "Please wait a moment.",
                session_id,
                reason="Customer requested human agent",
            )

        else:
            # General conversation - could add more sophisticated handling
            return _success_response({
                "response": "I can help you with questions about loan data. "
                           "Try asking something like 'How many loans are in the database?' "
                           "or 'What is the average loan amount?'",
                "session_id": session_id,
                "escalate": False,
            })

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return _error_response(500, "An unexpected error occurred")


def _classify_intent(message: str) -> str:
    """
    Simple intent classification.

    In production, this could use a more sophisticated NLU model.
    """
    message_lower = message.lower()

    # Check for greetings
    greetings = ["hello", "hi", "hey", "good morning", "good afternoon"]
    if any(g in message_lower for g in greetings) and len(message.split()) < 5:
        return "greeting"

    # Check for human agent request
    human_requests = ["human", "agent", "representative", "real person", "speak to someone"]
    if any(h in message_lower for h in human_requests):
        return "human_request"

    # Check for data queries
    data_keywords = [
        # Original order keywords
        "order", "shipping", "delivered", "track", "status",
        "bought", "purchase", "history", "when", "where",
        # Loan-related keywords
        "loan", "credit", "approved", "rejected", "amount", "score",
        "income", "average", "how many", "count", "show", "list",
        "total", "sum", "interest", "rate", "payment", "database",
    ]
    if any(k in message_lower for k in data_keywords):
        return "data_query"

    return "general"


def _invoke_text_to_sql(
    question: str,
    tenant_id: str,
    customer_context: dict,
) -> dict:
    """Invoke the Text-to-SQL Lambda function."""
    lambda_client = boto3.client("lambda")

    # Get Text-to-SQL function name from environment
    function_name = os.environ.get(
        "TEXT_TO_SQL_FUNCTION",
        f"customer-care-text-to-sql-{os.environ.get('ENVIRONMENT', 'dev')}"
    )

    payload = {
        "question": question,
        "tenant_id": tenant_id,
        "customer_context": customer_context,
    }

    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        response_payload = json.loads(response["Payload"].read())

        if isinstance(response_payload.get("body"), str):
            return json.loads(response_payload["body"])
        return response_payload.get("body", response_payload)

    except Exception as e:
        logger.error(f"Error invoking Text-to-SQL: {e}")
        return {
            "response": "I'm having trouble accessing your information. "
                       "Let me connect you with a support agent.",
            "escalate": True,
        }


def _format_chat_response(text_to_sql_response: dict, session_id: str) -> dict:
    """Format the Text-to-SQL response for chat."""
    return _success_response({
        "response": text_to_sql_response.get("response", ""),
        "session_id": session_id,
        "escalate": text_to_sql_response.get("escalate", False),
        "escalation_reason": text_to_sql_response.get("escalation_reason"),
    })


def _verification_required_response(session_id: Optional[str]) -> dict:
    """Response when customer verification is needed."""
    return {
        "statusCode": 200,
        "headers": _cors_headers(),
        "body": json.dumps({
            "response": "To help you with your order, I need to verify your identity. "
                       "Please provide your email address and order number.",
            "session_id": session_id,
            "requires_verification": True,
            "verification_fields": ["email", "order_id"],
        }),
    }


def _success_response(data: dict) -> dict:
    """Return a successful API response."""
    return {
        "statusCode": 200,
        "headers": _cors_headers(),
        "body": json.dumps(data),
    }


def _error_response(status_code: int, message: str) -> dict:
    """Return an error API response."""
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps({
            "error": message,
        }),
    }


def _escalation_response(message: str, session_id: str, reason: str) -> dict:
    """Return an escalation response."""
    return {
        "statusCode": 200,
        "headers": _cors_headers(),
        "body": json.dumps({
            "response": message,
            "session_id": session_id,
            "escalate": True,
            "escalation_reason": reason,
        }),
    }


def _cors_headers() -> dict:
    """Return CORS headers."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Tenant-Id",
    }
