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
from .license import validate_and_get_license_info, LicenseInfo
from .user_manager import UserManager, get_user_id_from_context


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

        # Supabase configuration (hardcoded, but can be overridden via env vars)
        # These are public credentials (anon key) - safe to include in Docker image
        self._supabase_defaults = {
            "SUPABASE_URL": "https://obrwsclermqxtipcauoz.supabase.co",
            "SUPABASE_ANON_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9icndzY2xlcm1xeHRpcGNhdW96Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjMyMjgyNTgsImV4cCI6MjA3ODgwNDI1OH0.B0xS8nHWtcLJC6Z3IRkO_IXSaV4uGNVutNX6l6YmfcY"
        }
        
        # Optional environment variables with defaults
        self._optional_vars = {
            "GOOGLE_DOCS_ID": None,
            "CHROMA_PERSIST_DIR": None,
            "MAX_ISSUES": "100",
            "MAX_PRS": "15",  # Reduced to 15 to prevent timeout on repos with many PRs (was 25, originally 50) 
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

        # Initialize license validation (Phase 1)
        self.license_info: Optional[LicenseInfo] = None
        self.user_id: Optional[str] = None
        self.user_manager: Optional[UserManager] = None
        self.machine_id: Optional[str] = None  # For trial user tracking and enforcement

        # Validate license and setup user management
        self._setup_license_and_user()

    def _validate_and_load(self) -> None:
        """Validate required variables and load all configuration."""
        missing_vars = []

        # Check required variables
        for var_name, description in self._required_vars.items():
            value = os.getenv(var_name)
            if not value:
                missing_vars.append(f"{var_name} ({description})")

        # Note: Supabase vars have defaults, so not checking them here

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

        # Supabase configuration (use defaults, allow environment override)
        self.supabase_url = os.getenv("SUPABASE_URL", self._supabase_defaults["SUPABASE_URL"])
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", self._supabase_defaults["SUPABASE_ANON_KEY"])

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
        self.max_prs = int(os.getenv("MAX_PRS", "15"))  # Default 15 to prevent timeouts on repos with many PRs
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
        
    def _setup_license_and_user(self) -> None:
        """Setup license validation and user management."""
        try:
            # Validate license (using Supabase)
            self.license_info = validate_and_get_license_info(
                supabase_url=self.supabase_url,
                supabase_key=self.supabase_anon_key
            )
            logger.info(f"License validated: {self.license_info.tier} tier")

            # Get machine ID for trial users (for tracking and limit enforcement)
            if self.license_info.is_trial:
                from .license import get_machine_id
                self.machine_id = get_machine_id()
                logger.info(f"Trial user - Machine ID: {self.machine_id[:8]}...")
                logger.info(f"Trial limits: 3 repositories, 10 analyses, {self.license_info.days_remaining()} days remaining")

            # Get user ID from license or environment
            self.user_id = get_user_id_from_context()
            logger.info(f"User ID: {self.user_id}")

            # Initialize user manager
            self.user_manager = UserManager(self.chroma_persist_dir)
            logger.info("User manager initialized")

        except Exception as e:
            logger.error(f"License/User setup failed: {e}")
            raise ConfigurationError(
                f"Failed to initialize license validation: {str(e)}"
            )

    def get_collection_name(self, repo_name: str, collection_type: str) -> str:
        """
        Get the full collection name for a repository and type.
        Now includes user isolation.

        Args:
            repo_name: Repository name in 'owner/repo' format
            collection_type: Type of collection (docs, code, issues, prs)

        Returns:
            Full collection name with user isolation
        """
        if self.user_manager and self.user_id:
            # Use user-isolated collection name
            return self.user_manager.get_collection_name(
                self.user_id,
                repo_name,
                collection_type
            )
        else:
            # Fallback to old naming (for backward compatibility)
            safe_repo_name = repo_name.replace('/', '_').replace('-', '_').lower()
            base_name = self.collection_names.get(collection_type, collection_type)
            return f"{safe_repo_name}_{base_name}"

    def get_user_chroma_dir(self) -> Path:
        """
        Get ChromaDB directory for current user.

        Returns:
            Path to user's ChromaDB directory
        """
        if self.user_manager and self.user_id:
            return self.user_manager.get_user_chroma_dir(self.user_id)
        else:
            return self.chroma_persist_dir

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
