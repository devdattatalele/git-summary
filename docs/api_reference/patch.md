# Patch API

The `issue_solver.patch` module contains functions for generating code patches and creating pull requests.

### `generate_patch_for_issue(issue_body: str, repo_full_name: str)`

Generates patch suggestions for a GitHub issue.

-   **Arguments:**
    -   `issue_body` (str): The body text of the GitHub issue.
    -   `repo_full_name` (str): The repository name.
-   **Returns:** A dictionary with `filesToUpdate` and `summaryOfChanges`.

### `create_pr(patch_data: dict, repo_full_name: str, base_branch: str, head_branch: str, issue_number: int)`

Creates a GitHub PR with the generated patches.

-   **Arguments:**
    -   `patch_data` (dict): The patch data from `generate_patch_for_issue`.
    -   `repo_full_name` (str): The repository name.
    -   `base_branch` (str): The base branch for the PR.
    -   `head_branch` (str): The name for the new branch.
    -   `issue_number` (int): The issue number to link.
-   **Returns:** The URL of the created PR if successful. 