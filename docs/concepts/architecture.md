# Architecture

The system is built on a modern Python AI stack, designed for modularity and scalability.

### Core Components

-   **`issue_solver` Package:** The main Python package containing all the core logic.
    -   `ingest.py`: Handles cloning repositories and populating the knowledge base.
    -   `analyze.py`: Contains the LangChain agent and logic for analyzing issues.
    -   `patch.py`: Responsible for generating code patches.
    -   `server.py`: Runs the FastMCP server to expose the tools to an AI agent.
-   **`scripts/`:** Contains standalone scripts, primarily the `client.py` used to interact with the MCP server.
-   **`tests/`:** Contains integration and unit tests.
-   **`docs/`:** Contains all the Markdown files for this documentation site.
-   **`chroma_db/`:** The directory where the ChromaDB vector stores are persisted.

### Technologies

-   **AI/LLM:** Google Gemini (gemini-2.5-flash, embedding-001)
-   **Framework:** LangChain
-   **Vector Database:** ChromaDB
-   **Server Protocol:** Model Context Protocol (MCP) via FastMCP
-   **GitHub Integration:** PyGithub
-   **Documentation:** MkDocs with the Material theme 