#!/usr/bin/env python3
"""
GitHub MCP Server - Model Context Protocol server that exposes GitHub issue resolution tools.

This server provides three main tools:
1. analyze_github_issue_tool - Analyzes GitHub issues using RAG
2. generate_code_patch_tool - Generates code patches for issues  
3. create_github_pr_tool - Creates GitHub Pull Requests with patches

Usage:
    python github_mcp_server.py
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict
from dotenv import load_dotenv

# MCP imports
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool, TextContent
import mcp.types as types

# Add current directory to path for imports
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "github_analyzer"))

# Import functions from existing modules
from .analyze import (
    parse_github_url, 
    get_github_issue, 
    create_langchain_agent, 
    parse_agent_output, 
    append_to_google_doc
)
from .patch import (
    initialize_chroma_clients, 
    generate_patch_for_issue, 
    create_pr
)

# Add path for ingestion script
# sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "github-rag-ingestion"))
from .ingest import (
    initialize_clients as init_ingestion_clients,
    fetch_repo_docs,
    fetch_repo_issues, 
    fetch_repo_code,
    fetch_repo_pr_history,
    chunk_and_embed_and_store
)

# Load environment variables
load_dotenv()

# Configure logging to stderr (never stdout for MCP servers)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)



# Initialize FastMCP server
mcp = FastMCP("github-issue-resolver")

@mcp.tool()
async def ingest_repository_tool(repo_name: str, skip_prs: bool = False, skip_code: bool = False) -> str:
    """
    Ingests a GitHub repository into the knowledge base for analysis.
    This should be run first before analyzing issues to build the RAG database.
    
    Args:
        repo_name: The GitHub repository in 'owner/repo' format (e.g., 'microsoft/vscode')
        skip_prs: Skip PR history ingestion for faster processing (default: False)
        skip_code: Skip code analysis for faster processing (default: False)
    
    Returns:
        Status message about the ingestion process and collections created
    """
    try:
        logger.info(f"Starting repository ingestion for: {repo_name}")
        
        # Initialize clients for ingestion
        github_client, embeddings = init_ingestion_clients()
        
        # Validate repository access
        try:
            repo = github_client.get_repo(repo_name)
            logger.info(f"Successfully connected to repository: {repo.full_name}")
        except Exception as e:
            raise RuntimeError(f"Could not access repository {repo_name}. Check the name and your GITHUB_TOKEN. Error: {e}")
        
        # Create persist directory if it doesn't exist
        chroma_persist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
        os.makedirs(chroma_persist_dir, exist_ok=True)
        
        total_stored = 0
        ingestion_results = []
        
        # Collection names (matching the constants from ingest_repo.py)
        COLLECTION_DOCS = "documentation"
        COLLECTION_ISSUES = "issues_history"
        COLLECTION_REPO_CODE = "repo_code_main"
        COLLECTION_PR_HISTORY = "pr_history"
        
        # 1. Documentation
        logger.info("Processing Documentation...")
        docs = fetch_repo_docs(repo.full_name)
        if docs:
            stored = chunk_and_embed_and_store(docs, embeddings, COLLECTION_DOCS)
            total_stored += stored
            ingestion_results.append(f"📚 Documentation: {stored} documents")
        else:
            ingestion_results.append("📚 Documentation: No documents found")
        
        # 2. Issues
        logger.info("Processing Issues...")
        issues = fetch_repo_issues(repo)
        if issues:
            stored = chunk_and_embed_and_store(issues, embeddings, COLLECTION_ISSUES)
            total_stored += stored
            ingestion_results.append(f"🐛 Issues: {stored} documents")
        else:
            ingestion_results.append("🐛 Issues: No issues found")
        
        # 3. Code (optional)
        if not skip_code:
            logger.info("Processing Code...")
            code_chunks = fetch_repo_code(repo.full_name)
            if code_chunks:
                stored = chunk_and_embed_and_store(code_chunks, embeddings, COLLECTION_REPO_CODE)
                total_stored += stored
                ingestion_results.append(f"💻 Code: {stored} documents")
            else:
                ingestion_results.append("💻 Code: No code found")
        else:
            ingestion_results.append("💻 Code: Skipped (skip_code=True)")
        
        # 4. PR History (optional)
        if not skip_prs:
            logger.info("Processing PR History...")
            pr_history = fetch_repo_pr_history(repo)
            if pr_history:
                stored = chunk_and_embed_and_store(pr_history, embeddings, COLLECTION_PR_HISTORY)
                total_stored += stored
                ingestion_results.append(f"🔄 PR History: {stored} documents")
            else:
                ingestion_results.append("🔄 PR History: No PRs found")
        else:
            ingestion_results.append("🔄 PR History: Skipped (skip_prs=True)")
        
        # Prepare collections list
        collections = [COLLECTION_DOCS, COLLECTION_ISSUES]
        if not skip_code:
            collections.append(COLLECTION_REPO_CODE)
        if not skip_prs:
            collections.append(COLLECTION_PR_HISTORY)
        
        # Create response
        result_message = f"""✅ Repository Ingestion Complete!

