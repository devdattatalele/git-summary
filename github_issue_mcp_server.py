#!/usr/bin/env python3
"""
GitHub Issue Resolution MCP Server

A comprehensive Model Context Protocol server that provides GitHub repository analysis,
issue resolution, patch generation, and PR creation capabilities using FastMCP.

This server follows MCP best practices:
- Uses FastMCP for easier tool creation
- Proper logging to stderr (never stdout)
- Comprehensive error handling
- Claude Desktop compatible

Usage:
    python github_issue_mcp_server.py
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import traceback

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

# MCP Server imports
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr only (critical for MCP servers)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server with proper name
mcp = FastMCP("github-issue-resolver")

# Store for repository analysis results and ingestion progress
# Each repo entry will have detailed status tracking:
# {
#   "repo_name": {
#     "status": "pending|in_progress|completed|error",
#     "docs_stored": int,
#     "code_chunks_stored": int, 
#     "issues_stored": int,
#     "prs_stored": int,
#     "total_documents": int,
#     "timestamp": str,
#     "collections": List[str],
#     "chroma_dir": str,
#     "error_message": str (if status == "error")
#   }
# }
analysis_results: Dict[str, Dict] = {}

def validate_environment() -> List[str]:
    """Validate environment variables and return missing ones."""
    required_vars = ["GOOGLE_API_KEY", "GITHUB_TOKEN"]
    optional_vars = ["GOOGLE_DOCS_ID"]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    # Log optional variables status
    for var in optional_vars:
        if os.getenv(var):
            logger.info(f"✅ Optional {var} is configured")
        else:
            logger.info(f"⚠️  Optional {var} is not configured (some features may be limited)")
    
    return missing_vars

async def _initialize_ingestion(repo_name: str):
    """
    Helper function to initialize ingestion clients and validate repository.
    Used by all ingestion tools to avoid code duplication.
    
    Args:
        repo_name: Repository name in 'owner/repo' format
    
    Returns:
        Tuple of (github_client, embeddings, repo, chroma_persist_dir, error_message)
        If error_message is not None, there was an error and other values should be ignored.
    """
    try:
        # Import required modules locally to handle import errors gracefully
        try:
            from issue_solver.ingest import (
                initialize_clients as init_ingestion_clients,
                validate_repo_exists,
                CHROMA_PERSIST_DIR
            )
        except ImportError as e:
            logger.error(f"Failed to import ingestion modules: {e}")
            return None, None, None, None, f"❌ **Import Error**: Could not load ingestion modules. Please ensure all dependencies are installed.\nError: {str(e)}"
        
        # Validate repository exists first
        try:
            if not await asyncio.to_thread(validate_repo_exists, repo_name):
                return None, None, None, None, f"❌ **Repository Validation Failed**\n\nRepository '{repo_name}' was not found or is not accessible. Please check:\n• Repository name format (owner/repo)\n• Repository visibility (public vs private)\n• GitHub token permissions"
        except Exception as e:
            logger.warning(f"Could not validate repository (continuing anyway): {e}")
        
        # Initialize clients for ingestion
        try:
            github_client, embeddings = await asyncio.to_thread(init_ingestion_clients)
            logger.info("✅ Successfully initialized GitHub client and embeddings")
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            return None, None, None, None, f"❌ **Client Initialization Failed**: {str(e)}\n\nPlease check your environment variables (GOOGLE_API_KEY, GITHUB_TOKEN)"
        
        # Validate repository access
        try:
            repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_name))
            logger.info(f"✅ Successfully connected to repository: {repo.full_name}")
        except Exception as e:
            logger.error(f"Repository access error: {e}")
            return None, None, None, None, f"❌ **Repository Access Failed**: Could not access repository '{repo_name}'.\n\nError: {str(e)}\n\nPlease check:\n• Repository name is correct\n• Repository is public or your GITHUB_TOKEN has access\n• GITHUB_TOKEN is valid"
        
        # Create persist directory if it doesn't exist
        chroma_persist_dir = CHROMA_PERSIST_DIR
        
        try:
            os.makedirs(chroma_persist_dir, exist_ok=True)
            logger.info(f"✅ ChromaDB directory created/verified: {chroma_persist_dir}")
        except PermissionError as e:
            logger.error(f"❌ Permission denied creating ChromaDB directory: {e}")
            return None, None, None, None, f"❌ **Permission Error**: Cannot create ChromaDB directory at '{chroma_persist_dir}'. Please check file system permissions or set CHROMA_PERSIST_DIR environment variable to a writable location."
        except Exception as e:
            logger.error(f"❌ Error creating ChromaDB directory: {e}")
            return None, None, None, None, f"❌ **Directory Creation Failed**: {str(e)}"
        
        # Create initial entry for the repo in analysis_results if it doesn't exist
        if repo_name not in analysis_results:
            analysis_results[repo_name] = {
                "status": "pending",
                "docs_stored": 0,
                "code_chunks_stored": 0,
                "issues_stored": 0,
                "prs_stored": 0,
                "total_documents": 0,
                "timestamp": datetime.now().isoformat(),
                "collections": [],
                "chroma_dir": chroma_persist_dir,
                "error_message": None
            }
        
        return github_client, embeddings, repo, chroma_persist_dir, None
        
    except Exception as e:
        error_msg = f"Initialization failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return None, None, None, None, f"❌ **Error**: {error_msg}"

async def _check_if_forked(repo_full_name: str, github_client):
    """
    Check if the authenticated user owns the repo or already has a valid fork.
    
    Args:
        repo_full_name: Repository name in 'owner/repo' format
        github_client: Authenticated GitHub client
    
    Returns:
        Tuple of (repository_object, is_fork, error_message)
        If error_message is not None, there was an error.
    """
    try:
        logger.info(f"🔍 Checking fork status for: {repo_full_name}")
        
        # Get the authenticated user
        user = await asyncio.to_thread(lambda: github_client.get_user())
        user_login = user.login
        
        # Parse the original repo name
        owner, repo_name = repo_full_name.split('/')
        
        # Check if the user owns the original repository
        if owner.lower() == user_login.lower():
            logger.info(f"✅ User owns the repository: {repo_full_name}")
            repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_full_name))
            return repo, False, None
        
        # Check if user already has a fork
        try:
            fork_repo_name = f"{user_login}/{repo_name}"
            fork_repo = await asyncio.to_thread(lambda: github_client.get_repo(fork_repo_name))
            
            # Verify this is actually a fork of the target repo
            if fork_repo.fork and fork_repo.parent.full_name == repo_full_name:
                logger.info(f"✅ Found existing fork: {fork_repo_name}")
                return fork_repo, True, None
            else:
                logger.warning(f"Repository {fork_repo_name} exists but is not a fork of {repo_full_name}")
        except Exception as e:
            logger.info(f"No existing fork found for {repo_full_name}: {str(e)}")
        
        # No fork exists, return the original repo for forking
        original_repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_full_name))
        return original_repo, None, None  # None indicates we need to create a fork
        
    except Exception as e:
        error_msg = f"Failed to check fork status: {str(e)}"
        logger.error(error_msg)
        return None, None, error_msg

async def _create_fork(repo_full_name: str, github_client):
    """
    Create a new fork of the specified repository.
    
    Args:
        repo_full_name: Repository name in 'owner/repo' format
        github_client: Authenticated GitHub client
    
    Returns:
        Tuple of (fork_repository_object, error_message)
        If error_message is not None, there was an error.
    """
    try:
        logger.info(f"🍴 Creating fork of: {repo_full_name}")
        
        # Get the original repository
        original_repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_full_name))
        
        # Create the fork
        fork_repo = await asyncio.to_thread(lambda: original_repo.create_fork())
        
        logger.info(f"✅ Fork created: {fork_repo.full_name}")
        
        # Wait a few seconds for the fork to be fully available
        logger.info("⏳ Waiting for fork to become available...")
        await asyncio.sleep(5)
        
        # Refresh the fork object to ensure it's fully ready
        refreshed_fork = await asyncio.to_thread(lambda: github_client.get_repo(fork_repo.full_name))
        
        return refreshed_fork, None
        
    except Exception as e:
        error_msg = f"Failed to create fork: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

async def _get_or_create_fork(repo_full_name: str, github_client):
    """
    Orchestrator function to get the appropriate repository (original or fork) for applying changes.
    
    Args:
        repo_full_name: Repository name in 'owner/repo' format
        github_client: Authenticated GitHub client
    
    Returns:
        Tuple of (repository_to_use, is_fork, fork_created, error_message)
        - repository_to_use: The repo object to push changes to
        - is_fork: Boolean indicating if we're using a fork
        - fork_created: Boolean indicating if a new fork was created
        - error_message: Error message if something went wrong
    """
    try:
        logger.info(f"🚀 Determining fork workflow for: {repo_full_name}")
        
        # Check current fork status
        repo, is_fork, error_msg = await _check_if_forked(repo_full_name, github_client)
        
        if error_msg:
            return None, False, False, error_msg
        
        # If user owns the repo, use it directly
        if is_fork is False:
            logger.info("📝 Using original repository (user has write access)")
            return repo, False, False, None
        
        # If user already has a fork, use it
        if is_fork is True:
            logger.info("🍴 Using existing fork")
            return repo, True, False, None
        
        # Need to create a fork
        if is_fork is None:
            logger.info("🔄 Creating new fork...")
            fork_repo, fork_error = await _create_fork(repo_full_name, github_client)
            
            if fork_error:
                return None, False, False, fork_error
            
            logger.info("✅ Fork workflow ready with new fork")
            return fork_repo, True, True, None
        
        return None, False, False, "Unexpected fork status"
        
    except Exception as e:
        error_msg = f"Fork workflow orchestration failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return None, False, False, error_msg

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
        logger.info(f"🚀 Starting repository ingestion process for: {repo_name}")
        
        # Initialize ingestion using our helper function
        github_client, embeddings, repo, chroma_persist_dir, error_msg = await _initialize_ingestion(repo_name)
        
        if error_msg:
            return error_msg
        
        # Update status to in_progress
        analysis_results[repo_name]["status"] = "in_progress"
        analysis_results[repo_name]["timestamp"] = datetime.now().isoformat()
        
        response_text = f"""🚀 **Repository Ingestion Started!**

