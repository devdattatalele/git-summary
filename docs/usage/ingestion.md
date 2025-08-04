# Ingesting a Repository

Before you can analyze issues, you must first build the knowledge base for the repository. This is done using the `ingest_repository_tool`.

### Running Ingestion

1.  **Start the MCP Server:**
    ```bash
    python -m issue_solver.server
    ```

2.  **Run the Client and Call the Tool:**
    In a separate terminal, start the client and use the `ingest` command.

    ```bash
    python scripts/client.py issue_solver.server
    ```

    Once the client is running, you can ingest a repository:
    ```
    > ingest owner/repo_name
    ```
    For example:
    ```
    > ingest swarms/swarms
    ```

### Ingestion Options

You can speed up the ingestion process by skipping certain parts:

-   `--skip-prs`: Skips ingesting the pull request history.
-   `--skip-code`: Skips ingesting the source code.

Example:
```
> ingest owner/repo_name --skip-prs --skip-code
``` 