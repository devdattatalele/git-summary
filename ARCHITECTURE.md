# Project Architecture: V2 Service-Oriented Design

This document explains the professional, service-oriented architecture of the V2 GitHub Issue Solver and how it relates to the previous monolithic scripts.

## The Core Principle: Separation of Concerns

The V1 server mixed all its logic into one large file. The V2 server separates the project into distinct, logical layers. This is a standard practice for building robust, maintainable software.

### The Layers

1.  **`main.py` (The Entry Point):**
    *   **Responsibility:** To start the application.
    *   **Analogy:** The ignition key for the car. It doesn't drive, it just starts the engine.

2.  **`src/github_issue_solver/server.py` (The MCP Adapter):**
    *   **Responsibility:** To handle all communication with the MCP client (like Claude). It defines the tools with `@mcp.tool` and translates incoming requests into calls to the appropriate internal service.
    *   **Analogy:** The car's dashboard and steering wheel. It's the user interface for the driver (Claude).

3.  **`src/github_issue_solver/services/` (The Brains / The Managers):**
    *   **Responsibility:** To orchestrate the business logic. For example, `ingestion_service.py` knows the 4 steps of ingestion. It manages the state, calls the necessary workers, and handles high-level process errors.
    *   **Analogy:** The car's computer (ECU). It takes input from the driver and tells the engine, transmission, and brakes what to do.

4.  **`issue_solver/` (The Library / The Specialist Workers):**
    *   **Responsibility:** To perform the heavy, low-level tasks. `issue_solver/ingest.py` contains powerful "worker" functions like `fetch_repo_code` and `chunk_and_embed_and_store`. These functions are experts at their one job and are called upon by the "manager" services.
    *   **Analogy:** The engine, the transmission, the brakes. They are powerful components that do the actual work but are directed by the ECU.

## How is `ingest.py` Used?

**The new system absolutely uses the logic from `issue_solver/ingest.py`. It does not have independent ingestion logic.**

Here is the flow for a call to `ingest_repository_code`:

1.  Claude calls the tool.
2.  `server.py` receives the call and passes it to `ingestion_service.py`.
3.  `ingestion_service.py` (the manager) starts the business process:
    *   Updates the server's state.
    *   **Calls the `fetch_repo_code` function from `issue_solver/ingest.py` (the specialist worker) to get the data.**
    *   **Calls the `chunk_and_embed_and_store` function from `issue_solver/ingest.py` (another worker) to save the data.**
    *   Updates the server's state to "complete."
4.  `ingestion_service.py` returns a structured result to the `server.py`.
5.  `server.py` formats the result into a friendly message for Claude.

This layered design is what allows the V2 server to be so much more robust, testable, and maintainable than the original script.


