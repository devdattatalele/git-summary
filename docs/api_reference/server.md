# Dual-Server API Reference

The dual-MCP server architecture consists of two specialized servers working in harmony.

## Analysis Server (`github-issue-resolver`)

The custom analysis server provides AI-powered repository analysis and patch generation.

### Server Startup

```bash
python github_issue_mcp_server.py
```

### 🔍 Repository Ingestion Tools

#### `start_repository_ingestion(repo_name: str) -> str`
Initialize the 4-step repository ingestion process.
- **Parameters**: `repo_name` - Repository in 'owner/repo' format
- **Returns**: Status message with 4-step plan
- **Purpose**: Validates repository and sets up ingestion workflow

#### `ingest_repository_docs(repo_name: str) -> str`
**Step 1**: Ingest documentation files with smart prioritization.
- **Parameters**: `repo_name` - Repository in 'owner/repo' format  
- **Returns**: Documentation ingestion status and progress
- **Features**: Priority-based processing, intelligent chunking

#### `ingest_repository_code(repo_name: str) -> str`
**Step 2**: Analyze source code with function-level processing.
- **Parameters**: `repo_name` - Repository in 'owner/repo' format
- **Returns**: Code analysis status and chunk count
- **Features**: Language-based prioritization, optimized chunking

#### `ingest_repository_issues(repo_name: str, max_issues: int = 100) -> str`
**Step 3**: Process issues history with content filtering.
- **Parameters**: `repo_name`, `max_issues` (optional)
- **Returns**: Issues processing status
- **Features**: Historical pattern analysis, size optimization

#### `ingest_repository_prs(repo_name: str, max_prs: int = 50) -> str`
**Step 4**: Analyze PR history with diff optimization.
- **Parameters**: `repo_name`, `max_prs` (optional)
- **Returns**: Final ingestion completion status
- **Features**: Solution pattern extraction, diff size limits

### 🤖 AI Analysis Tools

#### `analyze_github_issue_tool(issue_url: str) -> dict`
Perform comprehensive AI analysis of GitHub issues using RAG.
- **Parameters**: `issue_url` - Full GitHub issue URL
- **Returns**: Structured analysis with summary, solution, complexity
- **Features**: Repository context awareness, similar issue detection

#### `generate_code_patch_tool(issue_body: str, repo_full_name: str) -> dict`
Generate intelligent code patches using repository knowledge.
- **Parameters**: `issue_body`, `repo_full_name`
- **Returns**: Patch data with file modifications and diffs
- **Features**: Context-aware generation, unified diff format

### 📊 Repository Management Tools

#### `get_repository_status(repo_name: str) -> str`
Get detailed ingestion progress and statistics.
- **Parameters**: `repo_name` - Repository in 'owner/repo' format
- **Returns**: Step-by-step progress, completion percentage
- **Features**: Real-time progress tracking, error reporting

#### `get_repository_info(repo_name: str) -> str`
Get repository metadata and default branch information.
- **Parameters**: `repo_name` - Repository in 'owner/repo' format
- **Returns**: Repository details, default branch, structure info
- **Purpose**: Repository setup verification before operations

#### `get_repository_structure(repo_name: str, max_files: int = 50) -> str`
View repository file structure from knowledge base.
- **Parameters**: `repo_name`, `max_files` (optional)
- **Returns**: Directory structure, file types, key files
- **Purpose**: Understanding codebase layout for manual analysis

#### `list_ingested_repositories() -> str`
List all repositories available in the knowledge base.
- **Returns**: All ingested repositories with metadata
- **Purpose**: Managing multiple repository knowledge bases

#### `clear_repository_data(repo_name: str, confirm: bool = False) -> str`
Clear all data for a specific repository.
- **Parameters**: `repo_name`, `confirm` (must be True)
- **Returns**: Deletion confirmation and cleanup status
- **Purpose**: Repository data management and cleanup

#### `validate_repository_tool(repo_name: str) -> str`
Validate repository exists and is accessible.
- **Parameters**: `repo_name` - Repository in 'owner/repo' format
- **Returns**: Repository validation results
- **Purpose**: Pre-ingestion access verification

## GitHub Server (`github`)

The official GitHub MCP server provides comprehensive GitHub operations via Docker.

### Server Deployment

```bash
# Automatically configured via setup_mcp_server.py
docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server
```

### 🔄 Core GitHub Operations

#### `github:createPullRequest`
Create pull requests with generated patches.
- **Purpose**: Apply analysis server patches to repositories
- **Features**: Branch management, file modifications, issue linking

#### `github:createBranch`
Create feature branches for development.
- **Purpose**: Branch management for patch application
- **Features**: Base branch selection, naming conventions

#### `github:commitFiles`
Commit file changes to branches.
- **Purpose**: Apply patch modifications to repository
- **Features**: Batch file operations, commit messaging

### 📝 Issue & Repository Management

#### `github:getIssue`, `github:updateIssue`, `github:createIssue`
Complete issue lifecycle management.

#### `github:getRepository`, `github:searchRepositories`, `github:forkRepository`
Repository discovery and management operations.

### 🎯 Workflow Integration

The dual-server architecture enables seamless workflow integration:

1. **Analysis Server** generates intelligent patches
2. **GitHub Server** applies patches with enterprise reliability
3. **Claude Desktop** orchestrates the complete workflow

## Error Handling

### Analysis Server Error Responses
All tools return structured error information:
```json
{
  "error": "Description of the error",
  "success": false,
  "suggestion": "Recommended next steps"
}
```

### GitHub Server Error Handling
Robust error handling with detailed GitHub API error messages and recovery suggestions.

## Performance Considerations

- **Analysis Server**: Optimized chunking reduces processing time by 20-33%
- **GitHub Server**: Go implementation provides high-performance operations
- **Timeout Prevention**: Smart yielding prevents Claude Desktop timeouts
- **Memory Management**: Efficient resource utilization for large repositories 