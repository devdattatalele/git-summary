# Analyze API

The `issue_solver.analyze` module contains functions for fetching and analyzing GitHub issues.

### `parse_github_url(url: str)`

Parses a GitHub issue URL to get the owner, repo, and issue number.

-   **Arguments:**
    -   `url` (str): The full URL of the GitHub issue.
-   **Returns:** A tuple containing `(owner, repo, issue_number)`.

### `get_github_issue(owner: str, repo_name: str, issue_number: int)`

Fetches issue data from GitHub.

-   **Arguments:**
    -   `owner` (str): The repository owner.
    -   `repo_name` (str): The repository name.
    -   `issue_number` (int): The issue number.
-   **Returns:** A `github.Issue` object.

### `create_langchain_agent(issue)`

Creates and runs the LangChain agent to analyze the issue.

-   **Arguments:**
    -   `issue`: A `github.Issue` object.
-   **Returns:** The raw output string from the agent, typically containing a JSON object.

### `parse_agent_output(raw_output: str)`

Extracts and parses the JSON from the agent's raw output string.

-   **Arguments:**
    -   `raw_output` (str): The raw string from the agent.
-   **Returns:** A dictionary containing the analysis. 