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

# Store for repository analysis results
analysis_results = {}

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

@mcp.tool()
async def ingest_repository_tool(
    repo_name: str, 
    skip_prs: bool = False, 
    skip_code: bool = False,
    max_issues: int = 100,
    max_prs: int = 50
) -> str:
    """
    Ingest a GitHub repository into the knowledge base for analysis.
    This should be run first before analyzing issues to build the RAG database.
    
    Args:
        repo_name: Repository name in 'owner/repo' format (e.g., 'microsoft/vscode')
        skip_prs: Skip PR history ingestion for faster processing (default: False)
        skip_code: Skip code analysis for faster processing (default: False)
        max_issues: Maximum number of issues to process (default: 100)
        max_prs: Maximum number of PRs to process (default: 50)
    
    Returns:
        Status message about the ingestion process and collections created
    """
    try:
        logger.info(f"Starting repository ingestion for: {repo_name}")
        logger.info(f"⚙️  Settings: skip_prs={skip_prs}, skip_code={skip_code}, max_issues={max_issues}, max_prs={max_prs}")
        
        # Import required modules locally to handle import errors gracefully
        try:
            from issue_solver.ingest import (
                initialize_clients as init_ingestion_clients,
                fetch_repo_issues, 
                fetch_repo_pr_history,
                chunk_and_embed_and_store,
                validate_repo_exists
            )
        except ImportError as e:
            logger.error(f"Failed to import ingestion modules: {e}")
            return f"❌ **Import Error**: Could not load ingestion modules. Please ensure all dependencies are installed.\nError: {str(e)}"
        
        # Validate repository exists first
        try:
            if not await asyncio.to_thread(validate_repo_exists, repo_name):
                return f"❌ **Repository Validation Failed**\n\nRepository '{repo_name}' was not found or is not accessible. Please check:\n• Repository name format (owner/repo)\n• Repository visibility (public vs private)\n• GitHub token permissions"
        except Exception as e:
            logger.warning(f"Could not validate repository (continuing anyway): {e}")
        
        # Initialize clients for ingestion
        try:
            github_client, embeddings = await asyncio.to_thread(init_ingestion_clients)
            logger.info("✅ Successfully initialized GitHub client and embeddings")
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            return f"❌ **Client Initialization Failed**: {str(e)}\n\nPlease check your environment variables (GOOGLE_API_KEY, GITHUB_TOKEN)"
        
        # Validate repository access
        try:
            repo = await asyncio.to_thread(lambda: github_client.get_repo(repo_name))
            logger.info(f"✅ Successfully connected to repository: {repo.full_name}")
        except Exception as e:
            logger.error(f"Repository access error: {e}")
            return f"❌ **Repository Access Failed**: Could not access repository '{repo_name}'.\n\nError: {str(e)}\n\nPlease check:\n• Repository name is correct\n• Repository is public or your GITHUB_TOKEN has access\n• GITHUB_TOKEN is valid"
        
        # Create persist directory if it doesn't exist (use same path as ingest.py)
        # Import the CHROMA_PERSIST_DIR from ingest module for consistency
        from issue_solver.ingest import CHROMA_PERSIST_DIR
        chroma_persist_dir = CHROMA_PERSIST_DIR
        
        # Debug information for troubleshooting
        logger.info(f"🔍 Current working directory: {os.getcwd()}")
        logger.info(f"📁 ChromaDB directory path: {chroma_persist_dir}")
        logger.info(f"📂 Parent directory exists: {os.path.exists(os.path.dirname(chroma_persist_dir))}")
        logger.info(f"🔓 Parent directory writable: {os.access(os.path.dirname(chroma_persist_dir), os.W_OK)}")
        
        try:
            os.makedirs(chroma_persist_dir, exist_ok=True)
            logger.info(f"✅ ChromaDB directory created/verified: {chroma_persist_dir}")
        except PermissionError as e:
            logger.error(f"❌ Permission denied creating ChromaDB directory: {e}")
            return f"❌ **Permission Error**: Cannot create ChromaDB directory at '{chroma_persist_dir}'. Please check file system permissions or set CHROMA_PERSIST_DIR environment variable to a writable location."
        except Exception as e:
            logger.error(f"❌ Error creating ChromaDB directory: {e}")
            return f"❌ **Directory Creation Failed**: {str(e)}"
        
        total_stored = 0
        ingestion_results = []
        
        # Collection names
        COLLECTION_DOCS = "documentation"
        COLLECTION_ISSUES = "issues_history"
        COLLECTION_REPO_CODE = "repo_code_main"
        COLLECTION_PR_HISTORY = "pr_history"
        
        # 1. Documentation
        logger.info("📚 Processing Documentation...")
        try:
            # Import the async function
            from issue_solver.ingest import fetch_repo_docs
            docs = await fetch_repo_docs(repo.full_name)
            if docs:
                logger.info(f"📄 Found {len(docs)} documentation files, now embedding and storing...")
                stored = await chunk_and_embed_and_store(docs, embeddings, COLLECTION_DOCS, repo.full_name)
                total_stored += stored
                ingestion_results.append(f"📚 Documentation: {stored} documents")
                logger.info(f"✅ Documentation: {stored} documents processed")
            else:
                ingestion_results.append("📚 Documentation: No documents found")
                logger.info("ℹ️  No documentation found")
        except Exception as e:
            logger.error(f"Documentation processing error: {e}")
            ingestion_results.append(f"📚 Documentation: Error - {str(e)}")
        
        # 2. Issues
        logger.info("🐛 Processing Issues...")
        try:
            issues = await asyncio.to_thread(fetch_repo_issues, repo, max_issues)
            if issues:
                logger.info(f"🔍 Found {len(issues)} issues, now embedding and storing...")
                stored = await chunk_and_embed_and_store(issues, embeddings, COLLECTION_ISSUES, repo.full_name)
                total_stored += stored
                ingestion_results.append(f"🐛 Issues: {stored} documents")
                logger.info(f"✅ Issues: {stored} documents processed")
            else:
                ingestion_results.append("🐛 Issues: No issues found")
                logger.info("ℹ️  No issues found")
        except Exception as e:
            logger.error(f"Issues processing error: {e}")
            ingestion_results.append(f"🐛 Issues: Error - {str(e)}")
        
        # 3. Code (optional)
        if not skip_code:
            logger.info("💻 Processing Code...")
            try:
                # Import the async function
                from issue_solver.ingest import fetch_repo_code
                code_chunks = await fetch_repo_code(repo.full_name)
                if code_chunks:
                    logger.info(f"📝 Found {len(code_chunks)} code chunks, now embedding and storing...")
                    stored = await chunk_and_embed_and_store(code_chunks, embeddings, COLLECTION_REPO_CODE, repo.full_name)
                    total_stored += stored
                    ingestion_results.append(f"💻 Code: {stored} documents")
                    logger.info(f"✅ Code: {stored} documents processed")
                else:
                    ingestion_results.append("💻 Code: No code found")
                    logger.info("ℹ️  No code found")
            except Exception as e:
                logger.error(f"Code processing error: {e}")
                ingestion_results.append(f"💻 Code: Error - {str(e)}")
        else:
            ingestion_results.append("💻 Code: Skipped (skip_code=True)")
            logger.info("⏭️  Code processing skipped")
        
        # 4. PR History (optional)
        if not skip_prs:
            logger.info("🔄 Processing PR History...")
            try:
                pr_history = await asyncio.to_thread(fetch_repo_pr_history, repo, max_prs)
                if pr_history:
                    logger.info(f"🔀 Found {len(pr_history)} PR records, now embedding and storing...")
                    stored = await chunk_and_embed_and_store(pr_history, embeddings, COLLECTION_PR_HISTORY, repo.full_name)
                    total_stored += stored
                    ingestion_results.append(f"🔄 PR History: {stored} documents")
                    logger.info(f"✅ PR History: {stored} documents processed")
                else:
                    ingestion_results.append("🔄 PR History: No PRs found")
                    logger.info("ℹ️  No PRs found")
            except Exception as e:
                logger.error(f"PR processing error: {e}")
                ingestion_results.append(f"🔄 PR History: Error - {str(e)}")
        else:
            ingestion_results.append("🔄 PR History: Skipped (skip_prs=True)")
            logger.info("⏭️  PR processing skipped")
        
        # Prepare collections list with repository-specific names
        safe_repo_name = repo.full_name.replace('/', '_').replace('-', '_').lower()
        collections = [f"{safe_repo_name}_{COLLECTION_DOCS}", f"{safe_repo_name}_{COLLECTION_ISSUES}"]
        if not skip_code:
            collections.append(f"{safe_repo_name}_{COLLECTION_REPO_CODE}")
        if not skip_prs:
            collections.append(f"{safe_repo_name}_{COLLECTION_PR_HISTORY}")
        
        # Store ingestion metadata
        ingestion_metadata = {
            "repo_name": repo_name,
            "total_documents": total_stored,
            "timestamp": datetime.now().isoformat(),
            "collections": collections,
            "chroma_dir": chroma_persist_dir
        }
        analysis_results[repo_name] = ingestion_metadata
        
        # Create detailed response with progress information
        result_message = f"""✅ **Repository Ingestion Complete!**

📊 **Summary:**
• Repository: {repo.full_name}
• Total Documents: {total_stored}
• ChromaDB Location: {chroma_persist_dir}
• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• Processing Time: Complete

📁 **Collections Created:**
{chr(10).join([f"  • {col}" for col in collections])}

📈 **Processing Results:**
{chr(10).join([f"  {result}" for result in ingestion_results])}

🎯 **Next Steps:**
1. Use `analyze_github_issue_tool` to analyze specific issues from {repo.full_name}
2. Use `generate_code_patch_tool` to create patches for issues
3. Use `create_github_pr_tool` to create Pull Requests

💡 **Progress Tracking:**
You can monitor detailed progress in Claude Desktop's logs at:
`~/Library/Logs/Claude/mcp-server-github-issue-resolver.log`

🎉 **Knowledge base is ready for AI analysis!**"""
        
        logger.info("🎉 Repository ingestion completed successfully")
        logger.info(f"🎯 ChromaDB location: {chroma_persist_dir}")
        logger.info(f"✅ Ready for issue analysis and patch generation!")
        return result_message
        
    except Exception as e:
        error_msg = f"Repository ingestion failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return f"❌ **Ingestion Failed**: {error_msg}"

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
            }, indent=2)
        
        # Parse the GitHub URL
        try:
            owner, repo, issue_number = parse_github_url(issue_url)
            logger.info(f"✅ Parsed URL - Owner: {owner}, Repo: {repo}, Issue: {issue_number}")
        except Exception as e:
            logger.error(f"URL parsing error: {e}")
            return json.dumps({
                "error": f"Invalid GitHub issue URL: {str(e)}",
                "success": False
            }, indent=2)
        
        # Check if repository is ingested
        repo_full_name = f"{owner}/{repo}"
        if repo_full_name not in analysis_results:
            return json.dumps({
                "error": f"Repository '{repo_full_name}' has not been ingested yet. Please run 'ingest_repository_tool' first.",
                "success": False,
                "suggestion": f"Run: ingest_repository_tool('{repo_full_name}')"
            }, indent=2)
        
        # Fetch the GitHub issue
        try:
            issue = await asyncio.to_thread(get_github_issue, owner, repo, issue_number)
            logger.info(f"✅ Fetched issue: {issue.title}")
        except Exception as e:
            logger.error(f"Issue fetch error: {e}")
            return json.dumps({
                "error": f"Could not fetch GitHub issue: {str(e)}",
                "success": False
            }, indent=2)
        
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
            }, indent=2)
        
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
            }, indent=2)
        
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
        return json.dumps(response_data, indent=2)
        
    except Exception as e:
        error_msg = f"Issue analysis failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps({
            "error": error_msg,
            "success": False
        }, indent=2)

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
            }, indent=2)
        
        # Check if repository is ingested
        if repo_full_name not in analysis_results:
            return json.dumps({
                "error": f"Repository '{repo_full_name}' has not been ingested yet. Please run 'ingest_repository_tool' first.",
                "success": False,
                "suggestion": f"Run: ingest_repository_tool('{repo_full_name}')"
            }, indent=2)
        
        # Generate patch using existing function
        try:
            patch_data = await asyncio.to_thread(generate_patch_for_issue, issue_body, repo_full_name)
            logger.info("✅ Patch generation completed")
            
            # Enhance patch data with metadata
            enhanced_patch_data = {
                "success": True,
                "patch_data": patch_data,
                "metadata": {
                    "repo_name": repo_full_name,
                    "generated_on": datetime.now().isoformat(),
                    "files_modified": len(patch_data.get("filesToUpdate", [])),
                    "ingestion_info": analysis_results.get(repo_full_name, {})
                }
            }
            
            return json.dumps(enhanced_patch_data, indent=2)
            
        except Exception as e:
            logger.error(f"Patch generation error: {e}")
            return json.dumps({
                "error": f"Patch generation failed: {str(e)}",
                "success": False
            }, indent=2)
        
    except Exception as e:
        error_msg = f"Code patch generation failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps({
            "error": error_msg,
            "success": False
        }, indent=2)

