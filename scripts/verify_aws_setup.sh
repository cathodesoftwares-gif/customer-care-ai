#!/bin/bash
# Quick AWS Setup Verification Script

echo "=========================================="
echo "AWS Setup Verification"
echo "=========================================="
echo ""

# Check AWS CLI
echo "1. Checking AWS CLI..."
if command -v aws &> /dev/null; then
    aws --version
    echo "✅ AWS CLI installed"
else
    echo "❌ AWS CLI not found"
    echo "   Install: brew install awscli"
fi
echo ""

# Check SAM CLI
echo "2. Checking SAM CLI..."
if command -v sam &> /dev/null; then
    sam --version
    echo "✅ SAM CLI installed"
else
    echo "❌ SAM CLI not found"
    echo "   Install: brew install aws-sam-cli"
fi
echo ""

# Check AWS Credentials
echo "3. Checking AWS Credentials..."
if aws sts get-caller-identity &> /dev/null; then
    echo "✅ AWS credentials configured"
    aws sts get-caller-identity
else
    echo "❌ AWS credentials not configured"
    echo "   Configure: aws configure"
fi
echo ""

# Check Bedrock Access (if credentials exist)
if aws sts get-caller-identity &> /dev/null; then
    echo "4. Checking Bedrock Access..."
    REGION=${AWS_REGION:-us-east-1}
    if aws bedrock list-foundation-models --region $REGION --by-provider anthropic --query 'modelSummaries[?contains(modelId, `claude-3-sonnet`)].modelId' --output text 2>/dev/null | grep -q "claude"; then
        echo "✅ Bedrock Claude 3 Sonnet accessible"
    else
        echo "⚠️  Bedrock access not verified"
        echo "   Enable model access in AWS Console → Bedrock → Model access"
    fi
fi

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""

if ! command -v sam &> /dev/null; then
    echo "1. Install SAM CLI:"
    echo "   brew install aws-sam-cli"
    echo ""
fi

if ! aws sts get-caller-identity &> /dev/null; then
    echo "2. Configure AWS credentials:"
    echo "   aws configure"
    echo ""
fi

echo "3. Deploy the application:"
echo "   sam build"
echo "   sam deploy --guided"
echo ""
