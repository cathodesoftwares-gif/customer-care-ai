"""
Schema Indexer Lambda

Connects to client databases, extracts schema information,
and stores it for RAG retrieval.
"""

import json
import logging
import os
from typing import Any

import boto3

from common.db_connector import DatabaseConnector

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for schema indexing.

    Expected event structure:
    {
        "tenant_id": "tenant-uuid",
        "secret_arn": "arn:aws:secretsmanager:...",
        "action": "index"  # or "refresh"
    }

    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "tables_indexed": 5,
            "s3_location": "s3://bucket/tenant-id/schema.json"
        }
    }
    """
    try:
        tenant_id = event.get("tenant_id")
        secret_arn = event.get("secret_arn")
        action = event.get("action", "index")

        if not tenant_id:
            return _error_response(400, "Missing required field: tenant_id")
        if not secret_arn:
            return _error_response(400, "Missing required field: secret_arn")

        logger.info(f"Indexing schema for tenant {tenant_id}")

        # Connect to the database and extract schema
        db = DatabaseConnector()
        schema = db.get_schema(secret_arn)

        logger.info(f"Extracted schema with {len(schema)} tables")

        # Get semantic descriptions (from tenant config or generate)
        enriched_schema = _enrich_schema(schema, tenant_id)

        # Store schema in S3
        s3_location = _store_schema(tenant_id, enriched_schema)

        # In production, also index in vector DB for RAG
        # _index_for_rag(tenant_id, enriched_schema)

        return _success_response({
            "success": True,
            "tables_indexed": len(schema),
            "s3_location": s3_location,
            "schema_summary": _get_schema_summary(schema),
        })

    except Exception as e:
        logger.exception(f"Schema indexing failed: {e}")
        return _error_response(500, f"Schema indexing failed: {str(e)}")


def _enrich_schema(schema: dict, tenant_id: str) -> dict:
    """
    Enrich schema with semantic descriptions.

    In production, this could:
    - Use stored tenant-specific mappings
    - Use LLM to generate descriptions
    - Apply default descriptions for common patterns
    """
    enriched = {}

    # Common semantic mappings
    common_mappings = {
        "status": "Order/item status indicator",
        "created_at": "Record creation timestamp",
        "updated_at": "Last modification timestamp",
        "email": "Customer email address",
        "tracking_number": "Shipment tracking identifier",
        "total_amount": "Total order value in currency",
    }

    for table_name, table_info in schema.items():
        enriched[table_name] = {
            "columns": [],
            "description": f"Table containing {table_name} data",
        }

        for col in table_info["columns"]:
            col_enriched = col.copy()

            # Add semantic description if available
            if col["name"] in common_mappings:
                col_enriched["semantic_description"] = common_mappings[col["name"]]

            enriched[table_name]["columns"].append(col_enriched)

    return enriched


def _store_schema(tenant_id: str, schema: dict) -> str:
    """Store schema in S3."""
    s3 = boto3.client("s3")

    bucket_name = os.environ.get(
        "SCHEMA_BUCKET",
        f"customer-care-schemas-{os.environ.get('AWS_ACCOUNT_ID', 'default')}"
    )

    key = f"{tenant_id}/schema.json"

    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=json.dumps(schema, indent=2),
        ContentType="application/json",
    )

    return f"s3://{bucket_name}/{key}"


def _get_schema_summary(schema: dict) -> dict:
    """Get a summary of the schema for the response."""
    return {
        "table_count": len(schema),
        "tables": [
            {
                "name": table_name,
                "column_count": len(table_info["columns"]),
            }
            for table_name, table_info in schema.items()
        ],
    }


def _success_response(data: dict) -> dict:
    """Return a successful response."""
    return {
        "statusCode": 200,
        "body": json.dumps(data),
    }


def _error_response(status_code: int, message: str) -> dict:
    """Return an error response."""
    return {
        "statusCode": status_code,
        "body": json.dumps({
            "success": False,
            "error": message,
        }),
    }
