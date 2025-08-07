#!/usr/bin/env python3
"""
Setup and validation script for GitHub Issue Resolution MCP Server

This script:
1. Validates all required dependencies are installed
2. Checks environment variables
3. Tests module imports
4. Provides setup instructions
5. Validates MCP server functionality
"""

import os
import sys
import subprocess
import importlib
from pathlib import Path
# add dotenv loader
from dotenv import load_dotenv

# load .env into environment
load_dotenv()

def check_python_version():
    """Check if Python version is 3.10 or higher."""
    print("🐍 Checking Python version...")
    
    if sys.version_info < (3, 10):
        print(f"❌ Python 3.10+ required. Current version: {sys.version}")
        return False
    
    print(f"✅ Python version: {sys.version}")
    return True

def check_pip_packages():
    """Check if all required packages are installed."""
    print("\n📦 Checking required packages...")
    
    required_packages = [
        "python-dotenv",
        "PyGithub", 
        "google-generativeai",
        "langchain",
        "langchain-core",
        "langchain-chroma", 
        "langchain-google-genai",
        "chromadb",
        "mcp",
        "httpx",
        "aiofiles",
        "tqdm"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            # Try to import the package
            if package == "PyGithub":
                importlib.import_module("github")
            elif package == "python-dotenv":
                importlib.import_module("dotenv")
            elif package == "google-generativeai":
                importlib.import_module("google.generativeai")
            else:
                importlib.import_module(package.replace("-", "_"))
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("\n💡 To install missing packages, run:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_environment_variables():
    """Check if required environment variables are set."""
    print("\n🔐 Checking environment variables...")
    
    required_vars = ["GOOGLE_API_KEY", "GITHUB_TOKEN"]
    optional_vars = ["GOOGLE_DOCS_ID"]
    
    missing_required = []
    
    for var in required_vars:
        if os.getenv(var):
            print(f"  ✅ {var} (set)")
        else:
            print(f"  ❌ {var} (missing)")
            missing_required.append(var)
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"  ✅ {var} (optional, set)")
        else:
            print(f"  ⚠️  {var} (optional, not set)")
    
    if missing_required:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_required)}")
        print("\n💡 Create a .env file with:")
        for var in missing_required:
            print(f"{var}=your_{var.lower()}_here")
        return False
    
    print("✅ All required environment variables are set")
    return True

def check_project_structure():
    """Check if project structure is correct."""
    print("\n📁 Checking project structure...")
    
    current_dir = Path.cwd()
    required_structure = {
        "issue_solver/__init__.py": "Package initialization file",
        "issue_solver/server.py": "Original server module", 
        "issue_solver/analyze.py": "Issue analysis module",
        "issue_solver/ingest.py": "Repository ingestion module",
        "issue_solver/patch.py": "Patch generation module",
        "github_issue_mcp_server.py": "Main MCP server",
        "requirements.txt": "Dependencies file"
    }
    
    missing_files = []
    
    for file_path, description in required_structure.items():
        full_path = current_dir / file_path
        if full_path.exists():
            print(f"  ✅ {file_path} ({description})")
        else:
            print(f"  ❌ {file_path} ({description})")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ Missing files: {', '.join(missing_files)}")
        return False
    
    print("✅ Project structure is correct")
    return True

def test_module_imports():
    """Test importing the issue_solver modules."""
    print("\n🔧 Testing module imports...")
    
    # Add current directory to Python path
    current_dir = str(Path.cwd())
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    modules_to_test = [
        ("issue_solver.analyze", "Issue analysis module"),
        ("issue_solver.ingest", "Repository ingestion module"), 
        ("issue_solver.patch", "Patch generation module"),
        ("mcp.server.fastmcp", "FastMCP server")
    ]
    
    failed_imports = []
    
    for module_name, description in modules_to_test:
        try:
            importlib.import_module(module_name)
            print(f"  ✅ {module_name} ({description})")
        except ImportError as e:
            print(f"  ❌ {module_name} ({description}) - Error: {e}")
            failed_imports.append((module_name, str(e)))
    
    if failed_imports:
        print(f"\n❌ Failed to import {len(failed_imports)} modules")
        for module_name, error in failed_imports:
            print(f"  • {module_name}: {error}")
        return False
    
    print("✅ All modules imported successfully")
    return True

def test_mcp_server():
    """Test that the MCP server can be started (dry run)."""
    print("\n🚀 Testing MCP server initialization...")
    
    try:
        # Import the server module without running it
        import github_issue_mcp_server
        print("  ✅ MCP server module loads successfully")
        
        # Check if FastMCP instance is created
        if hasattr(github_issue_mcp_server, 'mcp'):
            print("  ✅ FastMCP instance created")
        else:
            print("  ❌ FastMCP instance not found")
            return False
        
        print("✅ MCP server is ready to run")
        return True
        
    except Exception as e:
        print(f"  ❌ MCP server initialization failed: {e}")
        return False

