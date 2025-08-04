#!/usr/bin/env python3
"""
GitHub Issue Resolution MCP Server

A comprehensive Model Context Protocol server that provides GitHub repository analysis,
issue resolution, patch generation, and PR creation capabilities.

This server integrates all the functionality from your existing scripts:
- Repository ingestion and analysis
- Issue analysis using LangChain agents
- Code patch generation
- GitHub PR creation
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import traceback

# MCP Server imports
from mcp.server.models import InitializeResult
from mcp.server import NotificationOptions, Server
from mcp.server.models import (
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult
)
from mcp.types import TextContent as TextContentType

# Add the project root to Python path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import your existing modules
try:
    # Repository ingestion
    from ingest_repo import (
        ingest_repository,
        get_repo_stats,
        validate_repo_exists
    )
    
    # Issue analysis
    from analyze_issue import (
        parse_github_url,
        get_github_issue,
        create_langchain_agent,
        parse_agent_output,
        append_to_google_doc
    )
    
    # Patch generation
    from patch_generator import (
        generate_patch_for_issue,
        create_pr,
        generate_and_create_pr
    )
except ImportError as e:
    print(f"Warning: Could not import some modules: {e}")
    print("Some functionality may be limited.")

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging to stderr (not stdout for MCP)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Initialize the MCP server
server = Server("github-issue-resolver")

# Server capabilities and metadata
SERVER_CAPABILITIES = {
    "tools": {
        "listChanged": True
    },
    "resources": {},
    "prompts": {}
}

SERVER_INFO = {
    "name": "GitHub Issue Resolution Server",
    "version": "1.0.0",
    "description": "Comprehensive GitHub repository analysis and issue resolution server"
}

@server.list_tools()
async def handle_list_tools() -> ListToolsResult:
    """List all available tools."""
    tools = [
        Tool(
            name="ingest_repository_tool",
            description=(
                "Ingest and analyze a GitHub repository to create a comprehensive knowledge base. "
                "This tool fetches repository structure, code files, documentation, issues, and PRs "
                "to build a ChromaDB vector database for later analysis. This must be run first "
                "before analyzing issues from the repository."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name in 'owner/repo' format (e.g., 'microsoft/vscode')"
                    },
                    "skip_prs": {
                        "type": "boolean",
                        "description": "Skip processing pull requests (default: False)",
                        "default": False
                    },
                    "skip_code": {
                        "type": "boolean", 
                        "description": "Skip code file analysis (default: False)",
                        "default": False
                    },
                    "max_issues": {
                        "type": "integer",
                        "description": "Maximum number of issues to process (default: 100)",
                        "default": 100
                    }
                },
                "required": ["repo_name"]
            }
        ),
        
        Tool(
            name="analyze_github_issue_tool",
            description=(
                "Analyze a GitHub issue using AI and repository knowledge base. "
                "Provides comprehensive analysis including summary, proposed solution, "
                "complexity rating, and similar issues. Results are saved to Google Docs "
                "and returned for display. Requires repository to be ingested first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_url": {
                        "type": "string",
                        "description": "Full GitHub issue URL (e.g., 'https://github.com/owner/repo/issues/123')"
                    }
                },
                "required": ["issue_url"]
            }
        ),
        
        Tool(
            name="generate_code_patch_tool",
            description=(
                "Generate code patches to resolve a GitHub issue using RAG and AI. "
                "Analyzes the issue against repository knowledge base and creates "
                "specific file patches with unified diff format. Returns structured "
                "patch data that can be used to create PRs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_body": {
                        "type": "string",
                        "description": "The issue description/body text to generate patches for"
                    },
                    "repo_full_name": {
                        "type": "string",
                        "description": "Repository name in 'owner/repo' format"
                    }
                },
                "required": ["issue_body", "repo_full_name"]
            }
        ),
        
        Tool(
            name="create_github_pr_tool",
            description=(
                "Create a GitHub Pull Request with generated patches. "
                "Takes patch data from generate_code_patch_tool and creates "
                "a draft PR with the changes. Automatically links to the "
                "original issue if issue_number is provided."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "patch_data_json": {
                        "type": "string",
                        "description": "JSON string containing patch data from generate_code_patch_tool"
                    },
                    "repo_full_name": {
                        "type": "string",
                        "description": "Repository name in 'owner/repo' format"
                    },
                    "issue_number": {
                        "type": "integer",
                        "description": "GitHub issue number to link the PR to",
                        "default": None
                    },
                    "base_branch": {
                        "type": "string",
                        "description": "Base branch for the PR (default: 'main')",
                        "default": "main"
                    }
                },
                "required": ["patch_data_json", "repo_full_name"]
            }
        ),
        
        Tool(
            name="get_repository_stats_tool",
            description=(
                "Get statistics and information about an ingested repository. "
                "Shows ChromaDB collection sizes, repository metadata, and "
                "ingestion status. Useful for verifying successful ingestion."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name in 'owner/repo' format"
                    }
                },
                "required": ["repo_name"]
            }
        ),
        
        Tool(
            name="validate_repository_tool",
            description=(
                "Validate that a GitHub repository exists and is accessible. "
                "Checks repository permissions and basic metadata before "
                "attempting ingestion or analysis."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name in 'owner/repo' format"
                    }
                },
                "required": ["repo_name"]
            }
        )
    ]
    
    return ListToolsResult(tools=tools)

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool execution requests."""
    try:
        logger.info(f"Executing tool: {name} with arguments: {arguments}")
        
        if name == "ingest_repository_tool":
            return await _handle_ingest_repository(arguments)
        elif name == "analyze_github_issue_tool":
            return await _handle_analyze_issue(arguments)
        elif name == "generate_code_patch_tool":
            return await _handle_generate_patch(arguments)
        elif name == "create_github_pr_tool":
            return await _handle_create_pr(arguments)
        elif name == "get_repository_stats_tool":
            return await _handle_get_repo_stats(arguments)
        elif name == "validate_repository_tool":
            return await _handle_validate_repository(arguments)
        else:
            error_msg = f"Unknown tool: {name}"
            logger.error(error_msg)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {error_msg}")]
            )
    
    except Exception as e:
        error_msg = f"Error executing tool {name}: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {error_msg}")]
        )

