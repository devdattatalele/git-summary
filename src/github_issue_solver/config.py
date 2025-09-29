"""
Configuration management for the GitHub Issue Solver MCP Server.

Handles environment variables, validation, and configuration defaults
with proper error handling and security practices.
"""

import os
from typing import List, Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

from .exceptions import ConfigurationError


class Config:
    """Configuration manager for the GitHub Issue Solver MCP Server."""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration with environment variables.
        
        Args:
            env_file: Optional path to .env file
        """
        # Load environment variables
        if env_file and Path(env_file).exists():
            load_dotenv(env_file)
        else:
            load_dotenv()  # Load from default locations
        
        # Required environment variables
        self._required_vars = {
            "GOOGLE_API_KEY": "Google API key for embeddings and analysis",
            "GITHUB_TOKEN": "GitHub personal access token for repository access"
        }
        
        # Optional environment variables with defaults
        self._optional_vars = {
            "GOOGLE_DOCS_ID": None,
            "CHROMA_PERSIST_DIR": None,
            "MAX_ISSUES": "100",
            "MAX_PRS": "50", 
            "MAX_FILES": "50",
            "ENABLE_PATCH_GENERATION": "true",
            "MAX_COMPLEXITY_FOR_AUTO_PR": "4",
            "LOG_LEVEL": "INFO",
            "HEALTH_CHECK_INTERVAL": "300",  # 5 minutes
            "RETRY_ATTEMPTS": "3",
            "RETRY_DELAY": "1",
            "EMBEDDING_PROVIDER": "google",  # 'google' or 'fastembed'
            "EMBEDDING_MODEL_NAME": "BAAI/bge-small-en-v1.5",  # Model for FastEmbed
        }
        
        # Initialize configuration
        self._validate_and_load()
        
    def _validate_and_load(self) -> None:
        """Validate required variables and load all configuration."""
        missing_vars = []
        
        # Check required variables
        for var_name, description in self._required_vars.items():
            value = os.getenv(var_name)
            if not value:
                missing_vars.append(f"{var_name} ({description})")
        
        if missing_vars:
            raise ConfigurationError(
                f"Missing required environment variables: {', '.join([var.split(' (')[0] for var in missing_vars])}",
                missing_vars=missing_vars,
                details={
                    "missing_variables": missing_vars,
                    "suggestion": "Please set these environment variables in your .env file or system environment"
                }
            )
        
        # Load all configuration values
        self._load_values()
        logger.info("Configuration loaded and validated successfully")
    
    def _load_values(self) -> None:
        """Load all configuration values from environment."""
        # Required values
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.github_token = os.getenv("GITHUB_TOKEN")
        
        # Optional values with defaults
        self.google_docs_id = os.getenv("GOOGLE_DOCS_ID")
        
        # Database configuration
        project_root = Path(__file__).parent.parent.parent.absolute()
        default_chroma_dir = project_root / "chroma_db"
        self.chroma_persist_dir = Path(
            os.getenv("CHROMA_PERSIST_DIR", str(default_chroma_dir))
        ).absolute()
        
        # Numeric configuration
        self.max_issues = int(os.getenv("MAX_ISSUES", "100"))
        self.max_prs = int(os.getenv("MAX_PRS", "50"))
        self.max_files = int(os.getenv("MAX_FILES", "50"))
        self.max_complexity_for_auto_pr = int(os.getenv("MAX_COMPLEXITY_FOR_AUTO_PR", "4"))
        self.health_check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL", "300"))
        self.retry_attempts = int(os.getenv("RETRY_ATTEMPTS", "3"))
        self.retry_delay = float(os.getenv("RETRY_DELAY", "1"))
        
        # Boolean configuration
        self.enable_patch_generation = os.getenv("ENABLE_PATCH_GENERATION", "true").lower() == "true"
        
        # Logging configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        
        # Collection names
        self.collection_names = {
            "documentation": "documentation",
            "code": "repo_code_main", 
            "issues": "issues_history",
            "prs": "pr_history"
        }
        
        # Embedding configuration
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "google").lower()
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-en-v1.5")
        
        # Gemini model configuration (keep the existing ones)
        self.gemini_embedding_model = "models/embedding-004"
        self.gemini_chat_model = "gemini-1.5-pro-latest"  # Updated to a more recent model
        
    def get_collection_name(self, repo_name: str, collection_type: str) -> str:
        """
        Get the full collection name for a repository and type.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            collection_type: Type of collection (docs, code, issues, prs)
            
        Returns:
            Full collection name
        """
        safe_repo_name = repo_name.replace('/', '_').replace('-', '_').lower()
        base_name = self.collection_names.get(collection_type, collection_type)
        return f"{safe_repo_name}_{base_name}"
    
    def ensure_chroma_dir(self) -> None:
        """Ensure ChromaDB directory exists with proper permissions."""
        try:
            self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"ChromaDB directory ensured: {self.chroma_persist_dir}")
        except PermissionError as e:
            raise ConfigurationError(
                f"Cannot create ChromaDB directory: {self.chroma_persist_dir}",
                details={
                    "directory": str(self.chroma_persist_dir),
                    "error": str(e),
                    "suggestion": "Please check file system permissions or set CHROMA_PERSIST_DIR to a writable location"
                }
            )
    
    def validate_api_access(self) -> Dict[str, bool]:
        """
        Validate API access for external services.
        
        Returns:
            Dictionary with validation results for each service
        """
        results = {}
        
        # Test Google API
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.google_api_key)
            # Simple test call
            results["google_api"] = True
        except Exception as e:
            logger.warning(f"Google API validation failed: {e}")
            results["google_api"] = False
        
        # Test GitHub API  
        try:
            from github import Github
            github_client = Github(self.github_token)
            github_client.get_user().login  # Simple test call
            results["github_api"] = True
        except Exception as e:
            logger.warning(f"GitHub API validation failed: {e}")
            results["github_api"] = False
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive configuration status.
        
        Returns:
            Dictionary with configuration status and details
        """
        api_status = self.validate_api_access()
        
        return {
            "configuration": {
                "chroma_dir": str(self.chroma_persist_dir),
                "chroma_dir_exists": self.chroma_persist_dir.exists(),
                "google_docs_configured": bool(self.google_docs_id),
                "patch_generation_enabled": self.enable_patch_generation,
                "log_level": self.log_level,
            },
            "limits": {
                "max_issues": self.max_issues,
                "max_prs": self.max_prs,
                "max_files": self.max_files,
                "max_complexity_for_auto_pr": self.max_complexity_for_auto_pr,
            },
            "api_access": api_status,
            "retry_config": {
                "attempts": self.retry_attempts,
                "delay": self.retry_delay,
            },
            "health": {
                "check_interval": self.health_check_interval,
            }
        }
    
    def __repr__(self) -> str:
        """String representation of configuration (without sensitive data)."""
        return (
            f"Config("
            f"chroma_dir={self.chroma_persist_dir}, "
            f"max_issues={self.max_issues}, "
            f"max_prs={self.max_prs}, "
            f"patch_gen={self.enable_patch_generation}"
            f")"
        )
