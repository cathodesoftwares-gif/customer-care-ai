# Local Testing Guide

## Prerequisites

Install Python dependencies:

```bash
cd /Users/namanraghuvanshi/.gemini/antigravity/scratch/customer-care-ai

# Install all dependencies
pip install boto3 sqlglot pydantic psycopg2-binary pytest
```

---

## Option 1: Interactive Demo Mode (Recommended for Quick Testing)

**No AWS credentials needed!** Uses mock data.

```bash
python scripts/test_queries.py
```

**What you can do:**
- Type questions like "Where is my order #12345?"
- See the sample database schema
- Test the conversation flow
- No real database or AWS required

**Example session:**
```
Enter your question: Where is my order #12345?
→ Shows mock order status

Enter your question: Show me my order history
→ Shows mock order list

Enter your question: quit
→ Exits
```

---

## Option 2: Test SQL Validator

Tests the security validation without AWS:

```bash
python scripts/test_queries.py --validator
```

**What it tests:**
- ✅ Valid SELECT queries pass
- ❌ Dangerous queries (INSERT, DELETE, DROP) are blocked
- ❌ SQL injection attempts are detected

---

## Option 3: Unit Tests

Run the full test suite:

```bash
# Run all unit tests
python -m pytest tests/unit/ -v

# Run specific test file
python -m pytest tests/unit/test_sql_validator.py -v

# Run with detailed output
python -m pytest tests/unit/ -v -s
```

---

## Option 4: Test with AWS Bedrock (Requires AWS Credentials)

If you have AWS credentials configured with Bedrock access:

```bash
# Set environment variables
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret

# Run integration tests
python -m pytest tests/integration/ -v
```

**Note:** This will make actual Bedrock API calls and incur costs (~$0.01 per query).

---

## Option 5: SAM Local (Full Lambda Simulation)

Test the Lambda functions locally using SAM CLI:

```bash
# Build the project
sam build

# Start local API Gateway
sam local start-api

# In another terminal, test the endpoint
curl -X POST http://localhost:3000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Where is my order #12345?",
    "tenant_id": "test-tenant",
    "customer_context": {
      "email": "john@example.com"
    }
  }'
```

---

## Option 6: Test with Local PostgreSQL Database

Set up a real test database:

```bash
# Make script executable
chmod +x scripts/setup_local_db.sh

# Run setup (uses Docker)
./scripts/setup_local_db.sh

# Or if you have PostgreSQL installed locally
USE_LOCAL_PG=1 ./scripts/setup_local_db.sh
```

**Database details:**
- Host: localhost
- Port: 5432
- Database: customer_care_test
- User: testuser
- Password: testpass

**Sample customers:**
- john@example.com (2 orders)
- jane@example.com (2 orders)
- bob@example.com (1 order)

---

## Quick Verification Checklist

Run these commands to verify everything works:

```bash
# 1. Check Python syntax
python -c "import ast; ast.parse(open('functions/text_to_sql/app.py').read()); print('✅ Syntax OK')"

# 2. Test imports (after installing dependencies)
python -c "import sys; sys.path.insert(0, 'layers/common/python'); from common.sql_validator import SQLValidator; print('✅ Imports OK')"

# 3. Run demo mode
echo "Where is my order?" | python scripts/test_queries.py

# 4. Run unit tests
python -m pytest tests/unit/ -v
```

---

## Troubleshooting

### "No module named 'boto3'"
```bash
pip install boto3 sqlglot pydantic psycopg2-binary
```

### "No module named 'pytest'"
```bash
pip install pytest
```

### SAM build fails
```bash
# Install SAM CLI
brew install aws-sam-cli  # macOS
# or
pip install aws-sam-cli
```

### Docker PostgreSQL won't start
```bash
# Check if port 5432 is already in use
lsof -i :5432

# Stop existing PostgreSQL
docker stop customer-care-pg
```

---

## What to Test

| Feature | Test Method | Command |
|---------|-------------|---------|
| SQL Validation | Unit tests | `pytest tests/unit/test_sql_validator.py -v` |
| Demo Mode | Interactive script | `python scripts/test_queries.py` |
| Bedrock Integration | Integration tests | `pytest tests/integration/ -v` (needs AWS) |
| Full Lambda | SAM Local | `sam local start-api` |
| Database Schema | Local DB | `./scripts/setup_local_db.sh` |

---

## Next Steps After Local Testing

1. ✅ Verify all tests pass locally
2. Deploy to AWS: `sam build && sam deploy --config-env dev`
3. Test deployed endpoint with real Bedrock
4. Set up RDS for multi-tenant support (Phase 2)
