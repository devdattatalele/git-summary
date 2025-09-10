"""
Health service for the GitHub Issue Solver MCP Server.

Provides health monitoring, system status checking, and recovery capabilities
to ensure the MCP server operates reliably and can self-diagnose issues.
"""

import asyncio
import logging
import time
import psutil
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from ..config import Config
from ..models import HealthStatus
from ..services.state_manager import StateManager
from ..services.repository_service import RepositoryService
from ..exceptions import GitHubIssueSolverError

logger = logging.getLogger(__name__)


class HealthService:
    """Service for health monitoring and system diagnostics."""
    
    def __init__(self, config: Config, state_manager: StateManager, repository_service: RepositoryService):
        """
        Initialize health service.
        
        Args:
            config: Configuration instance
            state_manager: State manager for checking persistence health
            repository_service: Repository service for API health checks
        """
        self.config = config
        self.state_manager = state_manager
        self.repository_service = repository_service
        
        # Health monitoring state
        self._last_health_check = None
        self._health_history: List[HealthStatus] = []
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Performance tracking
        self._performance_metrics = {
            "requests_processed": 0,
            "average_response_time": 0.0,
            "errors_count": 0,
            "uptime_start": datetime.now()
        }
        
    async def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if not self._monitoring_active:
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(target=self._monitor_health, daemon=True)
            self._monitor_thread.start()
            logger.info("Health monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._monitoring_active = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        logger.info("Health monitoring stopped")
    
    def _monitor_health(self) -> None:
        """Background thread for periodic health checks."""
        while self._monitoring_active:
            try:
                # Run health check in background
                asyncio.run(self._periodic_health_check())
                time.sleep(self.config.health_check_interval)
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                time.sleep(60)  # Back off on error
    
    async def _periodic_health_check(self) -> None:
        """Perform periodic health check."""
        try:
            health_status = await self.get_health_status()
            
            # Store health history (keep last 24 hours)
            self._health_history.append(health_status)
            cutoff_time = datetime.now() - timedelta(hours=24)
            self._health_history = [
                h for h in self._health_history 
                if h.timestamp > cutoff_time
            ]
            
            # Log health issues
            if health_status.status != "healthy":
                logger.warning(f"Health check failed: {health_status.status}")
                for check, passed in health_status.checks.items():
                    if not passed:
                        logger.warning(f"Failed health check: {check}")
                        
        except Exception as e:
            logger.error(f"Periodic health check failed: {e}")
    
    async def get_health_status(self) -> HealthStatus:
        """
        Get comprehensive health status.
        
        Returns:
            Current health status with all checks
        """
        checks = {}
        details = {}
        
        try:
            # System resource checks
            system_health = await self._check_system_resources()
            checks.update(system_health["checks"])
            details["system"] = system_health["details"]
            
            # Configuration checks
            config_health = await self._check_configuration()
            checks.update(config_health["checks"])
            details["configuration"] = config_health["details"]
            
            # External API checks
            api_health = await self._check_external_apis()
            checks.update(api_health["checks"])
            details["apis"] = api_health["details"]
            
            # Storage checks
            storage_health = await self._check_storage()
            checks.update(storage_health["checks"])
            details["storage"] = storage_health["details"]
            
            # State management checks
            state_health = await self._check_state_management()
            checks.update(state_health["checks"])
            details["state"] = state_health["details"]
            
            # Determine overall health status
            failed_checks = [name for name, passed in checks.items() if not passed]
            critical_failures = [name for name in failed_checks if "critical" in name.lower()]
            
            if critical_failures:
                overall_status = "unhealthy"
            elif failed_checks:
                overall_status = "degraded"
            else:
                overall_status = "healthy"
            
            # Add performance metrics
            details["performance"] = self._get_performance_metrics()
            
            health_status = HealthStatus(
                status=overall_status,
                timestamp=datetime.now(),
                checks=checks,
                details=details
            )
            
            self._last_health_check = health_status
            return health_status
            
        except Exception as e:
            logger.error(f"Health status check failed: {e}")
            return HealthStatus(
                status="unhealthy",
                timestamp=datetime.now(),
                checks={"health_check_error": False},
                details={"error": str(e)}
            )
    
    async def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource availability."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_ok = cpu_percent < 90
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_ok = memory.percent < 90
            
            # Disk space (for ChromaDB)
            disk_usage = psutil.disk_usage(str(self.config.chroma_persist_dir.parent))
            disk_ok = (disk_usage.free / disk_usage.total) > 0.1  # At least 10% free
            
            return {
                "checks": {
                    "cpu_usage_ok": cpu_ok,
                    "memory_usage_ok": memory_ok,
                    "disk_space_ok": disk_ok
                },
                "details": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": memory.available / (1024**3),
                    "disk_free_gb": disk_usage.free / (1024**3),
                    "disk_total_gb": disk_usage.total / (1024**3)
                }
            }
            
        except Exception as e:
            logger.error(f"System resource check failed: {e}")
            return {
                "checks": {"system_resources_critical": False},
                "details": {"error": str(e)}
            }
    
    async def _check_configuration(self) -> Dict[str, Any]:
        """Check configuration validity."""
        try:
            # Environment variables
            config_status = self.config.get_status()
            api_access = config_status["api_access"]
            
            # ChromaDB directory
            chroma_dir_ok = self.config.chroma_persist_dir.exists() and self.config.chroma_persist_dir.is_dir()
            
            return {
                "checks": {
                    "google_api_configured": api_access.get("google_api", False),
                    "github_api_configured": api_access.get("github_api", False),
                    "chroma_directory_ok": chroma_dir_ok,
                    "configuration_valid": all(api_access.values()) and chroma_dir_ok
                },
                "details": {
                    "config_status": config_status,
                    "chroma_dir": str(self.config.chroma_persist_dir),
                    "chroma_dir_exists": chroma_dir_ok
                }
            }
            
        except Exception as e:
            logger.error(f"Configuration check failed: {e}")
            return {
                "checks": {"configuration_critical": False},
                "details": {"error": str(e)}
            }
    
    async def _check_external_apis(self) -> Dict[str, Any]:
        """Check external API connectivity."""
        try:
            # GitHub API
            github_ok = await self.repository_service.test_connection()
            
            # API rate limits
            api_limits = await self.repository_service.check_api_limits()
            github_rate_ok = api_limits.get("core", {}).get("remaining", 0) > 10
            
            # Google API (basic check)
            google_ok = True
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.config.google_api_key)
                google_ok = True
            except Exception as e:
                logger.warning(f"Google API check failed: {e}")
                google_ok = False
            
            return {
                "checks": {
                    "github_api_ok": github_ok,
                    "github_rate_limit_ok": github_rate_ok,
                    "google_api_ok": google_ok
                },
                "details": {
                    "github_connection": github_ok,
                    "github_api_limits": api_limits,
                    "google_api_configured": google_ok
                }
            }
            
        except Exception as e:
            logger.error(f"External API check failed: {e}")
            return {
                "checks": {"external_apis_critical": False},
                "details": {"error": str(e)}
            }
    
    async def _check_storage(self) -> Dict[str, Any]:
        """Check storage systems (ChromaDB)."""
        try:
            # ChromaDB accessibility
            chroma_ok = True
            collections_count = 0
            
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(self.config.chroma_persist_dir))
                collections = client.list_collections()
                collections_count = len(collections)
                chroma_ok = True
            except Exception as e:
                logger.warning(f"ChromaDB check failed: {e}")
                chroma_ok = False
            
            # State file accessibility
            state_file_ok = True
            try:
                state_file = self.config.chroma_persist_dir / "state.json"
                if state_file.exists():
                    # Try to read state file
                    with open(state_file, 'r') as f:
                        state_data = f.read()
                    state_file_ok = len(state_data) > 0
            except Exception as e:
                logger.warning(f"State file check failed: {e}")
                state_file_ok = False
            
            return {
                "checks": {
                    "chromadb_accessible": chroma_ok,
                    "state_file_ok": state_file_ok,
                    "storage_healthy": chroma_ok and state_file_ok
                },
                "details": {
                    "chromadb_collections": collections_count,
                    "chroma_path": str(self.config.chroma_persist_dir),
                    "state_file_exists": (self.config.chroma_persist_dir / "state.json").exists()
                }
            }
            
        except Exception as e:
            logger.error(f"Storage check failed: {e}")
            return {
                "checks": {"storage_critical": False},
                "details": {"error": str(e)}
            }
    
    async def _check_state_management(self) -> Dict[str, Any]:
        """Check state management functionality."""
        try:
            # Get repository count
            repositories = self.state_manager.list_repositories()
            repo_count = len(repositories)
            
            # Check if state can be saved (test operation)
            state_writable = True
            try:
                # This will trigger a save operation
                test_repos = self.state_manager.get_all_repository_statuses()
                state_writable = True
            except Exception as e:
                logger.warning(f"State write test failed: {e}")
                state_writable = False
            
            return {
                "checks": {
                    "state_readable": True,  # We got here so it's readable
                    "state_writable": state_writable,
                    "repositories_tracked": repo_count > 0
                },
                "details": {
                    "repositories_count": repo_count,
                    "repositories": repositories[:10] if repositories else []  # First 10
                }
            }
            
        except Exception as e:
            logger.error(f"State management check failed: {e}")
            return {
                "checks": {"state_management_critical": False},
                "details": {"error": str(e)}
            }
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        uptime = datetime.now() - self._performance_metrics["uptime_start"]
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "uptime_hours": uptime.total_seconds() / 3600,
            "requests_processed": self._performance_metrics["requests_processed"],
            "average_response_time": self._performance_metrics["average_response_time"],
            "errors_count": self._performance_metrics["errors_count"],
            "health_checks_count": len(self._health_history)
        }
    
    def record_request(self, duration: float, success: bool = True) -> None:
        """
        Record a request for performance tracking.
        
        Args:
            duration: Request duration in seconds
            success: Whether the request was successful
        """
        self._performance_metrics["requests_processed"] += 1
        
        # Update average response time
        current_avg = self._performance_metrics["average_response_time"]
        count = self._performance_metrics["requests_processed"]
        self._performance_metrics["average_response_time"] = (
            (current_avg * (count - 1) + duration) / count
        )
        
        if not success:
            self._performance_metrics["errors_count"] += 1
    
    async def get_health_summary(self) -> Dict[str, Any]:
        """
        Get a summary of health status and trends.
        
        Returns:
            Health summary with trends and recommendations
        """
        current_health = await self.get_health_status()
        
        # Calculate health trends from history
        recent_history = self._health_history[-10:]  # Last 10 checks
        health_trend = "stable"
        
        if len(recent_history) >= 3:
            recent_statuses = [h.status for h in recent_history]
            if recent_statuses[-1] == "healthy" and recent_statuses[-2] != "healthy":
                health_trend = "improving"
            elif recent_statuses[-1] != "healthy" and recent_statuses[-2] == "healthy":
                health_trend = "degrading"
        
        # Generate recommendations
        recommendations = []
        for check_name, passed in current_health.checks.items():
            if not passed:
                recommendations.append(self._get_recommendation_for_check(check_name))
        
        return {
            "current_status": current_health.status,
            "health_trend": health_trend,
            "last_check": current_health.timestamp.isoformat(),
            "checks_passed": sum(1 for passed in current_health.checks.values() if passed),
            "total_checks": len(current_health.checks),
            "recommendations": [r for r in recommendations if r],
            "monitoring_active": self._monitoring_active,
            "health_history_size": len(self._health_history)
        }
    
    def _get_recommendation_for_check(self, check_name: str) -> Optional[str]:
        """Get recommendation for a failed health check."""
        recommendations = {
            "cpu_usage_ok": "High CPU usage detected. Consider reducing concurrent operations.",
            "memory_usage_ok": "High memory usage detected. Check for memory leaks or reduce batch sizes.",
            "disk_space_ok": "Low disk space. Clean up old ChromaDB data or expand storage.",
            "github_api_ok": "GitHub API connection failed. Check GITHUB_TOKEN and network connectivity.",
            "google_api_ok": "Google API connection failed. Check GOOGLE_API_KEY configuration.",
            "chromadb_accessible": "ChromaDB not accessible. Check file permissions and disk space.",
            "state_writable": "Cannot write state. Check file permissions for ChromaDB directory."
        }
        return recommendations.get(check_name)
    
    async def cleanup_old_data(self, max_age_days: int = 30) -> Dict[str, Any]:
        """
        Cleanup old data to free resources.
        
        Args:
            max_age_days: Maximum age for data retention
            
        Returns:
            Cleanup results
        """
        try:
            # Cleanup old repository entries
            cleaned_repos = self.state_manager.cleanup_old_entries(max_age_days)
            
            # Cleanup health history
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            old_health_count = len(self._health_history)
            self._health_history = [
                h for h in self._health_history 
                if h.timestamp > cutoff_time
            ]
            cleaned_health = old_health_count - len(self._health_history)
            
            logger.info(f"Cleanup completed: {cleaned_repos} repos, {cleaned_health} health records")
            
            return {
                "success": True,
                "repositories_cleaned": cleaned_repos,
                "health_records_cleaned": cleaned_health,
                "cleanup_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