async def _handle_ingest_repository(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle repository ingestion."""
    repo_name = arguments.get("repo_name")
    skip_prs = arguments.get("skip_prs", False)
    skip_code = arguments.get("skip_code", False)
    max_issues = arguments.get("max_issues", 100)
    
    try:
        logger.info(f"Starting repository ingestion for {repo_name}")
        
        # Validate repository exists
        if not await asyncio.to_thread(validate_repo_exists, repo_name):
            return CallToolResult(
                content=[TextContent(
                    type="text", 
                    text=f"❌ Repository '{repo_name}' not found or not accessible"
                )]
            )
        
        # Run ingestion in thread to avoid blocking
        result = await asyncio.to_thread(
            ingest_repository,
            repo_name=repo_name,
            skip_prs=skip_prs,
            skip_code=skip_code,
            max_issues=max_issues
        )
        
        # Format result for display
        if result.get("success", False):
            stats = result.get("stats", {})
            response_text = f"""✅ **Repository Ingestion Complete!**

📊 **Ingestion Statistics:**
• Repository: {repo_name}
• Code Files: {stats.get('code_files', 0)} processed
• Issues: {stats.get('issues', 0)} processed
• Pull Requests: {stats.get('prs', 0)} processed
• Documentation: {stats.get('docs', 0)} files processed
• ChromaDB Collections: {', '.join(stats.get('collections', []))}

🎯 **Next Steps:**
1. You can now analyze issues using: analyze <github_issue_url>
2. Generate patches with: patch <repo_name> <issue_description>
3. Create PRs with: pr <repo_name> <issue_number> <patch_json>

⚡ Repository knowledge base is ready for AI analysis!"""
        else:
            response_text = f"❌ Repository ingestion failed: {result.get('error', 'Unknown error')}"
        
        return CallToolResult(
            content=[TextContent(type="text", text=response_text)]
        )
    
    except Exception as e:
        error_msg = f"Repository ingestion failed: {str(e)}"
        logger.error(error_msg)
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {error_msg}")]
        )

async def _handle_analyze_issue(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle GitHub issue analysis."""
    issue_url = arguments.get("issue_url")
    
    try:
        logger.info(f"Analyzing GitHub issue: {issue_url}")
        
        # Parse GitHub URL
        owner, repo, issue_number = parse_github_url(issue_url)
        
        # Get issue data
        issue = await asyncio.to_thread(get_github_issue, owner, repo, issue_number)
        
        # Run LangChain agent analysis
        agent_output = await asyncio.to_thread(create_langchain_agent, issue)
        
        # Parse the agent output
        analysis = parse_agent_output(agent_output)
        
        # Create detailed report (matching original analyze_issue.py format)
        report_text = f"""---
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

**Proposed Solution:**
{analysis.get('proposed_solution', 'N/A')}

---

"""
        
        # Save to Google Docs (in background)
        try:
            await asyncio.to_thread(append_to_google_doc, report_text)
        except Exception as e:
            logger.warning(f"Failed to save to Google Docs: {e}")
        
        # Return both structured data and formatted report
        response_data = {
            "detailed_report": report_text,
            "analysis": analysis,
            "issue_info": {
                "repository": issue.repository.full_name,
                "number": issue.number,
                "title": issue.title,
                "url": issue.html_url
            }
        }
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(response_data, indent=2))]
        )
    
    except Exception as e:
        error_msg = f"Issue analysis failed: {str(e)}"
        logger.error(error_msg)
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {error_msg}")]
        )

