# B2B SaaS Customer Care AI - System Architecture

## Overview

An AI-powered customer care system that connects to B2B clients' databases, understands their schema, and answers end-customer queries by dynamically generating and executing SQL.

---

## High-Level Architecture

```mermaid
flowchart TB
    subgraph "End Customer Layer"
        CW[Chat Widget]
        API_EXT[Public API]
    end
    
    subgraph "B2B Client Layer"
        AD[Admin Dashboard]
        WEBHOOK[Webhooks]
    end
    
    subgraph "AWS Infrastructure"
        APIGW[API Gateway]
        
        subgraph "Lambda Functions"
            AUTH[Auth Handler]
            CHAT[Chat Orchestrator]
            T2S[Text-to-SQL Engine]
            QE[Query Executor]
            SI[Schema Indexer]
        end
        
        subgraph "AI/ML"
            BEDROCK[Bedrock - DeepSeek R1]
            KB[Bedrock Knowledge Base]
        end
        
        subgraph "Data Stores"
            RDS[(RDS - App DB)]
            SM[Secrets Manager]
            S3[S3 - Schema Store]
        end
    end
    
    subgraph "Client Infrastructure"
        CDB[(Client Database)]
    end
    
    CW --> APIGW
    API_EXT --> APIGW
    AD --> APIGW
    
    APIGW --> AUTH
    APIGW --> CHAT
    APIGW --> SI
    
    CHAT --> T2S
    T2S --> BEDROCK
    T2S --> KB
    T2S --> QE
    
    QE --> SM
    QE --> CDB
    
    SI --> S3
    SI --> KB
    
    AUTH --> RDS
    CHAT --> RDS
```

---

## Core Components Deep Dive

### 1. Text-to-SQL Engine (The Core Value)

This is the heart of the system. Here's how it works:

```mermaid
sequenceDiagram
    participant C as Customer
    participant CH as Chat Handler
    participant T2S as Text-to-SQL
    participant KB as Knowledge Base
    participant BR as Bedrock
    participant QE as Query Executor
    participant DB as Client DB
    
    C->>CH: "Where is my order #12345?"
    CH->>CH: Identify tenant, validate customer
    CH->>T2S: Process query with context
    
    T2S->>KB: Retrieve relevant schema
    KB-->>T2S: Tables: orders, shipments, customers
    
    T2S->>BR: Generate SQL with schema context
    Note over BR: Prompt includes:<br/>1. Schema info<br/>2. Semantic mappings<br/>3. Few-shot examples<br/>4. Customer context
    
    BR-->>T2S: SELECT o.status, s.tracking_number...
    
    T2S->>T2S: Validate SQL (read-only, no injection)
    T2S->>QE: Execute validated query
    
    QE->>DB: Run query with read-only credentials
    DB-->>QE: Result rows
    
    QE-->>T2S: Query results
    T2S->>BR: Generate natural language response
    BR-->>T2S: "Your order #12345 shipped on..."
    
    T2S-->>CH: Final response
    CH-->>C: Display to customer
```

#### Key Design Decisions for Text-to-SQL:

| Decision | Options | Recommended | Rationale |
|----------|---------|-------------|-----------|
| **LLM Model** | DeepSeek R1 vs Claude 3 models | **DeepSeek R1** | Excellent reasoning capabilities for SQL generation |
| **Schema Retrieval** | Full schema vs RAG | **RAG** | Large schemas won't fit in context |
| **Query Generation** | Single-shot vs Multi-step | **Multi-step** | Complex queries need reasoning |
| **Validation** | Regex vs AST parsing | **AST parsing** | More reliable SQL validation |

---

### 2. Multi-Tenant Data Model

