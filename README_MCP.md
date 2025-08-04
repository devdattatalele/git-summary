# GitHub Issue Resolution - MCP Integration

This document describes the Model Context Protocol (MCP) integration for the AI GitHub Issue Resolution System.

## 🚀 Overview

The MCP integration transforms the existing GitHub issue resolution system into a standardized, tool-based architecture where any MCP-compliant LLM client can interact with sophisticated GitHub capabilities.

### Key Components

1. **MCP Server** (`github_mcp_server.py`) - Exposes GitHub functionality as MCP tools
2. **MCP Client** (`mcp_client.py`) - Provides chat interface using Google Gemini
3. **Existing Modules** - Wrapped and accessible through MCP tools

## 🏗️ Architecture

```
┌─────────────────┐    JSON-RPC    ┌─────────────────┐
│                 │ ◄─────────────► │                 │
│   MCP Client    │                │   MCP Server    │
│                 │                │                 │
│ • Google Gemini │                │ • Tool Wrapper  │
│ • Chat Interface│                │ • ChromaDB      │
│ • Tool Calling  │                │ • GitHub API    │
└─────────────────┘                └─────────────────┘
        │                                    │
        │                                    │
        ▼                                    ▼
┌─────────────────┐                ┌─────────────────┐
│     User        │                │   Existing      │
│   Interface     │                │   Modules       │
│                 │                │                 │
│ • Commands      │                │ • analyze_issue │
│ • Chat          │                │ • patch_gen     │ 
│ • Results       │                │ • pr_creation   │
└─────────────────┘                └─────────────────┘
```

## 🔧 Available MCP Tools

### 1. `ingest_repository_tool`
**Purpose:** Ingests a GitHub repository into the knowledge base for analysis

**Input:**
- `repo_name` (required): Repository in `owner/repo` format (e.g., `microsoft/vscode`)
- `skip_prs` (optional): Skip PR history ingestion for faster processing (default: False)
- `skip_code` (optional): Skip code analysis for faster processing (default: False)

**Output:** Status message about ingestion progress and collections created

**Note:** This tool should be run FIRST before analyzing any issues from a repository.

### 2. `analyze_github_issue_tool`
**Purpose:** Analyzes GitHub issues using RAG (Retrieval-Augmented Generation)

**Input:**
- `issue_url` (required): Full GitHub issue URL (e.g., `https://github.com/owner/repo/issues/123`)

**Output:** JSON with analysis results:
```json
{
  "summary": "Brief summary of the issue",
  "proposed_solution": "Detailed solution approach",
  "complexity": 3,
  "similar_issues": ["List of similar past issues"]
}
```

### 3. `generate_code_patch_tool`
**Purpose:** Generates code patches to resolve issues

**Input:**
- `issue_body` (required): Full text of the GitHub issue
- `repo_full_name` (required): Repository in `owner/repo` format

**Output:** JSON with patch data:
```json
{
  "filesToUpdate": [
    {
      "filePath": "path/to/file.py",
      "functionName": "function_name",
      "patch": "unified diff content"
    }
  ],
  "summaryOfChanges": "Description of changes made"
}
```

### 4. `create_github_pr_tool`
**Purpose:** Creates GitHub Pull Requests with generated patches

**Input:**
- `patch_data_json` (required): JSON string from `generate_code_patch_tool`
- `repo_full_name` (required): Repository in `owner/repo` format
- `issue_number` (required): GitHub issue number
- `base_branch` (optional): Base branch, defaults to "main"
- `head_branch` (optional): Head branch name, auto-generated if not provided

**Output:** PR URL or error message

## 📋 Prerequisites

1. **Environment Variables:**
   ```bash
   GOOGLE_API_KEY=your_google_api_key
   GITHUB_TOKEN=your_github_token
   GOOGLE_DOCS_ID=your_google_doc_id  # Optional, for logging
   ```

2. **Repository Knowledge Base:**
   ```bash
   # Run the ingestion script first
   python github-rag-ingestion/ingest_repo.py
   ```

3. **Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 🚀 Quick Start

### 1. Test the Integration
```bash
python test_mcp_integration.py
```

### 2. Start the MCP Client
```bash
python mcp_client.py github_mcp_server.py
```

### 3. Ingest a Repository (REQUIRED FIRST STEP)
```bash
# Ingest a repository to build the knowledge base
ingest microsoft/vscode
```
This step analyzes the repository's code, documentation, issues, and PR history to create a comprehensive knowledge base.

### 4. Interact with the System

#### Direct Commands:
```bash
# Analyze a GitHub issue (after ingestion)
analyze https://github.com/microsoft/vscode/issues/12345

# Generate a code patch
patch microsoft/vscode "Bug in editor causing crashes when opening large files"

# Create a Pull Request (use patch data from previous command)
pr microsoft/vscode 12345 '{"filesToUpdate":[...],"summaryOfChanges":"..."}'
```

