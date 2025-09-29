"""
State management service for the GitHub Issue Solver MCP Server.

Handles persistent state management for repository ingestion status,
with atomic operations and error recovery capabilities.
"""

import json
from loguru import logger
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock

from ..models import RepositoryStatus, IngestionStatus, IngestionStep, StepResult
from ..exceptions import StateManagementError
from ..config import Config



class StateManager:
    """Manages persistent state for repository ingestion and analysis."""
    
    def __init__(self, config: Config):
        """
        Initialize state manager.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self._state: Dict[str, RepositoryStatus] = {}
        self._lock = RLock()  # Thread-safe access
        
        # State persistence file
        self._state_file = self.config.chroma_persist_dir / "state.json"
        
        # Initialize state
        self._load_state()
        
    def _load_state(self) -> None:
        """Load state from persistent storage."""
        try:
            if self._state_file.exists():
                with open(self._state_file, 'r') as f:
                    state_data = json.load(f)
                
                # Reconstruct RepositoryStatus objects
                for repo_name, repo_data in state_data.items():
                    self._state[repo_name] = self._deserialize_repository_status(repo_data)
                
                logger.info(f"Loaded state for {len(self._state)} repositories")
            else:
                logger.info("No existing state file found, starting with empty state")
                
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            # Start with empty state on load failure
            self._state = {}
    
    def _save_state(self) -> None:
        """Save current state to persistent storage."""
        try:
            # Ensure directory exists
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Serialize state
            state_data = {}
            for repo_name, repo_status in self._state.items():
                state_data[repo_name] = repo_status.to_dict()
            
            # Atomic write using temporary file
            temp_file = self._state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state_data, f, indent=2, default=str)
            
            # Atomic move
            temp_file.replace(self._state_file)
            logger.debug(f"State saved for {len(self._state)} repositories")
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            raise StateManagementError(f"Failed to save state: {e}")
    
    def _deserialize_repository_status(self, data: Dict) -> RepositoryStatus:
        """Deserialize repository status from dictionary."""
        try:
            # Parse datetime fields
            created_at = datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
            updated_at = datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
            
            # Parse steps
            steps = {}
            for step_name, step_data in data.get('steps', {}).items():
                step = IngestionStep(step_name)
                steps[step] = StepResult(
                    step=step,
                    status=IngestionStatus(step_data['status']),
                    documents_stored=step_data.get('documents_stored', 0),
                    collection_name=step_data.get('collection_name'),
                    error_message=step_data.get('error_message'),
                    started_at=datetime.fromisoformat(step_data['started_at']) if step_data.get('started_at') else None,
                    completed_at=datetime.fromisoformat(step_data['completed_at']) if step_data.get('completed_at') else None,
                    duration_seconds=step_data.get('duration_seconds')
                )
            
            return RepositoryStatus(
                repo_name=data['repo_name'],
                overall_status=IngestionStatus(data['overall_status']),
                steps=steps,
                total_documents=data.get('total_documents', 0),
                chroma_dir=data.get('chroma_dir'),
                collections=data.get('collections', []),
                created_at=created_at,
                updated_at=updated_at,
                error_message=data.get('error_message')
            )
            
        except Exception as e:
            logger.error(f"Failed to deserialize repository status: {e}")
            # Return minimal status on error
            return RepositoryStatus(
                repo_name=data.get('repo_name', 'unknown'),
                overall_status=IngestionStatus.ERROR,
                error_message=f"Failed to load state: {e}"
            )
    
    def get_repository_status(self, repo_name: str) -> Optional[RepositoryStatus]:
        """
        Get repository status.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            Repository status or None if not found
        """
        with self._lock:
            return self._state.get(repo_name)
    
    def create_repository_status(self, repo_name: str) -> RepositoryStatus:
        """
        Create new repository status entry.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            Created repository status
        """
        with self._lock:
            if repo_name in self._state:
                logger.warning(f"Repository {repo_name} already exists in state")
                return self._state[repo_name]
            
            status = RepositoryStatus(
                repo_name=repo_name,
                overall_status=IngestionStatus.PENDING,
                chroma_dir=str(self.config.chroma_persist_dir),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            self._state[repo_name] = status
            self._save_state()
            
            logger.info(f"Created repository status for {repo_name}")
            return status
    
    def update_repository_step(
        self,
        repo_name: str,
        step: IngestionStep,
        status: IngestionStatus,
        **kwargs
    ) -> None:
        """
        Update a specific step for a repository.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            step: Ingestion step to update
            status: New status for the step
            **kwargs: Additional step attributes to update
        """
        with self._lock:
            if repo_name not in self._state:
                raise StateManagementError(f"Repository {repo_name} not found in state")
            
            repo_status = self._state[repo_name]
            repo_status.update_step(step, status, **kwargs)
            
            # Update total documents if provided
            if 'documents_stored' in kwargs:
                documents = kwargs['documents_stored']
                if step in repo_status.steps:
                    # Update total by difference
                    old_docs = repo_status.steps[step].documents_stored or 0
                    repo_status.total_documents += (documents - old_docs)
            
            # Add collection if provided
            if 'collection_name' in kwargs and kwargs['collection_name']:
                collection_name = kwargs['collection_name']
                if collection_name not in repo_status.collections:
                    repo_status.collections.append(collection_name)
            
            self._save_state()
            logger.debug(f"Updated {step.value} step for {repo_name}: {status.value}")
    
    def set_repository_error(self, repo_name: str, error_message: str, step: Optional[IngestionStep] = None) -> None:
        """
        Set error status for repository or specific step.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            error_message: Error message
            step: Optional specific step that failed
        """
        with self._lock:
            if repo_name not in self._state:
                # Create minimal status for error reporting
                self._state[repo_name] = RepositoryStatus(
                    repo_name=repo_name,
                    overall_status=IngestionStatus.ERROR,
                    error_message=error_message,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            else:
                repo_status = self._state[repo_name]
                repo_status.overall_status = IngestionStatus.ERROR
                repo_status.error_message = error_message
                repo_status.updated_at = datetime.now()
                
                if step:
                    repo_status.update_step(step, IngestionStatus.ERROR, error_message=error_message)
            
            self._save_state()
            logger.error(f"Set error for {repo_name}: {error_message}")
    
    def complete_repository_ingestion(self, repo_name: str) -> None:
        """
        Mark repository ingestion as complete.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
        """
        with self._lock:
            if repo_name not in self._state:
                raise StateManagementError(f"Repository {repo_name} not found in state")
            
            repo_status = self._state[repo_name]
            repo_status.overall_status = IngestionStatus.COMPLETED
            repo_status.updated_at = datetime.now()
            
            self._save_state()
            logger.info(f"Completed ingestion for {repo_name}")
    
    def delete_repository_status(self, repo_name: str) -> bool:
        """
        Delete repository status.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if repo_name in self._state:
                del self._state[repo_name]
                self._save_state()
                logger.info(f"Deleted repository status for {repo_name}")
                return True
            return False
    
    def list_repositories(self) -> List[str]:
        """
        List all repositories in state.
        
        Returns:
            List of repository names
        """
        with self._lock:
            return list(self._state.keys())
    
    def get_repositories_by_status(self, status: IngestionStatus) -> List[RepositoryStatus]:
        """
        Get repositories by status.
        
        Args:
            status: Status to filter by
            
        Returns:
            List of repository statuses matching the given status
        """
        with self._lock:
            return [
                repo_status for repo_status in self._state.values()
                if repo_status.overall_status == status
            ]
    
    def get_all_repository_statuses(self) -> Dict[str, RepositoryStatus]:
        """
        Get all repository statuses.
        
        Returns:
            Dictionary of all repository statuses
        """
        with self._lock:
            return dict(self._state)
    
    def cleanup_old_entries(self, max_age_days: int = 30) -> int:
        """
        Cleanup old repository entries.
        
        Args:
            max_age_days: Maximum age in days before cleanup
            
        Returns:
            Number of entries cleaned up
        """
        with self._lock:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            to_remove = []
            
            for repo_name, repo_status in self._state.items():
                if (repo_status.updated_at and repo_status.updated_at < cutoff_date and
                    repo_status.overall_status in [IngestionStatus.ERROR, IngestionStatus.CANCELLED]):
                    to_remove.append(repo_name)
            
            for repo_name in to_remove:
                del self._state[repo_name]
            
            if to_remove:
                self._save_state()
                logger.info(f"Cleaned up {len(to_remove)} old repository entries")
            
            return len(to_remove)
