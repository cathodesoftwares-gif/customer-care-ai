#!/usr/bin/env python3
"""
Quick test script to verify DeepSeek R1 integration with Bedrock.

This script tests:
1. Basic connection to Bedrock with DeepSeek R1
2. SQL generation
3. Response generation
"""

import sys
import os
import json

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'common', 'python'))

from common.bedrock_client import BedrockClient
from functions.text_to_sql.prompts.sql_generation import get_sample_schema


def test_deepseek_connection():
    """Test basic connection to DeepSeek R1."""
    print("=" * 60)
    print("Testing DeepSeek R1 Integration")
    print("=" * 60)
    
    try:
        client = BedrockClient()
        print(f"✓ BedrockClient initialized")
        print(f"  Model ID: {client.model_id}")
        print(f"  Region: {client.region}")
        
        # Verify it's using DeepSeek
        if "deepseek" in client.model_id.lower():
            print(f"✓ Using DeepSeek R1 model")
        else:
            print(f"⚠ Warning: Not using DeepSeek model!")
            
        return client
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return None


def test_sql_generation(client):
    """Test SQL generation with DeepSeek R1."""
    print("\n" + "=" * 60)
    print("Testing SQL Generation")
    print("=" * 60)
    
    question = "Show me all orders for customer with email john@example.com"
    schema = get_sample_schema()
    customer_context = {
        "email": "john@example.com",
        "customer_id": "1"
    }
    
    print(f"\nQuestion: {question}")
    print(f"Customer: {customer_context['email']}")
    
    try:
        result = client.generate_sql(
            question=question,
            schema_context=schema,
            customer_context=customer_context
        )
        
        print(f"\n✓ SQL Generated Successfully")
        print(f"\nSQL Query:")
        print("-" * 60)
        print(result['sql'])
        print("-" * 60)
        print(f"\nExplanation: {result['explanation']}")
        
        return result
    except Exception as e:
        print(f"\n✗ SQL Generation Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_response_generation(client):
    """Test natural language response generation."""
    print("\n" + "=" * 60)
    print("Testing Response Generation")
    print("=" * 60)
    
    question = "Where is my order #12345?"
    mock_results = [
        {
            "order_id": 12345,
            "status": "shipped",
            "tracking_number": "1Z999AA10123456784",
            "shipped_date": "2024-12-05",
            "estimated_delivery": "2024-12-10"
        }
    ]
    
    print(f"\nQuestion: {question}")
    print(f"Query Results: {len(mock_results)} row(s)")
    
    try:
        response = client.generate_response(
            question=question,
            query_results=mock_results,
            sql_explanation="Retrieved order status and tracking information"
        )
        
        print(f"\n✓ Response Generated Successfully")
        print(f"\nNatural Language Response:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        
        return response
    except Exception as e:
        print(f"\n✗ Response Generation Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Run all tests."""
    print("\n🧪 DeepSeek R1 Integration Test Suite\n")
    
    # Test 1: Connection
    client = test_deepseek_connection()
    if not client:
        print("\n❌ Tests failed: Could not initialize client")
        sys.exit(1)
    
    # Test 2: SQL Generation
    sql_result = test_sql_generation(client)
    
    # Test 3: Response Generation
    response_result = test_response_generation(client)
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    tests_passed = 0
    tests_total = 3
    
    if client:
        tests_passed += 1
        print("✓ Client Initialization")
    else:
        print("✗ Client Initialization")
    
    if sql_result:
        tests_passed += 1
        print("✓ SQL Generation")
    else:
        print("✗ SQL Generation")
    
    if response_result:
        tests_passed += 1
        print("✓ Response Generation")
    else:
        print("✗ Response Generation")
    
    print(f"\n{tests_passed}/{tests_total} tests passed")
    
    if tests_passed == tests_total:
        print("\n✅ All tests passed! DeepSeek R1 integration is working.")
        sys.exit(0)
    else:
        print(f"\n⚠️  {tests_total - tests_passed} test(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
