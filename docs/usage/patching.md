# Generating Patches

After analyzing an issue, you can use the `generate_code_patch_tool` to create a code patch to fix it.

### Running Patch Generation

With the MCP server and client running, use the `generate patch` command. You need to provide the issue body and the full repository name.

```
> generate patch for "owner/repo" with issue body "The login button is not working..."
```

> **Note:** For simplicity, you can copy the `proposed_solution` from the analysis output as the `issue_body` for patch generation, as it often contains the most relevant technical details.

### Creating a Pull Request

The system can also automatically create a pull request with the generated patch using the `create_github_pr_tool`. This is typically done as part of a larger workflow. See the `client.py` script for an example of how these tools can be chained together. 