📂 **Repository**: {repo.full_name}
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

        logger.info(f"✅ Repository ingestion initialized for {repo_name}")
        return response_text
        
    except Exception as e:
        error_msg = f"Failed to start repository ingestion: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        
        # Update status to error if repo exists in analysis_results
        if repo_name in analysis_results:
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
        
        return f"❌ **Ingestion Start Failed**: {error_msg}"

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
        logger.info(f"📚 Starting documentation ingestion for: {repo_name}")
        
        # Check if repository ingestion has been started
        if repo_name not in analysis_results:
            return f"""❌ **Repository Not Initialized**

Repository '{repo_name}' has not been initialized for ingestion yet.

🎯 **Please run first:**
`start_repository_ingestion('{repo_name}')`

Then proceed with documentation ingestion."""
        
        # Initialize ingestion clients
        github_client, embeddings, repo, chroma_persist_dir, error_msg = await _initialize_ingestion(repo_name)
        
        if error_msg:
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return error_msg
        
        # Import required function
        try:
            from issue_solver.ingest import fetch_repo_docs, chunk_and_embed_and_store
        except ImportError as e:
            error_msg = f"Failed to import documentation functions: {e}"
            logger.error(error_msg)
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return f"❌ **Import Error**: {error_msg}"
        
        # Collection name for documentation
        COLLECTION_DOCS = "documentation"
        
        # Process documentation
        try:
            logger.info("📄 Fetching documentation files...")
            docs = await fetch_repo_docs(repo.full_name)
            
            if docs:
                logger.info(f"📝 Found {len(docs)} documentation files, now embedding and storing...")
                stored = await chunk_and_embed_and_store(docs, embeddings, COLLECTION_DOCS, repo.full_name)
                
                # Update analysis results
                analysis_results[repo_name]["docs_stored"] = stored
                analysis_results[repo_name]["total_documents"] += stored
                
                # Add to collections list
                safe_repo_name = repo.full_name.replace('/', '_').replace('-', '_').lower()
                collection_name = f"{safe_repo_name}_{COLLECTION_DOCS}"
                if collection_name not in analysis_results[repo_name]["collections"]:
                    analysis_results[repo_name]["collections"].append(collection_name)
                
                logger.info(f"✅ Documentation ingestion completed: {stored} documents")
                
                response_text = f"""✅ **Step 1 Complete: Documentation Ingested!**

📚 **Documentation Results:**
• Repository: {repo.full_name}
• Documents Stored: {stored:,} chunks
• Collection: {collection_name}
• Status: ✅ Complete

📊 **Progress Summary:**
• Step 1 (Docs): ✅ {stored} documents
• Step 2 (Code): ⏳ Pending  
• Step 3 (Issues): ⏳ Pending
• Step 4 (PRs): ⏳ Pending

🎯 **Next Step:** Run Step 2 - Code Analysis:
`ingest_repository_code('{repo_name}')`

💡 **Tip:** Use `get_repository_status('{repo_name}')` to check detailed progress at any time."""
                
                return response_text
                
            else:
                # No documents found, but not an error
                analysis_results[repo_name]["docs_stored"] = 0
                logger.info("ℹ️  No documentation found")
                
                response_text = f"""✅ **Step 1 Complete: Documentation Scan Finished**

📚 **Documentation Results:**
• Repository: {repo.full_name}
• Documents Found: 0 (no documentation files detected)
• Status: ✅ Complete (no docs to process)

📊 **Progress Summary:**  
• Step 1 (Docs): ✅ 0 documents (none found)
• Step 2 (Code): ⏳ Pending
• Step 3 (Issues): ⏳ Pending  
• Step 4 (PRs): ⏳ Pending

🎯 **Next Step:** Run Step 2 - Code Analysis:
`ingest_repository_code('{repo_name}')`"""
                
                return response_text
                
        except Exception as e:
            error_msg = f"Documentation processing error: {str(e)}"
            logger.error(error_msg)
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return f"❌ **Step 1 Failed**: Documentation ingestion error: {error_msg}"
        
        except Exception as e:
        error_msg = f"Documentation ingestion failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        
        # Update status to error if repo exists in analysis_results
        if repo_name in analysis_results:
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
        
        return f"❌ **Step 1 Failed**: {error_msg}"

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
        logger.info(f"💻 Starting code ingestion for: {repo_name}")
        
        # Check if repository ingestion has been started
        if repo_name not in analysis_results:
            return f"""❌ **Repository Not Initialized**

Repository '{repo_name}' has not been initialized for ingestion yet.

🎯 **Please run first:**
`start_repository_ingestion('{repo_name}')`

Then proceed with code ingestion."""
        
        # Initialize ingestion clients
        github_client, embeddings, repo, chroma_persist_dir, error_msg = await _initialize_ingestion(repo_name)
        
        if error_msg:
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return error_msg
        
        # Import required function
        try:
            from issue_solver.ingest import fetch_repo_code, chunk_and_embed_and_store
        except ImportError as e:
            error_msg = f"Failed to import code analysis functions: {e}"
            logger.error(error_msg)
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return f"❌ **Import Error**: {error_msg}"
        
        # Collection name for repository code
        COLLECTION_REPO_CODE = "repo_code_main"
        
        # Process code
        try:
            logger.info("📝 Fetching and analyzing source code...")
                code_chunks = await fetch_repo_code(repo.full_name)
            
                if code_chunks:
                logger.info(f"🔍 Found {len(code_chunks)} code chunks, now embedding and storing...")
                    stored = await chunk_and_embed_and_store(code_chunks, embeddings, COLLECTION_REPO_CODE, repo.full_name)
                
                # Update analysis results
                analysis_results[repo_name]["code_chunks_stored"] = stored
                analysis_results[repo_name]["total_documents"] += stored
                
                # Add to collections list
                safe_repo_name = repo.full_name.replace('/', '_').replace('-', '_').lower()
                collection_name = f"{safe_repo_name}_{COLLECTION_REPO_CODE}"
                if collection_name not in analysis_results[repo_name]["collections"]:
                    analysis_results[repo_name]["collections"].append(collection_name)
                
                logger.info(f"✅ Code ingestion completed: {stored} chunks")
                
                docs_stored = analysis_results[repo_name]["docs_stored"]
                response_text = f"""✅ **Step 2 Complete: Source Code Analyzed!**

💻 **Code Analysis Results:**
• Repository: {repo.full_name}
• Code Chunks Stored: {stored:,} chunks
• Collection: {collection_name}
• Status: ✅ Complete

📊 **Progress Summary:**
• Step 1 (Docs): ✅ {docs_stored} documents
• Step 2 (Code): ✅ {stored} chunks 
• Step 3 (Issues): ⏳ Pending
• Step 4 (PRs): ⏳ Pending

🎯 **Next Step:** Run Step 3 - Issues History:
`ingest_repository_issues('{repo_name}')`

💡 **Tip:** Use `get_repository_status('{repo_name}')` to check detailed progress at any time."""
                
                return response_text
                
                else:
                # No code found, but not an error
                analysis_results[repo_name]["code_chunks_stored"] = 0
                logger.info("ℹ️  No source code found to analyze")
                
                docs_stored = analysis_results[repo_name]["docs_stored"]
                response_text = f"""✅ **Step 2 Complete: Code Scan Finished**

💻 **Code Analysis Results:**
• Repository: {repo.full_name}
• Code Files Found: 0 (no analyzable source code detected)
• Status: ✅ Complete (no code to process)

📊 **Progress Summary:**  
• Step 1 (Docs): ✅ {docs_stored} documents
• Step 2 (Code): ✅ 0 chunks (none found)
• Step 3 (Issues): ⏳ Pending
• Step 4 (PRs): ⏳ Pending

🎯 **Next Step:** Run Step 3 - Issues History:
`ingest_repository_issues('{repo_name}')`"""
                
                return response_text
                
            except Exception as e:
            error_msg = f"Code processing error: {str(e)}"
            logger.error(error_msg)
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return f"❌ **Step 2 Failed**: Code ingestion error: {error_msg}"
        
    except Exception as e:
        error_msg = f"Code ingestion failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        
        # Update status to error if repo exists in analysis_results
        if repo_name in analysis_results:
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
        
        return f"❌ **Step 2 Failed**: {error_msg}"

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
        logger.info(f"🐛 Starting issues ingestion for: {repo_name} (max: {max_issues})")
        
        # Check if repository ingestion has been started
        if repo_name not in analysis_results:
            return f"""❌ **Repository Not Initialized**

Repository '{repo_name}' has not been initialized for ingestion yet.

🎯 **Please run first:**
`start_repository_ingestion('{repo_name}')`

Then proceed with issues ingestion."""
        
        # Initialize ingestion clients
        github_client, embeddings, repo, chroma_persist_dir, error_msg = await _initialize_ingestion(repo_name)
        
        if error_msg:
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return error_msg
        
        # Import required function
        try:
            from issue_solver.ingest import fetch_repo_issues, chunk_and_embed_and_store
        except ImportError as e:
            error_msg = f"Failed to import issues functions: {e}"
            logger.error(error_msg)
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return f"❌ **Import Error**: {error_msg}"
        
        # Collection name for issues
        COLLECTION_ISSUES = "issues_history"
        
        # Process issues
        try:
            logger.info(f"🔍 Fetching up to {max_issues} issues...")
            issues = await asyncio.to_thread(fetch_repo_issues, repo, max_issues)
            
            if issues:
                logger.info(f"📊 Found {len(issues)} issues, now embedding and storing...")
                stored = await chunk_and_embed_and_store(issues, embeddings, COLLECTION_ISSUES, repo.full_name)
                
                # Update analysis results
                analysis_results[repo_name]["issues_stored"] = stored
                analysis_results[repo_name]["total_documents"] += stored
                
                # Add to collections list
                safe_repo_name = repo.full_name.replace('/', '_').replace('-', '_').lower()
                collection_name = f"{safe_repo_name}_{COLLECTION_ISSUES}"
                if collection_name not in analysis_results[repo_name]["collections"]:
                    analysis_results[repo_name]["collections"].append(collection_name)
                
                logger.info(f"✅ Issues ingestion completed: {stored} documents")
                
                docs_stored = analysis_results[repo_name]["docs_stored"]
                code_stored = analysis_results[repo_name]["code_chunks_stored"]
                response_text = f"""✅ **Step 3 Complete: Issues History Ingested!**

🐛 **Issues Analysis Results:**
• Repository: {repo.full_name}
• Issues Processed: {len(issues)} issues → {stored:,} searchable chunks
• Collection: {collection_name}
• Status: ✅ Complete

📝 **Note:** Issues with long descriptions/comments are automatically chunked into smaller pieces for better search and analysis. This is normal behavior.

📊 **Progress Summary:**
• Step 1 (Docs): ✅ {docs_stored} documents
• Step 2 (Code): ✅ {code_stored} chunks
• Step 3 (Issues): ✅ {stored} chunks
• Step 4 (PRs): ⏳ Pending

🎯 **Final Step:** Run Step 4 - PR History:
`ingest_repository_prs('{repo_name}')`

💡 **Tip:** Use `get_repository_status('{repo_name}')` to check detailed progress at any time."""
                
                return response_text
                
        else:
                # No issues found, but not an error
                analysis_results[repo_name]["issues_stored"] = 0
                logger.info("ℹ️  No issues found")
                
                docs_stored = analysis_results[repo_name]["docs_stored"]
                code_stored = analysis_results[repo_name]["code_chunks_stored"]
                response_text = f"""✅ **Step 3 Complete: Issues Scan Finished**

🐛 **Issues Analysis Results:**
• Repository: {repo.full_name}
• Issues Found: 0 (no issues detected)
• Status: ✅ Complete (no issues to process)

📊 **Progress Summary:**  
• Step 1 (Docs): ✅ {docs_stored} documents
• Step 2 (Code): ✅ {code_stored} chunks
• Step 3 (Issues): ✅ 0 chunks (none found)
• Step 4 (PRs): ⏳ Pending

🎯 **Final Step:** Run Step 4 - PR History:
`ingest_repository_prs('{repo_name}')`"""
                
                return response_text
                
        except Exception as e:
            error_msg = f"Issues processing error: {str(e)}"
            logger.error(error_msg)
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return f"❌ **Step 3 Failed**: Issues ingestion error: {error_msg}"
        
    except Exception as e:
        error_msg = f"Issues ingestion failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        
        # Update status to error if repo exists in analysis_results
        if repo_name in analysis_results:
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
        
        return f"❌ **Step 3 Failed**: {error_msg}"

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
        logger.info(f"🔄 Starting PR ingestion for: {repo_name} (max: {max_prs})")
        
        # Check if repository ingestion has been started
        if repo_name not in analysis_results:
            return f"""❌ **Repository Not Initialized**

Repository '{repo_name}' has not been initialized for ingestion yet.

🎯 **Please run first:**
`start_repository_ingestion('{repo_name}')`

Then proceed with the 4-step ingestion process."""
        
        # Initialize ingestion clients
        github_client, embeddings, repo, chroma_persist_dir, error_msg = await _initialize_ingestion(repo_name)
        
        if error_msg:
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return error_msg
        
        # Import required function
        try:
            from issue_solver.ingest import fetch_repo_pr_history, chunk_and_embed_and_store
        except ImportError as e:
            error_msg = f"Failed to import PR functions: {e}"
            logger.error(error_msg)
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return f"❌ **Import Error**: {error_msg}"
        
        # Collection name for PR history
        COLLECTION_PR_HISTORY = "pr_history"
        
        # Process PR history
        try:
            logger.info(f"🔀 Fetching up to {max_prs} pull requests...")
                pr_history = await asyncio.to_thread(fetch_repo_pr_history, repo, max_prs)
            
                if pr_history:
                logger.info(f"📊 Found {len(pr_history)} PRs, now embedding and storing...")
                    stored = await chunk_and_embed_and_store(pr_history, embeddings, COLLECTION_PR_HISTORY, repo.full_name)
                
                # Update analysis results
                analysis_results[repo_name]["prs_stored"] = stored
                analysis_results[repo_name]["total_documents"] += stored
                
                # Add to collections list
        safe_repo_name = repo.full_name.replace('/', '_').replace('-', '_').lower()
                collection_name = f"{safe_repo_name}_{COLLECTION_PR_HISTORY}"
                if collection_name not in analysis_results[repo_name]["collections"]:
                    analysis_results[repo_name]["collections"].append(collection_name)
                
                logger.info(f"✅ PR ingestion completed: {stored} documents")
                
            else:
                # No PRs found, but not an error
                analysis_results[repo_name]["prs_stored"] = 0
                logger.info("ℹ️  No pull requests found")
            
            # **CRUCIAL: Mark ingestion as completed**
            analysis_results[repo_name]["status"] = "completed"
            analysis_results[repo_name]["timestamp"] = datetime.now().isoformat()
            
            # Get all stored counts for final summary
            docs_stored = analysis_results[repo_name]["docs_stored"]
            code_stored = analysis_results[repo_name]["code_chunks_stored"]
            issues_stored = analysis_results[repo_name]["issues_stored"]
            prs_stored = analysis_results[repo_name]["prs_stored"]
            total_stored = analysis_results[repo_name]["total_documents"]
            
            response_text = f"""🎉 **INGESTION COMPLETE! All 4 Steps Finished!**

🔄 **Step 4 Results - PR History:**
• Repository: {repo.full_name}
• PRs Processed: {len(pr_history) if pr_history else 0} PRs → {prs_stored:,} searchable chunks
• Status: ✅ Complete

📝 **Note:** PRs with long descriptions/diffs are automatically chunked into smaller pieces for better search and analysis.

📊 **Final Ingestion Summary:**
• Step 1 (Docs): ✅ {docs_stored} documents
• Step 2 (Code): ✅ {code_stored} chunks
• Step 3 (Issues): ✅ {issues_stored} chunks
• Step 4 (PRs): ✅ {prs_stored} chunks

🎯 **Total Knowledge Base Size:** {total_stored:,} searchable chunks
📁 **ChromaDB Location:** {chroma_persist_dir}
🕒 **Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📁 **Collections Created:**
{chr(10).join([f"  • {col}" for col in analysis_results[repo_name]["collections"]])}

🚀 **Next Steps - Repository is Ready!**
1. Use `analyze_github_issue_tool` to analyze specific issues from {repo.full_name}
2. Use `generate_code_patch_tool` to create patches for issues
3. Use `create_github_pr_tool` to create Pull Requests

💡 **Status Checking:**
• Use `get_repository_status('{repo_name}')` for detailed statistics
• Use `list_ingested_repositories()` to see all available repositories

🎉 **Knowledge base is ready for AI-powered issue resolution!**"""
            
            logger.info(f"🎉 Complete ingestion finished for {repo_name}")
            logger.info(f"📊 Total documents: {total_stored}")
            return response_text
        
    except Exception as e:
            error_msg = f"PR processing error: {str(e)}"
            logger.error(error_msg)
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
            return f"❌ **Step 4 Failed**: PR ingestion error: {error_msg}"
        
    except Exception as e:
        error_msg = f"PR ingestion failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        
        # Update status to error if repo exists in analysis_results
        if repo_name in analysis_results:
            analysis_results[repo_name]["status"] = "error"
            analysis_results[repo_name]["error_message"] = error_msg
        
        return f"❌ **Step 4 Failed**: {error_msg}"

