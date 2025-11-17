"""
Custom exceptions for the GitHub Issue Solver MCP Server.

Provides specific exception types for different failure scenarios with
detailed error information for better debugging and error handling.
"""

from typing import Optional, Dict, Any
from loguru import logger



class GitHubIssueSolverError(Exception):
    """Base exception for all GitHub Issue Solver errors."""
    
    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause
        logger.error(f"{self.__class__.__name__}: {message}")
        if details:
            logger.error(f"Error details: {details}")
        if cause:
            logger.error(f"Caused by: {cause}")


class ConfigurationError(GitHubIssueSolverError):
    """Raised when there are configuration issues."""

    def __init__(self, message: str, missing_vars: Optional[list] = None, **kwargs):
        details = kwargs.pop("details", {})  # Use pop to remove from kwargs
        if missing_vars:
            details["missing_environment_variables"] = missing_vars
        # Extract cause if present
        cause = kwargs.pop("cause", None)
        super().__init__(message, details=details, cause=cause)


class RepositoryError(GitHubIssueSolverError):
    """Raised when there are repository access or validation issues."""

    def __init__(
        self,
        message: str,
        repository: Optional[str] = None,
        github_error: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})  # Use pop to remove from kwargs
        if repository:
            details["repository"] = repository
        if github_error:
            details["github_error"] = github_error
        cause = kwargs.pop("cause", None)
        super().__init__(message, details=details, cause=cause)


class IngestionError(GitHubIssueSolverError):
    """Raised when repository ingestion fails."""

    def __init__(
        self,
        message: str,
        repository: Optional[str] = None,
        step: Optional[str] = None,
        documents_processed: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})  # Use pop to remove from kwargs
        if repository:
            details["repository"] = repository
        if step:
            details["ingestion_step"] = step
        if documents_processed is not None:
            details["documents_processed"] = documents_processed
        cause = kwargs.pop("cause", None)
        super().__init__(message, details=details, cause=cause)


class AnalysisError(GitHubIssueSolverError):
    """Raised when issue analysis fails."""

    def __init__(
        self,
        message: str,
        issue_url: Optional[str] = None,
        repository: Optional[str] = None,
        analysis_stage: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})  # Use pop to remove from kwargs
        if issue_url:
            details["issue_url"] = issue_url
        if repository:
            details["repository"] = repository
        if analysis_stage:
            details["analysis_stage"] = analysis_stage
        cause = kwargs.pop("cause", None)
        super().__init__(message, details=details, cause=cause)


class PatchGenerationError(GitHubIssueSolverError):
    """Raised when patch generation fails."""

    def __init__(
        self,
        message: str,
        repository: Optional[str] = None,
        issue_description: Optional[str] = None,
        generation_stage: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})  # Use pop to remove from kwargs
        if repository:
            details["repository"] = repository
        if issue_description:
            details["issue_description"] = issue_description[:200] + "..." if len(issue_description) > 200 else issue_description
        if generation_stage:
            details["generation_stage"] = generation_stage
        cause = kwargs.pop("cause", None)
        super().__init__(message, details=details, cause=cause)


class ChromaDBError(GitHubIssueSolverError):
    """Raised when ChromaDB operations fail."""

    def __init__(
        self,
        message: str,
        collection: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})  # Use pop to remove from kwargs
        if collection:
            details["collection"] = collection
        if operation:
            details["operation"] = operation
        cause = kwargs.pop("cause", None)
        super().__init__(message, details=details, cause=cause)


class StateManagementError(GitHubIssueSolverError):
    """Raised when state management operations fail."""

    def __init__(
        self,
        message: str,
        repository: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})  # Use pop to remove from kwargs
        if repository:
            details["repository"] = repository
        if operation:
            details["operation"] = operation
        cause = kwargs.pop("cause", None)
        super().__init__(message, details=details, cause=cause)
