"""
User-wise ChromaDB management for multi-tenancy lite.

This module provides user isolation for ChromaDB collections,
allowing multiple users to safely share the same server instance
without data leakage.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger

from .validation import validate_user_id, validate_repo_name
from .constants import CHROMADB


class UserManager:
    """
    Manage user-specific ChromaDB collections and metadata.

    Each user gets their own isolated ChromaDB directory and collections.
    """

    def __init__(self, base_chroma_dir: Path):
        """
        Initialize user manager.

        Args:
            base_chroma_dir: Base directory for ChromaDB storage
        """
        self.base_chroma_dir = Path(base_chroma_dir)
        self.base_chroma_dir.mkdir(parents=True, exist_ok=True)

        self.users_metadata_file = self.base_chroma_dir / "users_metadata.json"
        self.users_metadata = self._load_users_metadata()

    def _load_users_metadata(self) -> Dict[str, Any]:
        """Load users metadata from disk."""
        if self.users_metadata_file.exists():
            try:
                with open(self.users_metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load users metadata: {e}")
                return {}
        return {}

    def _save_users_metadata(self) -> None:
        """Save users metadata to disk."""
        try:
            self.users_metadata_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.users_metadata_file.with_suffix('.tmp')

            with open(temp_file, 'w') as f:
                json.dump(self.users_metadata, f, indent=2, default=str)

            temp_file.replace(self.users_metadata_file)
        except Exception as e:
            logger.error(f"Failed to save users metadata: {e}")
            raise

    def get_user_chroma_dir(self, user_id: str) -> Path:
        """
        Get ChromaDB directory for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Path to user's ChromaDB directory
        """
        # Validate user ID
        user_id = validate_user_id(user_id)

        # Create user-specific directory
        user_dir = self.base_chroma_dir / f"user_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)

        # Track user in metadata
        if user_id not in self.users_metadata:
            self.users_metadata[user_id] = {
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'repositories': [],
                'total_collections': 0
            }
            self._save_users_metadata()

        return user_dir

    def get_collection_name(
        self,
        user_id: str,
        repo_name: str,
        collection_type: str
    ) -> str:
        """
        Get user-specific collection name.

        Args:
            user_id: User identifier
            repo_name: Repository name (owner/repo)
            collection_type: Type of collection (docs, code, issues, prs)

        Returns:
            User-specific collection name
        """
        # Validate inputs
        user_id = validate_user_id(user_id)
        repo_name = validate_repo_name(repo_name)

        # Sanitize repo name
        safe_repo_name = repo_name.replace('/', '_').replace('-', '_').lower()

        # Create collection name with user prefix
        # Format: user_<userid>_<repo>_<type>
        return f"user_{user_id}_{safe_repo_name}_{collection_type}"

    def list_user_repositories(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all repositories ingested by a user.

        Args:
            user_id: User identifier

        Returns:
            List of repository metadata
        """
        user_id = validate_user_id(user_id)

        if user_id not in self.users_metadata:
            return []

        return self.users_metadata[user_id].get('repositories', [])

    def add_user_repository(
        self,
        user_id: str,
        repo_name: str,
        collections: List[str]
    ) -> None:
        """
        Track a repository for a user.

        Args:
            user_id: User identifier
            repo_name: Repository name
            collections: List of collection names created
        """
        user_id = validate_user_id(user_id)
        repo_name = validate_repo_name(repo_name)

        if user_id not in self.users_metadata:
            self.get_user_chroma_dir(user_id)  # Initialize user

        user_data = self.users_metadata[user_id]

        # Check if repo already exists
        existing_repos = [r['name'] for r in user_data.get('repositories', [])]
        if repo_name in existing_repos:
            # Update existing repository
            for repo in user_data['repositories']:
                if repo['name'] == repo_name:
                    repo['last_updated'] = datetime.now().isoformat()
                    repo['collections'] = collections
                    break
        else:
            # Add new repository
            if 'repositories' not in user_data:
                user_data['repositories'] = []

            user_data['repositories'].append({
                'name': repo_name,
                'collections': collections,
                'added_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            })

        # Update counts
        user_data['total_collections'] = len(collections)
        user_data['last_active'] = datetime.now().isoformat()

        self._save_users_metadata()

    def remove_user_repository(self, user_id: str, repo_name: str) -> bool:
        """
        Remove a repository from user's list.

        Args:
            user_id: User identifier
            repo_name: Repository name

        Returns:
            True if removed, False if not found
        """
        user_id = validate_user_id(user_id)
        repo_name = validate_repo_name(repo_name)

        if user_id not in self.users_metadata:
            return False

        user_data = self.users_metadata[user_id]
        repositories = user_data.get('repositories', [])

        # Find and remove repository
        initial_count = len(repositories)
        user_data['repositories'] = [
            r for r in repositories if r['name'] != repo_name
        ]

        if len(user_data['repositories']) < initial_count:
            self._save_users_metadata()
            return True

        return False

    def check_user_has_repository(self, user_id: str, repo_name: str) -> bool:
        """
        Check if user has already ingested a repository.

        Args:
            user_id: User identifier
            repo_name: Repository name

        Returns:
            True if user has the repository, False otherwise
        """
        user_id = validate_user_id(user_id)
        repo_name = validate_repo_name(repo_name)

        if user_id not in self.users_metadata:
            return False

        user_data = self.users_metadata[user_id]
        repositories = user_data.get('repositories', [])

        return any(r['name'] == repo_name for r in repositories)

    def get_user_repository_info(
        self,
        user_id: str,
        repo_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get information about a user's repository.

        Args:
            user_id: User identifier
            repo_name: Repository name

        Returns:
            Repository info or None if not found
        """
        user_id = validate_user_id(user_id)
        repo_name = validate_repo_name(repo_name)

        if user_id not in self.users_metadata:
            return None

        user_data = self.users_metadata[user_id]
        repositories = user_data.get('repositories', [])

        for repo in repositories:
            if repo['name'] == repo_name:
                return repo

        return None

    def list_all_users(self) -> List[str]:
        """
        List all user IDs.

        Returns:
            List of user IDs
        """
        return list(self.users_metadata.keys())

    def get_user_stats(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            User statistics or None if user not found
        """
        user_id = validate_user_id(user_id)

        if user_id not in self.users_metadata:
            return None

        user_data = self.users_metadata[user_id]

        return {
            'user_id': user_id,
            'total_repositories': len(user_data.get('repositories', [])),
            'total_collections': user_data.get('total_collections', 0),
            'created_at': user_data.get('created_at'),
            'last_active': user_data.get('last_active'),
            'repositories': user_data.get('repositories', [])
        }

    def cleanup_user_data(self, user_id: str) -> bool:
        """
        Clean up all data for a user (ChromaDB directory and metadata).

        Args:
            user_id: User identifier

        Returns:
            True if cleanup successful
        """
        user_id = validate_user_id(user_id)

        try:
            # Remove ChromaDB directory
            user_dir = self.base_chroma_dir / f"user_{user_id}"
            if user_dir.exists():
                import shutil
                shutil.rmtree(user_dir)
                logger.info(f"Removed ChromaDB directory for user: {user_id}")

            # Remove from metadata
            if user_id in self.users_metadata:
                del self.users_metadata[user_id]
                self._save_users_metadata()
                logger.info(f"Removed metadata for user: {user_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to cleanup user data: {e}")
            return False


def get_user_id_from_context() -> str:
    """
    Get user ID from current context.

    For Docker deployment, this can be:
    1. Environment variable (USER_ID)
    2. License key hash
    3. Default user if not specified

    Returns:
        User ID
    """
    # Try environment variable first
    user_id = os.getenv('USER_ID')
    if user_id:
        return validate_user_id(user_id)

    # Try license key (will implement in license module)
    license_key = os.getenv('LICENSE_KEY')
    if license_key:
        # Use first 8 characters of license key as user ID
        import hashlib
        user_id = hashlib.sha256(license_key.encode()).hexdigest()[:16]
        return user_id

    # Default to 'default_user' for development
    return 'default_user'
