"""
SQL Generation Prompts and Examples

Contains prompt templates, few-shot examples, and schema helpers
for the Text-to-SQL generation pipeline.
"""


def get_sample_schema() -> str:
    """
    Return a sample e-commerce schema for testing/demo purposes.

    This represents a typical e-commerce database that customers
    would query about orders, products, etc.
    """
    return """TABLE: customers
  - id: integer (PK) NOT NULL
  - email: varchar NOT NULL
  - first_name: varchar NULL
  - last_name: varchar NULL
  - phone: varchar NULL
  - created_at: timestamp NOT NULL

TABLE: orders
  - id: integer (PK) NOT NULL
  - customer_id: integer (FK -> customers.id) NOT NULL
  - status: varchar NOT NULL  -- Values: 'pending', 'processing', 'shipped', 'delivered', 'cancelled'
  - total_amount: decimal NOT NULL
  - shipping_address: text NULL
  - tracking_number: varchar NULL
  - created_at: timestamp NOT NULL
  - updated_at: timestamp NOT NULL
  - shipped_at: timestamp NULL
  - delivered_at: timestamp NULL

TABLE: order_items
  - id: integer (PK) NOT NULL
  - order_id: integer (FK -> orders.id) NOT NULL
  - product_id: integer (FK -> products.id) NOT NULL
  - quantity: integer NOT NULL
  - unit_price: decimal NOT NULL

TABLE: products
  - id: integer (PK) NOT NULL
  - name: varchar NOT NULL
  - description: text NULL
  - price: decimal NOT NULL
  - category: varchar NULL
  - in_stock: boolean NOT NULL

TABLE: shipments
  - id: integer (PK) NOT NULL
  - order_id: integer (FK -> orders.id) NOT NULL
  - carrier: varchar NOT NULL  -- Values: 'ups', 'fedex', 'usps', 'dhl'
  - tracking_number: varchar NOT NULL
  - status: varchar NOT NULL  -- Values: 'in_transit', 'out_for_delivery', 'delivered', 'exception'
  - estimated_delivery: date NULL
  - actual_delivery: date NULL
  - last_update: timestamp NOT NULL
"""


def get_few_shot_examples() -> str:
    """
    Return few-shot examples for SQL generation.

    These examples help the model understand the expected format
    and common query patterns.
    """
    return """EXAMPLE QUERIES:

User: "Where is my order #12345?"
Context: Customer email is john@example.com
SQL:
SELECT o.id as order_id, o.status, o.tracking_number, s.carrier, s.status as shipment_status, s.estimated_delivery
FROM orders o
LEFT JOIN shipments s ON o.id = s.order_id
JOIN customers c ON o.customer_id = c.id
WHERE o.id = 12345 AND c.email = 'john@example.com'
LIMIT 1;

---

User: "What products did I order?"
Context: Customer email is jane@example.com
SQL:
SELECT p.name, oi.quantity, oi.unit_price, o.id as order_id, o.created_at as order_date
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
JOIN products p ON oi.product_id = p.id
JOIN customers c ON o.customer_id = c.id
WHERE c.email = 'jane@example.com'
ORDER BY o.created_at DESC
LIMIT 100;

---

User: "When will my order arrive?"
Context: Customer ID is 42
SQL:
SELECT o.id as order_id, o.status, s.estimated_delivery, s.carrier, s.tracking_number
FROM orders o
LEFT JOIN shipments s ON o.id = s.order_id
WHERE o.customer_id = 42 AND o.status IN ('shipped', 'processing')
ORDER BY o.created_at DESC
LIMIT 5;

---

User: "Show my order history"
Context: Customer email is user@example.com
SQL:
SELECT o.id as order_id, o.status, o.total_amount, o.created_at
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE c.email = 'user@example.com'
ORDER BY o.created_at DESC
LIMIT 20;
"""


def format_customer_context(customer_context: dict) -> str:
    """
    Format customer context for inclusion in prompts.

    Args:
        customer_context: Dict with customer information.

    Returns:
        Formatted string for prompt inclusion.
    """
    if not customer_context:
        return ""

    lines = ["CUSTOMER CONTEXT (use these values to scope queries):"]

    if customer_context.get("email"):
        lines.append(f"  - Customer Email: '{customer_context['email']}'")

    if customer_context.get("customer_id"):
        lines.append(f"  - Customer ID: {customer_context['customer_id']}")

    if customer_context.get("order_id"):
        lines.append(f"  - Specific Order ID: {customer_context['order_id']}")

    return "\n".join(lines)
