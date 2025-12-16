"""
Bedrock Client for Text-to-SQL Generation

Provides a wrapper around AWS Bedrock to generate SQL queries
from natural language using DeepSeek R1 (or other supported models).
"""

import json
import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BedrockClient:
    """Client for interacting with AWS Bedrock Claude model."""

    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize the Bedrock client.

        Args:
            model_id: The Bedrock model ID to use. Defaults to DeepSeek R1.
            region: AWS region. Defaults to environment variable or us-east-1.
        """
        self.model_id = model_id or os.environ.get(
            "BEDROCK_MODEL_ID", "deepseek.r1-v1:0"
        )
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.client = boto3.client("bedrock-runtime", region_name=self.region)

    def generate_sql(
        self,
        question: str,
        schema_context: str,
        customer_context: Optional[dict] = None,
    ) -> dict:
        """
        Generate SQL from a natural language question.

        Args:
            question: The user's natural language question.
            schema_context: Database schema information as a string.
            customer_context: Optional customer info for query scoping.

        Returns:
            dict with 'sql' (the generated query) and 'explanation' fields.
        """
        # Build the customer context string
        customer_info = ""
        if customer_context:
            customer_info = f"""
Customer Context (use this to scope queries to this customer only):
- Customer Email: {customer_context.get('email', 'N/A')}
- Customer ID: {customer_context.get('customer_id', 'N/A')}
"""

        prompt = f"""You are a SQL expert. Generate a PostgreSQL query to answer the user's question.

DATABASE SCHEMA:
{schema_context}

{customer_info}

RULES:
1. Generate ONLY SELECT statements - never INSERT, UPDATE, DELETE, or DROP
2. Always scope queries to the specific customer when customer context is provided
3. Use proper JOIN syntax when needed
4. Limit results to 100 rows unless specifically asked for more
5. Return clean, executable SQL without markdown formatting

USER QUESTION: {question}

Respond in JSON format:
{{
    "sql": "YOUR SQL QUERY HERE",
    "explanation": "Brief explanation of what the query does"
}}
"""

        try:
            response = self._invoke_model(prompt, max_tokens=1024)
            return self._parse_sql_response(response)
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            raise

    def generate_response(
        self,
        question: str,
        query_results: list[dict],
        sql_explanation: str,
    ) -> str:
        """
        Generate a natural language response from query results.

        Args:
            question: The original user question.
            query_results: List of dictionaries from the SQL query.
            sql_explanation: Explanation of what the query did.

        Returns:
            Natural language response for the customer.
        """
        # Format results for the prompt
        if not query_results:
            results_text = "No results found."
        elif len(query_results) > 10:
            results_text = json.dumps(query_results[:10], indent=2, default=str)
            results_text += f"\n... and {len(query_results) - 10} more rows"
        else:
            results_text = json.dumps(query_results, indent=2, default=str)

        prompt = f"""You are a helpful customer service AI. Convert these database results into a friendly, natural response.

ORIGINAL QUESTION: {question}

WHAT WE LOOKED UP: {sql_explanation}

QUERY RESULTS:
{results_text}

RULES:
1. Be friendly and helpful
2. Present the information clearly
3. If no results were found, apologize and suggest the customer verify their order details
4. Don't mention SQL, databases, or queries - speak naturally
5. Format dates and numbers nicely for readability

Respond directly to the customer:"""

        try:
            response = self._invoke_model(prompt, max_tokens=500)
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I'm having trouble processing your request. Please try again or contact our support team."

    def _invoke_model(self, prompt: str, max_tokens: int = 1024) -> str:
        """
        Invoke the Bedrock model with a prompt.

        Args:
            prompt: The prompt to send to the model.
            max_tokens: Maximum tokens in the response.

        Returns:
            The model's response text.
        """
        # Check if we're using DeepSeek or Claude model
        is_deepseek = "deepseek" in self.model_id.lower()
        
        if is_deepseek:
            # DeepSeek R1 format
            body = json.dumps({
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": 0.1,  # Low temperature for consistent SQL generation
            })
        else:
            # Claude format (Anthropic)
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,  # Low temperature for consistent SQL generation
            })

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            
            # Parse response based on model type
            if is_deepseek:
                # DeepSeek returns text in 'completion' or 'text' field
                return response_body.get("completion", response_body.get("text", ""))
            else:
                # Claude returns text in content array
                return response_body["content"][0]["text"]

        except ClientError as e:
            logger.error(f"Bedrock API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error invoking Bedrock: {e}")
            raise

    def _parse_sql_response(self, response: str) -> dict:
        """
        Parse the SQL generation response from the model.

        Args:
            response: Raw response text from the model.

        Returns:
            dict with 'sql' and 'explanation' keys.
        """
        try:
            # Try to parse as JSON
            # Handle case where model wraps JSON in markdown code blocks
            cleaned = response.strip()
            if cleaned.startswith("```"):
                # Remove markdown code block
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])

            result = json.loads(cleaned)
            return {
                "sql": result.get("sql", "").strip(),
                "explanation": result.get("explanation", ""),
            }
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract SQL directly
            logger.warning("Failed to parse JSON response, extracting SQL directly")
            return {
                "sql": response.strip(),
                "explanation": "SQL extracted from raw response",
            }
