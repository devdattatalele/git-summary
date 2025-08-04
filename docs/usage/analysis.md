# Analyzing an Issue

Once a repository has been ingested, you can analyze any issue from it using the `analyze_github_issue_tool`.

### Running Analysis

With the MCP server and client running, use the `analyze` command followed by the full URL of the GitHub issue.

```
> analyze https://github.com/owner/repo/issues/123
```

### Output

The tool will return a JSON object containing a detailed analysis, including:

-   `summary`: A one-sentence summary of the problem.
-   `proposed_solution`: A detailed, step-by-step technical plan to solve the issue.
-   `complexity`: An integer from 1 to 5.
-   `similar_issues`: An array of relevant past issues from the knowledge base.
-   `detailed_report`: A formatted Markdown report of the analysis. 