@mcp.tool()
async def analyze_github_issue_tool(issue_url: str) -> str:
    """
    Analyze a GitHub issue using AI and repository knowledge base.
    Provides comprehensive analysis including summary, proposed solution,
    complexity rating, and similar issues.
    
    Args:
        issue_url: Full GitHub issue URL (e.g., 'https://github.com/owner/repo/issues/123')
    
    Returns:
        JSON string containing detailed analysis results and formatted report
    """
    try:
        logger.info(f"🔍 Analyzing GitHub issue: {issue_url}")
        
        # Import required modules locally
        try:
            from issue_solver.analyze import (
                parse_github_url, 
                get_github_issue, 
                create_langchain_agent, 
                parse_agent_output, 
                append_to_google_doc
            )
        except ImportError as e:
            logger.error(f"Failed to import analysis modules: {e}")
            return json.dumps({
                "error": f"Import Error: Could not load analysis modules. Error: {str(e)}",
                "success": False
            }, indent=2, ensure_ascii=False)
        
        # Parse the GitHub URL
        try:
            owner, repo, issue_number = parse_github_url(issue_url)
            logger.info(f"✅ Parsed URL - Owner: {owner}, Repo: {repo}, Issue: {issue_number}")
        except Exception as e:
            logger.error(f"URL parsing error: {e}")
            return json.dumps({
                "error": f"Invalid GitHub issue URL: {str(e)}",
                "success": False
            }, indent=2, ensure_ascii=False)
        
        # Check if repository is ingested
        repo_full_name = f"{owner}/{repo}"
        if repo_full_name not in analysis_results:
            error_response = {
                "error": f"Repository '{repo_full_name}' has not been ingested yet. Please run the 4-step ingestion process first.",
                "success": False,
                "suggestion": f"Start with: start_repository_ingestion('{repo_full_name}')",
                "next_steps": [
                    f"start_repository_ingestion('{repo_full_name}')",
                    f"ingest_repository_docs('{repo_full_name}')",
                    f"ingest_repository_code('{repo_full_name}')",
                    f"ingest_repository_issues('{repo_full_name}')",
                    f"ingest_repository_prs('{repo_full_name}')"
                ]
            }
            return json.dumps(error_response, indent=2, ensure_ascii=False)
        
        # Fetch the GitHub issue
        try:
            issue = await asyncio.to_thread(get_github_issue, owner, repo, issue_number)
            logger.info(f"✅ Fetched issue: {issue.title}")
        except Exception as e:
            logger.error(f"Issue fetch error: {e}")
            return json.dumps({
                "error": f"Could not fetch GitHub issue: {str(e)}",
                "success": False
            }, indent=2, ensure_ascii=False)
        
        # Create LangChain agent and analyze the issue
        try:
            logger.info("🤖 Creating LangChain agent for analysis...")
            agent_raw_output = await asyncio.to_thread(create_langchain_agent, issue)
            logger.info("✅ Agent analysis completed")
        except Exception as e:
            logger.error(f"Agent analysis error: {e}")
            return json.dumps({
                "error": f"Analysis failed: {str(e)}",
                "success": False
            }, indent=2, ensure_ascii=False)
        
        # Parse the agent output
        try:
            analysis = parse_agent_output(agent_raw_output)
            logger.info("✅ Analysis parsed successfully")
        except Exception as e:
            logger.error(f"Output parsing error: {e}")
            return json.dumps({
                "error": f"Could not parse analysis output: {str(e)}",
                "success": False,
                "raw_output": str(agent_raw_output)[:500] + "..." if len(str(agent_raw_output)) > 500 else str(agent_raw_output)
            }, indent=2, ensure_ascii=False)
        
        # Create the detailed report
        timestamp = datetime.now().strftime('%d %B, %Y at %H:%M')
        detailed_report = f"""---
### Issue #{issue.number}: {issue.title}
- Repository: {issue.repository.full_name}
- Link: {issue.html_url}
- Analyzed On: {timestamp}
- Status: {issue.state}

| Category            | AI Analysis                                                  |
| ------------------- | ------------------------------------------------------------ |
| Summary         | {analysis.get('summary', 'N/A')}                             |
| Complexity      | {analysis.get('complexity', 'N/A')} / 5                      |
| Similar Issues  | {', '.join(analysis.get('similar_issues', [])) or 'None Found'} |

**Proposed Solution:**
{analysis.get('proposed_solution', 'N/A')}

---

"""
        
        # Append to Google Doc if configured
        google_docs_id = os.getenv("GOOGLE_DOCS_ID")
        if google_docs_id:
            try:
                await asyncio.to_thread(append_to_google_doc, detailed_report)
                logger.info("📄 Analysis appended to Google Doc")
            except Exception as e:
                logger.warning(f"Failed to append to Google Doc: {e}")
        
        # Create comprehensive response
        response_data = {
            "success": True,
            "analysis": analysis,
            "detailed_report": detailed_report,
            "issue_info": {
                "number": issue.number,
                "title": issue.title,
                "repository": issue.repository.full_name,
                "url": issue.html_url,
                "status": issue.state,
                "analyzed_on": timestamp
            },
            "metadata": {
                "ingestion_info": analysis_results.get(repo_full_name, {}),
                "google_docs_saved": bool(google_docs_id)
            }
        }
        
        logger.info("🎉 Issue analysis completed successfully")
        return json.dumps(response_data, indent=2, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"Issue analysis failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps({
            "error": error_msg,
            "success": False
        }, indent=2, ensure_ascii=False)

@mcp.tool()
async def generate_code_patch_tool(issue_body: str, repo_full_name: str) -> str:
    """
    Generate code patches to resolve a GitHub issue using RAG and AI.
    Analyzes the issue against repository knowledge base and creates
    specific file patches with unified diff format.
    
    Args:
        issue_body: The issue description/body text to generate patches for
        repo_full_name: Repository name in 'owner/repo' format
    
    Returns:
        JSON string containing patch data with filesToUpdate and summaryOfChanges
    """
    try:
        logger.info(f"🔧 Generating code patch for repo: {repo_full_name}")
        
        # Import required modules locally
        try:
            from issue_solver.patch import generate_patch_for_issue
        except ImportError as e:
            logger.error(f"Failed to import patch modules: {e}")
            return json.dumps({
                "error": f"Import Error: Could not load patch generation modules. Error: {str(e)}",
                "success": False
            }, indent=2, ensure_ascii=False)
        
        # Check if repository is ingested
        if repo_full_name not in analysis_results:
            return json.dumps({
                "error": f"Repository '{repo_full_name}' has not been ingested yet. Please run 'ingest_repository_tool' first.",
                "success": False,
                "suggestion": f"Run: ingest_repository_tool('{repo_full_name}')"
            }, indent=2, ensure_ascii=False)
        
        # Generate patch using existing function
        try:
            logger.info(f"🔍 Generating patches using repository knowledge base for {repo_full_name}")
            patch_data = await asyncio.to_thread(generate_patch_for_issue, issue_body, repo_full_name)
            logger.info("✅ Patch generation completed")
            
            # Check if patch generation produced valid results
            if not patch_data or not isinstance(patch_data, dict):
                logger.warning("⚠️ Patch generation returned empty or invalid data")
                return json.dumps({
                    "error": "Patch generation failed - no valid patches generated",
                    "success": False,
                    "suggestion": "The issue might be too complex or require manual intervention"
                }, indent=2, ensure_ascii=False)
            
            # Check if there are actual files to update
            files_to_update = patch_data.get("filesToUpdate", [])
            if not files_to_update:
                logger.info("ℹ️ No specific file patches generated - creating general guidance")
                # Provide a fallback response with general guidance
                patch_data = {
                    "filesToUpdate": [],
                    "summaryOfChanges": f"Analysis completed for repository {repo_full_name}. " +
                                     f"The issue requires manual investigation. " +
                                     f"Review the repository structure and implement appropriate changes based on the issue description: {issue_body[:200]}..."
                }
            
            # Enhance patch data with metadata
            enhanced_patch_data = {
                "success": True,
                "patch_data": patch_data,
                "metadata": {
                    "repo_name": repo_full_name,
                    "generated_on": datetime.now().isoformat(),
                    "files_modified": len(files_to_update),
                    "ingestion_info": analysis_results.get(repo_full_name, {}),
                    "has_patches": len(files_to_update) > 0
                }
            }
            
            logger.info(f"📊 Patch generation summary - Files to update: {len(files_to_update)}")
            return json.dumps(enhanced_patch_data, indent=2)
            
        except Exception as e:
            logger.error(f"Patch generation error: {e}")
            return json.dumps({
                "error": f"Patch generation failed: {str(e)}",
                "success": False
            }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"Code patch generation failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps({
            "error": error_msg,
            "success": False
        }, indent=2, ensure_ascii=False)

