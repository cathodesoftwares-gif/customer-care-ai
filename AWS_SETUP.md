# AWS Setup Guide for Customer Care AI Deployment

## Prerequisites Checklist

Before deploying, you need:
- [ ] AWS Account
- [ ] AWS CLI installed
- [ ] AWS SAM CLI installed
- [ ] AWS credentials configured
- [ ] Bedrock model access enabled

---

## Step 1: Install AWS CLI

### Check if already installed:
```bash
aws --version
```

### Install if needed:

**macOS:**
```bash
brew install awscli
```

**Or download installer:**
```bash
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
```

---

## Step 2: Install AWS SAM CLI

### Check if already installed:
```bash
sam --version
```

### Install:

**macOS:**
```bash
brew install aws-sam-cli
```

**Or using pip:**
```bash
pip install aws-sam-cli
```

---

## Step 3: Get AWS Credentials

### Option A: Create IAM User (Recommended for Development)

1. **Go to AWS Console**: https://console.aws.amazon.com/
2. **Navigate to IAM** → Users → Create User
3. **User name**: `customer-care-ai-deployer`
4. **Permissions**: Attach these policies:
   - `AWSLambda_FullAccess`
   - `IAMFullAccess` (for creating Lambda execution roles)
   - `AmazonAPIGatewayAdministrator`
   - `AmazonS3FullAccess`
   - `CloudFormationFullAccess`
   - `SecretsManagerReadWrite`
   - Custom policy for Bedrock (see below)

5. **Create Access Key**:
   - Go to Security Credentials tab
   - Create Access Key → CLI
   - **Save the Access Key ID and Secret Access Key**

### Bedrock Access Policy

Create a custom inline policy for Bedrock:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
        }
    ]
}
```

---

## Step 4: Configure AWS Credentials

### Method 1: Using AWS CLI (Recommended)

```bash
aws configure
```

**Enter when prompted:**
- AWS Access Key ID: `[your-access-key-id]`
- AWS Secret Access Key: `[your-secret-access-key]`
- Default region name: `us-east-1` (Bedrock is available here)
- Default output format: `json`

### Method 2: Manual Configuration

Create `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
```

Create `~/.aws/config`:
```ini
[default]
region = us-east-1
output = json
```

### Verify Configuration:
```bash
aws sts get-caller-identity
```

Should return your AWS account info.

---

## Step 5: Enable Bedrock Model Access

### Important: Request Model Access

1. **Go to AWS Console** → Bedrock
2. **Navigate to**: Model access (left sidebar)
3. **Click**: "Manage model access" or "Request model access"
4. **Select**: `Claude 3 Sonnet` by Anthropic
5. **Submit request**

**⚠️ Note:** Model access can take a few minutes to be approved (usually instant for Claude models).

### Verify Bedrock Access:

```bash
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?contains(modelId, `claude-3-sonnet`)].modelId'
```

Should return:
```json
[
    "anthropic.claude-3-sonnet-20240229-v1:0"
]
```

---

## Step 6: Verify All Prerequisites

Run this verification script:

```bash
cd /Users/namanraghuvanshi/.gemini/antigravity/scratch/customer-care-ai

# Check AWS CLI
echo "Checking AWS CLI..."
aws --version

# Check SAM CLI
echo "Checking SAM CLI..."
sam --version

# Check AWS credentials
echo "Checking AWS credentials..."
aws sts get-caller-identity

# Check Bedrock access
echo "Checking Bedrock access..."
aws bedrock list-foundation-models --region us-east-1 --by-provider anthropic --query 'modelSummaries[?contains(modelId, `claude`)].modelId' --output table
```

---

## Step 7: Deploy the Application

Once all prerequisites are met:

```bash
cd /Users/namanraghuvanshi/.gemini/antigravity/scratch/customer-care-ai

# Build the application
sam build

# Deploy (guided mode for first time)
sam deploy --guided
```

### During `sam deploy --guided`, you'll be asked:

| Prompt | Recommended Answer |
|--------|-------------------|
| Stack Name | `customer-care-ai-dev` |
| AWS Region | `us-east-1` |
| Parameter Environment | `dev` |
| Confirm changes before deploy | `Y` |
| Allow SAM CLI IAM role creation | `Y` |
| Disable rollback | `N` |
| Save arguments to config file | `Y` |
| SAM configuration file | `samconfig.toml` |
| SAM configuration environment | `default` |

---

## Common Issues & Solutions

### Issue: "Unable to locate credentials"
**Solution:**
```bash
aws configure
# Enter your credentials
```

### Issue: "Bedrock model not found"
**Solution:**
- Check region is `us-east-1`
- Request model access in Bedrock console
- Wait a few minutes for approval

### Issue: "SAM CLI not found"
**Solution:**
```bash
brew install aws-sam-cli
# or
pip install aws-sam-cli
```

### Issue: "Access Denied" during deployment
**Solution:**
- Ensure IAM user has CloudFormation, Lambda, API Gateway permissions
- Check `aws sts get-caller-identity` shows correct account

---

## Next Steps After Deployment

Once deployed successfully, you'll get:
- ✅ API Gateway endpoint URL
- ✅ Lambda functions deployed
- ✅ S3 bucket for schemas

Test your endpoint:
```bash
# Get the API endpoint from SAM output
API_ENDPOINT="https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/dev"

# Test the query endpoint
curl -X POST $API_ENDPOINT/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Where is my order #12345?",
    "tenant_id": "demo",
    "customer_context": {
      "email": "john@example.com"
    }
  }'
```

---

## Cost Estimate

| Service | Estimated Monthly Cost |
|---------|----------------------|
| Lambda (low usage) | ~$0 (free tier) |
| API Gateway | ~$3.50/million requests |
| Bedrock Claude 3 Sonnet | ~$0.003/1K input + $0.015/1K output tokens |
| S3 | ~$0.50 |
| **Total for MVP** | **~$5-20/month** |

---

## Security Best Practices

1. ✅ Never commit AWS credentials to git
2. ✅ Use IAM roles in production (not access keys)
3. ✅ Enable CloudTrail for audit logging
4. ✅ Rotate access keys regularly
5. ✅ Use least-privilege IAM policies
