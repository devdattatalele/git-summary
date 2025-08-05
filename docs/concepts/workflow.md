# Workflow

The GitHub Issue Solver automates the process of resolving issues through a structured, multi-stage workflow.

![Workflow Diagram](../assets/workflow.png)

### 1. Ingestion

The system first builds a comprehensive knowledge base for a target repository. It clones the repo and ingests multiple sources of data:

-   **Source Code:** Code is parsed and chunked at the function/class level.
-   **Documentation:** All `.md` and `.txt` files.
-   **Issue History:** All open and closed issues and their discussions.
-   **Pull Request History:** Merged PRs, including their descriptions and code diffs.

This data is converted into vector embeddings and stored in a specialized ChromaDB database.

### 2. Analysis

When a user submits a GitHub issue URL, an AI agent analyzes it. It queries the knowledge base to find relevant context (e.g., similar past issues that were solved, relevant functions from the codebase). Using this context, the agent produces:

-   A summary of the problem.
-   A detailed, step-by-step proposed solution.
-   A complexity score (from 1 to 5).
-   Links to similar past issues.

### 3. Patch Generation

Based on the analysis, the system can generate a code patch in the unified diff format. The AI uses the retrieved context (especially from past PRs and relevant code) to create a precise and targeted fix.

### 4. Pull Request Creation

Finally, the system automatically creates a new branch, applies the generated patch, and opens a draft Pull Request on GitHub, linking it to the original issue. 
