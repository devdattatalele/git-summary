# github_mcp_client.py
"""
MCP Client for GitHub Issue Resolution System using Google Gemini
"""

import asyncio
import logging
import json
import os
import sys
from typing import Dict, List, Any
from dotenv import load_dotenv

# Google Gemini imports
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# MCP imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class GitHubMCPClient:
    """MCP Client for GitHub issue resolution using Google Gemini."""
    
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        # Configure Google Gemini
        genai.configure(api_key=self.google_api_key)
        
        # Initialize Gemini model
        self.model = genai.GenerativeModel(
            'gemini-1.5-pro-latest',
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=4096,
                response_mime_type="text/plain"
            ),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        self.session = None
        self.available_tools = []

    async def connect_to_server(self, server_script_path: str):
        """Connect to the MCP server."""
        try:
            # Server parameters for the GitHub MCP server
            server_params = StdioServerParameters(
                command="python",
                args=[server_script_path],
                env=dict(os.environ)  # Pass through all environment variables
            )
            
            # Create stdio client connection
            stdio_transport = await stdio_client(server_params)
            self.session = ClientSession(stdio_transport[0], stdio_transport[1])
            
            # Initialize the session
            await self.session.initialize()
            
            # List available tools
            tools_response = await self.session.list_tools()
            self.available_tools = tools_response.tools
            
            logger.info(f"Connected to MCP server. Available tools: {[tool.name for tool in self.available_tools]}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False

    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call an MCP tool and return the result."""
        try:
            if not self.session:
                raise RuntimeError("Not connected to MCP server")
            
            # Call the tool
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract content from result
            if hasattr(result, 'content') and result.content:
                return result.content[0].text if result.content[0].text else str(result.content[0])
            else:
                return str(result)
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return f"Error calling tool: {str(e)}"

    def format_tools_for_gemini(self) -> List[Dict[str, Any]]:
        """Format MCP tools for Gemini function calling."""
        gemini_tools = []
        
        for tool in self.available_tools:
            # Convert MCP tool schema to Gemini function calling format
            gemini_tool = {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            
            # Convert input schema if available
            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                schema = tool.inputSchema
                if isinstance(schema, dict) and "properties" in schema:
                    gemini_tool["parameters"]["properties"] = schema["properties"]
                    if "required" in schema:
                        gemini_tool["parameters"]["required"] = schema["required"]
            
            gemini_tools.append(gemini_tool)
        
        return gemini_tools

    async def process_query(self, user_query: str) -> str:
        """Process a user query using Gemini with MCP tool calling."""
        try:
            if not self.session:
                return "Error: Not connected to MCP server. Please connect first."
            
            # Format tools for Gemini
            tools = self.format_tools_for_gemini()
            
            # Create the system prompt
            system_prompt = f"""You are an AI assistant that helps with GitHub issue resolution. You have access to the following tools:

{json.dumps(tools, indent=2)}

When a user asks you to analyze a GitHub issue or generate patches, use the appropriate tools:
1. analyze_github_issue_tool: For analyzing GitHub issues
2. generate_code_patch_tool: For generating code patches  
3. create_github_pr_tool: For creating Pull Requests
4. get_repository_status: For checking repository knowledge base status

Always provide clear, helpful responses and explain what actions you're taking."""

            # Create the conversation
            messages = [
                {"role": "user", "content": f"{system_prompt}\n\nUser Query: {user_query}"}
            ]
            
            # Start chat with function calling
            chat = self.model.start_chat(history=[])
            
            # Send message with tools
            response = await asyncio.to_thread(
                chat.send_message,
                user_query,
                tools=[genai.protos.Tool(function_declarations=[
                    genai.protos.FunctionDeclaration(
                        name=tool["name"],
                        description=tool["description"],
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                k: genai.protos.Schema(
                                    type=getattr(genai.protos.Type, v.get("type", "STRING").upper()),
                                    description=v.get("description", "")
                                ) for k, v in tool["parameters"]["properties"].items()
                            },
                            required=tool["parameters"].get("required", [])
                        )
                    ) for tool in tools
                ])]
            )
            
            # Process function calls if any
            if response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        # Extract function call details
                        func_call = part.function_call
                        tool_name = func_call.name
                        arguments = dict(func_call.args)
                        
                        logger.info(f"Calling tool: {tool_name} with args: {arguments}")
                        
                        # Call the MCP tool
                        tool_result = await self.call_mcp_tool(tool_name, arguments)
                        
                        # Send function result back to Gemini
                        function_response = await asyncio.to_thread(
                            chat.send_message,
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"result": tool_result}
                                )
                            )
                        )
                        
                        return function_response.text
                    elif hasattr(part, 'text') and part.text:
                        return part.text
            
            # If no function calls, return the direct response
            return response.text if hasattr(response, 'text') else str(response)
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return f"Error processing query: {str(e)}"

    async def chat_loop(self):
        """Interactive chat loop."""
        print("GitHub Issue Resolution Assistant (Powered by MCP + Gemini)")
        print("=" * 60)
        print("Available commands:")
        print("- Analyze issue: 'analyze https://github.com/owner/repo/issues/123'")
        print("- Generate patch: 'generate patch for issue about [description]'")
        print("- Check repository: 'check status of owner/repo'")
        print("- Help: 'help' or '?'")
        print("- Quit: 'quit' or 'exit'")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\n🤖 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("\n👋 Goodbye!")
                    break
                
                if user_input.lower() in ['help', '?']:
                    print("""
Available operations:
1. Analyze GitHub Issue: 
   - "analyze https://github.com/owner/repo/issues/123"
   - Provides summary, complexity, and proposed solution

2. Generate Code Patch:
   - "generate patch for owner/repo about login issue"
   - Creates unified diff patches for the issue

3. Create Pull Request:
   - "create PR for patch data and repo owner/repo issue 123"
   - Creates a draft PR with generated patches

4. Check Repository Status:
   - "check status of owner/repo" 
   - Shows knowledge base availability

Example workflow:
- analyze https://github.com/microsoft/vscode/issues/12345
- generate patch for microsoft/vscode about the terminal bug
- create PR with the generated patch
                    """)
                    continue
                
                if not user_input:
                    continue
                
                print("\n🔍 Processing...")
                response = await self.process_query(user_input)
                print(f"\n🤖 Assistant: {response}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")

    async def close(self):
        """Close the MCP session."""
        if self.session:
            await self.session.close()

async def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python github_mcp_client.py <server_script_path>")
        print("Example: python github_mcp_client.py github_mcp_server.py")
        sys.exit(1)
    
    server_script = sys.argv[1]
    
    # Check if server script exists
    if not os.path.exists(server_script):
        print(f"Error: Server script '{server_script}' not found")
        sys.exit(1)
    
    client = GitHubMCPClient()
    
    try:
        # Connect to the MCP server
        print(f"Connecting to MCP server: {server_script}")
        if await client.connect_to_server(server_script):
            print("✅ Connected successfully!")
            
            # Start interactive chat
            await client.chat_loop()
        else:
            print("❌ Failed to connect to MCP server")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main()) 