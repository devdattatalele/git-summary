#!/usr/bin/env python3
"""
GitHub MCP Client - A client to interact with the GitHub issue resolution MCP server.

This client connects to the GitHub MCP server and provides a chat interface
for interacting with GitHub issue analysis and resolution tools using Google Gemini.

Usage:
    python scripts/client.py <server_module_path>
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# MCP client imports
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Google Generative AI imports
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class MCPClient:
    """MCP Client for GitHub issue resolution using Google Gemini."""
    
    def __init__(self):
        """Initialize the MCP client with Google Gemini."""
        self.session: Optional[ClientSession] = None
        self.available_tools: List[Dict[str, Any]] = []
        
        # Configure Google Gemini
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        genai.configure(api_key=api_key)
        
        # Initialize the Gemini model
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        print("🤖 GitHub MCP Client initialized with Google Gemini")
    
    async def connect_to_server(self, server_script: str):
        """Connect to the MCP server."""
        try:
            # Determine the server script path
            if not os.path.isabs(server_script):
                server_script = os.path.abspath(server_script)
            
            if not os.path.exists(server_script):
                raise FileNotFoundError(f"Server script not found: {server_script}")
            
            print(f"🔌 Connecting to MCP server: {server_script}")
            
            # Create server parameters
            server_params = StdioServerParameters(
                command="python",
                args=[server_script],
                env=dict(os.environ)  # Pass through all environment variables
            )
            
            # Connect to the server
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    
                    # Initialize the session
                    await session.initialize()
                    
                    # List available tools
                    tools_response = await session.list_tools()
                    self.available_tools = tools_response.tools
                    
                    print(f"✅ Connected to server. Available tools: {len(self.available_tools)}")
                    for tool in self.available_tools:
                        print(f"   📋 {tool.name}: {tool.description}")
                    
                    # Start the chat loop
                    await self.chat_loop()
        
        except Exception as e:
            print(f"❌ Failed to connect to server: {e}")
            raise
    
    async def process_query(self, user_input: str) -> str:
        """Process a user query using Gemini and available MCP tools."""
        try:
            if not self.session:
                return "❌ Error: Not connected to MCP server"
            
            # Prepare the system message with available tools
            tools_description = self._format_tools_for_llm()
            
            system_message = f"""You are an AI assistant that helps with GitHub issue analysis and resolution.

You have access to the following tools through MCP (Model Context Protocol):

{tools_description}

When a user asks about GitHub issues or wants to resolve them, use the appropriate tools to help them.
Always explain what you're doing and provide clear, helpful responses.

Guidelines:
1. For GitHub issue analysis, use analyze_github_issue_tool with the full GitHub issue URL
2. For generating code patches, use generate_code_patch_tool with the issue body and repository name
3. For creating pull requests, use create_github_pr_tool with the patch data from step 2
4. Always provide clear explanations of what each tool does and what results you get

User query: {user_input}"""

            # Create chat with Gemini
            chat = self.model.start_chat(history=[])
            
            # Send the query and get response
            response = await asyncio.to_thread(
                chat.send_message, 
                system_message
            )
            
            response_text = response.text
            
            # Check if the response contains tool usage requests
            if any(tool.name in response_text.lower() for tool in self.available_tools):
                # Try to extract and execute tool calls
                response_text = await self._handle_tool_calls(response_text, user_input)
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return f"❌ Error processing query: {str(e)}"
    
    def _format_tools_for_llm(self) -> str:
        """Format available tools for the LLM context."""
        tools_text = ""
        for tool in self.available_tools:
            tools_text += f"\n🔧 **{tool.name}**\n"
            tools_text += f"   Description: {tool.description}\n"
            
            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                if 'properties' in tool.inputSchema:
                    tools_text += "   Parameters:\n"
                    for param_name, param_info in tool.inputSchema['properties'].items():
                        required = param_name in tool.inputSchema.get('required', [])
                        req_text = " (required)" if required else " (optional)"
                        param_desc = param_info.get('description', 'No description')
                        tools_text += f"     - {param_name}{req_text}: {param_desc}\n"
            tools_text += "\n"
        
        return tools_text
    
    async def _handle_tool_calls(self, llm_response: str, original_query: str) -> str:
        """Handle tool calls based on LLM response."""
        # This is a simplified tool calling mechanism
        # In a production system, you'd parse the LLM response more carefully
        
        result_text = llm_response + "\n\n"
        
        # Check for specific tool patterns in the LLM response
        lower_response = llm_response.lower()
        
        if "analyze_github_issue_tool" in lower_response:
            # Try to extract GitHub URL from original query
            github_url = self._extract_github_url(original_query)
            if github_url:
                result_text += await self._call_analyze_tool(github_url)
        
        elif "generate_code_patch_tool" in lower_response:
            result_text += "\n🔧 To generate a code patch, I need:\n"
            result_text += "1. Issue body text\n"
            result_text += "2. Repository name (owner/repo format)\n"
            result_text += "Please provide these details to proceed.\n"
        
        elif "create_github_pr_tool" in lower_response:
            result_text += "\n🔧 To create a GitHub PR, I need:\n"
            result_text += "1. Patch data (JSON from generate_code_patch_tool)\n"
            result_text += "2. Repository name (owner/repo format)\n" 
            result_text += "3. Issue number\n"
            result_text += "Please provide these details to proceed.\n"
        
        return result_text
    
    def _extract_github_url(self, text: str) -> Optional[str]:
        """Extract GitHub issue URL from text."""
        import re
        
        # Pattern to match GitHub issue URLs
        pattern = r'https://github\.com/[^/]+/[^/]+/issues/\d+'
        matches = re.findall(pattern, text)
        
        return matches[0] if matches else None
    
    async def _call_analyze_tool(self, github_url: str) -> str:
        """Call the analyze_github_issue_tool."""
        try:
            print(f"🔍 Analyzing GitHub issue: {github_url}")
            
            result = await self.session.call_tool(
                "analyze_github_issue_tool",
                arguments={"issue_url": github_url}
            )
            
            if result.content:
                # Parse the JSON response
                analysis_data = json.loads(result.content[0].text)
                
                formatted_result = f"""