#### Natural Language Chat:
```bash
# Ask the AI assistant naturally
"Can you analyze this GitHub issue: https://github.com/microsoft/vscode/issues/12345?"

"I have a bug in my repository where the login function crashes. Can you help me generate a patch?"

"Please create a pull request for issue #123 in the microsoft/vscode repository"
```

## 📝 Example Workflow

### Complete Issue Resolution Flow:

1. **Start the client:**
   ```bash
   python mcp_client.py github_mcp_server.py
   ```

2. **Ingest the repository (FIRST TIME ONLY):**
   ```
   💬 You: ingest microsoft/vscode
   ```
   *This builds the knowledge base and may take several minutes*

3. **Analyze an issue:**
   ```
   💬 You: analyze https://github.com/microsoft/vscode/issues/12345
   ```

4. **Review detailed analysis results** - Same quality and format as the original `analyze_issue.py` script, displayed both in the client AND saved to Google Docs

5. **Generate a patch:**
   ```
   💬 You: patch microsoft/vscode "Editor crashes when opening files larger than 100MB due to memory allocation issue in TextBuffer class"
   ```

6. **Review the generated patch** (automatically displayed)

7. **Create a Pull Request:**
   ```
   💬 You: pr microsoft/vscode 12345 '{"filesToUpdate":[{"filePath":"src/vs/editor/common/model/textBuffer.ts","functionName":"allocateMemory","patch":"@@ -45,7 +45,7 @@..."}],"summaryOfChanges":"Fix memory allocation for large files"}'
   ```

8. **PR is created automatically** and URL is returned

## 🔍 Advanced Usage

### Custom MCP Client Integration

You can integrate these tools into any MCP-compliant client:

```python
# Example: Using the tools in a custom MCP client
from mcp.client.session import ClientSession

async def analyze_issue(session, issue_url):
    result = await session.call_tool(
        "analyze_github_issue_tool",
        arguments={"issue_url": issue_url}
    )
    return json.loads(result.content[0].text)

async def generate_patch(session, issue_body, repo_name):
    result = await session.call_tool(
        "generate_code_patch_tool",
        arguments={
            "issue_body": issue_body,
            "repo_full_name": repo_name
        }
    )
    return json.loads(result.content[0].text)
```

### Integration with Claude Desktop

You can also use these tools with Claude Desktop by adding to your configuration:

```json
{
  "mcpServers": {
    "github-resolver": {
      "command": "python",
      "args": ["/absolute/path/to/github_mcp_server.py"]
    }
  }
}
```

## 🛠️ Troubleshooting

### Common Issues:

1. **"ChromaDB not found" error:**
   ```bash
   # Run the ingestion script first
   python github-rag-ingestion/ingest_repo.py
   ```

2. **"Missing environment variables" error:**
   - Check your `.env` file contains `GOOGLE_API_KEY` and `GITHUB_TOKEN`

3. **Server startup fails:**
   ```bash
   # Test manually
   python github_mcp_server.py
   # Check the error output
   ```

4. **Tool calls fail:**
   - Ensure the repository knowledge base exists in `chroma_db/`
   - Verify API keys have proper permissions

### Debug Mode:

Enable detailed logging:
```bash
export MCP_DEBUG=1
python mcp_client.py github_mcp_server.py
```

## 📊 Performance Considerations

- **Initial Setup:** ChromaDB initialization takes ~10-30 seconds
- **Analysis:** GitHub issue analysis takes ~15-30 seconds
- **Patch Generation:** Code patch generation takes ~30-60 seconds
- **PR Creation:** Pull request creation takes ~10-20 seconds

## 🔄 Migration from Legacy System

If you were using the standalone scripts:

### Before (Legacy):
```bash
python github_analyzer/analyze_issue.py https://github.com/owner/repo/issues/123
python patch_generator.py
```

### After (MCP):
```bash
python mcp_client.py github_mcp_server.py
# Then in the client:
analyze https://github.com/owner/repo/issues/123
patch owner/repo "issue description"
pr owner/repo 123 '{"filesToUpdate":...}'
```

## 📚 Additional Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [Google Gemini API Documentation](https://ai.google.dev/)
- [GitHub API Documentation](https://docs.github.com/en/rest)

## 🤝 Contributing

When contributing to the MCP integration:

1. Follow MCP best practices for tool design
2. Ensure tools are stateless and deterministic
3. Provide comprehensive error handling
4. Test with multiple MCP clients
5. Document tool schemas clearly

## 📄 License

This MCP integration inherits the same license as the main project. 