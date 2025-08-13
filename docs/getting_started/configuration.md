# Configuration

The dual-MCP server architecture uses environment variables to manage API keys and configuration for both the analysis and GitHub servers.

## Environment Variables

### 1. Create a `.env` File

Create a file named `.env` in the root of the project directory. You can copy the provided example file:

```bash
cp env.template .env
```

### 2. Required API Keys

Configure the following required credentials in your `.env` file:

#### Analysis Server Configuration
```env
# Google Gemini API (for AI analysis)
GOOGLE_API_KEY=your_google_api_key_here

# GitHub API access (for repository data)
GITHUB_TOKEN=your_github_personal_access_token

# Optional: Google Docs integration
GOOGLE_DOCS_ID=your_google_docs_document_id
```

#### GitHub Server Configuration
The GitHub server (Docker) automatically uses the same `GITHUB_TOKEN` from your environment. The setup script configures this automatically.

### 3. API Key Setup Guide

#### Google API Key (Gemini)
1. Visit [Google AI Studio](https://ai.google.dev/)
2. Sign in with your Google account
3. Click "Get API Key" and create a new project
4. Copy the generated API key to `GOOGLE_API_KEY` in your `.env` file

#### GitHub Personal Access Token
1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select the following scopes:
   - ✅ `repo` - Full repository access (required for both servers)
   - ✅ `workflow` - GitHub Actions workflow access (recommended)
4. Copy the generated token to `GITHUB_TOKEN` in your `.env` file

**Important**: These scopes are required for:
- **Analysis Server**: Reading repository data (docs, code, issues, PRs)
- **GitHub Server**: Creating branches, PRs, and managing repository operations

### 4. Dual-Server Configuration

The `setup_mcp_server.py` script automatically configures both servers in Claude Desktop:

#### Analysis Server (`github-issue-resolver`)
- Uses Python environment with your API keys
- Configured with local project paths
- Custom ChromaDB persistence directory

#### GitHub Server (`github`)
- Uses Docker container `ghcr.io/github/github-mcp-server`
- Configured with your GitHub token via environment variables
- Provides complete GitHub API access

### 5. Optional Configuration

#### Google Docs Integration (Optional)
If you want analysis reports saved to Google Docs:

1. Follow the [Google Docs API quickstart](https://developers.google.com/docs/api/quickstart/python#authorize_credentials_for_a_desktop_application)
2. Create OAuth 2.0 credentials for a **Desktop app**
3. Download the `credentials.json` file to your project root
4. Add your Google Docs document ID to `GOOGLE_DOCS_ID` in `.env`
5. First run will prompt for browser authorization

#### ChromaDB Configuration (Optional)
```env
# Optional: Custom ChromaDB location
CHROMA_PERSIST_DIR=/custom/path/to/chroma_db
```

## Verification

After configuration, verify your setup:

```bash
# Run the setup script
python setup_mcp_server.py

# This will validate:
# ✅ All required environment variables
# ✅ API key access and permissions
# ✅ Docker and GitHub server setup
# ✅ Claude Desktop configuration
```

## Security Notes

- **Keep your `.env` file secure** - Never commit it to version control
- **Use minimal required scopes** for GitHub tokens
- **Rotate tokens periodically** for security
- **The dual-server architecture isolates concerns** - analysis server only reads, GitHub server handles operations

## Troubleshooting

### API Key Issues
```bash
# Test Google API key
curl -H "Authorization: Bearer $GOOGLE_API_KEY" \
  "https://generativelanguage.googleapis.com/v1beta/models"

# Test GitHub token
curl -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/user"
```

### Docker Configuration Issues
```bash
# Verify Docker environment
docker run --rm -e GITHUB_PERSONAL_ACCESS_TOKEN=$GITHUB_TOKEN \
  ghcr.io/github/github-mcp-server --help
```

For more troubleshooting help, see our [Troubleshooting Guide](../troubleshooting/common_issues.md). 