🎯 **GitHub Issue Analysis Results:**

📋 **Summary:** {analysis_data.get('summary', 'N/A')}

🔧 **Proposed Solution:** {analysis_data.get('proposed_solution', 'N/A')}

📊 **Complexity:** {analysis_data.get('complexity', 'N/A')}/5

🔍 **Similar Issues Found:** {len(analysis_data.get('similar_issues', []))}
"""
                
                if analysis_data.get('similar_issues'):
                    formatted_result += "\n**Similar Issues:**\n"
                    for issue in analysis_data.get('similar_issues', [])[:3]:  # Show top 3
                        formatted_result += f"- {issue}\n"
                
                return formatted_result
            else:
                return "❌ No content returned from analysis tool"
        
        except Exception as e:
            return f"❌ Error calling analysis tool: {str(e)}"
    
    async def call_tool_directly(self, tool_name: str, **kwargs) -> str:
        """Directly call a tool with provided arguments."""
        try:
            if not self.session:
                return "❌ Error: Not connected to MCP server"
            
            print(f"🔧 Calling tool: {tool_name}")
            
            result = await self.session.call_tool(tool_name, arguments=kwargs)
            
            if result.content:
                if tool_name == "analyze_github_issue_tool":
                    # Format analysis results nicely
                    try:
                        analysis_data = json.loads(result.content[0].text)
                        return self._format_analysis_result(analysis_data)
                    except json.JSONDecodeError:
                        return result.content[0].text
                
                elif tool_name == "generate_code_patch_tool":
                    # Format patch results nicely  
                    try:
                        patch_data = json.loads(result.content[0].text)
                        return self._format_patch_result(patch_data)
                    except json.JSONDecodeError:
                        return result.content[0].text
                
                else:
                    return result.content[0].text
            else:
                return f"✅ Tool {tool_name} executed successfully (no content returned)"
        
        except Exception as e:
            return f"❌ Error calling tool {tool_name}: {str(e)}"
    
    def _format_analysis_result(self, analysis_data: Dict[str, Any]) -> str:
        """Format analysis results for display."""
        # Check if this is the new detailed format
        if 'detailed_report' in analysis_data and 'analysis' in analysis_data:
            # New format - display the detailed report that matches the original analyze_issue.py output
            result = f"""
🎯 **GitHub Issue Analysis Complete!**

{analysis_data['detailed_report']}

📊 **Summary Data:**
• Complexity: {analysis_data['analysis'].get('complexity', 'N/A')}/5
• Similar Issues: {len(analysis_data['analysis'].get('similar_issues', []))} found
• Repository: {analysis_data['issue_info'].get('repository', 'N/A')}
• Issue #{analysis_data['issue_info'].get('number', 'N/A')}: {analysis_data['issue_info'].get('title', 'N/A')}

✅ Analysis has been saved to Google Docs (if configured)
"""
            
            # Add similar issues if found
            if analysis_data['analysis'].get('similar_issues'):
                result += "\n🔍 **Similar Issues Found:**\n"
                for i, issue in enumerate(analysis_data['analysis'].get('similar_issues', [])[:5], 1):
                    result += f"{i}. {issue}\n"
        else:
            # Fallback to old format for compatibility
            result = f"""
🎯 **GitHub Issue Analysis Results:**

📋 **Summary:** 
{analysis_data.get('summary', 'N/A')}

🔧 **Proposed Solution:** 
{analysis_data.get('proposed_solution', 'N/A')}

📊 **Complexity Level:** {analysis_data.get('complexity', 'N/A')}/5