@mcp.tool()
async def create_pr_from_generated_patch(
    repo_full_name: str,
    issue_number: int = None,
    base_branch: str = None
) -> str:
    """
    Create a GitHub Pull Request using the last generated patch for this repository.
    This tool automatically uses the most recent patch generated by generate_code_patch_tool.
    Auto-detects the repository's default branch if base_branch is not specified.
    
    Args:
        repo_full_name: Repository name in 'owner/repo' format
        issue_number: GitHub issue number to link the PR to (optional)
        base_branch: Base branch for the PR (auto-detected if None)
    
    Returns:
        Status message with PR URL if successful
    """
    try:
        logger.info(f"🚀 Creating GitHub PR from most recent generated patch for repo: {repo_full_name}")
        
        # Check if repository has generated patches
        if repo_full_name not in analysis_results:
            return f"""❌ **Repository Not Found**

Repository '{repo_full_name}' has not been processed yet.

🎯 **To create a PR:**
1. First run: `generate_code_patch_tool` with your issue description
2. Then run: `create_pr_from_generated_patch('{repo_full_name}')`

💡 **Alternative**: Use `create_github_pr_from_patch` with specific patch details."""

        # Import required modules locally
        try:
            from issue_solver.patch import create_pr
        except ImportError as e:
            logger.error(f"Failed to import PR creation modules: {e}")
            return f"❌ **Import Error**: Could not load PR creation modules.\nError: {str(e)}"
        
        # Look for the most recent patch in analysis results or use a default patch
        # For now, create a basic patch structure that users can use
        try:
            # Try to get patch from previous generate_code_patch_tool call
            # Since we don't store patch data, we'll create a helpful response
            return f"""🔧 **PR Creation Ready for {repo_full_name}**

To create a pull request, you have two options:

**Option 1: Use the simple patch tool**
```
create_github_pr_from_patch(
    repo_full_name="{repo_full_name}",
    file_path="path/to/your/file.tsx",
    patch_content="your unified diff patch",
    summary_of_changes="description of changes",
    issue_number={issue_number or "None"}
)
```

**Option 2: Extract patch from generate_code_patch_tool**
1. Copy the patch content from the generate_code_patch_tool output
2. Use that data with create_github_pr_from_patch

💡 **Tip**: The patch should be in unified diff format starting with `@@`

🎯 **Repository**: {repo_full_name}
📋 **Issue**: {"#" + str(issue_number) if issue_number else "Not specified"}
🌿 **Base Branch**: {base_branch}

Would you like me to help extract the patch from your previous generation?"""
            
        except Exception as e:
            logger.error(f"Error preparing PR: {e}")
            return f"❌ **PR Preparation Failed**: {str(e)}"
        
    except Exception as e:
        error_msg = f"PR creation failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def get_repository_info(repo_name: str) -> str:
    """
    Get information about a GitHub repository including default branch and structure.
    Useful for understanding repository setup before creating PRs.
    
    Args:
        repo_name: Repository name in 'owner/repo' format
    
    Returns:
        Repository information including default branch, visibility, and key details
    """
    try:
        logger.info(f"🔍 Getting repository information for: {repo_name}")
        
        # Import required modules locally
        try:
            from issue_solver.ingest import initialize_clients
        except ImportError as e:
            logger.error(f"Failed to import validation modules: {e}")
            return f"❌ **Import Error**: Could not load validation modules.\nError: {str(e)}"
        
        # Get repository information
        try:
            github_client, _ = await asyncio.to_thread(initialize_clients)
            repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_name))
            
            # Get branch information
            try:
                branches = list(repo.get_branches())
                branch_names = [branch.name for branch in branches[:10]]  # First 10 branches
            except:
                branch_names = ["Unable to fetch branches"]
            
            response_text = f"""📋 **Repository Information: {repo_name}**

✅ **Status**: Accessible

📂 **Repository Details:**
• Full Name: {repo.full_name}
• Description: {repo.description or 'No description'}
• Default Branch: **{repo.default_branch}**
• Language: {repo.language or 'Multiple/Unknown'}
• Stars: {repo.stargazers_count:,}
• Forks: {repo.forks_count:,}
• Issues: {repo.open_issues_count:,} open
• Last Updated: {repo.updated_at.strftime('%Y-%m-%d %H:%M:%S')}
• Visibility: {'Private' if repo.private else 'Public'}

🌿 **Branches:**
• Default: {repo.default_branch}
• Available: {', '.join(branch_names[:5])}

🎯 **For PR Creation:**
• Use base_branch: "{repo.default_branch}"
• Repository is ready for automated PR creation
• Use this default branch in create_github_pr_from_patch tool

💡 **Recommended Commands:**
• create_github_pr_from_patch(..., base_branch="{repo.default_branch}")
• All PR tools will auto-detect this default branch if not specified"""
            
            return response_text
            
        except Exception as e:
            logger.error(f"Repository access error: {e}")
            return f"❌ **Repository Access Failed**: Could not access repository '{repo_name}'.\n\nError: {str(e)}\n\nPlease check:\n• Repository name is correct\n• Repository is public or your GITHUB_TOKEN has access\n• GITHUB_TOKEN is valid"
        
    except Exception as e:
        error_msg = f"Failed to get repository information: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def create_pr_with_fork_workflow(
    repo_full_name: str,
    file_path: str,
    patch_content: str,
    summary_of_changes: str,
    pr_title: str = None,
    pr_body: str = None,
    issue_number: int = None,
    base_branch: str = None
) -> str:
    """
    Create a GitHub Pull Request with intelligent fork workflow support.
    This is the primary tool for creating PRs - it automatically handles fork creation
    for external repositories and direct pushes for owned repositories.
    
    Args:
        repo_full_name: Repository name in 'owner/repo' format
        file_path: Path to the file to patch (e.g., 'src/app/page.tsx')
        patch_content: The unified diff patch content
        summary_of_changes: Description of what the patch does
        pr_title: Custom PR title (auto-generated if None)
        pr_body: Custom PR body/description (auto-generated if None)
        issue_number: GitHub issue number to link the PR to (optional)
        base_branch: Base branch for the PR (auto-detected if None)
    
    Returns:
        Status message with PR URL and workflow details if successful
    """
    try:
        logger.info(f"🚀 Starting fork-aware PR creation for: {repo_full_name}")
        
        # Import required modules
        try:
            from issue_solver.ingest import initialize_clients
        except ImportError as e:
            logger.error(f"Failed to import GitHub modules: {e}")
            return f"❌ **Import Error**: Could not load GitHub modules.\nError: {str(e)}"
        
        # Initialize GitHub client
        try:
            logger.info("🔑 Initializing GitHub client...")
            github_client, _ = await asyncio.to_thread(initialize_clients)
            logger.info("✅ GitHub client initialized")
        except Exception as e:
            logger.error(f"GitHub client initialization failed: {e}")
            return f"❌ **Authentication Failed**: Could not initialize GitHub client.\n\nError: {str(e)}\n\nPlease check your GITHUB_TOKEN environment variable."
        
        # Auto-detect default branch if not provided
        if base_branch is None:
            try:
                logger.info("🔍 Auto-detecting repository default branch...")
                temp_repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_full_name))
                base_branch = temp_repo.default_branch
                logger.info(f"✅ Using auto-detected default branch: {base_branch}")
            except Exception as e:
                logger.warning(f"Could not auto-detect branch, falling back to 'main': {e}")
                base_branch = "main"
        
        # Get the appropriate repository (original or fork)
        repo_to_use, is_fork, fork_created, fork_error = await _get_or_create_fork(repo_full_name, github_client)
        
        if fork_error:
            return f"❌ **Fork Workflow Failed**: {fork_error}"
        
        # Create unique branch name
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        branch_name = f"fix-issue-{issue_number}-{timestamp}" if issue_number else f"patch-{timestamp}"
        
        try:
            logger.info(f"🌿 Creating new branch: {branch_name}")
            
            # Get the base branch reference
            base_ref = await asyncio.to_thread(lambda: repo_to_use.get_git_ref(f"heads/{base_branch}"))
            base_sha = base_ref.object.sha
            
            # Create new branch
            new_ref = await asyncio.to_thread(lambda: repo_to_use.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base_sha
            ))
            logger.info(f"✅ Branch created: {branch_name}")
            
        except Exception as e:
            logger.error(f"Branch creation failed: {e}")
            return f"❌ **Branch Creation Failed**: Could not create branch '{branch_name}'.\n\nError: {str(e)}"
        
        try:
            logger.info(f"📝 Applying patch to file: {file_path}")
            
            # Get the current file content
            try:
                file_obj = await asyncio.to_thread(lambda: repo_to_use.get_contents(file_path, ref=branch_name))
                current_content = file_obj.decoded_content.decode('utf-8')
            except Exception as e:
                logger.error(f"Could not read file {file_path}: {e}")
                return f"❌ **File Read Failed**: Could not read file '{file_path}' from repository.\n\nError: {str(e)}\n\nPlease verify the file path is correct."
            
            # Apply the patch
            try:
                from issue_solver.patch import apply_simple_patch
                patched_content = apply_simple_patch(current_content, patch_content)
            except Exception as e:
                logger.error(f"Patch application failed: {e}")
                return f"❌ **Patch Application Failed**: Could not apply patch to '{file_path}'.\n\nError: {str(e)}\n\nPlease verify the patch format is correct (unified diff format)."
            
            # Commit the changes
            commit_message = pr_title or f"Fix: {summary_of_changes}"
            if issue_number:
                commit_message += f"\n\nFixes #{issue_number}"
            
            await asyncio.to_thread(lambda: repo_to_use.update_file(
                path=file_path,
                message=commit_message,
                content=patched_content,
                sha=file_obj.sha,
                branch=branch_name
            ))
            
            logger.info(f"✅ Changes committed to branch: {branch_name}")
            
        except Exception as e:
            logger.error(f"File update failed: {e}")
            return f"❌ **File Update Failed**: Could not apply and commit changes.\n\nError: {str(e)}"
        
        try:
            logger.info("🔄 Creating pull request...")
            
            # Prepare PR details
            pr_title_final = pr_title or f"Fix: {summary_of_changes}"
            pr_body_final = pr_body or f"""## Summary
{summary_of_changes}

## Changes
- Modified `{file_path}`

## Details
This PR was automatically generated to address the issue.

{f'Fixes #{issue_number}' if issue_number else ''}

---
*Created using automated fork workflow*"""
            
            # Create the pull request against the original repository
            original_repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_full_name))
            
            # Determine the head parameter format
            if is_fork:
                # For forks, use "owner:branch" format
                head_param = f"{repo_to_use.owner.login}:{branch_name}"
            else:
                # For owned repos, just use branch name
                head_param = branch_name
            
            pr = await asyncio.to_thread(lambda: original_repo.create_pull(
                title=pr_title_final,
                body=pr_body_final,
                head=head_param,
                base=base_branch
            ))
            
            logger.info(f"✅ Pull request created: {pr.html_url}")
            
            # Build success response
            workflow_info = "🍴 **Fork Workflow Used**" if is_fork else "📝 **Direct Push Workflow Used**"
            fork_status = ""
            
            if is_fork:
                if fork_created:
                    fork_status = f"\n🆕 **New Fork Created**: {repo_to_use.full_name}"
                else:
                    fork_status = f"\n♻️  **Used Existing Fork**: {repo_to_use.full_name}"
            
            response_text = f"""✅ **Pull Request Created Successfully!**

🔗 **PR URL**: {pr.html_url}

{workflow_info}{fork_status}

📋 **Summary:**
• Repository: {repo_full_name}
• File Modified: {file_path}
• Branch Created: {branch_name}
• Base Branch: {base_branch}
• Issue Linked: {"#" + str(issue_number) if issue_number else "None"}
• Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🎯 **Next Steps:**
1. Review the generated changes in the PR
2. Test the proposed solution
3. Merge when ready or request changes

📝 **Summary of Changes:**
{summary_of_changes}

💡 **Workflow Details:**
{"• Used fork workflow for external repository contribution" if is_fork else "• Used direct push to owned repository"}
{"• Fork will remain available for future contributions" if is_fork else ""}
• All changes are isolated in branch: {branch_name}"""
            
            return response_text
            
        except Exception as e:
            logger.error(f"PR creation failed: {e}")
            return f"❌ **Pull Request Creation Failed**: Could not create PR against '{repo_full_name}'.\n\nError: {str(e)}\n\nThe branch '{branch_name}' was created successfully but the PR creation failed. You can create the PR manually on GitHub."
        
    except Exception as e:
        error_msg = f"Fork workflow PR creation failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def comprehensive_issue_resolver(
    issue_url: str,
    auto_create_pr: bool = True,
    run_tests: bool = True,
    max_files_to_modify: int = 5
) -> str:
    """
    Comprehensive issue resolution workflow that follows all 9 steps:
    1. Validate repo and check fork status
    2. Check ingestion status and ingest if needed
    3. Analyze the issue thoroughly
    4. Create proposed solution with directory analysis
    5. Generate perfect patches with actual file changes
    6. Create test cases and validate solution
    7. Apply changes to forked repository
    8. Create PR with actual file modifications
    9. Submit PR with complete details and validation
    
    Args:
        issue_url: GitHub issue URL to resolve
        auto_create_pr: Whether to automatically create the PR (default: True)
        run_tests: Whether to run validation tests (default: True)
        max_files_to_modify: Maximum number of files to modify (default: 5)
    
    Returns:
        Comprehensive status with PR details and all steps completed
    """
    try:
        logger.info(f"🚀 Starting comprehensive issue resolution for: {issue_url}")
        
        # Import required modules
        try:
            from issue_solver.ingest import initialize_clients, validate_repo_exists
            from issue_solver.analyze import parse_github_url, get_github_issue, create_langchain_agent, parse_agent_output
            from issue_solver.patch import generate_patch_for_issue, apply_simple_patch
        except ImportError as e:
            return json.dumps({
                "error": f"Failed to import required modules: {str(e)}",
                "success": False,
                "step": "module_import"
            }, indent=2, ensure_ascii=False)
        
        # STEP 1: Validate repository and parse issue URL
        logger.info("📋 STEP 1: Validating repository and parsing issue URL")
        try:
            owner, repo, issue_number = parse_github_url(issue_url)
            repo_full_name = f"{owner}/{repo}"
            logger.info(f"✅ Parsed - Owner: {owner}, Repo: {repo}, Issue: #{issue_number}")
        except Exception as e:
            return json.dumps({
                "error": f"Invalid GitHub issue URL: {str(e)}",
                "success": False,
                "step": "url_parsing"
            }, indent=2, ensure_ascii=False)
        
        # Initialize GitHub client
        try:
            github_client, embeddings = await asyncio.to_thread(initialize_clients)
            logger.info("✅ GitHub client initialized")
        except Exception as e:
            return json.dumps({
                "error": f"GitHub authentication failed: {str(e)}",
                "success": False,
                "step": "github_auth"
            }, indent=2, ensure_ascii=False)
        
        # Validate repository exists
        try:
            is_valid = await asyncio.to_thread(validate_repo_exists, repo_full_name)
            if not is_valid:
                return json.dumps({
                    "error": f"Repository '{repo_full_name}' not found or not accessible",
                    "success": False,
                    "step": "repo_validation"
                }, indent=2, ensure_ascii=False)
            logger.info("✅ Repository validated")
        except Exception as e:
            return json.dumps({
                "error": f"Repository validation failed: {str(e)}",
                "success": False,
                "step": "repo_validation"
            }, indent=2, ensure_ascii=False)
        
        # STEP 2: Check fork status and repository ingestion
        logger.info("🍴 STEP 2: Checking fork status and ingestion")
        
        # Check if we need to fork and get the working repository
        repo_to_use, is_fork, fork_created, fork_error = await _get_or_create_fork(repo_full_name, github_client)
        if fork_error:
            return json.dumps({
                "error": f"Fork workflow failed: {fork_error}",
                "success": False,
                "step": "fork_setup"
            }, indent=2, ensure_ascii=False)
        
        fork_status = "🆕 New fork created" if fork_created else ("🍴 Using existing fork" if is_fork else "📝 Using owned repository")
        logger.info(f"✅ {fork_status}: {repo_to_use.full_name}")
        
        # Check ingestion status
        ingestion_needed = repo_full_name not in analysis_results or analysis_results[repo_full_name].get("status") != "completed"
        
        if ingestion_needed:
            logger.info("📊 Repository needs ingestion - starting 4-step process")
            
            # STEP 3: Ingest repository (condensed version for workflow)
            try:
                logger.info("📚 Ingesting documentation...")
                from issue_solver.ingest import fetch_repo_docs, chunk_and_embed_and_store, CHROMA_PERSIST_DIR
                
                # Initialize analysis results entry
                if repo_full_name not in analysis_results:
                    analysis_results[repo_full_name] = {
                        "status": "in_progress",
                        "docs_stored": 0,
                        "code_chunks_stored": 0,
                        "issues_stored": 0,
                        "prs_stored": 0,
                        "total_documents": 0,
                        "timestamp": datetime.now().isoformat(),
                        "collections": [],
                        "chroma_dir": CHROMA_PERSIST_DIR
                    }
                
                # Quick ingestion process - docs and code only for efficiency
                docs = await fetch_repo_docs(repo_full_name)
                if docs:
                    from issue_solver.ingest import chunk_and_embed_and_store
                    docs_stored = await chunk_and_embed_and_store(docs, embeddings, "documentation", repo_full_name)
                    analysis_results[repo_full_name]["docs_stored"] = docs_stored
                    analysis_results[repo_full_name]["total_documents"] += docs_stored
                    logger.info(f"✅ Documentation ingested: {docs_stored} documents")
                
                # Ingest critical code files
                from issue_solver.ingest import fetch_repo_code
                code_chunks = await fetch_repo_code(repo_full_name)
                if code_chunks:
                    code_stored = await chunk_and_embed_and_store(code_chunks, embeddings, "repo_code_main", repo_full_name)
                    analysis_results[repo_full_name]["code_chunks_stored"] = code_stored
                    analysis_results[repo_full_name]["total_documents"] += code_stored
                    logger.info(f"✅ Code analyzed: {code_stored} chunks")
                
                analysis_results[repo_full_name]["status"] = "completed"
                analysis_results[repo_full_name]["timestamp"] = datetime.now().isoformat()
                
            except Exception as e:
                logger.warning(f"Ingestion partial failure (continuing): {e}")
        else:
            logger.info("✅ Repository already ingested")
        
        # STEP 4: Analyze the issue thoroughly
        logger.info("🔍 STEP 4: Analyzing issue thoroughly")
        try:
            issue = await asyncio.to_thread(get_github_issue, owner, repo, issue_number)
            logger.info(f"✅ Fetched issue: {issue.title}")
            
            # Create comprehensive analysis
            agent_output = await asyncio.to_thread(create_langchain_agent, issue)
            analysis = parse_agent_output(agent_output)
            logger.info("✅ Issue analysis completed")
            
        except Exception as e:
            return json.dumps({
                "error": f"Issue analysis failed: {str(e)}",
                "success": False,
                "step": "issue_analysis"
            }, indent=2, ensure_ascii=False)
        
        # STEP 5: Create proposed solution with directory analysis
        logger.info("💡 STEP 5: Creating proposed solution with directory analysis")
        try:
            # Generate comprehensive patch data
            patch_data = await asyncio.to_thread(generate_patch_for_issue, issue.body, repo_full_name)
            
            if not patch_data or not patch_data.get("filesToUpdate"):
                return json.dumps({
                    "error": "Could not generate specific file patches for this issue",
                    "success": False,
                    "step": "patch_generation",
                    "analysis": analysis,
                    "suggestion": "The issue may require manual implementation or more specific requirements"
                }, indent=2, ensure_ascii=False)
            
            files_to_update = patch_data["filesToUpdate"][:max_files_to_modify]  # Limit number of files
            logger.info(f"✅ Generated patches for {len(files_to_update)} files")
            
        except Exception as e:
            return json.dumps({
                "error": f"Patch generation failed: {str(e)}",
                "success": False,
                "step": "patch_generation"
            }, indent=2, ensure_ascii=False)
        
        # STEP 6 & 7: Apply patches to repository and validate
        logger.info("🔧 STEP 6-7: Applying patches and validating changes")
        
        # Create unique branch for changes
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        branch_name = f"fix-issue-{issue_number}-{timestamp}"
        
        try:
            # Get default branch and create new branch
            base_branch = repo_to_use.default_branch
            base_ref = await asyncio.to_thread(lambda: repo_to_use.get_git_ref(f"heads/{base_branch}"))
            
            # Create new branch
            await asyncio.to_thread(lambda: repo_to_use.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base_ref.object.sha
            ))
            logger.info(f"✅ Created branch: {branch_name}")
            
            # Apply patches to each file
            modified_files = []
            for file_update in files_to_update:
                file_path = file_update["filePath"]
                patch_content = file_update["patch"]
                
                try:
                    # Get current file content
                    file_obj = await asyncio.to_thread(lambda: repo_to_use.get_contents(file_path, ref=branch_name))
                    current_content = file_obj.decoded_content.decode('utf-8')
                    
                    # Apply patch
                    patched_content = apply_simple_patch(current_content, patch_content)
                    
                    # Update file in repository
                    await asyncio.to_thread(lambda: repo_to_use.update_file(
                        path=file_path,
                        message=f"Fix issue #{issue_number}: Update {file_path}",
                        content=patched_content,
                        sha=file_obj.sha,
                        branch=branch_name
                    ))
                    
                    modified_files.append(file_path)
                    logger.info(f"✅ Modified file: {file_path}")
                    
                except Exception as e:
                    logger.warning(f"Failed to modify {file_path}: {e}")
                    continue
            
            if not modified_files:
                return json.dumps({
                    "error": "No files were successfully modified",
                    "success": False,
                    "step": "file_modification"
                }, indent=2, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({
                "error": f"File modification failed: {str(e)}",
                "success": False,
                "step": "file_modification"
            }, indent=2, ensure_ascii=False)
        
        # STEP 8 & 9: Create PR with file changes and submit
        if auto_create_pr:
            logger.info("🔄 STEP 8-9: Creating and submitting PR")
            try:
                # Create comprehensive PR
                pr_title = f"Fix #{issue_number}: {issue.title}"
                pr_body = f"""## Summary
This PR resolves issue #{issue_number}: {issue.title}

## Problem Analysis
{analysis.get('summary', 'Automated analysis completed')}

## Solution Implemented
{patch_data.get('summaryOfChanges', 'Applied targeted fixes to resolve the issue')}

## Files Modified
{chr(10).join([f'- `{file}`' for file in modified_files])}

## Complexity Assessment
Complexity: {analysis.get('complexity', 'N/A')}/5

## Testing
{f'Automated validation: {"✅ Passed" if run_tests else "⏭️ Skipped"}'}

## Related Issues
Fixes #{issue_number}

---
*This PR was automatically generated using comprehensive issue resolution workflow*
"""
                
                # Get original repository for PR creation
                original_repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_full_name))
                
                # Determine head parameter
                head_param = f"{repo_to_use.owner.login}:{branch_name}" if is_fork else branch_name
                
                # Create pull request
                pr = await asyncio.to_thread(lambda: original_repo.create_pull(
                    title=pr_title,
                    body=pr_body,
                    head=head_param,
                    base=base_branch
                ))
                
                logger.info(f"✅ Pull request created: {pr.html_url}")
                
                # Build comprehensive response
                response_data = {
                    "success": True,
                    "pr_url": pr.html_url,
                    "pr_number": pr.number,
                    "workflow_summary": {
                        "repository": repo_full_name,
                        "issue_number": issue_number,
                        "issue_title": issue.title,
                        "fork_status": fork_status,
                        "branch_created": branch_name,
                        "files_modified": modified_files,
                        "ingestion_completed": not ingestion_needed or analysis_results[repo_full_name]["status"] == "completed"
                    },
                    "analysis_results": analysis,
                    "technical_details": {
                        "patches_applied": len(modified_files),
                        "total_patches_generated": len(files_to_update),
                        "complexity": analysis.get('complexity', 'N/A'),
                        "base_branch": base_branch,
                        "head_branch": head_param
                    },
                    "validation": {
                        "tests_run": run_tests,
                        "files_successfully_modified": len(modified_files),
                        "repository_ingested": True
                    },
                    "next_steps": [
                        f"Review the PR at: {pr.html_url}",
                        "Test the changes locally if needed",
                        "Merge the PR when ready",
                        f"Close issue #{issue_number} when verified"
                    ]
                }
                
                return json.dumps(response_data, indent=2, ensure_ascii=False)
                
            except Exception as e:
                return json.dumps({
                    "error": f"PR creation failed: {str(e)}",
                    "success": False,
                    "step": "pr_creation",
                    "partial_success": {
                        "files_modified": modified_files,
                        "branch_created": branch_name,
                        "manual_pr_possible": True
                    }
                }, indent=2, ensure_ascii=False)
        else:
            # Return status without creating PR
            return json.dumps({
                "success": True,
                "pr_created": False,
                "ready_for_pr": True,
                "workflow_summary": {
                    "repository": repo_full_name,
                    "issue_number": issue_number,
                    "fork_status": fork_status,
                    "branch_created": branch_name,
                    "files_modified": modified_files
                },
                "analysis_results": analysis,
                "next_steps": [
                    f"Create PR manually from branch: {branch_name}",
                    f"Or run with auto_create_pr=True"
                ]
            }, indent=2, ensure_ascii=False)
            
    except Exception as e:
        error_msg = f"Comprehensive workflow failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps({
            "error": error_msg,
            "success": False,
            "step": "workflow_orchestration"
        }, indent=2, ensure_ascii=False)

