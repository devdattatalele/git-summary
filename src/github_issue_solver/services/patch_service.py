"""
Patch service for the GitHub Issue Solver MCP Server.

Handles code patch generation for issue resolution using RAG and AI
with proper error handling and result validation.
"""

import asyncio
from loguru import logger
import time
from typing import Dict, Any, List
from datetime import datetime

from ..config import Config
from ..models import PatchResult, FilePatch
from ..exceptions import PatchGenerationError
from ..services.state_manager import StateManager

# Import patch generation functions from original modules
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from issue_solver.patch import generate_patch_for_issue



class PatchService:
    """Service for code patch generation using AI and RAG."""
    
    def __init__(self, config: Config, state_manager: StateManager):
        """
        Initialize patch service.
        
        Args:
            config: Configuration instance
            state_manager: State manager for checking ingestion status
        """
        self.config = config
        self.state_manager = state_manager
        
    async def generate_code_patch(self, issue_body: str, repo_full_name: str) -> PatchResult:
        """
        Generate code patches to resolve a GitHub issue.
        
        Args:
            issue_body: The issue description/body text
            repo_full_name: Repository name in 'owner/repo' format
            
        Returns:
            Patch result with generated patches or guidance
        """
        start_time = time.time()
        
        try:
            logger.info(f"Generating code patch for repo: {repo_full_name}")
            
            # Check if repository is ingested
            repo_status = self.state_manager.get_repository_status(repo_full_name)
            if not repo_status:
                raise PatchGenerationError(
                    f"Repository '{repo_full_name}' has not been ingested yet",
                    repository=repo_full_name,
                    generation_stage="repository_check",
                    details={
                        "suggestion": "Please run the 4-step ingestion process first",
                        "next_steps": [
                            f"start_repository_ingestion('{repo_full_name}')",
                            f"ingest_repository_docs('{repo_full_name}')",
                            f"ingest_repository_code('{repo_full_name}')",
                            f"ingest_repository_issues('{repo_full_name}')",
                            f"ingest_repository_prs('{repo_full_name}')"
                        ]
                    }
                )
            
            if repo_status.total_documents == 0:
                raise PatchGenerationError(
                    f"Repository '{repo_full_name}' has no ingested data for patch generation",
                    repository=repo_full_name,
                    generation_stage="data_validation",
                    details={
                        "ingestion_status": repo_status.overall_status.value,
                        "suggestion": "Complete repository ingestion to enable patch generation"
                    }
                )
            
            # Generate patches using existing function
            try:
                logger.info(f"Generating patches using repository knowledge base for {repo_full_name}")
                patch_data = await asyncio.to_thread(generate_patch_for_issue, issue_body, repo_full_name)
                logger.info("Patch generation completed")
            except Exception as e:
                raise PatchGenerationError(
                    f"Patch generation failed: {str(e)}",
                    repository=repo_full_name,
                    issue_description=issue_body,
                    generation_stage="patch_generation",
                    cause=e
                )
            
            # Validate and process patch data
            if not patch_data or not isinstance(patch_data, dict):
                logger.warning("Patch generation returned empty or invalid data")
                return self._create_fallback_result(repo_full_name, issue_body, start_time)
            
            # Process files to update
            files_to_update = []
            raw_files = patch_data.get("filesToUpdate", [])
            
            if raw_files:
                for file_data in raw_files:
                    if isinstance(file_data, dict):
                        file_patch = FilePatch(
                            file_path=file_data.get("filePath", ""),
                            patch_content=file_data.get("patch", ""),
                            operation=file_data.get("operation", "modify"),
                            original_content=file_data.get("originalContent")
                        )
                        files_to_update.append(file_patch)
                    else:
                        logger.warning(f"Invalid file patch data format: {file_data}")
            
            # Get summary of changes
            summary_of_changes = patch_data.get("summaryOfChanges", "")
            
            # If no specific patches but we have analysis, create guidance
            if not files_to_update and summary_of_changes:
                logger.info("No specific file patches generated - providing general guidance")
                summary_of_changes = f"Analysis completed for repository {repo_full_name}. " + summary_of_changes
            
            duration = time.time() - start_time
            logger.info(f"Patch generation completed in {duration:.2f}s - {len(files_to_update)} files to update")
            
            return PatchResult(
                success=True,
                repo_name=repo_full_name,
                files_to_update=files_to_update,
                summary_of_changes=summary_of_changes,
                generated_at=datetime.now(),
                metadata={
                    "duration_seconds": duration,
                    "files_modified": len(files_to_update),
                    "ingestion_status": repo_status.overall_status.value,
                    "total_documents_used": repo_status.total_documents,
                    "collections_available": repo_status.collections,
                    "has_specific_patches": len(files_to_update) > 0,
                    "generation_method": "rag_ai_analysis"
                }
            )
            
        except PatchGenerationError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Unexpected error during patch generation: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")  # This will log the full stack trace

            return PatchResult(
                success=False,
                repo_name=repo_full_name,
                error_message=f"Unexpected error during patch generation: {type(e).__name__}: {str(e)}",
                generated_at=datetime.now(),
                metadata={
                    "duration_seconds": duration,
                    "error_type": type(e).__name__
                }
            )
    
    def _create_fallback_result(self, repo_full_name: str, issue_body: str, start_time: float) -> PatchResult:
        """
        Create fallback result when no specific patches are generated.
        
        Args:
            repo_full_name: Repository name
            issue_body: Issue description
            start_time: Generation start time
            
        Returns:
            Fallback patch result with general guidance
        """
        duration = time.time() - start_time
        
        fallback_summary = f"""Analysis completed for repository {repo_full_name}. 

The issue requires manual investigation and implementation. Based on the repository structure and issue description, please:

1. Review the repository codebase and identify relevant files
2. Understand the current implementation patterns
3. Implement appropriate changes based on the issue description
4. Test the changes thoroughly before creating a pull request

Issue Description Summary:
{issue_body[:200]}{"..." if len(issue_body) > 200 else ""}

This type of issue may require:
- Code refactoring or restructuring
- New feature implementation
- Bug fixes in multiple related files
- Configuration or documentation updates

Please use the repository structure information and ingested code patterns to guide your implementation."""
        
        return PatchResult(
            success=True,
            repo_name=repo_full_name,
            files_to_update=[],  # Empty list for manual implementation
            summary_of_changes=fallback_summary,
            generated_at=datetime.now(),
            metadata={
                "duration_seconds": duration,
                "files_modified": 0,
                "has_specific_patches": False,
                "generation_method": "fallback_guidance",
                "requires_manual_implementation": True
            }
        )
    
    async def validate_patch_prerequisites(self, repo_full_name: str) -> Dict[str, Any]:
        """
        Validate prerequisites for patch generation.
        
        Args:
            repo_full_name: Repository name in 'owner/repo' format
            
        Returns:
            Validation results
        """
        try:
            repo_status = self.state_manager.get_repository_status(repo_full_name)
            
            validation = {
                "repository_ingested": repo_status is not None,
                "ready_for_patch_generation": False,
                "total_documents": 0,
                "collections_available": [],
                "ingestion_complete": False
            }
            
            if repo_status:
                validation.update({
                    "total_documents": repo_status.total_documents,
                    "collections_available": repo_status.collections,
                    "ingestion_status": repo_status.overall_status.value,
                    "ingestion_complete": repo_status.overall_status.value == "completed",
                    "ready_for_patch_generation": repo_status.total_documents > 0,
                    "step_status": {
                        step.value: result.status.value
                        for step, result in repo_status.steps.items()
                    }
                })
                
                # Additional readiness checks
                has_code = any("code" in collection for collection in repo_status.collections)
                has_docs = any("docs" in collection or "documentation" in collection for collection in repo_status.collections)
                
                validation.update({
                    "has_code_data": has_code,
                    "has_documentation": has_docs,
                    "patch_generation_recommended": has_code and repo_status.total_documents >= 10
                })
            
            return validation
            
        except Exception as e:
            logger.error(f"Error validating patch prerequisites for {repo_full_name}: {e}")
            return {
                "repository_ingested": False,
                "ready_for_patch_generation": False,
                "error": str(e)
            }
    
    async def get_implementation_guidance(self, repo_full_name: str, issue_description: str) -> Dict[str, Any]:
        """
        Get implementation guidance for manual issue resolution.
        
        Args:
            repo_full_name: Repository name in 'owner/repo' format
            issue_description: Description of the issue
            
        Returns:
            Implementation guidance and suggestions
        """
        try:
            repo_status = self.state_manager.get_repository_status(repo_full_name)
            if not repo_status:
                return {
                    "error": f"Repository {repo_full_name} not ingested",
                    "guidance": "Please ingest the repository first to get implementation guidance"
                }
            
            # Analyze issue type for specific guidance
            issue_lower = issue_description.lower()
            guidance_type = self._classify_issue_type(issue_lower)
            
            guidance = {
                "repository": repo_full_name,
                "issue_type": guidance_type,
                "general_approach": self._get_general_approach(guidance_type),
                "specific_suggestions": self._get_specific_suggestions(guidance_type),
                "repository_context": {
                    "total_documents": repo_status.total_documents,
                    "collections": repo_status.collections,
                    "ingestion_status": repo_status.overall_status.value
                },
                "next_steps": [
                    "Review repository structure and existing code patterns",
                    "Identify files that need to be modified",
                    "Implement changes following existing conventions",
                    "Test changes thoroughly",
                    "Create pull request with clear documentation"
                ]
            }
            
            return guidance
            
        except Exception as e:
            logger.error(f"Error generating implementation guidance: {e}")
            return {
                "error": str(e),
                "guidance": "Unable to generate specific guidance due to error"
            }
    
    def _classify_issue_type(self, issue_description: str) -> str:
        """Classify issue type based on description."""
        if any(word in issue_description for word in ["auth", "login", "authentication", "user", "session"]):
            return "authentication"
        elif any(word in issue_description for word in ["api", "endpoint", "request", "response", "http"]):
            return "api"
        elif any(word in issue_description for word in ["ui", "component", "layout", "design", "css", "style"]):
            return "ui_component"
        elif any(word in issue_description for word in ["bug", "error", "exception", "crash", "fail"]):
            return "bug_fix"
        elif any(word in issue_description for word in ["feature", "add", "new", "implement"]):
            return "feature"
        else:
            return "general"
    
    def _get_general_approach(self, issue_type: str) -> str:
        """Get general approach based on issue type."""
        approaches = {
            "authentication": "Focus on authentication middleware, user session management, and security components",
            "api": "Review API route definitions, request/response handlers, and data validation",
            "ui_component": "Examine component structure, styling, and user interaction patterns",
            "bug_fix": "Identify the root cause, trace through related code, and implement targeted fixes",
            "feature": "Design the feature integration, identify extension points, and maintain consistency",
            "general": "Analyze the codebase structure, understand existing patterns, and plan implementation"
        }
        return approaches.get(issue_type, approaches["general"])
    
    def _get_specific_suggestions(self, issue_type: str) -> List[str]:
        """Get specific suggestions based on issue type."""
        suggestions = {
            "authentication": [
                "Look for files containing 'auth', 'login', 'session' in their names",
                "Check middleware directory for authentication components",
                "Review user model/schema definitions",
                "Examine route protection mechanisms"
            ],
            "api": [
                "Locate API route definitions (usually in routes/ or api/ directories)",
                "Check request/response validation logic",
                "Review error handling middleware",
                "Examine API documentation for consistency"
            ],
            "ui_component": [
                "Find component files in components/ or src/ directories",
                "Check styling files (CSS, SCSS, styled-components)",
                "Review component prop definitions and interfaces",
                "Look for similar existing components as patterns"
            ],
            "bug_fix": [
                "Trace the error through stack traces or logs",
                "Identify the specific function or method causing issues",
                "Check for edge cases and input validation",
                "Review related test cases if available"
            ],
            "feature": [
                "Identify where similar features are implemented",
                "Check configuration files for feature toggles",
                "Plan database schema changes if needed",
                "Consider backwards compatibility"
            ],
            "general": [
                "Start with main entry points (index, main, app files)",
                "Review project structure and naming conventions",
                "Understand the data flow and architecture patterns",
                "Check for existing similar functionality"
            ]
        }
        return suggestions.get(issue_type, suggestions["general"])