Repository: {repo.full_name}
Total Documents Stored: {total_stored}
ChromaDB Location: {chroma_persist_dir}

Collections Created:
{chr(10).join([f"• {col}" for col in collections])}

Ingestion Results:
{chr(10).join(ingestion_results)}

🎉 Knowledge base is ready! You can now analyze issues from this repository.
"""
        
        logger.info("Repository ingestion completed successfully")
        return result_message
        
    except Exception as e:
        logger.error(f"Error during repository ingestion: {e}")
        raise RuntimeError(f"Failed to ingest repository: {str(e)}")

@mcp.tool()
async def analyze_github_issue_tool(issue_url: str) -> str:
    """
    Analyzes a GitHub issue by its URL, providing a summary, proposed solution, 
    complexity, and relevant past issues based on repository knowledge.
    Uses the same sophisticated analysis as the original analyze_issue.py script.
    
    Args:
        issue_url: The full URL of the GitHub issue (e.g., 'https://github.com/owner/repo/issues/123')
    
    Returns:
        JSON string containing analysis results with summary, proposed_solution, complexity, and similar_issues
    """
    try:
        logger.info(f"Analyzing GitHub issue: {issue_url}")
        
        # Parse the GitHub URL
        owner, repo, issue_number = parse_github_url(issue_url)
        logger.info(f"Parsed URL - Owner: {owner}, Repo: {repo}, Issue: {issue_number}")
        
        # Fetch the GitHub issue
        issue = get_github_issue(owner, repo, issue_number)
        logger.info(f"Fetched issue: {issue.title}")
        
        # Create LangChain agent and analyze the issue (using the original sophisticated approach)
        logger.info("Creating LangChain agent for analysis...")
        agent_raw_output = create_langchain_agent(issue)
        logger.info("Agent analysis completed")
        
        # Parse the agent output
        analysis = parse_agent_output(agent_raw_output)
        logger.info("Analysis parsed successfully")
        
        # Create the detailed report text (same format as original analyze_issue.py)
        detailed_report = f"""---
### Issue #{issue.number}: {issue.title}
- Repository: {issue.repository.full_name}
- Link: {issue.html_url}
- Analyzed On: {datetime.now().strftime('%d %B, %Y at %H:%M')}
- Status: {issue.state}

| Category            | AI Analysis                                                  |
| ------------------- | ------------------------------------------------------------ |
| Summary         | {analysis.get('summary', 'N/A')}                             |
| Complexity      | {analysis.get('complexity', 'N/A')} / 5                      |
| Similar Issues  | {', '.join(analysis.get('similar_issues', [])) or 'None Found'} |

Proposed Solution:
{analysis.get('proposed_solution', 'N/A')}

---