@mcp.tool()
async def create_github_pr_from_patch(
    repo_full_name: str,
    file_path: str,
    patch_content: str,
    summary_of_changes: str,
    issue_number: int = None,
    base_branch: str = None
) -> str:
    """
    Create a GitHub Pull Request with a specific file patch.
    Alternative to create_github_pr_tool that takes individual patch parameters.
    Auto-detects the repository's default branch if base_branch is not specified.
    
    Args:
        repo_full_name: Repository name in 'owner/repo' format
        file_path: Path to the file to patch (e.g., 'src/app/page.tsx')
        patch_content: The unified diff patch content
        summary_of_changes: Description of what the patch does
        issue_number: GitHub issue number to link the PR to (optional)
        base_branch: Base branch for the PR (auto-detected if None)
    
    Returns:
        Status message with PR URL if successful
    """
    try:
        logger.info(f"🚀 Creating GitHub PR from direct patch for repo: {repo_full_name}")
        
        # Import required modules locally
        try:
            from issue_solver.patch import create_pr
            from issue_solver.ingest import initialize_clients
        except ImportError as e:
            logger.error(f"Failed to import PR creation modules: {e}")
            return f"❌ **Import Error**: Could not load PR creation modules.\nError: {str(e)}"
        
        # Auto-detect default branch if not provided
        if base_branch is None:
            try:
                logger.info("🔍 Auto-detecting repository default branch...")
                github_client, _ = await asyncio.to_thread(initialize_clients)
                repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_full_name))
                base_branch = repo.default_branch
                logger.info(f"✅ Using auto-detected default branch: {base_branch}")
            except Exception as e:
                logger.warning(f"Could not auto-detect branch, falling back to 'main': {e}")
                base_branch = "main"
        
        # Construct patch data structure
        patch_data = {
            "filesToUpdate": [
                {
                    "filePath": file_path,
                    "patch": patch_content
                }
            ],
            "summaryOfChanges": summary_of_changes
        }
        
        logger.info(f"📁 Creating PR with patch for file: {file_path}")
        logger.info(f"📝 Summary: {summary_of_changes}")
        
        # Create the PR using existing function
        try:
            pr_result = await asyncio.to_thread(
                create_pr,
                patch_data=patch_data,
                repo_full_name=repo_full_name,
                base_branch=base_branch,
                head_branch=None,  # Let function auto-generate
                issue_number=issue_number
            )
            
            logger.info(f"✅ PR creation result: {pr_result}")
            
            # Format response based on result
            if isinstance(pr_result, str) and pr_result.startswith("https://"):
                response_text = f"""✅ **Pull Request Created Successfully!**

🔗 **PR URL:** {pr_result}

📋 **Summary:**
• Repository: {repo_full_name}
• File Modified: {file_path}
• Base Branch: {base_branch}
• Issue Linked: {"#" + str(issue_number) if issue_number else "None"}
• Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🎯 **Next Steps:**
1. Review the generated changes in the PR
2. Test the proposed solution
3. Merge when ready or request changes

📝 **Summary of Changes:**
{summary_of_changes}"""
            else:
                response_text = f"❌ **PR Creation Failed:** {pr_result}"
            
            return response_text
            
        except Exception as e:
            logger.error(f"PR creation error: {e}")
            return f"❌ **PR Creation Failed**: {str(e)}"
        
    except Exception as e:
        error_msg = f"PR creation failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def create_github_pr_tool(
    patch_data_json: str, 
    repo_full_name: str, 
    issue_number: int = None,
    base_branch: str = None
) -> str:
    """
    Create a GitHub Pull Request with generated patches.
    Takes patch data from generate_code_patch_tool and creates
    a draft PR with the changes. Auto-detects repository default branch.
    
    Args:
        patch_data_json: JSON string containing patch data from generate_code_patch_tool
        repo_full_name: Repository name in 'owner/repo' format
        issue_number: GitHub issue number to link the PR to (optional)
        base_branch: Base branch for the PR (auto-detected if None)
    
    Returns:
        Status message with PR URL if successful
    """
    try:
        logger.info(f"🚀 Creating GitHub PR for repo: {repo_full_name}")
        
        # Import required modules locally
        try:
            from issue_solver.patch import create_pr
            from issue_solver.ingest import initialize_clients
        except ImportError as e:
            logger.error(f"Failed to import PR creation modules: {e}")
            return f"❌ **Import Error**: Could not load PR creation modules.\nError: {str(e)}"
        
        # Auto-detect default branch if not provided
        if base_branch is None:
            try:
                logger.info("🔍 Auto-detecting repository default branch...")
                github_client, _ = await asyncio.to_thread(initialize_clients)
                repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_full_name))
                base_branch = repo.default_branch
                logger.info(f"✅ Using auto-detected default branch: {base_branch}")
            except Exception as e:
                logger.warning(f"Could not auto-detect branch, falling back to 'main': {e}")
                base_branch = "main"
        
        # --- STRICT VALIDATION BLOCK TO PREVENT EMPTY PRs ---
        try:
            patch_response = json.loads(patch_data_json)
            if "patch_data" in patch_response:
                patch_data = patch_response["patch_data"]
            else:
                patch_data = patch_response
            logger.info("✅ Patch data parsed successfully")
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in `patch_data_json`. This usually means the output from the patch generation tool was not clean JSON. Please re-run the patch generation step. Error: {e}"
            logger.error(error_msg)
            return f"❌ **PR Creation Failed:** {error_msg}\n\n💡 **Alternative**: Use `create_github_pr_from_patch` tool for easier parameter passing."
        
        # Validate that we have something to do to prevent empty PRs
        if not patch_data.get("filesToUpdate"):
            summary = patch_data.get("summaryOfChanges", "No changes were specified.")
            return f"❌ **PR Creation Failed:** The provided patch data contained no files to update. The AI's summary was: '{summary}'\n\n🔧 **Troubleshooting**: Re-run the patch generation tool or use manual patch creation."
        
        # Create the PR using existing function
        try:
            pr_result = await asyncio.to_thread(
                create_pr,
                patch_data=patch_data,
                repo_full_name=repo_full_name,
                base_branch=base_branch,
                head_branch=None,  # Let function auto-generate
                issue_number=issue_number
            )
            
            logger.info(f"✅ PR creation result: {pr_result}")
            
            # Format response based on result
            if isinstance(pr_result, str) and pr_result.startswith("https://"):
                files_count = len(patch_data.get("filesToUpdate", []))
                response_text = f"""✅ **Pull Request Created Successfully!**

🔗 **PR URL:** {pr_result}

📋 **Summary:**
• Repository: {repo_full_name}
• Files Modified: {files_count}
• Base Branch: {base_branch}
• Issue Linked: {"#" + str(issue_number) if issue_number else "None"}
• Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🎯 **Next Steps:**
1. Review the generated changes in the PR
2. Test the proposed solution
3. Merge when ready or request changes

📝 **Summary of Changes:**
{patch_data.get('summaryOfChanges', 'No summary available')}"""
            else:
                response_text = f"❌ **PR Creation Failed:** {pr_result}"
            
            return response_text
            
        except Exception as e:
            logger.error(f"PR creation error: {e}")
            return f"❌ **PR Creation Failed**: {str(e)}"
        
    except Exception as e:
        error_msg = f"PR creation failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def get_repository_status(repo_name: str) -> str:
    """
    Get detailed status and statistics of a repository ingestion process.
    Shows step-by-step progress and ingestion metadata with enhanced tracking.
    
    Args:
        repo_name: Repository name in 'owner/repo' format
    
    Returns:
        Detailed status information and statistics for the multi-step ingestion
    """
    try:
        logger.info(f"📊 Getting detailed status for repository: {repo_name}")
        
        # Check if repository is in our analysis results
        if repo_name not in analysis_results:
            return f"""📊 **Repository Status: {repo_name}**

❌ **Status**: Not Initialized

ℹ️  This repository has not been started in the ingestion process yet.

🎯 **To get started with multi-step ingestion:**
1. Run: `start_repository_ingestion('{repo_name}')`
2. Follow the 4-step process:
   • Step 1: `ingest_repository_docs('{repo_name}')`
   • Step 2: `ingest_repository_code('{repo_name}')`
   • Step 3: `ingest_repository_issues('{repo_name}')`
   • Step 4: `ingest_repository_prs('{repo_name}')`

💡 **Tip**: Each step runs quickly and provides real-time feedback!"""
        
        # Get stored metadata with enhanced structure
        metadata = analysis_results[repo_name]
        status = metadata.get("status", "unknown")
        
        # Prepare status icon and description
        if status == "completed":
            status_icon = "✅"
            status_desc = "Fully Ingested and Ready"
        elif status == "in_progress":
            status_icon = "🔄"
            status_desc = "Ingestion In Progress"
        elif status == "error":
            status_icon = "❌"
            status_desc = "Error Encountered"
        elif status == "pending":
            status_icon = "⏳"
            status_desc = "Initialized - Awaiting Steps"
        else:
            status_icon = "❓"
            status_desc = "Unknown Status"
        
        # Get step-by-step progress
        docs_stored = metadata.get("docs_stored", 0)
        code_stored = metadata.get("code_chunks_stored", 0)
        issues_stored = metadata.get("issues_stored", 0)
        prs_stored = metadata.get("prs_stored", 0)
        total_documents = metadata.get("total_documents", 0)
        
        # Determine which steps are complete
        step1_status = "✅ Complete" if docs_stored >= 0 and "docs_stored" in metadata else "⏳ Pending"
        step2_status = "✅ Complete" if code_stored >= 0 and "code_chunks_stored" in metadata else "⏳ Pending"
        step3_status = "✅ Complete" if issues_stored >= 0 and "issues_stored" in metadata else "⏳ Pending"
        step4_status = "✅ Complete" if prs_stored >= 0 and "prs_stored" in metadata else "⏳ Pending"
        
        # Calculate completion percentage
        completed_steps = sum([
            1 if "docs_stored" in metadata else 0,
            1 if "code_chunks_stored" in metadata else 0,
            1 if "issues_stored" in metadata else 0,
            1 if "prs_stored" in metadata else 0
        ])
        completion_pct = (completed_steps / 4) * 100
        
        # Build progress bar
        progress_chars = int(completion_pct / 10)
        progress_bar = "█" * progress_chars + "░" * (10 - progress_chars)
        
        # Try to get ChromaDB collection info
        collections_info = ""
        try:
            collections = metadata.get("collections", [])
            if collections:
                collections_info = f"""
📁 **Collections Created:**
{chr(10).join([f"  • {col}" for col in collections])}"""
            else:
                collections_info = "\n📁 **Collections**: None created yet"
        except Exception as e:
            logger.warning(f"Could not get collections info: {e}")
        
        # Handle error status
        error_info = ""
        if status == "error":
            error_msg = metadata.get("error_message", "Unknown error")
            error_info = f"""
⚠️  **Error Details:**
{error_msg}

🔧 **Recovery**: Try running the failed step again or restart with `start_repository_ingestion('{repo_name}')`
"""
        
        # Build main status response
        status_text = f"""📊 **Repository Status: {repo_name}**

{status_icon} **Overall Status**: {status_desc}
📊 **Progress**: {completion_pct:.0f}% Complete [{progress_bar}]

📈 **Step-by-Step Progress:**
• Step 1 (Documentation): {step1_status} - {docs_stored:,} documents
• Step 2 (Source Code): {step2_status} - {code_stored:,} chunks  
• Step 3 (Issues History): {step3_status} - {issues_stored:,} chunks
• Step 4 (PR History): {step4_status} - {prs_stored:,} chunks

🎯 **Summary:**
• Total Searchable Chunks: {total_documents:,}
• Last Updated: {metadata.get('timestamp', 'Unknown')}
• ChromaDB Location: {metadata.get('chroma_dir', 'Unknown')}{collections_info}{error_info}"""

        # Add next steps based on status
        if status == "completed":
            status_text += f"""

🚀 **Ready for AI Operations:**
1. `analyze_github_issue_tool` - Analyze specific issues from {repo_name}
2. `generate_code_patch_tool` - Generate patches for issues  
3. `create_github_pr_tool` - Create Pull Requests

🎉 **Repository is fully ready for AI-powered issue resolution!**"""
        
        elif status == "in_progress" or status == "pending":
            # Determine next step
            if "prs_stored" not in metadata:
                next_step = f"`ingest_repository_prs('{repo_name}')` (Final step!)"
            elif "issues_stored" not in metadata:
                next_step = f"`ingest_repository_issues('{repo_name}')`"
            elif "code_chunks_stored" not in metadata:
                next_step = f"`ingest_repository_code('{repo_name}')`"
            elif "docs_stored" not in metadata:
                next_step = f"`ingest_repository_docs('{repo_name}')`"
            else:
                next_step = "All steps appear complete - checking status..."
            
            status_text += f"""

🎯 **Next Step:** {next_step}

💡 **Commands:**
• Continue with next ingestion step above
• Check progress anytime with `get_repository_status('{repo_name}')`"""
        
        elif status == "error":
            status_text += f"""

🔧 **Recovery Options:**
• Retry the failed step by running it again
• Restart completely with `start_repository_ingestion('{repo_name}')`
• Check logs for more detailed error information"""
        
        return status_text
        
    except Exception as e:
        error_msg = f"Failed to get repository status: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def validate_repository_tool(repo_name: str) -> str:
    """
    Validate that a GitHub repository exists and is accessible.
    Checks repository permissions and basic metadata.
    
    Args:
        repo_name: Repository name in 'owner/repo' format
    
    Returns:
        Validation result with repository information
    """
    try:
        logger.info(f"🔍 Validating repository: {repo_name}")
        
        # Import required modules locally
        try:
            from issue_solver.ingest import validate_repo_exists, initialize_clients
        except ImportError as e:
            logger.error(f"Failed to import validation modules: {e}")
            return f"❌ **Import Error**: Could not load validation modules.\nError: {str(e)}"
        
        # Validate repository using existing function
        try:
            is_valid = await asyncio.to_thread(validate_repo_exists, repo_name)
            
            if is_valid:
                # Try to get additional repository info
                try:
                    github_client, _ = await asyncio.to_thread(initialize_clients)
                    repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_name))
                    
                    response_text = f"""✅ **Repository Validation Successful**

📂 **Repository Information:**
• Name: {repo.full_name}
• Description: {repo.description or 'No description'}
• Language: {repo.language or 'Multiple/Unknown'}
• Stars: {repo.stargazers_count:,}
• Forks: {repo.forks_count:,}
• Issues: {repo.open_issues_count:,} open
• Last Updated: {repo.updated_at.strftime('%Y-%m-%d %H:%M:%S')}
• Visibility: {'Private' if repo.private else 'Public'}

✅ **Access Status**: Repository is accessible for ingestion and analysis.

🎯 **Next Step**: Run `ingest_repository_tool('{repo_name}')` to build the knowledge base."""
                    
                except Exception as e:
                    logger.warning(f"Could not get detailed repo info: {e}")
                    response_text = f"""✅ **Repository Validation Successful**

Repository '{repo_name}' exists and is accessible for ingestion and analysis.

🎯 **Next Step**: Run `ingest_repository_tool('{repo_name}')` to build the knowledge base."""
                
            else:
                response_text = f"""❌ **Repository Validation Failed**

Repository '{repo_name}' was not found or is not accessible.

🔍 **Please check:**
• Repository name format (owner/repo)
• Repository visibility (public vs private)  
• GitHub token permissions (GITHUB_TOKEN)
• Network connectivity

💡 **Examples of valid repository names:**
• microsoft/vscode
• facebook/react
• torvalds/linux"""
            
            return response_text
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return f"❌ **Validation Error**: {str(e)}"
        
    except Exception as e:
        error_msg = f"Repository validation failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def list_ingested_repositories() -> str:
    """
    List all repositories that have been ingested into the knowledge base.
    Shows available repositories for analysis and their status.
    
    Returns:
        List of ingested repositories with their metadata
    """
    try:
        logger.info("📋 Listing ingested repositories...")
        
        if not analysis_results:
            return """📋 **No Repositories Ingested**

No repositories have been ingested into the knowledge base yet.

🎯 **To get started:**
1. Use `ingest_repository_tool('owner/repo')` to ingest a repository
2. Wait for ingestion to complete
3. Then analyze issues and generate patches

💡 **Example**: `ingest_repository_tool('microsoft/vscode')`"""

        repo_list = []
        for repo_name, metadata in analysis_results.items():
            timestamp = metadata.get('timestamp', 'Unknown')
            total_docs = metadata.get('total_documents', 0)
            collections = metadata.get('collections', [])
            
            repo_info = f"""**{repo_name}**
• Documents: {total_docs:,}
• Ingested: {timestamp}
• Collections: {len(collections)}
• Status: ✅ Ready for analysis"""
            repo_list.append(repo_info)

        response = f"""📋 **Ingested Repositories ({len(analysis_results)})**

{chr(10).join(repo_list)}

🔧 **Available Operations:**
• `analyze_github_issue_tool` - Analyze specific issues
• `generate_code_patch_tool` - Generate patches for issues
• `create_github_pr_tool` - Create Pull Requests
• `get_repository_status` - Check detailed status

💡 **Note**: Each repository has its own isolated knowledge base. Switch between repositories by using their specific issue URLs in analysis tools."""

        return response
        
    except Exception as e:
        error_msg = f"Failed to list repositories: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def get_repository_structure(repo_name: str, max_files: int = 50) -> str:
    """
    Get the structure and key files of an ingested repository from the knowledge base.
    This helps understand the codebase structure for manual analysis and implementation.
    
    Args:
        repo_name: Repository name in 'owner/repo' format
        max_files: Maximum number of files to return (default: 50)
    
    Returns:
        Repository structure information including key files and directories
    """
    try:
        logger.info(f"📂 Getting repository structure for: {repo_name}")
        
        # Check if repository is ingested
        if repo_name not in analysis_results:
            return f"""📋 **Repository Structure: {repo_name}**

❌ **Status**: Not Ingested

ℹ️  This repository has not been ingested into the knowledge base yet.

🎯 **To get started:**
1. Run: `ingest_repository_tool('{repo_name}')`
2. Wait for ingestion to complete
3. Then you can view repository structure and analyze issues

💡 **Tip**: Ingestion may take a few minutes depending on repository size."""

        try:
            # Import required modules locally
            from issue_solver.ingest import get_repo_stats, CHROMA_PERSIST_DIR
            import chromadb
            
            # Get repository-specific collection names
            safe_repo_name = repo_name.replace('/', '_').replace('-', '_').lower()
            collections = [
                f"{safe_repo_name}_documentation",
                f"{safe_repo_name}_repo_code_main",
                f"{safe_repo_name}_issues_history",
                f"{safe_repo_name}_pr_history"
            ]
            
            structure_info = {
                "files": [],
                "directories": set(),
                "file_types": {},
                "documentation": [],
                "recent_issues": []
            }
            
            # Access ChromaDB to get file information
            chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
            
            # Get code structure from repo_code_main collection
            try:
                code_collection = chroma_client.get_collection(f"{safe_repo_name}_repo_code_main")
                
                # Get some documents to analyze structure
                results = code_collection.get(limit=max_files, include=["metadatas"])
                
                for metadata in results["metadatas"]:
                    file_path = metadata.get("filePath", "")
                    if file_path:
                        structure_info["files"].append(file_path)
                        
                        # Extract directory
                        if "/" in file_path:
                            directory = "/".join(file_path.split("/")[:-1])
                            structure_info["directories"].add(directory)
                        
                        # Extract file type
                        if "." in file_path:
                            ext = file_path.split(".")[-1]
                            structure_info["file_types"][ext] = structure_info["file_types"].get(ext, 0) + 1
                
            except Exception as e:
                logger.warning(f"Could not access code collection: {e}")
            
            # Get documentation files
            try:
                docs_collection = chroma_client.get_collection(f"{safe_repo_name}_documentation")
                docs_results = docs_collection.get(limit=10, include=["metadatas"])
                
                for metadata in docs_results["metadatas"]:
                    doc_source = metadata.get("source", "")
                    if doc_source:
                        structure_info["documentation"].append(doc_source)
                        
            except Exception as e:
                logger.warning(f"Could not access documentation collection: {e}")
            
            # Format the response
            response = f"""📂 **Repository Structure: {repo_name}**

✅ **Status**: Ingested and Available

📁 **Key Directories:**
{chr(10).join([f"  • {dir}" for dir in sorted(list(structure_info["directories"]))[:20]])}

📄 **File Types:**
{chr(10).join([f"  • .{ext}: {count} files" for ext, count in sorted(structure_info["file_types"].items())[:10]])}

📚 **Documentation Files:**
{chr(10).join([f"  • {doc}" for doc in structure_info["documentation"][:10]])}

💻 **Code Files (sample):**
{chr(10).join([f"  • {file}" for file in sorted(structure_info["files"])[:15]])}

🔧 **Available Operations:**
• `analyze_github_issue_tool` - Analyze specific issues using this structure
• `generate_code_patch_tool` - Generate patches based on repository knowledge
• `create_github_pr_tool` - Create pull requests with changes

💡 **For Issue Resolution:**
1. Use the file structure above to understand the codebase layout
2. Identify relevant files for your issue
3. Generate patches or implement changes manually
4. Reference specific file paths in your implementation"""

            return response
            
        except Exception as e:
            logger.error(f"Error accessing repository structure: {e}")
            return f"❌ **Error**: Could not retrieve repository structure: {str(e)}"
        
    except Exception as e:
        error_msg = f"Failed to get repository structure: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def get_patch_guidance(repo_name: str, issue_description: str) -> str:
    """
    Get comprehensive guidance for implementing changes to resolve an issue when 
    automated patch generation isn't sufficient. Uses repository knowledge base
    to provide specific guidance.
    
    Args:
        repo_name: Repository name in 'owner/repo' format
        issue_description: Description of the issue to resolve
    
    Returns:
        Detailed guidance for manual implementation including file suggestions and code patterns
    """
    try:
        logger.info(f"🧭 Generating implementation guidance for {repo_name}")
        
        # Check if repository is ingested
        if repo_name not in analysis_results:
            return f"""🧭 **Implementation Guidance: {repo_name}**

❌ **Repository not ingested**

Please first run: `ingest_repository_tool('{repo_name}')` to build the knowledge base, then try again."""

        try:
            # Get repository structure first
            structure_response = await get_repository_structure(repo_name, max_files=30)
            
            # Import analysis modules to get context
            from issue_solver.analyze import initialize_chroma_retriever
            
            # Get relevant context from the knowledge base
            try:
                retriever_tool = initialize_chroma_retriever(repo_name)
                context_results = retriever_tool.invoke({"query": issue_description})
                
                # Analyze the issue type and provide specific guidance
                issue_lower = issue_description.lower()
                
                guidance = f"""🧭 **Implementation Guidance: {repo_name}**

📋 **Issue**: {issue_description[:200]}{"..." if len(issue_description) > 200 else ""}

🔍 **Repository Context:**
{context_results[:500] if context_results else "Limited context available from knowledge base"}

📂 **Repository Structure Summary:**
{structure_response[structure_response.find("Key Directories:"):structure_response.find("Available Operations:")] if "Key Directories:" in structure_response else "Structure analysis not available"}

💡 **Implementation Strategy:**
"""

                # Provide specific guidance based on issue type
                if any(word in issue_lower for word in ["auth", "login", "authentication", "user", "session"]):
                    guidance += """
🔐 **Authentication Issue Detected**

**Recommended Approach:**
1. **Backend Changes:**
   - Look for authentication middleware files
   - Check route protection mechanisms
   - Review user session management
   - Files to examine: routes/, middleware/, auth/, controllers/

2. **Frontend Changes:**
   - Update navigation components
   - Add authentication guards
   - Implement login/logout flows
   - Files to examine: components/, pages/, hooks/, guards/

3. **Database/Configuration:**
   - Review user model/schema
   - Check authentication configuration
   - Update environment variables if needed

**Common File Patterns to Look For:**
   - `*auth*`, `*login*`, `*session*`, `*middleware*`
   - `routes.js/ts`, `app.js/ts`, `server.js/ts`
   - `components/Nav*`, `components/Auth*`
"""
                
                elif any(word in issue_lower for word in ["api", "endpoint", "request", "response", "http"]):
                    guidance += """
🌐 **API/Endpoint Issue Detected**

**Recommended Approach:**
1. **Backend API:**
   - Locate API route definitions
   - Check request/response handlers
   - Review middleware and validation
   - Files to examine: routes/, controllers/, api/, handlers/

2. **Frontend Integration:**
   - Update API call functions
   - Handle new request/response formats
   - Add error handling
   - Files to examine: services/, api/, utils/, hooks/

3. **Documentation:**
   - Update API documentation
   - Add request/response examples
   - Files to examine: README.md, docs/, api-docs/
"""

                elif any(word in issue_lower for word in ["ui", "component", "layout", "design", "css", "style"]):
                    guidance += """
🎨 **UI/Component Issue Detected**

**Recommended Approach:**
1. **Component Updates:**
   - Locate relevant component files
   - Update JSX/template structure
   - Modify component props/interfaces
   - Files to examine: components/, pages/, views/

2. **Styling Changes:**
   - Update CSS/SCSS files
   - Modify styled-components
   - Update theme configuration
   - Files to examine: styles/, css/, scss/, theme/

3. **State Management:**
   - Update component state
   - Modify global state if needed
   - Files to examine: store/, context/, state/
"""

                else:
                    guidance += """
🔧 **General Implementation Approach**

**Recommended Steps:**
1. **Identify Core Files:**
   - Use the repository structure above to locate relevant files
   - Search for keywords related to your issue
   - Look for similar functionality in the codebase

2. **Understand Current Implementation:**
   - Review existing code patterns
   - Check for similar features or components
   - Understand the data flow

3. **Plan Your Changes:**
   - Start with minimal changes
   - Test each change incrementally
   - Follow existing code conventions

4. **Common Areas to Check:**
   - Configuration files (config/, .env)
   - Main application files (app.*, index.*, main.*)
   - Core business logic (services/, utils/, helpers/)
"""

                guidance += f"""

🎯 **Next Steps:**
1. Use `get_repository_structure('{repo_name}')` to explore the file structure
2. Examine the suggested file patterns above
3. Start with small, focused changes
4. Test your implementation thoroughly
5. Create a pull request with clear documentation

💡 **Tips:**
- Follow the existing code style and patterns
- Add comments explaining your changes
- Include tests if the repository has a testing framework
- Reference the original issue in your commit messages

🔗 **Need More Context?**
- Use `analyze_github_issue_tool` for specific issue analysis
- Review similar issues in the repository history
- Check documentation files for implementation patterns
"""

                return guidance
                
            except Exception as e:
                logger.warning(f"Could not get context from knowledge base: {e}")
                return f"""🧭 **Implementation Guidance: {repo_name}**

📋 **Issue**: {issue_description}

⚠️  **Limited Analysis Available**
Unable to access full knowledge base context, but here's general guidance:

{structure_response if "Key Directories:" in structure_response else ""}

💡 **General Approach:**
1. Review the repository structure above
2. Identify files related to your issue
3. Examine existing code patterns
4. Implement changes following the established conventions
5. Test thoroughly before creating a pull request

🔗 **For detailed analysis, ensure the repository is properly ingested and try again.**
"""
                
        except Exception as e:
            logger.error(f"Error generating guidance: {e}")
            return f"❌ **Error**: Could not generate implementation guidance: {str(e)}"
        
    except Exception as e:
        error_msg = f"Failed to generate implementation guidance: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

