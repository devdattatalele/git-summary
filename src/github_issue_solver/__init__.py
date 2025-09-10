"""
GitHub Issue Solver MCP Server

A professional Model Context Protocol server for automated GitHub issue resolution,
repository analysis, and intelligent patch generation.

This server follows MCP best practices with proper separation of concerns,
robust error handling, and modular architecture.
"""

__version__ = "2.0.0"
__author__ = "GitHub Issue Solver Team"

from .server import GitHubIssueSolverServer
from .config import Config
from .models import (
    RepositoryStatus,
    IngestionResult,
    AnalysisResult,
    PatchResult,
)
from .exceptions import (
    GitHubIssueSolverError,
    ConfigurationError,
    RepositoryError,
    IngestionError,
    AnalysisError,
    PatchGenerationError,
)

__all__ = [
    # Core
    "GitHubIssueSolverServer",
    "Config",
    # Models
    "RepositoryStatus",
    "IngestionResult", 
    "AnalysisResult",
    "PatchResult",
    # Exceptions
    "GitHubIssueSolverError",
    "ConfigurationError",
    "RepositoryError",
    "IngestionError",
    "AnalysisError", 
    "PatchGenerationError",
]
