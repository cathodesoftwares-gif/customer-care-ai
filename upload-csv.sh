#!/bin/bash
# Upload Loan.csv to S3 bucket

echo "🔍 Getting S3 bucket name from CloudFormation..."

# Get bucket name from CloudFormation
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name customer-care-ai-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`SchemaStoreBucketName`].OutputValue' \
  --output text 2>/dev/null)

if [ -z "$BUCKET" ]; then
    echo "❌ Error: Could not get bucket name from CloudFormation"
    echo ""
    echo "Make sure:"
    echo "  1. AWS credentials are configured: aws configure"
    echo "  2. Stack 'customer-care-ai-dev' is deployed"
    echo ""
    exit 1
fi

echo "✅ Found bucket: $BUCKET"
echo ""

# Check if CSV file exists
if [ ! -f "data/Loan.csv" ]; then
    echo "❌ Error: data/Loan.csv not found!"
    exit 1
fi

# Upload CSV to S3
echo "📤 Uploading Loan.csv to S3..."
aws s3 cp data/Loan.csv "s3://${BUCKET}/data/Loan.csv"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Upload complete!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "CSV Location: s3://${BUCKET}/data/Loan.csv"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Your Lambda functions will now use this CSV data!"
    echo ""
    echo "Try asking:"
    echo "  • How many loans are in the database?"
    echo "  • What is the average loan amount?"
    echo "  • Show me approved loans with high credit scores"
    echo ""
else
    echo "❌ Upload failed!"
    exit 1
fi