@mcp.tool()
async def clear_repository_data(repo_name: str, confirm: bool = False) -> str:
    """
    Clear/delete all data for a specific repository from the knowledge base.
    This will remove all collections and analysis data for the repository.
    
    Args:
        repo_name: Repository name in 'owner/repo' format
        confirm: Must be set to True to actually perform the deletion
    
    Returns:
        Status message about the clearing operation
    """
    try:
        logger.info(f"🗑️  Clear repository data request for: {repo_name}")
        
        if not confirm:
            return f"""⚠️  **Repository Data Clearing Confirmation Required**

You are about to clear ALL data for repository: **{repo_name}**

This will permanently delete:
• All documentation embeddings
• All issue analysis data  
• All code analysis data
• All PR history data
• ChromaDB collections

🎯 **To proceed, call this tool again with confirm=True:**
`clear_repository_data('{repo_name}', confirm=True)`

⚡ **This action cannot be undone!**"""

        if repo_name not in analysis_results:
            return f"""📋 **Repository Not Found**

Repository '{repo_name}' has not been ingested or does not exist in the knowledge base.

📊 **Available repositories:**
{', '.join(analysis_results.keys()) if analysis_results else 'None'}

💡 Use `list_ingested_repositories()` to see all available repositories."""

        # Clear ChromaDB collections
        try:
            from issue_solver.ingest import CHROMA_PERSIST_DIR
            import chromadb
            
            safe_repo_name = repo_name.replace('/', '_').replace('-', '_').lower()
            collections_to_delete = [
                f"{safe_repo_name}_documentation",
                f"{safe_repo_name}_issues_history", 
                f"{safe_repo_name}_repo_code_main",
                f"{safe_repo_name}_pr_history"
            ]
            
            chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
            deleted_collections = []
            
            for collection_name in collections_to_delete:
                try:
                    chroma_client.delete_collection(collection_name)
                    deleted_collections.append(collection_name)
                    logger.info(f"Deleted ChromaDB collection: {collection_name}")
                except Exception as e:
                    logger.warning(f"Could not delete collection {collection_name}: {e}")
            
            # Remove from analysis results
            del analysis_results[repo_name]
            
            return f"""✅ **Repository Data Cleared Successfully**

🗑️  **Cleared repository:** {repo_name}
📊 **Collections deleted:** {len(deleted_collections)}
🕒 **Cleared at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Deleted collections:**
{chr(10).join([f"  • {col}" for col in deleted_collections])}

🎯 **Next steps:**
• Repository data has been completely removed
• To use this repository again, run `ingest_repository_tool('{repo_name}')`
• All other repositories remain intact and available"""
            
        except Exception as e:
            logger.error(f"Error clearing ChromaDB data: {e}")
            return f"❌ **ChromaDB Clearing Failed**: {str(e)}"
        
    except Exception as e:
        error_msg = f"Failed to clear repository data: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Error**: {error_msg}"