"""
        
        # Append to Google Doc if configured
        google_docs_id = os.getenv("GOOGLE_DOCS_ID")
        if google_docs_id:
            try:
                append_to_google_doc(detailed_report)
                logger.info("Analysis appended to Google Doc")
            except Exception as e:
                logger.warning(f"Failed to append to Google Doc: {e}")
        
        # Return a combined response that includes both the structured data and the formatted report
        response_data = {
            "analysis": analysis,
            "detailed_report": detailed_report,
            "issue_info": {
                "number": issue.number,
                "title": issue.title,
                "repository": issue.repository.full_name,
                "url": issue.html_url,
                "status": issue.state,
                "analyzed_on": datetime.now().strftime('%d %B, %Y at %H:%M')
            }
        }
        
        return json.dumps(response_data, indent=2)
        
    except Exception as e:
        logger.error(f"Error analyzing GitHub issue: {e}")
        raise RuntimeError(f"Failed to analyze GitHub issue: {str(e)}")

@mcp.tool()
async def generate_code_patch_tool(issue_body: str, repo_full_name: str) -> str:
    """
    Generates a code patch (unified diff) and a summary of changes to resolve a given issue,
    leveraging PR history and the current codebase structure.
    
    Args:
        issue_body: The full body text of the GitHub issue that needs a patch
        repo_full_name: The full name of the repository (e.g., 'owner/repo') where the issue is located
    
    Returns:
        JSON string containing patch data with filesToUpdate and summaryOfChanges
    """
    try:
        logger.info(f"Generating code patch for repo: {repo_full_name}")
        
        # Generate patch using existing function
        # Note: The function internally initializes its own ChromaDB clients
        patch_data = generate_patch_for_issue(issue_body=issue_body, repo_full_name=repo_full_name)
        logger.info("Patch generation completed")
        
        return json.dumps(patch_data, indent=2)
        
    except Exception as e:
        logger.error(f"Error generating code patch: {e}")
        raise RuntimeError(f"Failed to generate code patch: {str(e)}")

@mcp.tool()
async def create_github_pr_tool(
    patch_data_json: str, 
    repo_full_name: str, 
    issue_number: int, 
    base_branch: str = "main", 
    head_branch: str = None
) -> str:
    """
    Creates a draft GitHub Pull Request with the provided patch data.
    Requires patch data generated by 'generate_code_patch_tool'.
    
    Args:
        patch_data_json: A JSON string containing the patch data (filesToUpdate, summaryOfChanges) 
                        obtained from 'generate_code_patch_tool'
        repo_full_name: Repository name in 'owner/repo' format
        issue_number: The GitHub issue number this PR is for
        base_branch: Base branch for the PR (default: 'main')
        head_branch: Head branch name (auto-generated if null)
    
    Returns:
        PR URL if successful, error message if failed
    """
    try:
        logger.info(f"Creating GitHub PR for repo: {repo_full_name}, issue: {issue_number}")
        
        # Parse the patch data JSON
        try:
            patch_data = json.loads(patch_data_json)
            logger.info("Patch data parsed successfully")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in patch_data_json: {e}")
            raise RuntimeError(f"Invalid JSON format in patch_data_json: {str(e)}")
        
        # Create the PR using existing function
        pr_url = create_pr(
            patch_data=patch_data,
            repo_full_name=repo_full_name,
            base_branch=base_branch,
            head_branch=head_branch,
            issue_number=issue_number
        )
        
        logger.info(f"PR creation result: {pr_url}")
        return pr_url
        
    except Exception as e:
        logger.error(f"Error creating GitHub PR: {e}")
        raise RuntimeError(f"Failed to create GitHub PR: {str(e)}")

def validate_environment():
    """Validate that all required environment variables are set."""
    required_vars = [
        "GOOGLE_API_KEY",
        "GITHUB_TOKEN"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    logger.info("Environment variables validated")


def main():
    """Main function to run the MCP server."""
    try:
        logger.info("Starting GitHub MCP Server...")
        
        # Validate environment
        validate_environment()
        
        # Import datetime here since it's used in analyze_github_issue_tool
        from datetime import datetime
        globals()['datetime'] = datetime
        
        logger.info("MCP Server initialized successfully")
        logger.info("Available tools:")
        logger.info("  - ingest_repository_tool: Ingest repository for knowledge base")
        logger.info("  - analyze_github_issue_tool: Analyze GitHub issues using RAG")
        logger.info("  - generate_code_patch_tool: Generate code patches for issues")
        logger.info("  - create_github_pr_tool: Create GitHub Pull Requests")
        
        logger.info("🚀 Ready to accept MCP connections!")
        logger.info("💡 First step: Use ingest_repository_tool to build knowledge base")
        
        # Run the FastMCP server
        mcp.run(transport='stdio')
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 