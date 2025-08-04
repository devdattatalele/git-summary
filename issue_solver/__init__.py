"""
Core package for the GitHub Issue Solver.

This package contains the main logic for ingesting repositories, analyzing issues,
generating patches, and managing the MCP server.
"""

from .analyze import (
    parse_github_url,
    get_github_issue,
    create_langchain_agent,
    parse_agent_output,
    append_to_google_doc,
)

from .ingest import (
    initialize_clients as init_ingestion_clients,
    fetch_repo_docs,
    fetch_repo_issues,
    fetch_repo_code,
    fetch_repo_pr_history,
    chunk_and_embed_and_store,
)

from .patch import (
    initialize_chroma_clients,
    generate_patch_for_issue,
    create_pr,
    generate_and_create_pr,
)

from .server import mcp

__all__ = [
    # analyze
    "parse_github_url",
    "get_github_issue",
    "create_langchain_agent",
    "parse_agent_output",
    "append_to_google_doc",
    # ingest
    "init_ingestion_clients",
    "fetch_repo_docs",
    "fetch_repo_issues",
    "fetch_repo_code",
    "fetch_repo_pr_history",
    "chunk_and_embed_and_store",
    # patch
    "initialize_chroma_clients",
    "generate_patch_for_issue",
    "create_pr",
    "generate_and_create_pr",
    # server
    "mcp",
] 