"""
MCP tools for the GitHub Issue Solver server.

Individual tool implementations following MCP best practices with proper
separation of concerns and comprehensive error handling.
"""

from .ingestion_tools import (
    start_repository_ingestion_tool,
    ingest_repository_docs_tool,
    ingest_repository_code_tool,
    ingest_repository_issues_tool,
    ingest_repository_prs_tool
)

from .analysis_tools import (
    analyze_github_issue_tool,
    get_repository_status_tool,
    get_repository_info_tool,
    validate_repository_tool,
    list_ingested_repositories_tool
)

from .patch_tools import (
    generate_code_patch_tool,
    get_patch_guidance_tool,
    get_repository_structure_tool
)

from .management_tools import (
    clear_repository_data_tool,
    get_health_status_tool,
    cleanup_old_data_tool
)

__all__ = [
    # Ingestion tools
    "start_repository_ingestion_tool",
    "ingest_repository_docs_tool", 
    "ingest_repository_code_tool",
    "ingest_repository_issues_tool",
    "ingest_repository_prs_tool",
    
    # Analysis tools
    "analyze_github_issue_tool",
    "get_repository_status_tool",
    "get_repository_info_tool",
    "validate_repository_tool",
    "list_ingested_repositories_tool",
    
    # Patch tools
    "generate_code_patch_tool",
    "get_patch_guidance_tool", 
    "get_repository_structure_tool",
    
    # Management tools
    "clear_repository_data_tool",
    "get_health_status_tool",
    "cleanup_old_data_tool"
]