@mcp.tool()
async def create_github_pr_tool(
    patch_data_json: str, 
    repo_full_name: str, 
    issue_number: int = None,
    base_branch: str = "main"
) -> str:
    """
    Create a GitHub Pull Request with generated patches.
    Takes patch data from generate_code_patch_tool and creates
    a draft PR with the changes.
    
    Args:
        patch_data_json: JSON string containing patch data from generate_code_patch_tool
        repo_full_name: Repository name in 'owner/repo' format
        issue_number: GitHub issue number to link the PR to (optional)
        base_branch: Base branch for the PR (default: 'main')
    
    Returns:
        Status message with PR URL if successful
    """
    try:
        logger.info(f"🚀 Creating GitHub PR for repo: {repo_full_name}")
        
        # Import required modules locally
        try:
            from issue_solver.patch import create_pr
        except ImportError as e:
            logger.error(f"Failed to import PR creation modules: {e}")
            return f"❌ **Import Error**: Could not load PR creation modules.\nError: {str(e)}"
        
        # Parse the patch data JSON
        try:
            patch_response = json.loads(patch_data_json)
            if "patch_data" in patch_response:
                patch_data = patch_response["patch_data"]
            else:
                patch_data = patch_response
            logger.info("✅ Patch data parsed successfully")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in patch_data_json: {e}")
            return f"❌ **JSON Error**: Invalid JSON format in patch_data_json.\nError: {str(e)}"
        
        # Validate patch data has required fields
        if not patch_data.get("filesToUpdate"):
            return f"❌ **Validation Error**: No files to update found in patch data."
        
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
    Get status and statistics of an ingested repository.
    Shows ChromaDB information and ingestion metadata.
    
    Args:
        repo_name: Repository name in 'owner/repo' format
    
    Returns:
        Status information and statistics
    """
    try:
        logger.info(f"📊 Getting status for repository: {repo_name}")
        
        # Check if repository is in our analysis results
        if repo_name not in analysis_results:
            return f"""📊 **Repository Status: {repo_name}**

