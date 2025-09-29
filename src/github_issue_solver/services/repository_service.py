"""
Repository service for the GitHub Issue Solver MCP Server.

Handles GitHub repository operations including validation, access checking,
and repository information retrieval with proper error handling.
"""

import asyncio
from loguru import logger
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from github import Github, GithubException
from github.Repository import Repository
from github.Issue import Issue

from ..config import Config
from ..exceptions import RepositoryError
from ..models import IssueInfo



class RepositoryService:
    """Service for GitHub repository operations."""
    
    def __init__(self, config: Config):
        """
        Initialize repository service.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self._github_client: Optional[Github] = None
        
    @property
    def github_client(self) -> Github:
        """Get or create GitHub client."""
        if self._github_client is None:
            self._github_client = Github(self.config.github_token)
        return self._github_client
    
    async def validate_repository(self, repo_name: str) -> bool:
        """
        Validate that a repository exists and is accessible.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            True if repository is valid and accessible
            
        Raises:
            RepositoryError: If repository validation fails
        """
        try:
            logger.info(f"Validating repository: {repo_name}")
            
            # Run GitHub API call in thread pool
            repo = await asyncio.to_thread(self._get_repository_sync, repo_name)
            
            logger.info(f"Repository validated successfully: {repo.full_name}")
            return True
            
        except GithubException as e:
            if e.status == 404:
                raise RepositoryError(
                    f"Repository '{repo_name}' not found",
                    repository=repo_name,
                    github_error=f"HTTP {e.status}: {e.data.get('message', 'Not Found')}"
                )
            elif e.status == 403:
                raise RepositoryError(
                    f"Access denied to repository '{repo_name}'",
                    repository=repo_name,
                    github_error=f"HTTP {e.status}: {e.data.get('message', 'Forbidden')}"
                )
            else:
                raise RepositoryError(
                    f"GitHub API error for repository '{repo_name}'",
                    repository=repo_name,
                    github_error=f"HTTP {e.status}: {e.data.get('message', 'Unknown error')}"
                )
        except Exception as e:
            raise RepositoryError(
                f"Failed to validate repository '{repo_name}': {str(e)}",
                repository=repo_name,
                cause=e
            )
    
    def _get_repository_sync(self, repo_name: str) -> Repository:
        """Synchronous repository getter for thread pool execution."""
        return self.github_client.get_repo(repo_name)
    
    async def get_repository(self, repo_name: str) -> Repository:
        """
        Get repository object.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            GitHub repository object
            
        Raises:
            RepositoryError: If repository cannot be accessed
        """
        try:
            logger.debug(f"Getting repository: {repo_name}")
            repo = await asyncio.to_thread(self._get_repository_sync, repo_name)
            return repo
        except Exception as e:
            raise RepositoryError(
                f"Failed to get repository '{repo_name}': {str(e)}",
                repository=repo_name,
                cause=e
            )
    
    async def get_repository_info(self, repo_name: str) -> Dict[str, Any]:
        """
        Get comprehensive repository information.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            Dictionary with repository information
            
        Raises:
            RepositoryError: If repository information cannot be retrieved
        """
        try:
            repo = await self.get_repository(repo_name)
            
            # Get branch information safely
            try:
                branches = await asyncio.to_thread(lambda: list(repo.get_branches()))
                branch_names = [branch.name for branch in branches[:10]]  # First 10 branches
            except Exception as e:
                logger.warning(f"Could not get branches for {repo_name}: {e}")
                branch_names = ["Unable to fetch branches"]
            
            info = {
                "full_name": repo.full_name,
                "description": repo.description,
                "default_branch": repo.default_branch,
                "language": repo.language,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "open_issues": repo.open_issues_count,
                "last_updated": repo.updated_at.isoformat(),
                "is_private": repo.private,
                "is_fork": repo.fork,
                "size_kb": repo.size,
                "branches": branch_names,
                "topics": repo.get_topics(),
                "clone_url": repo.clone_url,
                "ssh_url": repo.ssh_url,
                "created_at": repo.created_at.isoformat(),
                "archived": repo.archived,
                "disabled": getattr(repo, 'disabled', False),
                "has_issues": repo.has_issues,
                "has_wiki": repo.has_wiki,
                "has_pages": repo.has_pages,
                "has_downloads": repo.has_downloads,
            }
            
            logger.info(f"Retrieved repository info for {repo_name}")
            return info
            
        except RepositoryError:
            raise
        except Exception as e:
            raise RepositoryError(
                f"Failed to get repository info for '{repo_name}': {str(e)}",
                repository=repo_name,
                cause=e
            )
    
    def parse_github_url(self, url: str) -> Tuple[str, str, int]:
        """
        Parse GitHub issue URL to extract components.
        
        Args:
            url: GitHub issue URL
            
        Returns:
            Tuple of (owner, repo, issue_number)
            
        Raises:
            RepositoryError: If URL parsing fails
        """
        import re
        
        try:
            # Pattern for GitHub issue URLs
            pattern = r'https://github\.com/([^/]+)/([^/]+)/issues/(\d+)'
            match = re.match(pattern, url.strip())
            
            if not match:
                raise RepositoryError(
                    f"Invalid GitHub issue URL format: {url}",
                    details={
                        "url": url,
                        "expected_format": "https://github.com/owner/repo/issues/123"
                    }
                )
            
            owner, repo, issue_number = match.groups()
            return owner, repo, int(issue_number)
            
        except ValueError as e:
            raise RepositoryError(
                f"Invalid issue number in URL: {url}",
                details={"url": url, "error": str(e)}
            )
        except Exception as e:
            raise RepositoryError(
                f"Failed to parse GitHub URL: {url}",
                details={"url": url},
                cause=e
            )
    
    async def get_github_issue(self, owner: str, repo: str, issue_number: int) -> IssueInfo:
        """
        Get GitHub issue information.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            
        Returns:
            Issue information
            
        Raises:
            RepositoryError: If issue cannot be retrieved
        """
        try:
            repo_name = f"{owner}/{repo}"
            logger.info(f"Getting issue #{issue_number} from {repo_name}")
            
            repository = await self.get_repository(repo_name)
            issue = await asyncio.to_thread(repository.get_issue, issue_number)
            
            # Extract assignee names
            assignees = []
            if issue.assignees:
                assignees = [assignee.login for assignee in issue.assignees]
            
            # Extract label names
            labels = []
            if issue.labels:
                labels = [label.name for label in issue.labels]
            
            issue_info = IssueInfo(
                number=issue.number,
                title=issue.title,
                body=issue.body or "",
                url=issue.html_url,
                state=issue.state,
                repository=repository.full_name,
                created_at=issue.created_at,
                updated_at=issue.updated_at,
                labels=labels,
                assignees=assignees
            )
            
            logger.info(f"Retrieved issue #{issue_number}: {issue.title}")
            return issue_info
            
        except GithubException as e:
            if e.status == 404:
                raise RepositoryError(
                    f"Issue #{issue_number} not found in {owner}/{repo}",
                    repository=f"{owner}/{repo}",
                    github_error=f"HTTP {e.status}: {e.data.get('message', 'Not Found')}"
                )
            else:
                raise RepositoryError(
                    f"GitHub API error getting issue #{issue_number}",
                    repository=f"{owner}/{repo}",
                    github_error=f"HTTP {e.status}: {e.data.get('message', 'Unknown error')}"
                )
        except Exception as e:
            raise RepositoryError(
                f"Failed to get issue #{issue_number} from {owner}/{repo}: {str(e)}",
                repository=f"{owner}/{repo}",
                cause=e
            )
    
    async def check_api_limits(self) -> Dict[str, Any]:
        """
        Check GitHub API rate limits.
        
        Returns:
            Dictionary with rate limit information
        """
        try:
            rate_limit = await asyncio.to_thread(self.github_client.get_rate_limit)
            
            core_info = rate_limit.core
            search_info = rate_limit.search
            
            return {
                "core": {
                    "limit": core_info.limit,
                    "remaining": core_info.remaining,
                    "reset": core_info.reset.isoformat(),
                    "used": core_info.limit - core_info.remaining
                },
                "search": {
                    "limit": search_info.limit,
                    "remaining": search_info.remaining,
                    "reset": search_info.reset.isoformat(),
                    "used": search_info.limit - search_info.remaining
                }
            }
            
        except Exception as e:
            logger.warning(f"Failed to get API limits: {e}")
            return {
                "error": str(e),
                "core": {"limit": 0, "remaining": 0, "used": 0},
                "search": {"limit": 0, "remaining": 0, "used": 0}
            }
    
    async def test_connection(self) -> bool:
        """
        Test GitHub API connection.
        
        Returns:
            True if connection is working
        """
        try:
            user = await asyncio.to_thread(self.github_client.get_user)
            logger.info(f"GitHub connection test successful - authenticated as: {user.login}")
            return True
        except Exception as e:
            logger.error(f"GitHub connection test failed: {e}")
            return False
