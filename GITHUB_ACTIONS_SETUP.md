# GitHub Actions CI/CD Setup Guide

## Overview

This project uses GitHub Actions for automated testing and deployment to AWS.

### Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `deploy.yml` | Push to `main` | Build, test, and deploy to AWS |
| `test.yml` | Pull requests, other branches | Run tests only |

---

## Setup Instructions

### Step 1: Create GitHub Repository

```bash
cd /Users/namanraghuvanshi/.gemini/antigravity/scratch/customer-care-ai

# Initialize git (if not already done)
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: Customer Care AI with CI/CD"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/customer-care-ai.git
git branch -M main
git push -u origin main
```

---

### Step 2: Create IAM User for GitHub Actions

#### Option A: Using AWS Console

1. Go to **AWS Console** → **IAM** → **Users** → **Create User**
2. **Username**: `github-actions-deployer`
3. **Permissions**: Attach these policies:
   - `AWSLambda_FullAccess`
   - `IAMFullAccess`
   - `AmazonAPIGatewayAdministrator`
   - `AmazonS3FullAccess`
   - `CloudFormationFullAccess`
   - `SecretsManagerReadWrite`
   - Custom policy for Bedrock (see below)

4. **Create Access Key**:
   - Go to Security Credentials
   - Create Access Key → Application running outside AWS
   - **Save the Access Key ID and Secret Access Key**

#### Bedrock Policy (Custom Inline Policy)

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

#### Option B: Using AWS CLI

```bash
# Create IAM user
aws iam create-user --user-name github-actions-deployer

# Attach policies
aws iam attach-user-policy \
  --user-name github-actions-deployer \
  --policy-arn arn:aws:iam::aws:policy/AWSLambda_FullAccess

aws iam attach-user-policy \
  --user-name github-actions-deployer \
  --policy-arn arn:aws:iam::aws:policy/IAMFullAccess

aws iam attach-user-policy \
  --user-name github-actions-deployer \
  --policy-arn arn:aws:iam::aws:policy/AmazonAPIGatewayAdministrator

aws iam attach-user-policy \
  --user-name github-actions-deployer \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

aws iam attach-user-policy \
  --user-name github-actions-deployer \
  --policy-arn arn:aws:iam::aws:policy/AWSCloudFormationFullAccess

# Create access key
aws iam create-access-key --user-name github-actions-deployer
```

---

### Step 3: Add Secrets to GitHub

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `AWS_ACCESS_KEY_ID` | Your IAM user's access key ID |
| `AWS_SECRET_ACCESS_KEY` | Your IAM user's secret access key |
| `AWS_REGION` | `us-east-1` (optional, defaults to us-east-1) |

---

### Step 4: Enable Bedrock Model Access

1. Go to **AWS Console** → **Bedrock**
2. Click **Model access** (left sidebar)
3. Click **Manage model access** or **Request model access**
4. Select **Claude 3 Sonnet** by Anthropic
5. Submit request (usually approved instantly)

---

### Step 5: Push and Deploy

```bash
# Make sure workflow files are committed
git add .github/workflows/
git commit -m "Add GitHub Actions CI/CD workflows"
git push

# GitHub Actions will automatically:
# 1. Run tests
# 2. Build SAM application
# 3. Deploy to AWS
# 4. Test the deployed API
```

---

## Monitoring Deployments

### View Workflow Runs

1. Go to your GitHub repository
2. Click the **Actions** tab
3. See all workflow runs and their status

### Deployment Summary

After each deployment, GitHub Actions will show:
- ✅ Test results
- 🚀 Deployment status
- 🔗 API endpoint URL

---

## Workflow Details

### Deploy Workflow (`deploy.yml`)

Runs on every push to `main`:

1. **Checkout code**
2. **Set up Python 3.12**
3. **Install AWS SAM CLI**
4. **Configure AWS credentials**
5. **Install dependencies**
6. **Run unit tests** (fails if tests fail)
7. **Build SAM application** (using Docker containers)
8. **Deploy to AWS** (creates/updates CloudFormation stack)
9. **Get API endpoint** (from CloudFormation outputs)
10. **Test deployed API** (smoke test)

### Test Workflow (`test.yml`)

Runs on pull requests and non-main branches:

1. **Checkout code**
2. **Set up Python 3.12**
3. **Install dependencies**
4. **Run unit tests**
5. **Test SQL validator**
6. **Report results**

---

## Manual Deployment

You can also trigger deployment manually:

1. Go to **Actions** tab
2. Select **Deploy to AWS** workflow
3. Click **Run workflow**
4. Select branch and click **Run workflow**

---

## Troubleshooting

### "AWS credentials not configured"
- Check that secrets are added to GitHub repository
- Verify secret names match exactly: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

### "Access Denied" during deployment
- Ensure IAM user has all required permissions
- Check CloudFormation, Lambda, API Gateway, S3 permissions

### "Bedrock model not found"
- Enable model access in AWS Console → Bedrock → Model access
- Ensure region is `us-east-1`

### Tests failing
- Check test output in GitHub Actions logs
- Run tests locally: `python -m pytest tests/unit/ -v`

---

## Cost Considerations

### GitHub Actions

- **Public repositories**: Free unlimited minutes
- **Private repositories**: 2,000 free minutes/month
- Each deployment takes ~5-10 minutes

### AWS Resources

Same as manual deployment:
- Lambda: Free tier (1M requests/month)
- API Gateway: ~$3.50/million requests
- Bedrock: Pay per use (~$0.003/1K input tokens)
- S3: ~$0.50/month

**Estimated total**: $5-20/month for MVP

---

## Next Steps

1. ✅ Create GitHub repository
2. ✅ Create IAM user for GitHub Actions
3. ✅ Add secrets to GitHub
4. ✅ Enable Bedrock model access
5. ✅ Push code and watch it deploy!

After first successful deployment:
- Test the API endpoint
- Set up monitoring with CloudWatch
- Configure custom domain (optional)
