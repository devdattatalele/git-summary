# Running the Client

The `scripts/client.py` is an interactive command-line client for interacting with the MCP server.

### Starting the Client

1.  **Start the MCP Server:**
    ```bash
    python -m issue_solver.server
    ```

2.  **Start the Client:**
    In a separate terminal:
    ```bash
    python scripts/client.py issue_solver.server
    ```

### Available Commands

Once the client is running, you can use the following commands:

-   **`ingest <repo_name> [--skip-prs] [--skip-code]`**: Ingests a repository.
-   **`analyze <issue_url>`**: Analyzes a GitHub issue.
-   **`generate patch for "<repo_name>" with issue body "<issue_body>"`**: Generates a code patch.
-   **`create pr for "<repo_name>" issue <issue_number> with patch data """<patch_json>"""`**: Creates a pull request.
-   **`run full analysis for <issue_url>`**: A high-level command that runs the full analysis and patch generation workflow.
-   **`help`**: Displays a list of available commands.
-   **`exit`**: Exits the client. 