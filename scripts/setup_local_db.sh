#!/bin/bash
# Setup Local PostgreSQL Database for Testing
#
# This script creates a sample e-commerce database for local testing.
# Requires: PostgreSQL installed locally or Docker

set -e

DB_NAME="customer_care_test"
DB_USER="testuser"
DB_PASSWORD="testpass"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

echo "Setting up test database: $DB_NAME"

# Check if using Docker
if command -v docker &> /dev/null && [ -z "$USE_LOCAL_PG" ]; then
    echo "Using Docker for PostgreSQL..."
    
    # Stop existing container if running
    docker stop customer-care-pg 2>/dev/null || true
    docker rm customer-care-pg 2>/dev/null || true
    
    # Start PostgreSQL container
    docker run -d \
        --name customer-care-pg \
        -e POSTGRES_DB=$DB_NAME \
        -e POSTGRES_USER=$DB_USER \
        -e POSTGRES_PASSWORD=$DB_PASSWORD \
        -p $DB_PORT:5432 \
        postgres:15
    
    echo "Waiting for PostgreSQL to start..."
    sleep 5
else
    echo "Using local PostgreSQL installation..."
    # Create database (requires psql/createdb)
    createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME 2>/dev/null || true
fi

# Create tables
echo "Creating schema..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << 'EOF'

-- Drop existing tables
DROP TABLE IF EXISTS shipments CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- Customers table
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    category VARCHAR(100),
    in_stock BOOLEAN DEFAULT true
);

-- Orders table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(10, 2) NOT NULL,
    shipping_address TEXT,
    tracking_number VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP
);

-- Order Items table
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL
);

-- Shipments table
CREATE TABLE shipments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    carrier VARCHAR(50) NOT NULL,
    tracking_number VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'in_transit',
    estimated_delivery DATE,
    actual_delivery DATE,
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data
INSERT INTO customers (email, first_name, last_name, phone) VALUES
    ('john@example.com', 'John', 'Doe', '555-0101'),
    ('jane@example.com', 'Jane', 'Smith', '555-0102'),
    ('bob@example.com', 'Bob', 'Wilson', '555-0103');

INSERT INTO products (name, description, price, category) VALUES
    ('Wireless Headphones', 'Premium noise-canceling headphones', 149.99, 'Electronics'),
    ('Running Shoes', 'Lightweight running shoes', 89.99, 'Sports'),
    ('Coffee Maker', 'Automatic drip coffee maker', 59.99, 'Home'),
    ('Laptop Stand', 'Ergonomic aluminum laptop stand', 45.99, 'Office'),
    ('Water Bottle', 'Insulated stainless steel bottle', 29.99, 'Sports');

INSERT INTO orders (customer_id, status, total_amount, tracking_number, shipped_at) VALUES
    (1, 'shipped', 149.99, '1Z999AA10123456784', '2024-12-05 10:00:00'),
    (1, 'delivered', 89.99, '1Z999AA10123456785', '2024-11-20 09:00:00'),
    (2, 'processing', 105.98, NULL, NULL),
    (2, 'delivered', 59.99, '1Z999AA10123456786', '2024-11-15 11:00:00'),
    (3, 'pending', 45.99, NULL, NULL);

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 1, 149.99),
    (2, 2, 1, 89.99),
    (3, 4, 1, 45.99),
    (3, 5, 2, 29.99),
    (4, 3, 1, 59.99),
    (5, 4, 1, 45.99);

INSERT INTO shipments (order_id, carrier, tracking_number, status, estimated_delivery) VALUES
    (1, 'ups', '1Z999AA10123456784', 'in_transit', '2024-12-10'),
    (2, 'fedex', '1Z999AA10123456785', 'delivered', '2024-11-22'),
    (4, 'ups', '1Z999AA10123456786', 'delivered', '2024-11-17');

EOF

echo ""
echo "Database setup complete!"
echo ""
echo "Connection details:"
echo "  Host:     $DB_HOST"
echo "  Port:     $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User:     $DB_USER"
echo "  Password: $DB_PASSWORD"
echo ""
echo "Sample customers:"
echo "  - john@example.com (2 orders)"
echo "  - jane@example.com (2 orders)"
echo "  - bob@example.com (1 order)"
