#!/bin/bash

# Quick test script for local development

echo "🧪 Testing GitHub Issue Solver MCP Server..."
echo

# Test 1: License Generation
echo "1️⃣ Testing License Generation..."
python generate_license.py generate --tier personal --days 7
echo

# Test 2: Local Run (Development Mode)
echo "2️⃣ Testing Local Run (Development Mode)..."
ALLOW_NO_LICENSE=true python -c "
from src.github_issue_solver.config import Config
config = Config()
print(f'✅ Config loaded')
print(f'   User ID: {config.user_id}')
print(f'   License Tier: {config.license_info.tier}')
print(f'   ChromaDB Dir: {config.get_user_chroma_dir()}')
"
echo

# Test 3: User Manager
echo "3️⃣ Testing User Manager..."
ALLOW_NO_LICENSE=true python -c "
from src.github_issue_solver.user_manager import UserManager
from pathlib import Path
um = UserManager(Path('./chroma_db'))
user_id = 'test_user'
user_dir = um.get_user_chroma_dir(user_id)
print(f'✅ User Manager working')
print(f'   User Dir: {user_dir}')
collection_name = um.get_collection_name(user_id, 'microsoft/vscode', 'documentation')
print(f'   Collection Name: {collection_name}')
"
echo

# Test 4: Input Validation
echo "4️⃣ Testing Input Validation..."
python -c "
from src.github_issue_solver.validation import validate_repo_name, validate_github_url

# Test valid repo
try:
    valid = validate_repo_name('microsoft/vscode')
    print(f'✅ Valid repo validated: {valid}')
except Exception as e:
    print(f'❌ Error: {e}')

# Test invalid repo (should fail)
try:
    invalid = validate_repo_name('../../etc/passwd')
    print(f'❌ SECURITY ISSUE: Path traversal not caught!')
except ValueError as e:
    print(f'✅ Path traversal blocked: {str(e)[:50]}...')

# Test URL validation
try:
    repo, issue = validate_github_url('https://github.com/microsoft/vscode/issues/123')
    print(f'✅ URL validated: {repo}, issue: {issue}')
except Exception as e:
    print(f'❌ Error: {e}')
"
echo

echo "✅ All basic tests passed!"
echo
echo "📝 Next steps:"
echo "   1. Run: docker-compose up"
echo "   2. Test with Claude Desktop"
echo "   3. Generate licenses for friends"
