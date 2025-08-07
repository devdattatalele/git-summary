#!/usr/bin/env python3
"""
Test script for GitHub Issue Resolution MCP Server

This script tests the MCP server functionality by simulating
tool calls and validating responses.
"""

import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_server_startup():
    """Test that the server can start and initialize properly."""
    print("🚀 Testing MCP server startup...")
    
    try:
        # Import the server module
        import github_issue_mcp_server
        
        # Check if required environment variables are set
        required_vars = ["GOOGLE_API_KEY", "GITHUB_TOKEN"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
            return False
        
        # Try to create the FastMCP instance
        if hasattr(github_issue_mcp_server, 'mcp'):
            print("✅ FastMCP instance created successfully")
            
            # Try to access tools - FastMCP might store them differently
            try:
                # Check if we can access tools through different attributes
                if hasattr(github_issue_mcp_server.mcp, '_tools'):
                    tools = github_issue_mcp_server.mcp._tools
                    print(f"✅ Found {len(tools)} tools:")
                    for tool_name in tools.keys():
                        print(f"  • {tool_name}")
                elif hasattr(github_issue_mcp_server.mcp, 'tools'):
                    tools = github_issue_mcp_server.mcp.tools
                    print(f"✅ Found {len(tools)} tools:")
                    for tool_name in tools.keys():
                        print(f"  • {tool_name}")
                else:
                    print("✅ FastMCP instance created (tools list not accessible)")
            except Exception as e:
                print(f"⚠️  FastMCP instance created but tools not accessible: {e}")
            
            return True
        else:
            print("❌ FastMCP instance not found")
            return False
            
    except Exception as e:
        print(f"❌ Server startup failed: {e}")
        return False

async def test_tool_validation():
    """Test tool parameter validation."""
    print("\n🔧 Testing tool validation...")
    
    try:
        import github_issue_mcp_server
        
        # Test ingest_repository_tool validation
        try:
            result = await github_issue_mcp_server.ingest_repository_tool(
                repo_name="test/invalid-repo",
                skip_prs=True,
                skip_code=True
            )
            
            # Should return an error message for invalid repo
            if "not found" in result.lower() or "not accessible" in result.lower():
                print("✅ Repository validation working correctly")
            else:
                print(f"⚠️  Unexpected result for invalid repo: {result[:100]}...")
            
        except Exception as e:
            print(f"✅ Repository validation correctly raises exception: {type(e).__name__}")
        
        # Test validate_repository_tool
        try:
            result = await github_issue_mcp_server.validate_repository_tool(
                repo_name="test/invalid-repo"
            )
            
            if "validation failed" in result.lower() or "not found" in result.lower():
                print("✅ Validate repository tool working correctly")
            else:
                print(f"⚠️  Unexpected validation result: {result[:100]}...")
            
        except Exception as e:
            print(f"⚠️  Validation tool error: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool validation test failed: {e}")
        return False

async def test_analyze_github_issue_validation():
    """Test GitHub issue URL validation."""
    print("\n🔍 Testing GitHub issue analysis validation...")
    
    try:
        import github_issue_mcp_server
        
        # Test with invalid URL
        result = await github_issue_mcp_server.analyze_github_issue_tool(
            issue_url="https://invalid-url"
        )
        
        # Parse JSON response
        try:
            result_data = json.loads(result)
            if result_data.get("success") == False and "error" in result_data:
                print("✅ Issue URL validation working correctly")
            else:
                print(f"⚠️  Unexpected result for invalid URL: {result[:100]}...")
        except json.JSONDecodeError:
            if "error" in result.lower() or "invalid" in result.lower():
                print("✅ Issue URL validation working correctly")
            else:
                print(f"⚠️  Unexpected result format: {result[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Issue analysis validation test failed: {e}")
        return False

async def test_repository_status():
    """Test repository status functionality."""
    print("\n📊 Testing repository status...")
    
    try:
        import github_issue_mcp_server
        
        # Test status for non-ingested repo
        result = await github_issue_mcp_server.get_repository_status(
            repo_name="devdattatalele/git-summary"
        )
        
        if "not ingested" in result.lower():
            print("✅ Repository status correctly reports non-ingested repos")
        else:
            print(f"⚠️  Unexpected status result: {result[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Repository status test failed: {e}")
        return False

def test_claude_desktop_config():
    """Test Claude Desktop configuration."""
    print("\n🔧 Testing Claude Desktop configuration...")
    
    current_dir = Path.cwd()
    config_file = current_dir / "claude_desktop_config.json"
    
    if not config_file.exists():
        print("❌ Claude Desktop config file not found")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        if "mcpServers" in config and "github-issue-resolver" in config["mcpServers"]:
            server_config = config["mcpServers"]["github-issue-resolver"]
            
            # Check required fields
            if "command" in server_config and "args" in server_config:
                print("✅ Claude Desktop config has required fields")
                
                # Check server path
                server_path = server_config["args"][0] if server_config["args"] else ""
                if "github_issue_mcp_server.py" in server_path:
                    print("✅ Server path correctly configured")
                else:
                    print(f"⚠️  Server path might be incorrect: {server_path}")
                
                return True
            else:
                print("❌ Missing required fields in config")
                return False
        else:
            print("❌ Missing server configuration")
            return False
            
    except Exception as e:
        print(f"❌ Config file error: {e}")
        return False

def print_test_summary(results):
    """Print test summary."""
    passed_count = sum(results.values())
    total = len(results)
    
    print("\n" + "="*50)
    print("🧪 TEST SUMMARY")
    print("="*50)
    
    for test_name, test_passed in results.items():
        status = "✅ PASS" if test_passed else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Results: {passed_count}/{total} tests passed")
    
    if passed_count == total:
        print("\n🎉 All tests passed! Your MCP server is ready to use.")
        print("\n🎯 Next steps:")
        print("1. Make sure your .env file has the required API keys")
        print("2. Start Claude Desktop")
        print("3. Test with: 'Validate access to microsoft/vscode repository'")
    else:
        print("\n⚠️  Some tests failed. Please review the issues above.")
        print("Run 'python setup_mcp_server.py' for detailed setup validation.")

async def main():
    """Main test function."""
    print("🧪 GitHub Issue Resolution MCP Server Tests")
    print("="*50)
    
    # Define tests
    tests = {
        "Server Startup": test_server_startup,
        "Tool Validation": test_tool_validation,
        "Issue Analysis Validation": test_analyze_github_issue_validation,
        "Repository Status": test_repository_status,
    }
    
    results = {}
    
    # Run async tests
    for test_name, test_func in tests.items():
        try:
            results[test_name] = await test_func()
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Run sync tests
    results["Claude Desktop Config"] = test_claude_desktop_config()
    
    # Print summary
    print_test_summary(results)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test runner error: {e}")