```mermaid
erDiagram
    TENANT ||--o{ DATABASE_CONNECTION : has
    TENANT ||--o{ SCHEMA_MAPPING : has
    TENANT ||--o{ CONVERSATION : has
    TENANT ||--o{ END_CUSTOMER : serves
    
    TENANT {
        uuid id PK
        string name
        string api_key
        jsonb settings
        timestamp created_at
    }
    
    DATABASE_CONNECTION {
        uuid id PK
        uuid tenant_id FK
        string db_type
        string secret_arn
        boolean is_active
        timestamp last_sync
    }
    
    SCHEMA_MAPPING {
        uuid id PK
        uuid tenant_id FK
        string table_name
        string column_name
        string semantic_description
        jsonb value_mappings
    }
    
    END_CUSTOMER {
        uuid id PK
        uuid tenant_id FK
        string identifier
        string email
        jsonb metadata
    }
    
    CONVERSATION {
        uuid id PK
        uuid tenant_id FK
        uuid customer_id FK
        jsonb messages
        timestamp created_at
    }
```

---

### 3. Security Architecture

```mermaid
flowchart TB
    subgraph "Security Layers"
        direction TB
        
        subgraph "L1: API Security"
            JWT[JWT Validation]
            RATE[Rate Limiting]
            WAF[AWS WAF]
        end
        
        subgraph "L2: Tenant Isolation"
            TID[Tenant ID Validation]
            SCOPE[Scope Enforcement]
        end
        
        subgraph "L3: Query Security"
            RO[Read-Only Enforcement]
            AST[SQL AST Validation]
            PARAM[Parameterized Queries]
        end
        
        subgraph "L4: Data Security"
            ENC[Encryption at Rest]
            TLS[TLS in Transit]
            MASK[PII Masking]
        end
    end
    
    L1 --> L2 --> L3 --> L4
```

#### Security Controls:

| Layer | Control | Implementation |
|-------|---------|----------------|
| **API** | Authentication | Cognito JWT for admin, API key + customer ID for widget |
| **API** | Rate Limiting | API Gateway throttling per tenant |
| **Tenant** | Isolation | Tenant ID in all queries, row-level security |
| **Query** | Read-Only | DB user with SELECT-only permissions |
| **Query** | SQL Injection | AST parsing, parameterized queries, keyword blacklist |
| **Query** | Scope Limiting | Customer can only query their own data |
| **Data** | Credentials | Secrets Manager with rotation |
| **Data** | Encryption | RDS encryption, S3 encryption |

---

### 4. Customer Authentication Flow

How does an end-customer prove they can access their order data?

```mermaid
sequenceDiagram
    participant EC as End Customer
    participant W as Chat Widget
    participant API as API Gateway
    participant AUTH as Auth Lambda
    participant DB as Client DB
    
    EC->>W: Opens chat widget
    W->>API: Initialize session (Tenant API Key)
    API->>AUTH: Validate tenant
    AUTH-->>W: Session token (unauthenticated)
    
    EC->>W: "Check my order #12345"
    W->>API: Query with session
    API->>AUTH: Check if customer context needed
    AUTH-->>W: Request: Need email to verify
    
    W->>EC: "Please enter your email"
    EC->>W: "john@example.com"
    
    W->>API: Verify customer (order #12345 + john@example.com)
    API->>AUTH: Validate ownership
    AUTH->>DB: SELECT * FROM orders WHERE id=12345 AND email='john@...'
    DB-->>AUTH: Order found, belongs to customer
    AUTH-->>W: Customer verified, scoped session
    
    Note over W,AUTH: All future queries scoped to this customer
```

#### Authentication Options:

| Method | Security Level | UX | Recommended For |
|--------|---------------|-----|-----------------|
| Order ID + Email | Medium | Simple | E-commerce |
| Magic Link (Email) | High | Extra step | Financial services |
| SSO Integration | Highest | Seamless | Enterprise clients |
| Order ID Only | Low | Simplest | Low-risk queries |

---

## AWS Services Mapping

