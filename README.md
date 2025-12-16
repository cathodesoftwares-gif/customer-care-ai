# Customer Care AI - B2B SaaS Text-to-SQL Engine

An AI-powered customer care system that connects to B2B clients' databases, understands their schema, and answers end-customer queries using natural language.

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- AWS SAM CLI
- AWS credentials with Bedrock access
- Docker (optional, for local PostgreSQL)

### Installation

```bash
# Clone and navigate to the project
cd customer-care-ai

# Install dependencies
pip install -r requirements.txt
pip install -r layers/common/requirements.txt

# Install dev dependencies
pip install pytest
```

### Local Development

#### 1. Run the Interactive Test Script

```bash
# Demo mode (no AWS required)
python scripts/test_queries.py

# Test the SQL validator
python scripts/test_queries.py --validator
```

#### 2. Set Up Local Database (Optional)

```bash
# Uses Docker to spin up PostgreSQL
chmod +x scripts/setup_local_db.sh
./scripts/setup_local_db.sh
```

#### 3. Run Unit Tests

```bash
python -m pytest tests/unit/ -v
```

#### 4. Build and Test with SAM

```bash
# Build the application
sam build

# Start local API
sam local start-api

# In another terminal, test the endpoint
curl -X POST http://localhost:3000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Where is my order #12345?", "tenant_id": "test"}'
```

### Deploy to AWS

```bash
# Deploy to dev environment
sam deploy --config-env dev

# Deploy to production
sam deploy --config-env prod
```

## 📁 Project Structure

```
customer-care-ai/
├── template.yaml              # SAM template
├── samconfig.toml            # Deployment config
│
├── layers/common/            # Shared Lambda layer
│   └── python/common/
│       ├── bedrock_client.py    # Bedrock API wrapper
│       ├── db_connector.py      # Database connectivity
│       └── sql_validator.py     # SQL safety validation
│
├── functions/
│   ├── text_to_sql/          # Core Text-to-SQL engine
│   │   ├── app.py            # Lambda handler
│   │   └── prompts/          # LLM prompt templates
│   │
│   ├── chat_handler/         # Conversation orchestration
│   │   └── app.py
│   │
│   └── schema_indexer/       # Schema extraction
│       └── app.py
│
├── tests/
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests
│
└── scripts/
    ├── setup_local_db.sh     # Local DB setup
    └── test_queries.py       # Interactive testing
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_MODEL_ID` | Bedrock model to use | `deepseek.r1-v1:0` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `DEBUG` | Enable debug output | `false` |

### AWS Resources Created

- **Lambda Functions**: text-to-sql, chat-handler, schema-indexer
- **API Gateway**: REST API with /query and /chat endpoints
- **S3 Bucket**: Schema storage
- **IAM Roles**: Bedrock and Secrets Manager access

## 🔒 Security

- All database queries are **read-only**
- SQL is validated using AST parsing to prevent injection
- Dangerous keywords (INSERT, UPDATE, DELETE, DROP) are blocked
- Customer data is scoped using verified identity

## 📊 Architecture

See [architecture.md](./docs/architecture.md) for detailed system design.

## 🛣️ Roadmap

- [ ] Phase 2: Multi-tenant support with RDS
- [ ] Phase 3: Admin dashboard and chat widget
- [ ] RAG-based schema retrieval with Bedrock Knowledge Base
- [ ] Human agent escalation integration

## License

MIT
