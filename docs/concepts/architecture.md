# Dual-MCP Server Architecture

The system is built on a revolutionary dual-server architecture that combines specialized AI analysis with robust GitHub automation, designed for enterprise-scale modularity and reliability.

## Architecture Overview

Our dual-MCP server architecture separates concerns into two specialized servers:

### 🧠 Analysis Server (`github-issue-resolver`)
**Role**: The "Brain" - Intelligent analysis and patch generation

### ✋ GitHub Server (`github/github-mcp-server`) 
**Role**: The "Hands" - Robust GitHub operations via Docker

## Core Components

### Analysis Server Components

-   **`github_issue_mcp_server.py`:** Main custom MCP server with FastMCP
-   **`issue_solver/` Package:** Core AI analysis logic
    -   `ingest.py`: 4-step repository ingestion with performance optimization
    -   `analyze.py`: LangChain RAG chains for reliable issue analysis
    -   `patch.py`: Intelligent patch generation with repository context
-   **`chroma_db/`:** Repository-specific vector stores with isolated knowledge bases
-   **`config/`:** Dual-server configuration for Claude Desktop

### GitHub Server Components

-   **Docker Container:** `ghcr.io/github/github-mcp-server`
-   **Go Implementation:** High-performance GitHub API operations
-   **Complete GitHub API:** Full access to all GitHub functionality
-   **Enterprise-Grade:** Robust, production-ready GitHub integration

### Supporting Infrastructure

-   **`examples/`:** Integration examples and client code
-   **`tests/`:** Comprehensive integration and unit tests
-   **`docs/`:** Complete documentation site
-   **`setup_mcp_server.py`:** Automated dual-server setup and configuration

## Technology Stack

### Analysis Server (Brain) Technologies

-   **AI/LLM:** Google Gemini 2.5-Flash (latest model)
-   **Framework:** LangChain with RAG chains (non-verbose for reliability)
-   **Vector Database:** ChromaDB with repository isolation
-   **Server Protocol:** Model Context Protocol (MCP) via FastMCP
-   **GitHub Integration:** PyGithub for data access
-   **Performance:** Optimized chunking and batch processing

### GitHub Server (Hands) Technologies

-   **Implementation:** Official Go-based GitHub MCP server
-   **Deployment:** Docker containerization for reliability
-   **GitHub API:** Complete GitHub API coverage
-   **Authentication:** Secure token-based authentication
-   **Operations:** Branch management, PR creation, issue handling

### Infrastructure Technologies

-   **Orchestration:** Claude Desktop MCP client
-   **Documentation:** MkDocs with Material theme
-   **Development:** Python 3.8+, Docker, comprehensive testing 