🔍 **Similar Issues Found:** {len(analysis_data.get('similar_issues', []))}
"""
            
            if analysis_data.get('similar_issues'):
                result += "\n**Similar Issues:**\n"
                for i, issue in enumerate(analysis_data.get('similar_issues', [])[:5], 1):
                    result += f"{i}. {issue}\n"
        
        return result
    
    def _format_patch_result(self, patch_data: Dict[str, Any]) -> str:
        """Format patch results for display."""
        files_to_update = patch_data.get('filesToUpdate', [])
        summary = patch_data.get('summaryOfChanges', 'N/A')
        
        result = f"""
🔧 **Code Patch Generated:**

📝 **Summary of Changes:**
{summary}

📁 **Files to Update:** {len(files_to_update)}
"""
        
        for i, file_info in enumerate(files_to_update[:3], 1):  # Show first 3 files
            file_path = file_info.get('filePath', 'Unknown')
            function_name = file_info.get('functionName', 'N/A')
            result += f"\n{i}. **File:** {file_path}"
            if function_name != 'N/A':
                result += f" (Function: {function_name})"
            result += f"\n   **Patch Preview:** {file_info.get('patch', 'N/A')[:200]}...\n"
        
        if len(files_to_update) > 3:
            result += f"\n... and {len(files_to_update) - 3} more files"
        
        return result
    
    async def chat_loop(self):
        """Main chat loop for user interaction."""
        print("\n💬 GitHub Issue Resolution Assistant")
        print("="*50)
        print("🚀 **WORKFLOW:** First ingest a repository, then analyze issues!")
        print("\nCommands:")
        print("  📥 ingest <owner/repo> - Ingest repository for analysis (REQUIRED FIRST)")
        print("  🔍 analyze <github_issue_url> - Analyze a GitHub issue")
        print("  🔧 patch <repo_name> <issue_body> - Generate code patch") 
        print("  📋 pr <repo_name> <issue_number> <patch_json> - Create PR")
        print("  💭 <message> - Chat with AI assistant")
        print("  ❌ quit - Exit the client")
        print("="*50)
        print("\n🔔 **Getting Started:**")
        print("1. First run: ingest microsoft/vscode")
        print("2. Then run: analyze https://github.com/microsoft/vscode/issues/12345")
        print("3. Generate patches and create PRs as needed")
        print("="*50)
        
        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                # Handle direct tool calls
                if user_input.startswith('ingest '):
                    repo_name = user_input[7:].strip()
                    if repo_name:
                        print(f"🔄 Starting ingestion for {repo_name}... This may take several minutes.")
                        response = await self.call_tool_directly(
                            "ingest_repository_tool",
                            repo_name=repo_name
                        )
                        print(f"\n🤖 Assistant:\n{response}")
                    else:
                        print("Usage: ingest <owner/repo>")
                        print("Example: ingest microsoft/vscode")
                
                elif user_input.startswith('analyze '):
                    github_url = user_input[8:].strip()
                    response = await self.call_tool_directly(
                        "analyze_github_issue_tool", 
                        issue_url=github_url
                    )
                    print(f"\n🤖 Assistant:\n{response}")
                
                elif user_input.startswith('patch '):
                    # Simple parsing - in production you'd want better argument parsing
                    parts = user_input[6:].strip().split(' ', 1)
                    if len(parts) >= 2:
                        repo_name = parts[0]
                        issue_body = parts[1]
                        response = await self.call_tool_directly(
                            "generate_code_patch_tool",
                            issue_body=issue_body,
                            repo_full_name=repo_name
                        )
                        print(f"\n🤖 Assistant:\n{response}")
                    else:
                        print("Usage: patch <repo_name> <issue_body>")
                
                elif user_input.startswith('pr '):
                    # Simple parsing for PR creation
                    parts = user_input[3:].strip().split(' ', 2)
                    if len(parts) >= 3:
                        repo_name = parts[0]
                        issue_number = int(parts[1])
                        patch_json = parts[2]
                        response = await self.call_tool_directly(
                            "create_github_pr_tool",
                            patch_data_json=patch_json,
                            repo_full_name=repo_name,
                            issue_number=issue_number
                        )
                        print(f"\n🤖 Assistant:\n{response}")
                    else:
                        print("Usage: pr <repo_name> <issue_number> <patch_json>")
                
                else:
                    # Regular chat with the assistant
                    response = await self.process_query(user_input)
                    print(f"\n🤖 Assistant:\n{response}")
            
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")

async def main():
    """Main function to run the MCP client."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/client.py <server_module_path>")
        print("Example: python scripts/client.py issue_solver.server")
        sys.exit(1)
    
    server_script = sys.argv[1]
    
    try:
        client = MCPClient()
        await client.connect_to_server(server_script)
    except Exception as e:
        print(f"❌ Failed to start client: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 