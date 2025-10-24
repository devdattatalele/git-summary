"""
Ingestion service for the GitHub Issue Solver MCP Server.

Handles the multi-step repository data ingestion process including documentation,
code analysis, issues history, and PR history with proper error handling and recovery.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from github.Repository import Repository

from ..config import Config
from ..models import IngestionResult, IngestionStep, IngestionStatus
from ..exceptions import IngestionError
from ..services.repository_service import RepositoryService
from ..services.state_manager import StateManager
from ..services.embedding_service import EmbeddingService

# Import ingestion functions from original modules
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from issue_solver.ingest import (
    fetch_repo_docs,
    fetch_repo_code, 
    fetch_repo_issues,
    fetch_repo_pr_history,
    chunk_and_embed_and_store
)


class IngestionService:
    """Service for repository data ingestion."""
    
    def __init__(self, config: Config, repository_service: RepositoryService, state_manager: StateManager, embedding_service: EmbeddingService):
        """
        Initialize ingestion service.
        
        Args:
            config: Configuration instance
            repository_service: Repository service for GitHub operations
            state_manager: State manager for persistence
            embedding_service: Service for providing embedding models
        """
        self.config = config
        self.repository_service = repository_service
        self.state_manager = state_manager
        self.embedding_service = embedding_service
        
    
    async def start_repository_ingestion(self, repo_name: str) -> IngestionResult:
        """
        Start the repository ingestion process.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            Ingestion result with initialization status
        """
        try:
            logger.info(f"Starting repository ingestion for: {repo_name}")
            start_time = time.time()
            
            # Validate repository exists and is accessible
            await self.repository_service.validate_repository(repo_name)
            
            # Ensure ChromaDB directory exists
            self.config.ensure_chroma_dir()
            
            # Initialize embeddings to test connection
            self.embedding_service.get_embeddings()
            
            # Create repository status in state manager
            self.state_manager.create_repository_status(repo_name)
            
            duration = time.time() - start_time
            logger.info(f"Repository ingestion initialized for {repo_name} in {duration:.2f}s")
            
            return IngestionResult(
                success=True,
                repo_name=repo_name,
                duration_seconds=duration,
                metadata={
                    "message": "Repository ingestion initialized successfully",
                    "next_step": "ingest_documentation",
                    "chroma_dir": str(self.config.chroma_persist_dir)
                }
            )
            
        except Exception as e:
            # Set error in state
            self.state_manager.set_repository_error(repo_name, str(e))
            
            logger.error(f"Failed to start ingestion for {repo_name}: {e}")
            return IngestionResult(
                success=False,
                repo_name=repo_name,
                error_message=str(e)
            )
    
    async def ingest_documentation(self, repo_name: str) -> IngestionResult:
        """
        Ingest documentation from repository (Step 1).
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            Ingestion result for documentation step
        """
        return await self._ingest_step(
            repo_name=repo_name,
            step=IngestionStep.DOCS,
            collection_type="documentation",
            fetch_function=lambda repo: fetch_repo_docs(repo),
            description="documentation files"
        )
    
    async def ingest_code(self, repo_name: str) -> IngestionResult:
        """
        Ingest source code from repository (Step 2).
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            Ingestion result for code step
        """
        return await self._ingest_step(
            repo_name=repo_name,
            step=IngestionStep.CODE,
            collection_type="code",
            fetch_function=lambda repo: fetch_repo_code(repo),
            description="source code files"
        )
    
    async def ingest_issues(self, repo_name: str, max_issues: Optional[int] = None) -> IngestionResult:
        """
        Ingest issues history from repository (Step 3).
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            max_issues: Maximum number of issues to process
            
        Returns:
            Ingestion result for issues step
        """
        max_issues = max_issues or self.config.max_issues
        
        return await self._ingest_step(
            repo_name=repo_name,
            step=IngestionStep.ISSUES,
            collection_type="issues",
            fetch_function=lambda repo: fetch_repo_issues(repo, max_issues),
            description=f"up to {max_issues} issues"
        )
    
    async def ingest_prs(self, repo_name: str, max_prs: Optional[int] = None) -> IngestionResult:
        """
        Ingest PR history from repository (Step 4).
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            max_prs: Maximum number of PRs to process
            
        Returns:
            Ingestion result for PRs step
        """
        max_prs = max_prs or self.config.max_prs
        
        result = await self._ingest_step(
            repo_name=repo_name,
            step=IngestionStep.PRS,
            collection_type="prs",
            fetch_function=lambda repo: fetch_repo_pr_history(repo, max_prs),
            description=f"up to {max_prs} pull requests"
        )
        
        # Mark overall ingestion as complete if this step succeeded
        if result.success:
            self.state_manager.complete_repository_ingestion(repo_name)
            logger.info(f"Completed full ingestion for {repo_name}")
        
        return result
    
    async def _ingest_step(
        self,
        repo_name: str,
        step: IngestionStep,
        collection_type: str,
        fetch_function,
        description: str
    ) -> IngestionResult:
        """
        Generic step ingestion handler.
        
        Args:
            repo_name: Repository name
            step: Ingestion step
            collection_type: Collection type for naming
            fetch_function: Function to fetch data
            description: Description for logging
            
        Returns:
            Ingestion result
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting {step.value} ingestion for {repo_name}: {description}")
            
            # Check if repository is initialized
            repo_status = self.state_manager.get_repository_status(repo_name)
            if not repo_status:
                raise IngestionError(
                    f"Repository {repo_name} not initialized",
                    repository=repo_name,
                    step=step.value
                )
            
            # Update step status to in progress
            self.state_manager.update_repository_step(
                repo_name, step, IngestionStatus.IN_PROGRESS,
                started_at=datetime.now()
            )
            
            # Get repository object
            repo = await self.repository_service.get_repository(repo_name)
            
            # Get embeddings client from our EmbeddingService
            embeddings = self.embedding_service.get_embeddings()
            
            # Fetch data
            logger.info(f"Fetching {description}...")
            
            if step == IngestionStep.ISSUES:
                # Issues require different parameter passing
                data = await asyncio.to_thread(fetch_function, repo)
            elif step == IngestionStep.PRS:
                # PRs require async fetching with timeout prevention
                data = await self._fetch_prs_with_timeout_prevention(repo, fetch_function)
            else:
                # Docs and code use repo.full_name
                data = await fetch_function(repo.full_name)
            
            documents_stored = 0
            collection_name = self.config.get_collection_name(repo_name, collection_type)
            
            if data:
                # Detect embedding provider for accurate time estimates
                is_fastembed = "FastEmbed" in str(type(embeddings)) or "fastembed" in str(type(embeddings)).lower()
                
                if is_fastembed:
                    # FastEmbed: Much faster, ~2-5 seconds per batch of 50 docs
                    estimated_batches = (len(data) + 49) // 50
                    estimated_time_seconds = estimated_batches * 4  # ~4s per batch
                    logger.info(f"Found {len(data)} items, embedding with FastEmbed (offline)...")
                    logger.info(f"⚡ FASTEMBED MODE: Estimated time ~{estimated_time_seconds}s ({estimated_batches} batches × ~4s each)")
                    logger.info(f"💡 Offline processing - no API quotas needed!")
                else:
                    # Gemini API: Slow due to rate limits
                    estimated_chunks = len(data)
                    estimated_time_minutes = (estimated_chunks * 50) // 60
                    logger.info(f"Found {len(data)} items, embedding with Gemini API...")
                    logger.info(f"⏰ GEMINI MODE: Estimated time ~{estimated_time_minutes} minutes ({estimated_chunks} chunks × ~50s each)")
                    logger.info(f"💡 Processing will be slow due to API quotas. Please be patient...")
                
                documents_stored = await chunk_and_embed_and_store(
                    data, embeddings, collection_type, repo_name
                )
                logger.info(f"Stored {documents_stored} document chunks")
            else:
                logger.info(f"No {description} found to process")
            
            # Update step status to completed
            completion_time = datetime.now()
            duration = time.time() - start_time
            
            self.state_manager.update_repository_step(
                repo_name, step, IngestionStatus.COMPLETED,
                documents_stored=documents_stored,
                collection_name=collection_name,
                completed_at=completion_time,
                duration_seconds=duration
            )
            
            logger.info(f"Completed {step.value} ingestion for {repo_name}: {documents_stored} documents in {duration:.2f}s")
            
            return IngestionResult(
                success=True,
                repo_name=repo_name,
                step=step,
                documents_stored=documents_stored,
                collection_name=collection_name,
                duration_seconds=duration,
                metadata={
                    "description": description,
                    "data_items_found": len(data) if data else 0
                }
            )
            
        except Exception as e:
            # Update step status to error
            error_msg = str(e)
            duration = time.time() - start_time
            
            # Provide specific guidance for quota exhaustion
            user_friendly_error = error_msg
            if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                user_friendly_error = (
                    f"Gemini API quota exhausted during {step.value} ingestion. "
                    f"Please wait 15+ minutes for quota reset, then retry this step. "
                    f"Consider upgrading to Gemini Pro API for higher quotas. "
                    f"Original error: {error_msg}"
                )
            
            self.state_manager.update_repository_step(
                repo_name, step, IngestionStatus.ERROR,
                error_message=user_friendly_error,
                completed_at=datetime.now(),
                duration_seconds=duration
            )
            
            logger.error(f"Failed {step.value} ingestion for {repo_name}: {user_friendly_error}")
            
            return IngestionResult(
                success=False,
                repo_name=repo_name,
                step=step,
                error_message=user_friendly_error,
                duration_seconds=duration
            )
    
    async def _fetch_prs_with_timeout_prevention(self, repo, fetch_function):
        """
        Fetch PRs with periodic yielding to prevent MCP timeout.
        
        This wrapper runs PR fetching in a separate thread but periodically
        checks if we should yield control to keep the MCP connection alive.
        """
        import threading
        import queue
        
        # Create a queue for communication between threads
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        # Flag to track completion
        completed = False
        
        def fetch_in_thread():
            """Run the synchronous fetch_function in a background thread."""
            try:
                result = fetch_function(repo)
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)
        
        # Start fetching in background thread
        thread = threading.Thread(target=fetch_in_thread, daemon=True)
        thread.start()
        logger.info("🔄 PR fetching started in background thread with periodic yielding...")
        
        # Periodically yield control while waiting for completion
        yield_interval = 5.0  # Yield every 5 seconds
        total_wait = 0
        max_wait = 240.0  # 4 minutes max (just under MCP timeout)
        
        while thread.is_alive() and total_wait < max_wait:
            await asyncio.sleep(yield_interval)
            total_wait += yield_interval
            logger.debug(f"⏱️ PR fetching in progress... ({total_wait:.0f}s elapsed)")
        
        # Check if thread finished
        if thread.is_alive():
            logger.error(f"❌ PR fetching exceeded {max_wait}s limit - stopping to prevent MCP timeout")
            # Note: We can't forcefully stop the thread, but we can return what we have
            # The thread will continue but we won't wait for it
            raise IngestionError(
                f"PR fetching exceeded time limit ({max_wait}s). "
                f"This repository has too many PRs. Try reducing MAX_PRS or use a different approach.",
                step="prs"
            )
        
        # Check for exceptions
        if not exception_queue.empty():
            raise exception_queue.get()
        
        # Get result
        if not result_queue.empty():
            result = result_queue.get()
            logger.info(f"✅ PR fetching completed successfully in {total_wait:.1f}s")
            return result
        else:
            raise IngestionError("PR fetching completed but no result was returned", step="prs")
    
    async def get_ingestion_progress(self, repo_name: str) -> Dict[str, Any]:
        """
        Get detailed ingestion progress for a repository.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            Dictionary with detailed progress information
        """
        repo_status = self.state_manager.get_repository_status(repo_name)
        if not repo_status:
            return {
                "error": f"Repository {repo_name} not found",
                "initialized": False
            }
        
        return {
            "initialized": True,
            "repo_name": repo_name,
            "overall_status": repo_status.overall_status.value,
            "completion_percentage": repo_status.get_completion_percentage(),
            "next_step": repo_status.get_next_step().value if repo_status.get_next_step() else None,
            "total_documents": repo_status.total_documents,
            "steps": {
                step.value: {
                    "status": result.status.value,
                    "documents_stored": result.documents_stored,
                    "collection_name": result.collection_name,
                    "error_message": result.error_message,
                    "duration_seconds": result.duration_seconds,
                    "started_at": result.started_at.isoformat() if result.started_at else None,
                    "completed_at": result.completed_at.isoformat() if result.completed_at else None
                }
                for step, result in repo_status.steps.items()
            },
            "collections": repo_status.collections,
            "created_at": repo_status.created_at.isoformat() if repo_status.created_at else None,
            "updated_at": repo_status.updated_at.isoformat() if repo_status.updated_at else None,
            "error_message": repo_status.error_message
        }
    
    async def retry_failed_step(self, repo_name: str, step: IngestionStep) -> IngestionResult:
        """
        Retry a failed ingestion step.
        
        Args:
            repo_name: Repository name in 'owner/repo' format  
            step: Step to retry
            
        Returns:
            Ingestion result for the retried step
        """
        logger.info(f"Retrying {step.value} ingestion for {repo_name}")
        
        if step == IngestionStep.DOCS:
            return await self.ingest_documentation(repo_name)
        elif step == IngestionStep.CODE:
            return await self.ingest_code(repo_name)
        elif step == IngestionStep.ISSUES:
            return await self.ingest_issues(repo_name)
        elif step == IngestionStep.PRS:
            return await self.ingest_prs(repo_name)
        else:
            return IngestionResult(
                success=False,
                repo_name=repo_name,
                step=step,
                error_message=f"Unknown step: {step.value}"
            )
