"""
Schema Indexer Lambda

Extracts schema information from data sources (CSV files in S3 or PostgreSQL),
enriches with semantic descriptions using LLM, and stores for query generation.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any

import boto3

from common.db_connector import DatabaseConnector
from common.schema_enricher import SchemaEnricher, SchemaEnricherMock

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for schema indexing.

    Expected event structure:
    {
        "tenant_id": "tenant-uuid",
        "source_type": "s3" | "postgresql",
        
        # If source_type is "s3":
        "s3_config": {
            "bucket": "my-data-bucket",
            "prefix": "data/tables/"
        },
        
        # If source_type is "postgresql":
        "secret_arn": "arn:aws:secretsmanager:...",
        
        # Optional:
        "use_llm_enrichment": true,  # Use LLM for descriptions (default: true)
        "action": "index"  # or "refresh"
    }

    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "tables_indexed": 5,
            "s3_location": "s3://bucket/tenant-id/schema.json",
            "schema_summary": {...}
        }
    }
    """
    try:
        # Parse input
        tenant_id = event.get("tenant_id")
        source_type = event.get("source_type", "postgresql")
        action = event.get("action", "index")
        use_llm = event.get("use_llm_enrichment", True)

        # Validate required fields
        if not tenant_id:
            return _error_response(400, "Missing required field: tenant_id")

        logger.info(f"Indexing schema for tenant {tenant_id} from {source_type}")

        # Initialize database connector
        db = DatabaseConnector()

        # Step 1: Extract schema based on source type
        if source_type == "s3":
            s3_config = event.get("s3_config", {})
            if not s3_config.get("bucket"):
                return _error_response(400, "Missing s3_config.bucket for S3 source")

            bucket = s3_config["bucket"]
            prefix = s3_config.get("prefix", "")

            logger.info(f"Extracting schema from S3: s3://{bucket}/{prefix}")
            raw_schema = db.get_schema_from_s3(bucket, prefix)

        elif source_type == "postgresql":
            secret_arn = event.get("secret_arn")
            if not secret_arn:
                return _error_response(400, "Missing secret_arn for PostgreSQL source")

            logger.info(f"Extracting schema from PostgreSQL")
            raw_schema = db.get_schema(secret_arn)

        else:
            return _error_response(400, f"Unsupported source_type: {source_type}")

        if not raw_schema:
            return _error_response(404, "No tables found in the data source")

        logger.info(f"Extracted schema with {len(raw_schema)} tables")

        # Step 2: Enrich with semantic descriptions
        if use_llm and os.environ.get("USE_LLM_ENRICHMENT", "true").lower() == "true":
            logger.info("Enriching schema with LLM descriptions...")
            try:
                enricher = SchemaEnricher()
                enriched_schema = enricher.enrich_schema(raw_schema)
            except Exception as e:
                logger.warning(f"LLM enrichment failed, using mock: {e}")
                enricher = SchemaEnricherMock()
                enriched_schema = enricher.enrich_schema(raw_schema)
        else:
            logger.info("Using basic enrichment (LLM disabled)")
            enricher = SchemaEnricherMock()
            enriched_schema = enricher.enrich_schema(raw_schema)

        # Add metadata
        enriched_schema["metadata"] = {
            "tenant_id": tenant_id,
            "source_type": source_type,
            "indexed_at": datetime.utcnow().isoformat(),
            "table_count": len(raw_schema),
        }

        # Step 3: Store schema in S3
        s3_location = _store_schema(tenant_id, enriched_schema)
        logger.info(f"Schema stored at {s3_location}")

        return _success_response({
            "success": True,
            "tables_indexed": len(raw_schema),
            "s3_location": s3_location,
            "schema_summary": _get_schema_summary(enriched_schema),
        })

    except Exception as e:
        logger.exception(f"Schema indexing failed: {e}")
        return _error_response(500, f"Schema indexing failed: {str(e)}")


def _store_schema(tenant_id: str, schema: dict) -> str:
    """Store enriched schema in S3."""
    s3 = boto3.client("s3")

    bucket_name = os.environ.get(
        "SCHEMA_BUCKET",
        f"customer-care-schemas-{os.environ.get('AWS_ACCOUNT_ID', 'default')}"
    )

    key = f"{tenant_id}/schema.json"

    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=json.dumps(schema, indent=2, default=str),
        ContentType="application/json",
    )

    return f"s3://{bucket_name}/{key}"


def _get_schema_summary(schema: dict) -> dict:
    """Get a summary of the schema for the response."""
    tables = schema.get("tables", schema)

    # Handle both old and new schema formats
    if "tables" in schema:
        tables = schema["tables"]

    return {
        "table_count": len(tables),
        "tables": [
            {
                "name": table_name,
                "column_count": len(table_info.get("columns", [])),
                "description": table_info.get("description", "")[:100],
            }
            for table_name, table_info in tables.items()
        ],
        "query_examples_count": len(schema.get("query_examples", [])),
    }


def _success_response(data: dict) -> dict:
    """Return a successful response."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(data),
    }


def _error_response(status_code: int, message: str) -> dict:
    """Return an error response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps({
            "success": False,
            "error": message,
        }),
    }