❌ **Status**: Not Ingested

ℹ️  This repository has not been ingested into the knowledge base yet.

🎯 **To get started:**
1. Run: `ingest_repository_tool('{repo_name}')`
2. Wait for ingestion to complete
3. Then you can analyze issues and generate patches

💡 **Tip**: Ingestion may take a few minutes depending on repository size."""
        
        # Get stored metadata
        metadata = analysis_results[repo_name]
        
        # Try to get ChromaDB stats if possible
        chroma_info = "ChromaDB information not available"
        try:
            from issue_solver.ingest import get_repo_stats
            stats = await asyncio.to_thread(get_repo_stats, repo_name)
            
            collection_info = []
            for collection_name, collection_stats in stats.get("collections", {}).items():
                collection_info.append(f"  • {collection_name}: {collection_stats.get('count', 0)} documents")
            
            if collection_info:
                chroma_info = f"📁 **ChromaDB Collections:**\n" + "\n".join(collection_info)
            
        except Exception as e:
            logger.warning(f"Could not get ChromaDB stats: {e}")
        
        status_text = f"""📊 **Repository Status: {repo_name}**

✅ **Status**: Ingested and Ready

📈 **Ingestion Summary:**
• Total Documents: {metadata.get('total_documents', 'Unknown')}
• Ingested On: {metadata.get('timestamp', 'Unknown')}
• ChromaDB Location: {metadata.get('chroma_dir', 'Unknown')}

{chroma_info}

🛠️  **Available Operations:**
1. `analyze_github_issue_tool` - Analyze specific issues
2. `generate_code_patch_tool` - Generate patches for issues  
3. `create_github_pr_tool` - Create Pull Requests

🎉 **Repository is ready for AI-powered issue resolution!**"""
        
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
        logger.info("  • ingest_repository_tool - Build knowledge base from GitHub repo")
        logger.info("  • analyze_github_issue_tool - Analyze issues using RAG")
        logger.info("  • generate_code_patch_tool - Generate patches for issues")
        logger.info("  • create_github_pr_tool - Create GitHub Pull Requests")
        logger.info("  • get_repository_status - Check ingestion status")
        logger.info("  • validate_repository_tool - Validate repository access")
        logger.info("  • list_ingested_repositories - List all ingested repositories")
        logger.info("  • clear_repository_data - Clear specific repository data")
        
        logger.info("🎯 Ready to accept MCP connections!")
        logger.info("💡 Tip: Start by ingesting a repository with 'ingest_repository_tool'")
        
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