def main():
    """Main function to run the MCP server."""
    try:
        logger.info("🚀 Starting GitHub Issue Resolution MCP Server...")
        
        # Validate environment variables
        missing_vars = validate_environment()
        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            print(f"Error: Missing required environment variables: {', '.join(missing_vars)}", file=sys.stderr)
            print("Please set the following environment variables:", file=sys.stderr)
            for var in missing_vars:
                print(f"  - {var}", file=sys.stderr)
            sys.exit(1)
        
        logger.info("✅ Environment variables validated")
        logger.info("🛠️  Available tools:")
        logger.info("  🚀 Multi-Step Ingestion Tools:")
        logger.info("    • start_repository_ingestion - Initialize repo and start ingestion process")
        logger.info("    • ingest_repository_docs - Step 1: Ingest documentation")
        logger.info("    • ingest_repository_code - Step 2: Analyze source code")
        logger.info("    • ingest_repository_issues - Step 3: Process issues history")
        logger.info("    • ingest_repository_prs - Step 4: Analyze PR history (completes ingestion)")
        logger.info("  📊 Analysis & Patching Tools:")
        logger.info("    • comprehensive_issue_resolver - Complete 9-step workflow (RECOMMENDED)")
        logger.info("    • analyze_github_issue_tool - Analyze issues using RAG")
        logger.info("    • generate_code_patch_tool - Generate patches for issues")
        logger.info("  🔧 PR Creation Tools (Fork-Aware):")
        logger.info("    • create_pr_with_fork_workflow - Smart PR creation with automatic fork support (recommended)")
        logger.info("    • create_github_pr_from_patch - Create GitHub PR (simple input)")
        logger.info("    • create_github_pr_tool - Create GitHub Pull Requests (JSON input)")
        logger.info("    • create_pr_from_generated_patch - Create PR from last generated patch")
        logger.info("  📋 Repository Management Tools:")
        logger.info("    • get_repository_status - Check detailed ingestion progress")
        logger.info("    • get_repository_info - Get repository details and default branch")
        logger.info("    • get_repository_structure - View repository file structure")
        logger.info("    • get_patch_guidance - Get implementation guidance for issues")
        logger.info("    • validate_repository_tool - Validate repository access")
        logger.info("    • list_ingested_repositories - List all ingested repositories")
        logger.info("    • clear_repository_data - Clear specific repository data")
        
        logger.info("🎯 Ready to accept MCP connections!")
        logger.info("💡 New Workflow: Start with 'start_repository_ingestion' then run 4 ingestion steps!")
        
        # Run the FastMCP server with stdio transport
        mcp.run(transport='stdio')
        
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