| Component | AWS Service | Configuration |
|-----------|-------------|---------------|
| **API Layer** | API Gateway (HTTP API) | Custom domain, CORS |
| **Compute** | Lambda (Python 3.12) | 512MB-1GB memory, 30s timeout |
| **LLM** | Bedrock (DeepSeek R1) | us-east-1 (check region availability) |
| **Vector Store** | Bedrock Knowledge Base + OpenSearch Serverless | For schema RAG |
| **App Database** | RDS PostgreSQL (db.t4g.micro → db.r6g.large) | Multi-AZ for prod |
| **Secrets** | Secrets Manager | Auto-rotation enabled |
| **Static Assets** | S3 + CloudFront | Admin dashboard, widget JS |
| **Auth** | Cognito | User pools for B2B clients |
| **IaC** | SAM or CDK | Python CDK recommended |
| **Monitoring** | CloudWatch + X-Ray | Distributed tracing |

---

## Data Flow Diagrams

### Flow 1: New Client Onboarding

```mermaid
sequenceDiagram
    participant Client as B2B Client
    participant Admin as Admin Dashboard
    participant API as API Gateway
    participant SI as Schema Indexer
    participant SM as Secrets Manager
    participant KB as Knowledge Base
    
    Client->>Admin: Sign up / Login
    Client->>Admin: Add database connection
    Admin->>API: Submit connection details
    API->>SM: Store credentials securely
    SM-->>API: Secret ARN
    
    API->>SI: Trigger schema indexing
    SI->>SM: Retrieve credentials
    SI->>Client: Connect & extract schema
    Client-->>SI: Schema metadata
    
    SI->>SI: Generate embeddings
    SI->>KB: Store schema vectors
    SI-->>API: Indexing complete
    
    API-->>Admin: Connection ready!
    Admin->>Client: Get embed code
```

### Flow 2: Customer Query Processing

```mermaid
flowchart LR
    subgraph "Input Processing"
        A[Customer Message] --> B[Intent Detection]
        B --> C{Needs Data?}
    end
    
    subgraph "SQL Generation"
        C -->|Yes| D[Schema Retrieval]
        D --> E[Context Assembly]
        E --> F[Bedrock: Generate SQL]
        F --> G[Validate SQL]
    end
    
    subgraph "Execution"
        G -->|Valid| H[Execute Query]
        G -->|Invalid| I[Fallback Response]
        H --> J[Format Results]
    end
    
    subgraph "Response"
        J --> K[Bedrock: NL Response]
        C -->|No| L[General Response]
        I --> L
        K --> M[Send to Customer]
        L --> M
    end
```

---

## Discussion Points

> [!IMPORTANT]
> Please review these architectural decisions and let me know your preferences:

### 1. Database Connectivity Approach

| Option | Pros | Cons |
|--------|------|------|
| **A: Direct Connection** | Simple, low latency | Requires client DB to be accessible |
| **B: Agent-Based** | Works with private DBs | More complex, client installs agent |
| **C: Data Sync** | Full control, works offline | Stale data, storage costs |

**Which clients will you target first?** (affects connectivity choice)

---

### 2. Customer Verification Strictness

For end-customers querying their data:
- **Lenient**: Order ID only (easy UX, lower security)
- **Moderate**: Order ID + Email (balanced)
- **Strict**: Email magic link or SMS OTP (high security)

**What level suits your target market?**

---

### 3. Query Complexity Support

| Level | Example Query | Complexity |
|-------|---------------|------------|
| **Simple** | "Where is my order?" | Single table lookup |
| **Medium** | "Show my order history for last 3 months" | Joins, date filtering |
| **Complex** | "Which of my orders had the fastest delivery?" | Aggregations, comparisons |

**Should MVP support all levels, or start simple?**

---

### 4. Fallback Strategy

When the AI can't answer:
- **A**: "I don't know" + suggest contacting support
- **B**: Escalate to human agent (requires integration)
- **C**: Create support ticket automatically

**What's your preferred fallback?**

---

## Next Steps After Approval

Once we align on the architecture, I'll create:

1. **SAM/CDK Project Structure** - Infrastructure as Code
2. **Text-to-SQL Lambda** - Core engine with Bedrock
3. **Local Testing Setup** - Mock database for development
4. **Schema Indexer** - For RAG-based retrieval

---

Let me know your thoughts on the discussion points above, and we can refine the architecture before implementation!
