#!/bin/bash
# Quick setup script for GitHub and CI/CD

set -e

echo "=========================================="
echo "GitHub Actions CI/CD Setup"
echo "=========================================="
echo ""

# Check if git is initialized
if [ ! -d .git ]; then
    echo "Initializing git repository..."
    git init
    echo "✅ Git initialized"
else
    echo "✅ Git already initialized"
fi

# Check for .gitignore
if [ ! -f .gitignore ]; then
    echo "❌ .gitignore not found"
else
    echo "✅ .gitignore exists"
fi

# Check for GitHub workflows
if [ -d .github/workflows ]; then
    echo "✅ GitHub Actions workflows created"
    echo "   - deploy.yml (deploys on push to main)"
    echo "   - test.yml (runs tests on PRs)"
else
    echo "❌ GitHub Actions workflows not found"
fi

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Create a GitHub repository:"
echo "   - Go to https://github.com/new"
echo "   - Repository name: customer-care-ai"
echo "   - Don't initialize with README"
echo ""
echo "2. Add all files and commit:"
echo "   git add ."
echo "   git commit -m 'Initial commit: Customer Care AI with CI/CD'"
echo ""
echo "3. Add remote and push:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/customer-care-ai.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "4. Set up AWS credentials in GitHub:"
echo "   - Go to repo Settings → Secrets and variables → Actions"
echo "   - Add AWS_ACCESS_KEY_ID"
echo "   - Add AWS_SECRET_ACCESS_KEY"
echo ""
echo "5. Watch it deploy automatically!"
echo "   - Go to Actions tab in GitHub"
echo ""
echo "See GITHUB_ACTIONS_SETUP.md for detailed instructions."
echo ""
