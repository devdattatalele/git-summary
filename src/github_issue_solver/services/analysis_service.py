"""
Analysis service for the GitHub Issue Solver MCP Server.

Handles GitHub issue analysis using RAG (Retrieval-Augmented Generation)
with repository knowledge base for comprehensive issue understanding.
"""

import asyncio
from loguru import logger
import time
from typing import Dict, Any, Optional
from datetime import datetime

from ..config import Config
from ..models import AnalysisResult, IssueInfo
from ..exceptions import AnalysisError
from ..services.repository_service import RepositoryService
from ..services.state_manager import StateManager

# Import analysis functions from original modules
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import additional required modules
import asyncio

from issue_solver.analyze import (
    create_langchain_agent,
    parse_agent_output,
    append_to_google_doc
)



class AnalysisService:
    """Service for GitHub issue analysis using AI and RAG."""
    
    def __init__(self, config: Config, repository_service: RepositoryService, state_manager: StateManager):
        """
        Initialize analysis service.
        
        Args:
            config: Configuration instance
            repository_service: Repository service for GitHub operations
            state_manager: State manager for checking ingestion status
        """
        self.config = config
        self.repository_service = repository_service
        self.state_manager = state_manager
        
    async def analyze_github_issue(self, issue_url: str) -> AnalysisResult:
        """
        Analyze a GitHub issue using AI and repository knowledge base.
        
        Args:
            issue_url: Full GitHub issue URL
            
        Returns:
            Analysis result with comprehensive issue analysis
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting issue analysis: {issue_url}")
            
            # Parse GitHub URL
            try:
                owner, repo, issue_number = self.repository_service.parse_github_url(issue_url)
                repo_full_name = f"{owner}/{repo}"
                logger.info(f"Parsed URL - Owner: {owner}, Repo: {repo}, Issue: {issue_number}")
            except Exception as e:
                raise AnalysisError(
                    f"Failed to parse GitHub URL: {str(e)}",
                    issue_url=issue_url,
                    analysis_stage="url_parsing",
                    cause=e
                )
            
            # Check if repository is ingested
            repo_status = self.state_manager.get_repository_status(repo_full_name)
            if not repo_status:
                raise AnalysisError(
                    f"Repository '{repo_full_name}' has not been ingested yet",
                    issue_url=issue_url,
                    repository=repo_full_name,
                    analysis_stage="repository_check",
                    details={
                        "suggestion": f"Please run the 4-step ingestion process first",
                        "next_steps": [
                            f"start_repository_ingestion('{repo_full_name}')",
                            f"ingest_repository_docs('{repo_full_name}')",
                            f"ingest_repository_code('{repo_full_name}')",
                            f"ingest_repository_issues('{repo_full_name}')",
                            f"ingest_repository_prs('{repo_full_name}')"
                        ]
                    }
                )
            
            if repo_status.overall_status.value != "completed":
                logger.warning(f"Repository {repo_full_name} ingestion is not complete: {repo_status.overall_status.value}")
                # Continue with analysis even if ingestion is incomplete
            
            # Get GitHub issue information
            try:
                issue_info = await self.repository_service.get_github_issue(owner, repo, issue_number)
                logger.info(f"Retrieved issue: {issue_info.title}")
            except Exception as e:
                raise AnalysisError(
                    f"Failed to fetch GitHub issue: {str(e)}",
                    issue_url=issue_url,
                    repository=repo_full_name,
                    analysis_stage="issue_retrieval",
                    cause=e
                )
            
            # Create a mock GitHub issue object for the legacy function
            # This is needed because the original function expects a GitHub API object
            mock_issue = type('MockIssue', (), {
                'number': issue_info.number,
                'title': issue_info.title,
                'body': issue_info.body,
                'html_url': issue_info.url,
                'state': issue_info.state,
                'repository': type('MockRepo', (), {'full_name': issue_info.repository})()
            })()
            
            # Perform AI analysis using LangChain agent
            try:
                logger.info("Creating LangChain agent for analysis...")
                agent_raw_output = await asyncio.to_thread(create_langchain_agent, mock_issue)
                logger.info("Agent analysis completed")
            except Exception as e:
                raise AnalysisError(
                    f"AI analysis failed: {str(e)}",
                    issue_url=issue_url,
                    repository=repo_full_name,
                    analysis_stage="ai_analysis",
                    cause=e
                )
            
            # Parse agent output
            try:
                logger.info(f"Parsing agent output (type: {type(agent_raw_output).__name__})...")
                analysis = parse_agent_output(agent_raw_output)
                logger.info("Analysis output parsed successfully")
            except Exception as e:
                logger.error(f"Failed to parse agent output: {type(e).__name__}: {e}")
                raise AnalysisError(
                    f"Failed to parse analysis output: {str(e)}",
                    issue_url=issue_url,
                    repository=repo_full_name,
                    analysis_stage="output_parsing",
                    details={
                        "raw_output": str(agent_raw_output)[:500] + "..." if len(str(agent_raw_output)) > 500 else str(agent_raw_output),
                        "output_type": type(agent_raw_output).__name__
                    },
                    cause=e
                )
            
            # Create detailed report
            try:
                timestamp = datetime.now().strftime('%d %B, %Y at %H:%M')
                logger.info(f"Creating detailed report with analysis keys: {list(analysis.keys())}")
                detailed_report = self._create_detailed_report(issue_info, analysis, timestamp)
                logger.info("Detailed report created successfully")
            except Exception as e:
                logger.error(f"Failed to create detailed report: {type(e).__name__}: {e}")
                raise
            
            # Append to Google Doc if configured
            if self.config.google_docs_id:
                try:
                    await asyncio.to_thread(append_to_google_doc, detailed_report)
                    logger.info("Analysis appended to Google Doc")
                    google_docs_saved = True
                except Exception as e:
                    logger.warning(f"Failed to append to Google Doc: {e}")
                    google_docs_saved = False
            else:
                google_docs_saved = False
            
            duration = time.time() - start_time
            logger.info(f"Issue analysis completed in {duration:.2f}s")
            
            return AnalysisResult(
                success=True,
                issue_info=issue_info,
                analysis=analysis,
                detailed_report=detailed_report,
                analyzed_at=datetime.now(),
                metadata={
                    "duration_seconds": duration,
                    "google_docs_saved": google_docs_saved,
                    "ingestion_status": repo_status.overall_status.value,
                    "total_documents": repo_status.total_documents,
                    "collections_used": repo_status.collections
                }
            )
            
        except AnalysisError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Unexpected error during analysis: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")  # This will log the full stack trace

            return AnalysisResult(
                success=False,
                error_message=f"Unexpected error during analysis: {type(e).__name__}: {str(e)}",
                analyzed_at=datetime.now(),
                metadata={
                    "duration_seconds": duration,
                    "error_type": type(e).__name__
                }
            )
    
    def _create_detailed_report(self, issue_info: IssueInfo, analysis: Dict[str, Any], timestamp: str) -> str:
        """
        Create a detailed analysis report.
        
        Args:
            issue_info: GitHub issue information
            analysis: AI analysis results
            timestamp: Analysis timestamp
            
        Returns:
            Formatted detailed report
        """
        similar_issues = analysis.get('similar_issues', [])
        similar_issues_str = ', '.join(similar_issues) if similar_issues else 'None Found'
        
        report = f"""---
