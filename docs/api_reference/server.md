# Server API

The `issue_solver.server` module contains the MCP server and its exposed tools.

### MCP Server

The server is an instance of `FastMCP` from the `mcp.server` library. It is run as a script to start the service.

```bash
python -m issue_solver.server
```

### Tools

The server exposes the following tools for an MCP client to use:

-   **`ingest_repository_tool(repo_name: str, skip_prs: bool, skip_code: bool)`**: Ingests a GitHub repository into the knowledge base.
-   **`analyze_github_issue_tool(issue_url: str)`**: Analyzes a GitHub issue by its URL.
-   **`generate_code_patch_tool(issue_body: str, repo_full_name: str)`**: Generates a code patch for an issue.
-   **`create_github_pr_tool(patch_data_json: str, repo_full_name: str, issue_number: int, ...)`**: Creates a GitHub Pull Request with the provided patch data. 