def create_claude_config():
    """Create Claude Desktop configuration file."""
    print("\n🔧 Creating Claude Desktop configuration...")
    
    current_dir = Path.cwd()
    
    # Find Python executable - prioritize the one with MCP installed
    import shutil
    
    # Test different Python executables to find one with MCP
    test_pythons = [
        shutil.which("python"),  # Homebrew Python (usually has packages)
        shutil.which("python3"), # System Python
        "/opt/homebrew/opt/python@3.13/bin/python3.13",  # Specific Homebrew path
        "/usr/local/bin/python3", # Alternative locations
        "python3"  # fallback
    ]
    
    python_path = None
    for test_python in test_pythons:
        if test_python and os.path.exists(test_python):
            # Test if this Python has MCP installed
            import subprocess
            try:
                result = subprocess.run([test_python, "-c", "import mcp"], 
                                      capture_output=True, timeout=5)
                if result.returncode == 0:
                    python_path = test_python
                    print(f"  ✅ Found Python with MCP: {python_path}")
                    break
            except:
                continue
    
    if not python_path:
        python_path = "python3"  # fallback
        print(f"  ⚠️  No Python with MCP found, using fallback: {python_path}")
    
    config_content = {
        "mcpServers": {
            "github-issue-resolver": {
                "command": python_path,
                "args": [str(current_dir / "github_issue_mcp_server.py")],
                "env": {
                    "PYTHONPATH": str(current_dir),
                    "CHROMA_PERSIST_DIR": str(current_dir / "chroma_db")
                }
            }
        }
    }
    
    # Determine config path based on OS
    home = Path.home()
    if sys.platform == "darwin":  # macOS
        config_dir = home / "Library" / "Application Support" / "Claude"
    elif sys.platform == "win32":  # Windows
        config_dir = home / "AppData" / "Roaming" / "Claude"
    else:  # Linux
        config_dir = home / ".config" / "claude"
    
    # Create local config file for user to copy
    local_config_dir = current_dir / "config"
    local_config_dir.mkdir(exist_ok=True)
    local_config_file = local_config_dir / "claude_desktop_config.json"
    
    config_file = config_dir / "claude_desktop_config.json"
    
    try:
        import json
        
        # Create directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Write local config file for user to copy
        with open(local_config_file, 'w') as f:
            json.dump(config_content, f, indent=2)
        
        print(f"  ✅ Configuration created at: {local_config_file}")
        print(f"  📋 To activate, copy to Claude Desktop:")
        
        if sys.platform == "darwin":  # macOS
            copy_cmd = f"cp {local_config_file} ~/Library/Application\\ Support/Claude/claude_desktop_config.json"
        elif sys.platform == "win32":  # Windows
            copy_cmd = f"copy {local_config_file} %APPDATA%\\Claude\\claude_desktop_config.json"
        else:  # Linux
            copy_cmd = f"cp {local_config_file} ~/.config/claude/claude_desktop_config.json"
        
        print(f"  💻 Command: {copy_cmd}")
        print("  🔄 Then restart Claude Desktop for changes to take effect")
        
        # Also try to write to system location if accessible
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(config_content, f, indent=2)
            print(f"  ✅ Also installed to system location: {config_file}")
        except PermissionError:
            print(f"  ⚠️  Could not write to system location (use copy command above)")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to create configuration: {e}")
        print(f"\n💡 Manual setup: Create the following file at {config_file}:")
        print(json.dumps(config_content, indent=2))
        return False

def print_usage_instructions():
    """Print usage instructions."""
    print("\n" + "="*60)
    print("🎉 SETUP COMPLETE!")
    print("="*60)
    
    print("\n📋 USAGE INSTRUCTIONS:")
    print("\n1. 🚀 Start the MCP server:")
    print("   python github_issue_mcp_server.py")
    
    print("\n2. 🔧 Configure Claude Desktop:")
    print("   • Restart Claude Desktop")
    print("   • Look for the tools icon in Claude Desktop")
    print("   • Your server should appear as 'github-issue-resolver'")
    
    print("\n3. 🎯 First steps in Claude:")
    print("   • Ingest a repository: 'Ingest the microsoft/vscode repository'")
    print("   • Analyze an issue: 'Analyze https://github.com/microsoft/vscode/issues/12345'")
    print("   • Generate patches: 'Generate a patch for the login issue in microsoft/vscode'")
    
    print("\n4. 🛠️  Available tools:")
    print("   • ingest_repository_tool - Build knowledge base")
    print("   • analyze_github_issue_tool - Analyze issues")
    print("   • generate_code_patch_tool - Generate patches")
    print("   • create_github_pr_tool - Create pull requests")
    print("   • get_repository_status - Check status")
    print("   • validate_repository_tool - Validate access")
    
    print("\n💡 TIPS:")
    print("   • Always ingest a repository before analyzing its issues")
    print("   • Check logs in ~/Library/Logs/Claude/ if issues occur")
    print("   • Use stderr logging only (never print to stdout)")
    
    print("\n🔗 HELPFUL COMMANDS:")
    print("   python github_issue_mcp_server.py  # Start server")
    print("   python setup_mcp_server.py        # Run this setup again")

def main():
    """Main setup function."""
    print("🔧 GitHub Issue Resolution MCP Server Setup")
    print("="*50)
    
    checks = [
        check_python_version,
        check_pip_packages,
        check_environment_variables,
        check_project_structure,
        test_module_imports,
        test_mcp_server
    ]
    
    all_passed = True
    for check in checks:
        if not check():
            all_passed = False
    
    if all_passed:
        print("\n🎉 All checks passed!")
        
        # Create Claude Desktop config
        create_claude_config()
        
        # Print usage instructions
        print_usage_instructions()
        
    else:
        print("\n❌ Some checks failed. Please fix the issues above before proceeding.")
        print("\n💡 Common fixes:")
        print("  • Install missing packages: pip install -r requirements.txt")
        print("  • Create .env file with required environment variables")
        print("  • Ensure all Python files are in the correct locations")
        
        sys.exit(1)

if __name__ == "__main__":
    main()
