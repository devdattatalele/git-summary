# Quick Start Guide

Get the GitHub Issue Resolution MCP Server running in just 5 minutes!

## Prerequisites

- **Python 3.8+** installed
- **Git** for cloning the repository
- **GitHub Personal Access Token** ([create one here](https://github.com/settings/tokens))
- **Google API Key** for Gemini ([get one here](https://makersuite.google.com/app/apikey))

## Step 1: Install

```bash
# Clone the repository
git clone https://github.com/your-username/github-issue-mcp-server.git
cd github-issue-mcp-server

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure

```bash
# Copy environment template
cp env.template .env

# Edit .env file with your API keys
nano .env  # or use your preferred editor
```

Add your API keys to the `.env` file:

```env
# Required
GITHUB_TOKEN=your_github_personal_access_token_here
GOOGLE_API_KEY=your_google_api_key_here

# Optional
GOOGLE_DOCS_ID=your_google_docs_document_id
```

## Step 3: Setup & Test

```bash
# Run automated setup
python setup_mcp_server.py

# Test the server
python test_mcp_server.py
```

You should see:
- ✅ All environment checks passed
- ✅ MCP server starts successfully
- ✅ All tools are available

## Step 4: Claude Desktop Integration

The setup script automatically creates `config/claude_desktop_config.json`. Copy it to Claude Desktop:

**macOS:**
```bash
cp config/claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```bash
copy config\claude_desktop_config.json %APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
cp config/claude_desktop_config.json ~/.config/claude/claude_desktop_config.json
```

## Step 5: Start Using!

1. **Restart Claude Desktop** to load the MCP server

2. **Test the connection** by typing in Claude:
   ```
   List all available tools
   ```

3. **Ingest your first repository**:
   ```
   Ingest the microsoft/vscode-docs repository for analysis
   ```

4. **Analyze an issue**:
   ```
   Analyze https://github.com/microsoft/vscode/issues/12345
   ```

## 🎉 You're Ready!

Your GitHub Issue Resolution MCP Server is now running and integrated with Claude Desktop. You can:

- **Ingest repositories** to build knowledge bases
- **Analyze issues** with AI-powered insights
- **Generate patches** for automatic fixes
- **Create pull requests** seamlessly

## Next Steps

- **[Full Installation Guide](installation.md)** - Detailed setup options
- **[Configuration Guide](configuration.md)** - Advanced settings
- **[Usage Examples](../usage/ingestion.md)** - Learn the workflow
- **[Troubleshooting](../troubleshooting/common_issues.md)** - If something goes wrong

## Quick Commands Reference

| Command | Purpose |
|---------|---------|
| `python setup_mcp_server.py` | Validate and configure everything |
| `python test_mcp_server.py` | Test MCP server functionality |
| `mkdocs serve` | View documentation locally |

## Need Help?

- 📖 **[Full Documentation](../index.md)**
- 🐛 **[Common Issues](../troubleshooting/common_issues.md)**
- 💬 **[GitHub Discussions](https://github.com/your-username/github-issue-mcp-server/discussions)**
- 🚨 **[Report Issues](https://github.com/your-username/github-issue-mcp-server/issues)**

---

**Happy coding!** 🚀
