"""
Ingestion tools for the GitHub Issue Solver MCP Server.

MCP tools for the multi-step repository ingestion process including
documentation, code analysis, issues history, and PR history.
"""

from loguru import logger
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

from ..services.ingestion_service import IngestionService
from ..models import IngestionStep, IngestionStatus
from ..exceptions import IngestionError, RepositoryError



def register_ingestion_tools(
    mcp: FastMCP, 
    ingestion_service: IngestionService
) -> None:
    """
    Register all ingestion tools with the MCP server.
    
    Args:
        mcp: FastMCP server instance
        ingestion_service: Ingestion service instance
    """
    
    @mcp.tool()
    async def start_repository_ingestion(repo_name: str) -> str:
        """
        Start the repository ingestion process by validating the repository 
        and setting up the initial state. This is the first step in the 
        multi-step ingestion workflow.
        
        Args:
            repo_name: Repository name in 'owner/repo' format (e.g., 'microsoft/vscode')
        
        Returns:
            Status message with the 4-step ingestion plan
        """
        try:
            logger.info(f"Starting repository ingestion: {repo_name}")
            
            result = await ingestion_service.start_repository_ingestion(repo_name)
            
            if result.success:
                return f"""🚀 **Repository Ingestion Started Successfully!**

📂 **Repository**: {repo_name}
🎯 **Status**: Initialization Complete - Ready for Step-by-Step Ingestion

📋 **4-Step Ingestion Plan:**

**Step 1: Documentation Ingestion** 📚
• Command: `ingest_repository_docs('{repo_name}')`
• Fetches and embeds README files, wikis, and documentation

**Step 2: Code Analysis** 💻  
• Command: `ingest_repository_code('{repo_name}')`
• Analyzes and chunks source code files for context

**Step 3: Issues History** 🐛
• Command: `ingest_repository_issues('{repo_name}')`
• Processes recent issues for pattern recognition

**Step 4: PR History** 🔄
• Command: `ingest_repository_prs('{repo_name}')`
• Analyzes pull request history for solution patterns

📊 **Progress Tracking:**
• Use `get_repository_status('{repo_name}')` to check progress at any time
• Each step provides real-time feedback and can be run independently
• Failed steps can be retried without affecting completed steps

💡 **Next Step:** Begin with Step 1 by running:
`ingest_repository_docs('{repo_name}')`

✅ **Repository validated and ready for multi-step ingestion!**"""
                
            else:
                return f"❌ **Ingestion Start Failed**: {result.error_message}"
                
        except RepositoryError as e:
            logger.error(f"Repository error during ingestion start: {e}")
            return f"❌ **Repository Error**: {e.message}"
        except IngestionError as e:
            logger.error(f"Ingestion error during start: {e}")
            return f"❌ **Ingestion Error**: {e.message}"
        except Exception as e:
            logger.error(f"Unexpected error during ingestion start: {e}")
            return f"❌ **Unexpected Error**: {str(e)}"
    
    @mcp.tool()
    async def ingest_repository_docs(repo_name: str) -> str:
        """
        Ingest documentation from a GitHub repository (Step 1 of 4).
        Fetches and embeds README files, wikis, and documentation into the knowledge base.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
        
        Returns:
            Status message about documentation ingestion results
        """
        try:
            logger.info(f"Ingesting documentation for: {repo_name}")
            
            result = await ingestion_service.ingest_documentation(repo_name)
            
            if result.success:
                progress = await ingestion_service.get_ingestion_progress(repo_name)
                next_step = progress.get("next_step", "ingest_repository_code")
                
                return f"""✅ **Step 1 Complete: Documentation Ingested!**

📚 **Documentation Results:**
• Repository: {repo_name}
• Documents Stored: {result.documents_stored:,} chunks
• Collection: {result.collection_name}
• Processing Time: {result.duration_seconds:.2f}s
• Status: ✅ Complete

📊 **Progress Summary:**
• Step 1 (Docs): ✅ {result.documents_stored} documents
• Step 2 (Code): ⏳ Pending  
• Step 3 (Issues): ⏳ Pending
• Step 4 (PRs): ⏳ Pending

🎯 **Next Step:** Run Step 2 - Code Analysis:
`ingest_repository_code('{repo_name}')`

💡 **Tip:** Use `get_repository_status('{repo_name}')` to check detailed progress at any time."""
            else:
                return f"❌ **Step 1 Failed**: Documentation ingestion error: {result.error_message}"
                
        except Exception as e:
            logger.error(f"Error during documentation ingestion: {e}")
            return f"❌ **Step 1 Failed**: {str(e)}"
    
    @mcp.tool()
    async def ingest_repository_code(repo_name: str) -> str:
        """
        Ingest source code from a GitHub repository (Step 2 of 4).
        Analyzes and chunks source code files for context understanding.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
        
        Returns:
            Status message about code ingestion results
        """
        try:
            logger.info(f"Ingesting code for: {repo_name}")
            
            result = await ingestion_service.ingest_code(repo_name)
            
            if result.success:
                progress = await ingestion_service.get_ingestion_progress(repo_name)
                docs_count = progress.get("steps", {}).get("documentation", {}).get("documents_stored", 0)
                
                return f"""✅ **Step 2 Complete: Source Code Analyzed!**

💻 **Code Analysis Results:**
• Repository: {repo_name}
• Code Chunks Stored: {result.documents_stored:,} chunks
• Collection: {result.collection_name}
• Processing Time: {result.duration_seconds:.2f}s
• Status: ✅ Complete

📊 **Progress Summary:**
• Step 1 (Docs): ✅ {docs_count} documents
• Step 2 (Code): ✅ {result.documents_stored} chunks 
• Step 3 (Issues): ⏳ Pending
• Step 4 (PRs): ⏳ Pending

🎯 **Next Step:** Run Step 3 - Issues History:
`ingest_repository_issues('{repo_name}')`

💡 **Tip:** Use `get_repository_status('{repo_name}')` to check detailed progress at any time."""
            else:
                return f"❌ **Step 2 Failed**: Code ingestion error: {result.error_message}"
                
        except Exception as e:
            logger.error(f"Error during code ingestion: {e}")
            return f"❌ **Step 2 Failed**: {str(e)}"
    
    @mcp.tool()
    async def ingest_repository_issues(repo_name: str, max_issues: int = 100) -> str:
        """
        Ingest issues history from a GitHub repository (Step 3 of 4).
        Processes recent issues for pattern recognition and context understanding.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            max_issues: Maximum number of issues to process (default: 100)
        
        Returns:
            Status message about issues ingestion results
        """
        try:
            logger.info(f"Ingesting issues for: {repo_name} (max: {max_issues})")
            
            result = await ingestion_service.ingest_issues(repo_name, max_issues)
            
            if result.success:
                progress = await ingestion_service.get_ingestion_progress(repo_name)
                docs_count = progress.get("steps", {}).get("documentation", {}).get("documents_stored", 0)
                code_count = progress.get("steps", {}).get("code", {}).get("documents_stored", 0)
                
                return f"""✅ **Step 3 Complete: Issues History Ingested!**

🐛 **Issues Analysis Results:**
• Repository: {repo_name}
• Issues Processed: {result.metadata.get('data_items_found', 0)} issues → {result.documents_stored:,} searchable chunks
• Collection: {result.collection_name}
• Processing Time: {result.duration_seconds:.2f}s
• Status: ✅ Complete

📝 **Note:** Issues with long descriptions/comments are automatically chunked into smaller pieces for better search and analysis.

📊 **Progress Summary:**
• Step 1 (Docs): ✅ {docs_count} documents
• Step 2 (Code): ✅ {code_count} chunks
• Step 3 (Issues): ✅ {result.documents_stored} chunks
• Step 4 (PRs): ⏳ Pending

🎯 **Final Step:** Run Step 4 - PR History:
`ingest_repository_prs('{repo_name}')`

💡 **Tip:** Use `get_repository_status('{repo_name}')` to check detailed progress at any time."""
            else:
                return f"❌ **Step 3 Failed**: Issues ingestion error: {result.error_message}"
                
        except Exception as e:
            logger.error(f"Error during issues ingestion: {e}")
            return f"❌ **Step 3 Failed**: {str(e)}"
    
    @mcp.tool()
    async def ingest_repository_prs(repo_name: str, max_prs: int = 50) -> str:
        """
        Ingest PR history from a GitHub repository (Step 4 of 4 - Final Step).
        Analyzes pull request history for solution patterns and completes the ingestion process.
        
        Args:
            repo_name: Repository name in 'owner/repo' format
            max_prs: Maximum number of PRs to process (default: 50)
        
        Returns:
            Final summary message announcing ingestion completion
        """
        try:
            logger.info(f"Ingesting PRs for: {repo_name} (max: {max_prs})")
            
            result = await ingestion_service.ingest_prs(repo_name, max_prs)
            
            if result.success:
                progress = await ingestion_service.get_ingestion_progress(repo_name)
                
                docs_count = progress.get("steps", {}).get("documentation", {}).get("documents_stored", 0)
                code_count = progress.get("steps", {}).get("code", {}).get("documents_stored", 0)
                issues_count = progress.get("steps", {}).get("issues", {}).get("documents_stored", 0)
                total_docs = progress.get("total_documents", 0)
                
                return f"""🎉 **INGESTION COMPLETE! All 4 Steps Finished!**

🔄 **Step 4 Results - PR History:**
• Repository: {repo_name}
• PRs Processed: {result.metadata.get('data_items_found', 0)} PRs → {result.documents_stored:,} searchable chunks
• Processing Time: {result.duration_seconds:.2f}s
• Status: ✅ Complete

📝 **Note:** PRs with long descriptions/diffs are automatically chunked into smaller pieces for better search and analysis.

📊 **Final Ingestion Summary:**
• Step 1 (Docs): ✅ {docs_count} documents
• Step 2 (Code): ✅ {code_count} chunks
• Step 3 (Issues): ✅ {issues_count} chunks
• Step 4 (PRs): ✅ {result.documents_stored} chunks

🎯 **Total Knowledge Base Size:** {total_docs:,} searchable chunks
📁 **Collections Created:** {len(progress.get('collections', []))} collections
🕒 **Completed:** {result.generated_at.strftime('%Y-%m-%d %H:%M:%S') if result.generated_at else 'Now'}

📁 **Collections:**
{chr(10).join([f"  • {col}" for col in progress.get('collections', [])])}

🚀 **Next Steps - Repository is Ready!**
1. Use `analyze_github_issue_tool` to analyze specific issues from {repo_name}
2. Use `generate_code_patch_tool` to create patches for issues
3. Use the official `github` server tools to create Pull Requests

💡 **Status Checking:**
• Use `get_repository_status('{repo_name}')` for detailed statistics
• Use `list_ingested_repositories()` to see all available repositories

🎉 **Knowledge base is ready for AI-powered issue resolution!**"""
            else:
                return f"❌ **Step 4 Failed**: PR ingestion error: {result.error_message}"
                
        except Exception as e:
            logger.error(f"Error during PR ingestion: {e}")
            return f"❌ **Step 4 Failed**: {str(e)}"


# Export tool registration function
start_repository_ingestion_tool = register_ingestion_tools
ingest_repository_docs_tool = register_ingestion_tools
ingest_repository_code_tool = register_ingestion_tools
ingest_repository_issues_tool = register_ingestion_tools
ingest_repository_prs_tool = register_ingestion_tools
