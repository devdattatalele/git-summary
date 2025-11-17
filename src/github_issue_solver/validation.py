"""
Input validation module to prevent security vulnerabilities.

This module provides validation functions for all user inputs to prevent:
- Command injection attacks
- Path traversal attacks
- SSRF attacks
- Invalid data formats
"""

import re
from typing import Optional
from urllib.parse import urlparse
from .exceptions import ConfigurationError


class InputValidator:
    """Centralized input validation for security."""

    # Patterns
    REPO_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$')
    GITHUB_URL_PATTERN = re.compile(
        r'^https://github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)(?:/issues/(\d+))?$'
    )

    # Limits
    MAX_REPO_NAME_LENGTH = 200
    MAX_ISSUE_DESCRIPTION_LENGTH = 50000
    MAX_BRANCH_NAME_LENGTH = 100

    @staticmethod
    def validate_repo_name(repo_name: str) -> str:
        """
        Validate GitHub repository name format.

        Args:
            repo_name: Repository name in format 'owner/repo'

        Returns:
            Validated repository name

        Raises:
            ValueError: If repository name is invalid
        """
        if not repo_name or not isinstance(repo_name, str):
            raise ValueError("Repository name must be a non-empty string")

        # Check length
        if len(repo_name) > InputValidator.MAX_REPO_NAME_LENGTH:
            raise ValueError(
                f"Repository name too long (max {InputValidator.MAX_REPO_NAME_LENGTH} chars)"
            )

        # Check format
        if not InputValidator.REPO_NAME_PATTERN.match(repo_name):
            raise ValueError(
                f"Invalid repository name format: {repo_name}. "
                "Must be in format 'owner/repo' with alphanumeric characters, "
                "hyphens, underscores, and dots only."
            )

        # Check for path traversal attempts
        if '..' in repo_name or '~' in repo_name or '/' * 2 in repo_name:
            raise ValueError(f"Path traversal detected in repository name: {repo_name}")

        # Check for shell metacharacters
        dangerous_chars = [';', '&', '|', '$', '`', '\n', '\r', '<', '>']
        for char in dangerous_chars:
            if char in repo_name:
                raise ValueError(
                    f"Invalid character '{char}' in repository name: {repo_name}"
                )

        return repo_name

    @staticmethod
    def validate_github_url(url: str) -> tuple[str, Optional[str]]:
        """
        Validate GitHub URL and extract repository name and issue number.

        Args:
            url: GitHub URL (repo or issue)

        Returns:
            Tuple of (repo_name, issue_number)

        Raises:
            ValueError: If URL is invalid or not from github.com
        """
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")

        # Parse URL
        parsed = urlparse(url.strip())

        # Validate scheme
        if parsed.scheme != 'https':
            raise ValueError(
                f"Only HTTPS URLs are allowed. Got: {parsed.scheme}://"
            )

        # Validate hostname (prevent SSRF)
        if parsed.netloc != 'github.com':
            raise ValueError(
                f"Only github.com URLs are allowed. Got: {parsed.netloc}"
            )

        # Match pattern
        match = InputValidator.GITHUB_URL_PATTERN.match(url.strip())
        if not match:
            raise ValueError(
                f"Invalid GitHub URL format: {url}. "
                "Expected format: https://github.com/owner/repo or "
                "https://github.com/owner/repo/issues/123"
            )

        owner, repo, issue_num = match.groups()
        repo_name = f"{owner}/{repo}"

        # Validate extracted repo name
        InputValidator.validate_repo_name(repo_name)

        return repo_name, issue_num

    @staticmethod
    def validate_user_id(user_id: str) -> str:
        """
        Validate user ID format.

        Args:
            user_id: User identifier

        Returns:
            Validated user ID

        Raises:
            ValueError: If user ID is invalid
        """
        if not user_id or not isinstance(user_id, str):
            raise ValueError("User ID must be a non-empty string")

        # Allow alphanumeric, hyphens, underscores only
        if not re.match(r'^[a-zA-Z0-9_-]+$', user_id):
            raise ValueError(
                f"Invalid user ID format: {user_id}. "
                "Only alphanumeric characters, hyphens, and underscores allowed."
            )

        if len(user_id) > 100:
            raise ValueError("User ID too long (max 100 chars)")

        return user_id

    @staticmethod
    def validate_collection_type(collection_type: str) -> str:
        """
        Validate collection type.

        Args:
            collection_type: Type of collection (docs, code, issues, prs)

        Returns:
            Validated collection type

        Raises:
            ValueError: If collection type is invalid
        """
        valid_types = {'documentation', 'code', 'issues', 'prs'}

        if collection_type not in valid_types:
            raise ValueError(
                f"Invalid collection type: {collection_type}. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        return collection_type

    @staticmethod
    def sanitize_for_logging(data: any) -> any:
        """
        Sanitize data for logging to prevent leaking sensitive information.

        Args:
            data: Data to sanitize (can be dict, list, string, etc.)

        Returns:
            Sanitized data safe for logging
        """
        if isinstance(data, dict):
            sensitive_keys = {
                'api_key', 'token', 'password', 'secret', 'credential',
                'github_token', 'google_api_key', 'authorization'
            }
            return {
                k: '***REDACTED***' if any(s in k.lower() for s in sensitive_keys) else InputValidator.sanitize_for_logging(v)
                for k, v in data.items()
            }
        elif isinstance(data, (list, tuple)):
            return [InputValidator.sanitize_for_logging(item) for item in data]
        elif isinstance(data, str):
            # Redact potential tokens in strings
            if len(data) > 20 and any(indicator in data.lower() for indicator in ['token', 'key', 'secret']):
                return '***REDACTED***'
            return data
        else:
            return data

    @staticmethod
    def validate_file_path(file_path: str, allowed_extensions: Optional[set] = None) -> str:
        """
        Validate file path to prevent path traversal.

        Args:
            file_path: File path to validate
            allowed_extensions: Optional set of allowed file extensions

        Returns:
            Validated file path

        Raises:
            ValueError: If file path is invalid
        """
        if not file_path or not isinstance(file_path, str):
            raise ValueError("File path must be a non-empty string")

        # Check for path traversal
        if '..' in file_path or file_path.startswith('/'):
            raise ValueError(f"Path traversal detected: {file_path}")

        # Check for null bytes
        if '\0' in file_path:
            raise ValueError(f"Null byte detected in file path: {file_path}")

        # Check extensions if provided
        if allowed_extensions:
            extension = file_path.split('.')[-1].lower() if '.' in file_path else ''
            if extension not in allowed_extensions:
                raise ValueError(
                    f"File extension '{extension}' not allowed. "
                    f"Allowed: {', '.join(allowed_extensions)}"
                )

        return file_path


# Convenience functions for backward compatibility
def validate_repo_name(repo_name: str) -> str:
    """Validate repository name."""
    return InputValidator.validate_repo_name(repo_name)


def validate_github_url(url: str) -> tuple[str, Optional[str]]:
    """Validate GitHub URL."""
    return InputValidator.validate_github_url(url)


def validate_user_id(user_id: str) -> str:
    """Validate user ID."""
    return InputValidator.validate_user_id(user_id)


def sanitize_for_logging(data: any) -> any:
    """Sanitize data for logging."""
    return InputValidator.sanitize_for_logging(data)
