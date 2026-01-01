"""
Schema Enricher for Semantic Understanding

Uses LLM (AWS Bedrock) to generate semantic descriptions for database
schema elements, making them more useful for Text-to-SQL generation.
"""

import json
import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SchemaEnricher:
    """Uses LLM to generate semantic descriptions for schema elements."""

    def __init__(
        self,
        model_id: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """
        Initialize the schema enricher.

        Args:
            model_id: Bedrock model ID. Defaults to Claude 3 Sonnet.
            region: AWS region. Defaults to environment variable.
        """
        self.model_id = model_id or os.environ.get(
            "BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"
        )
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.client = boto3.client("bedrock-runtime", region_name=self.region)

    def enrich_schema(self, raw_schema: dict) -> dict:
        """
        Enrich a raw schema with LLM-generated semantic descriptions.

        Args:
            raw_schema: Schema dict from DatabaseConnector

        Returns:
            Enriched schema with descriptions and query examples
        """
        enriched = {}

        for table_name, table_info in raw_schema.items():
            logger.info(f"Enriching table: {table_name}")

            # Generate table description
            table_description = self._generate_table_description(
                table_name,
                table_info.get("columns", []),
                table_info.get("sample_data", []),
            )

            # Generate column descriptions
            columns_with_descriptions = self._enrich_columns(
                table_name,
                table_info.get("columns", []),
                table_info.get("sample_data", []),
            )

            enriched[table_name] = {
                **table_info,
                "description": table_description,
                "columns": columns_with_descriptions,
            }

        # Generate example queries for the entire schema
        query_examples = self._generate_query_examples(enriched)
        
        return {
            "tables": enriched,
            "query_examples": query_examples,
            "enrichment_model": self.model_id,
        }

    def _generate_table_description(
        self,
        table_name: str,
        columns: list[dict],
        sample_data: list[dict],
    ) -> str:
        """Generate a natural language description of what a table stores."""
        column_names = [col["name"] for col in columns]
        sample_str = json.dumps(sample_data[:2], indent=2) if sample_data else "No sample data"

        prompt = f"""Analyze this database table and provide a brief, clear description (1-2 sentences) of what data it stores and its purpose.

Table name: {table_name}
Columns: {', '.join(column_names)}
Sample data:
{sample_str}

Respond with ONLY the description, no other text:"""

        try:
            response = self._invoke_model(prompt, max_tokens=150)
            return response.strip()
        except Exception as e:
            logger.warning(f"Failed to generate description for {table_name}: {e}")
            return f"Table containing {table_name} data"

    def _enrich_columns(
        self,
        table_name: str,
        columns: list[dict],
        sample_data: list[dict],
    ) -> list[dict]:
        """Add semantic descriptions to each column."""
        # For efficiency, batch column enrichment in one LLM call
        column_info = []
        for col in columns:
            sample_values = []
            for row in sample_data[:3]:
                if col["name"] in row:
                    sample_values.append(str(row[col["name"]]))
            column_info.append({
                "name": col["name"],
                "type": col.get("type", "unknown"),
                "samples": sample_values[:3],
            })

        prompt = f"""For each column in the database table '{table_name}', provide a brief semantic description (what does this column represent?).

Columns:
{json.dumps(column_info, indent=2)}

Respond in JSON format:
{{
  "column_name1": "description",
  "column_name2": "description"
}}

Only respond with the JSON, no other text:"""

        try:
            response = self._invoke_model(prompt, max_tokens=500)
            descriptions = self._parse_json_response(response)
        except Exception as e:
            logger.warning(f"Failed to enrich columns for {table_name}: {e}")
            descriptions = {}

        # Merge descriptions with original columns
        enriched_columns = []
        for col in columns:
            col_copy = col.copy()
            col_copy["semantic_description"] = descriptions.get(
                col["name"],
                self._get_default_description(col["name"])
            )
            enriched_columns.append(col_copy)

        return enriched_columns

    def _generate_query_examples(self, schema: dict) -> list[dict]:
        """Generate example natural language queries for the schema."""
        # Summarize schema for prompt
        tables_summary = []
        for table_name, table_info in schema.items():
            cols = [c["name"] for c in table_info.get("columns", [])]
            tables_summary.append(f"- {table_name}: {', '.join(cols)}")

        prompt = f"""Given this database schema, generate 5 example natural language questions that customers might ask. Focus on common business queries.

Database Tables:
{chr(10).join(tables_summary)}

Respond in JSON format:
[
  {{"question": "natural language question", "tables_needed": ["table1", "table2"]}},
  ...
]

Only respond with the JSON array, no other text:"""

        try:
            response = self._invoke_model(prompt, max_tokens=500)
            return self._parse_json_response(response)
        except Exception as e:
            logger.warning(f"Failed to generate query examples: {e}")
            return []

    def _invoke_model(self, prompt: str, max_tokens: int = 500) -> str:
        """Invoke Bedrock model with a prompt."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        })

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
        except ClientError as e:
            logger.error(f"Bedrock API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error invoking Bedrock: {e}")
            raise

    def _parse_json_response(self, response: str) -> any:
        """Parse JSON from LLM response, handling markdown code blocks."""
        cleaned = response.strip()
        
        # Remove markdown code blocks if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            return {}

    def _get_default_description(self, column_name: str) -> str:
        """Get a default description based on common column naming patterns."""
        name_lower = column_name.lower()

        # Common patterns
        patterns = {
            "id": "Unique identifier",
            "name": "Name or title",
            "email": "Email address",
            "phone": "Phone number",
            "address": "Physical address",
            "status": "Current status",
            "created_at": "Creation timestamp",
            "updated_at": "Last update timestamp",
            "deleted_at": "Deletion timestamp (soft delete)",
            "price": "Price amount",
            "amount": "Monetary amount",
            "total": "Total value",
            "quantity": "Count or quantity",
            "description": "Detailed description",
            "is_active": "Whether the record is active",
            "type": "Category or type classification",
        }

        # Check exact match
        if name_lower in patterns:
            return patterns[name_lower]

        # Check partial matches
        for pattern, desc in patterns.items():
            if pattern in name_lower:
                return desc

        # Check for foreign key pattern
        if name_lower.endswith("_id"):
            ref_entity = name_lower[:-3].replace("_", " ").title()
            return f"Reference to {ref_entity}"

        return f"The {column_name.replace('_', ' ')} value"


class SchemaEnricherMock:
    """Mock enricher for testing without Bedrock access."""

    def enrich_schema(self, raw_schema: dict) -> dict:
        """Return schema with basic auto-generated descriptions."""
        enriched = {}

        for table_name, table_info in raw_schema.items():
            columns = []
            for col in table_info.get("columns", []):
                col_copy = col.copy()
                col_copy["semantic_description"] = self._get_default_description(
                    col["name"]
                )
                columns.append(col_copy)

            enriched[table_name] = {
                **table_info,
                "description": f"Table storing {table_name.replace('_', ' ')} records",
                "columns": columns,
            }

        return {
            "tables": enriched,
            "query_examples": [],
            "enrichment_model": "mock",
        }

    def _get_default_description(self, column_name: str) -> str:
        """Same as SchemaEnricher._get_default_description."""
        name_lower = column_name.lower()

        patterns = {
            "id": "Unique identifier",
            "name": "Name or title",
            "email": "Email address",
            "status": "Current status",
            "created_at": "Creation timestamp",
            "updated_at": "Last update timestamp",
            "price": "Price amount",
            "amount": "Monetary amount",
            "total": "Total value",
        }

        if name_lower in patterns:
            return patterns[name_lower]

        if name_lower.endswith("_id"):
            ref_entity = name_lower[:-3].replace("_", " ").title()
            return f"Reference to {ref_entity}"

        return f"The {column_name.replace('_', ' ')} value"
