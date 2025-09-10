"""
Data models for the GitHub Issue Solver MCP Server.

Defines structured data models for repository status, ingestion results,
analysis results, and patch generation using dataclasses for type safety.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class IngestionStatus(Enum):
    """Status enumeration for repository ingestion."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class IngestionStep(Enum):
    """Enumeration of ingestion steps."""
    DOCS = "documentation"
    CODE = "code"
    ISSUES = "issues"
    PRS = "prs"


@dataclass
class StepResult:
    """Result of an individual ingestion step."""
    step: IngestionStep
    status: IngestionStatus
    documents_stored: int = 0
    collection_name: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step": self.step.value,
            "status": self.status.value,
            "documents_stored": self.documents_stored,
            "collection_name": self.collection_name,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class RepositoryStatus:
    """Comprehensive status tracking for repository ingestion."""
    repo_name: str
    overall_status: IngestionStatus
    steps: Dict[IngestionStep, StepResult] = field(default_factory=dict)
    total_documents: int = 0
    chroma_dir: Optional[str] = None
    collections: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        """Initialize step results if not provided."""
        if not self.steps:
            for step in IngestionStep:
                self.steps[step] = StepResult(step=step, status=IngestionStatus.PENDING)
    
    def get_completion_percentage(self) -> float:
        """Calculate completion percentage based on completed steps."""
        completed_steps = sum(
            1 for step_result in self.steps.values()
            if step_result.status == IngestionStatus.COMPLETED
        )
        return (completed_steps / len(IngestionStep)) * 100
    
    def get_next_step(self) -> Optional[IngestionStep]:
        """Get the next pending step in the ingestion process."""
        step_order = [IngestionStep.DOCS, IngestionStep.CODE, IngestionStep.ISSUES, IngestionStep.PRS]
        
        for step in step_order:
            if self.steps[step].status == IngestionStatus.PENDING:
                return step
        return None
    
    def update_step(self, step: IngestionStep, status: IngestionStatus, **kwargs) -> None:
        """Update a specific step's status and metadata."""
        if step not in self.steps:
            self.steps[step] = StepResult(step=step, status=status)
        else:
            self.steps[step].status = status
        
        # Update step attributes
        for key, value in kwargs.items():
            if hasattr(self.steps[step], key):
                setattr(self.steps[step], key, value)
        
        # Update overall status and timestamp
        self.updated_at = datetime.now()
        self._update_overall_status()
    
    def _update_overall_status(self) -> None:
        """Update overall status based on step statuses."""
        statuses = [step.status for step in self.steps.values()]
        
        if any(status == IngestionStatus.ERROR for status in statuses):
            self.overall_status = IngestionStatus.ERROR
        elif any(status == IngestionStatus.IN_PROGRESS for status in statuses):
            self.overall_status = IngestionStatus.IN_PROGRESS
        elif all(status == IngestionStatus.COMPLETED for status in statuses):
            self.overall_status = IngestionStatus.COMPLETED
        elif all(status == IngestionStatus.PENDING for status in statuses):
            self.overall_status = IngestionStatus.PENDING
        else:
            self.overall_status = IngestionStatus.IN_PROGRESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "repo_name": self.repo_name,
            "overall_status": self.overall_status.value,
            "steps": {step.value: result.to_dict() for step, result in self.steps.items()},
            "total_documents": self.total_documents,
            "chroma_dir": self.chroma_dir,
            "collections": self.collections,
            "completion_percentage": self.get_completion_percentage(),
            "next_step": self.get_next_step().value if self.get_next_step() else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "error_message": self.error_message,
        }


@dataclass
class IngestionResult:
    """Result of a repository ingestion operation."""
    success: bool
    repo_name: str
    step: Optional[IngestionStep] = None
    documents_stored: int = 0
    collection_name: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "repo_name": self.repo_name,
            "step": self.step.value if self.step else None,
            "documents_stored": self.documents_stored,
            "collection_name": self.collection_name,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


@dataclass
class IssueInfo:
    """Information about a GitHub issue."""
    number: int
    title: str
    body: str
    url: str
    state: str
    repository: str
    created_at: datetime
    updated_at: datetime
    labels: List[str] = field(default_factory=list)
    assignees: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "state": self.state,
            "repository": self.repository,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "labels": self.labels,
            "assignees": self.assignees,
        }


@dataclass
class AnalysisResult:
    """Result of GitHub issue analysis."""
    success: bool
    issue_info: Optional[IssueInfo] = None
    analysis: Dict[str, Any] = field(default_factory=dict)
    detailed_report: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    analyzed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "issue_info": self.issue_info.to_dict() if self.issue_info else None,
            "analysis": self.analysis,
            "detailed_report": self.detailed_report,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
        }


@dataclass
class FilePatch:
    """Represents a patch for a specific file."""
    file_path: str
    patch_content: str
    operation: str = "modify"  # modify, create, delete
    original_content: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file_path": self.file_path,
            "patch_content": self.patch_content,
            "operation": self.operation,
            "original_content": self.original_content,
        }


@dataclass
class PatchResult:
    """Result of code patch generation."""
    success: bool
    repo_name: str
    files_to_update: List[FilePatch] = field(default_factory=list)
    summary_of_changes: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "repo_name": self.repo_name,
            "files_to_update": [patch.to_dict() for patch in self.files_to_update],
            "summary_of_changes": self.summary_of_changes,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }


@dataclass
class HealthStatus:
    """Health status of the MCP server."""
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime
    checks: Dict[str, bool] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "checks": self.checks,
            "details": self.details,
        }