### Issue #{issue_info.number}: {issue_info.title}
- Repository: {issue_info.repository}
- Link: {issue_info.url}
- Analyzed On: {timestamp}
- Status: {issue_info.state}

| Category            | AI Analysis                                                  |
| ------------------- | ------------------------------------------------------------ |
| Summary         | {analysis.get('summary', 'N/A')}                             |
| Complexity      | {analysis.get('complexity', 'N/A')} / 5                      |
| Similar Issues  | {similar_issues_str} |

**Proposed Solution:**
{analysis.get('proposed_solution', 'N/A')}

---

"""
        return report
    
    async def get_repository_structure_summary(self, repo_name: str) -> Dict[str, Any]:
        """
        Get a summary of repository structure from ingested data.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            
        Returns:
            Repository structure summary
        """
        try:
            repo_status = self.state_manager.get_repository_status(repo_name)
            if not repo_status:
                return {
                    "error": f"Repository {repo_name} not ingested",
                    "available": False
                }
            
            # Get repository info
            repo_info = await self.repository_service.get_repository_info(repo_name)
            
            # Extract structure from collections if available
            structure_info = {
                "available": True,
                "repo_info": repo_info,
                "ingestion_status": repo_status.overall_status.value,
                "total_documents": repo_status.total_documents,
                "collections": repo_status.collections,
                "steps_completed": {
                    step.value: result.status.value == "completed"
                    for step, result in repo_status.steps.items()
                },
                "last_updated": repo_status.updated_at.isoformat() if repo_status.updated_at else None
            }
            
            return structure_info
            
        except Exception as e:
            logger.error(f"Failed to get repository structure for {repo_name}: {e}")
            return {
                "error": str(e),
                "available": False
            }
    
    async def validate_analysis_prerequisites(self, issue_url: str) -> Dict[str, Any]:
        """
        Validate prerequisites for issue analysis.
        
        Args:
            issue_url: GitHub issue URL
            
        Returns:
            Validation results
        """
        try:
            # Parse URL
            owner, repo, issue_number = self.repository_service.parse_github_url(issue_url)
            repo_full_name = f"{owner}/{repo}"
            
            # Check repository status
            repo_status = self.state_manager.get_repository_status(repo_full_name)
            
            # Check API access
            api_limits = await self.repository_service.check_api_limits()
            
            validation = {
                "url_valid": True,
                "repository": repo_full_name,
                "issue_number": issue_number,
                "repository_ingested": repo_status is not None,
                "ingestion_complete": repo_status.overall_status.value == "completed" if repo_status else False,
                "total_documents": repo_status.total_documents if repo_status else 0,
                "api_limits": api_limits,
                "ready_for_analysis": repo_status is not None and repo_status.total_documents > 0
            }
            
            if repo_status:
                validation["ingestion_status"] = repo_status.overall_status.value
                validation["collections"] = repo_status.collections
                validation["step_status"] = {
                    step.value: result.status.value
                    for step, result in repo_status.steps.items()
                }
            
            return validation
            
        except Exception as e:
            return {
                "url_valid": False,
                "error": str(e),
                "ready_for_analysis": False
            }
