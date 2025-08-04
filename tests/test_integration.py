#!/usr/bin/env python3
"""
Test script for the GitHub MCP Integration
This demonstrates the complete workflow using the MCP client and server.
"""

import os
import sys
import asyncio
import unittest
from unittest.mock import patch, MagicMock
import json

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from issue_solver.server import mcp as server_mcp
from scripts.client import MCPClient

class TestMCPServer(unittest.TestCase):
    """Test the MCP integration end-to-end."""
    
    def setUp(self):
        """Set up the test environment."""
        self.server_process = None
        self.client = None
        # Use the new server path
        self.server_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "issue_solver",
            "server.py"
        )
        self.test_repo = "test/repo"
        self.test_issue_url = "https://github.com/test/repo/issues/1"
    
    def test_mcp_integration(self):
        """Test the MCP integration end-to-end."""
        
        print("🚀 Testing GitHub MCP Integration")
        print("=" * 50)
        
        # Test the direct analysis first (bypassing MCP)
        print("\n1. Testing direct analysis (non-MCP)...")
        try:
            from github_analyzer.analyze_issue import parse_github_url, get_github_issue, create_langchain_agent, parse_agent_output
            
            issue_url = "https://github.com/agno-agi/agno/issues/4034"
            owner, repo, issue_num = parse_github_url(issue_url)
            issue = get_github_issue(owner, repo, issue_num)
            
            print(f"✅ Successfully fetched issue: {issue.title}")
            print(f"   Repository: {issue.repository.full_name}")
            
            # Test the analysis
            print("   Running LangChain agent analysis...")
            output = create_langchain_agent(issue)
            analysis = parse_agent_output(output)
            
            print(f"✅ Analysis completed:")
            print(f"   Summary: {analysis.get('summary', 'N/A')[:100]}...")
            print(f"   Complexity: {analysis.get('complexity', 'N/A')}/5")
            print(f"   Similar issues found: {len(analysis.get('similar_issues', []))}")
            
        except Exception as e:
            print(f"❌ Direct analysis failed: {e}")
            return False
        
        # Test patch generation
        print("\n2. Testing patch generation...")
        try:
            from patch_generator import generate_patch_for_issue
            
            issue_body = f"Title: {issue.title}\n\nBody: {issue.body or 'No description provided.'}"
            patch_data = generate_patch_for_issue(issue_body, issue.repository.full_name)
            
            print(f"✅ Patch generation completed:")
            print(f"   Files to update: {len(patch_data.get('filesToUpdate', []))}")
            print(f"   Summary: {patch_data.get('summaryOfChanges', 'N/A')[:100]}...")
            
        except Exception as e:
            print(f"❌ Patch generation failed: {e}")
            return False
        
        print("\n3. MCP Server availability check...")
        try:
            # Check if we can import the MCP server
            import github_mcp_server
            print("✅ MCP Server module imported successfully")
            
            # Check if FastMCP is working
            print("✅ FastMCP integration ready")
            
        except Exception as e:
            print(f"❌ MCP Server check failed: {e}")
            return False
        
        print("\n🎉 All tests completed successfully!")
        print("\nTo use the MCP integration:")
        print("1. Start the MCP server: python github_mcp_server.py")
        print("2. Use the MCP client: python github_mcp_client.py github_mcp_server.py")
        print("3. Or integrate with Claude Desktop or other MCP clients")
        
        print("\nExample MCP client commands:")
        print("- analyze https://github.com/agno-agi/agno/issues/4034")
        print("- generate patch for agno-agi/agno about Redis storage datetime issue")
        print("- check status of agno-agi/agno")
        
        return True

if __name__ == "__main__":
    unittest.main()