async def _handle_generate_patch(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle code patch generation."""
    issue_body = arguments.get("issue_body")
    repo_full_name = arguments.get("repo_full_name")
    
    try:
        logger.info(f"Generating patches for repository: {repo_full_name}")
        
        # Generate patches using your existing function
        patch_data = await asyncio.to_thread(generate_patch_for_issue, issue_body, repo_full_name)
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(patch_data, indent=2))]
        )
    
    except Exception as e:
        error_msg = f"Patch generation failed: {str(e)}"
        logger.error(error_msg)
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {error_msg}")]
        )

async def _handle_create_pr(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle GitHub PR creation."""
    patch_data_json = arguments.get("patch_data_json")
    repo_full_name = arguments.get("repo_full_name")
    issue_number = arguments.get("issue_number")
    base_branch = arguments.get("base_branch", "main")
    
    try:
        logger.info(f"Creating PR for repository: {repo_full_name}")
        
        # Parse patch data
        patch_data = json.loads(patch_data_json)
        
        # Create PR using your existing function
        pr_url = await asyncio.to_thread(
            create_pr,
            patch_data=patch_data,
            repo_full_name=repo_full_name,
            base_branch=base_branch,
            issue_number=issue_number
        )
        
        if pr_url.startswith("https://"):
            response_text = f"✅ **Pull Request Created Successfully!**\n\n🔗 **PR URL:** {pr_url}\n\n📋 **Summary:** Draft PR created with {len(patch_data.get('filesToUpdate', []))} file changes"
        else:
            response_text = f"❌ **PR Creation Failed:** {pr_url}"
        
        return CallToolResult(
            content=[TextContent(type="text", text=response_text)]
        )
    
    except Exception as e:
        error_msg = f"PR creation failed: {str(e)}"
        logger.error(error_msg)
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {error_msg}")]
        )

async def _handle_get_repo_stats(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle repository statistics request."""
    repo_name = arguments.get("repo_name")
    
    try:
        logger.info(f"Getting stats for repository: {repo_name}")
        
        # Get repository stats using your existing function
        stats = await asyncio.to_thread(get_repo_stats, repo_name)
        
        response_text = f"""📊 **Repository Statistics for {repo_name}**

🗄️ **ChromaDB Collections:**
"""
        
        for collection_name, collection_stats in stats.get("collections", {}).items():
            response_text += f"• **{collection_name}:** {collection_stats.get('count', 0)} documents\n"
        
        response_text += f"""
📈 **Processing Stats:**
• Total Documents: {stats.get('total_documents', 0)}
• Last Updated: {stats.get('last_updated', 'Unknown')}
• Status: {stats.get('status', 'Unknown')}
"""
        
        return CallToolResult(
            content=[TextContent(type="text", text=response_text)]
        )
    
    except Exception as e:
        error_msg = f"Failed to get repository stats: {str(e)}"
        logger.error(error_msg)
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {error_msg}")]
        )

async def _handle_validate_repository(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle repository validation."""
    repo_name = arguments.get("repo_name")
    
    try:
        logger.info(f"Validating repository: {repo_name}")
        
        # Validate repository using your existing function
        is_valid = await asyncio.to_thread(validate_repo_exists, repo_name)
        
        if is_valid:
            response_text = f"✅ **Repository Validation Successful**\n\nRepository '{repo_name}' exists and is accessible for ingestion and analysis."
        else:
            response_text = f"❌ **Repository Validation Failed**\n\nRepository '{repo_name}' was not found or is not accessible. Please check:\n• Repository name format (owner/repo)\n• Repository visibility (public vs private)\n• GitHub token permissions"
        
        return CallToolResult(
            content=[TextContent(type="text", text=response_text)]
        )
    
    except Exception as e:
        error_msg = f"Repository validation failed: {str(e)}"
        logger.error(error_msg)
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {error_msg}")]
        )

async def main():
    """Main function to run the MCP server."""
    logger.info("Starting GitHub Issue Resolution MCP Server...")
    
    # Check environment variables
    required_env_vars = ["GOOGLE_API_KEY", "GITHUB_TOKEN", "GOOGLE_DOCS_ID"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Import and run server with stdio transport
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializeResult(
                protocolVersion="2024-11-05",
                capabilities=SERVER_CAPABILITIES,
                serverInfo=SERVER_INFO,
            ),
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)