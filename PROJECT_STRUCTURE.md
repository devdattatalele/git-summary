# Project Structure

This document outlines the organized structure of the GitHub Issue Resolution MCP Server project.

## 📁 Root Directory

```
github-issue-mcp-server/
├── 📄 README.md                    # Main project documentation
├── 📄 LICENSE                      # MIT license
├── 📄 CONTRIBUTING.md               # Contribution guidelines
├── 📄 requirements.txt              # Production dependencies
├── 📄 requirements-dev.txt          # Development dependencies
├── 📄 .gitignore                    # Git ignore rules
├── 📄 env.template                  # Environment variable template
├── 📄 mkdocs.yml                    # Documentation configuration
├── 📄 PROJECT_STRUCTURE.md          # This file
├── 📄 github_issue_mcp_server.py    # Main MCP server
├── 📄 setup_mcp_server.py           # Setup and validation script
└── 📄 test_mcp_server.py            # Test suite
```

## 🔧 Core Components

### **`github_issue_mcp_server.py`**
- Main MCP server implementation
- FastMCP-based tool definitions
- 8 MCP tools for GitHub issue resolution
- Async processing with proper yielding

### **`issue_solver/`** - Core Modules
```
issue_solver/
├── 📄 __init__.py                   # Package initialization
├── 📄 ingest.py                     # Repository ingestion & RAG
├── 📄 analyze.py                    # Issue analysis & AI agents
├── 📄 patch.py                      # Patch generation & PR creation
└── 📄 server.py                     # Legacy server (kept for reference)
```

## 🔧 Configuration & Setup

### **`config/`** - Configuration Files
```
config/
└── 📄 claude_desktop_config.json    # Claude Desktop MCP configuration
```

### **`examples/`** - Usage Examples
```
examples/
└── 📄 client.py                     # Example MCP client implementation
```

### **`tests/`** - Test Suite
```
tests/
└── 📄 test_integration.py           # Integration tests
```

## 📚 Documentation

### **`docs/`** - MkDocs Documentation
```
docs/
├── 📄 index.md                      # Main documentation homepage
├── getting_started/
│   ├── 📄 quickstart.md             # 5-minute setup guide
│   ├── 📄 installation.md           # Detailed installation
│   ├── 📄 configuration.md          # Environment setup
│   └── 📄 claude_setup.md           # Claude Desktop integration
├── concepts/
│   ├── 📄 mcp_overview.md           # Model Context Protocol intro
│   ├── 📄 architecture.md           # System design
│   ├── 📄 rag_system.md             # RAG implementation
│   └── 📄 workflow.md               # Complete process flow
├── usage/
│   ├── 📄 ingestion.md              # Repository ingestion guide
│   ├── 📄 analysis.md               # Issue analysis workflow
│   ├── 📄 patching.md               # Patch generation
│   ├── 📄 multi_repo.md             # Multi-repository management
│   └── 📄 advanced.md               # Power user features
├── api_reference/
│   ├── 📄 server.md                 # MCP server API
│   ├── 📄 ingest.md                 # Ingestion module
│   ├── 📄 analyze.md                # Analysis module
│   ├── 📄 patch.md                  # Patch module
│   └── 📄 tools.md                  # MCP tools reference
├── examples/
│   ├── 📄 basic_usage.md            # Common workflows
│   ├── 📄 advanced_workflows.md     # Complex scenarios
│   └── 📄 integrations.md           # Third-party integrations
├── troubleshooting/
│   ├── 📄 common_issues.md          # FAQ and solutions
│   ├── 📄 performance.md            # Optimization guide
│   └── 📄 debugging.md              # Debug techniques
└── contributing/
    ├── 📄 development.md             # Development setup
    ├── 📄 testing.md                 # Testing guidelines
    └── 📄 documentation.md           # Docs contribution
```

## 🚀 GitHub Integration

### **`.github/workflows/`** - CI/CD Pipelines
```
.github/
└── workflows/
    └── 📄 test.yml                  # Automated testing workflow
```

## 🎯 File Purposes

### **Core Functionality**
- **`github_issue_mcp_server.py`**: Main entry point, MCP protocol implementation
- **`issue_solver/ingest.py`**: Repository data processing, vector database creation
- **`issue_solver/analyze.py`**: AI-powered issue analysis using LangChain
- **`issue_solver/patch.py`**: Code patch generation and GitHub PR creation

### **Setup & Testing**
- **`setup_mcp_server.py`**: Environment validation, dependency checks, configuration generation
- **`test_mcp_server.py`**: Comprehensive test suite for all components
- **`env.template`**: Environment variable template with instructions

### **Documentation**
- **`README.md`**: Project overview, quick start, comprehensive guide
- **`CONTRIBUTING.md`**: Development guidelines, contribution process
- **`docs/`**: Complete MkDocs-powered documentation site

### **Configuration**
- **`requirements.txt`**: Production Python dependencies
- **`requirements-dev.txt`**: Development and testing dependencies
- **`mkdocs.yml`**: Documentation site configuration
- **`.gitignore`**: Version control exclusions

## 🗂️ Data Storage

### **Generated During Runtime**
```
# These directories are created automatically and ignored by git
chroma_db/                           # Vector database (ChromaDB)
├── [collection_ids]/                # Repository-specific collections
└── chroma.sqlite3                   # Database index

site/                                # Generated documentation (mkdocs build)
└── [static_files]/                  # HTML, CSS, JS for docs site
```

## 🔒 Security & Privacy

### **Excluded from Version Control**
- **`.env`**: Environment variables with API keys
- **`chroma_db/`**: Vector database with repository content
- **`token.json`**: Google API credentials
- **`*.log`**: Log files with potentially sensitive data
- **`config/claude_desktop_config.json`**: Contains absolute paths

### **Included Templates**
- **`env.template`**: Safe template for environment setup
- **`config/claude_desktop_config.json`**: Generated configuration for Claude Desktop

## 🛠️ Development Workflow

1. **Setup**: `python setup_mcp_server.py`
2. **Test**: `python test_mcp_server.py`
3. **Develop**: Edit core modules in `issue_solver/`
4. **Document**: Update relevant files in `docs/`
5. **Build docs**: `mkdocs serve` for local preview
6. **Deploy**: `mkdocs build` for production

## 📋 Quality Assurance

### **Automated Checks**
- **GitHub Actions**: Continuous integration testing
- **Multi-platform**: Windows, macOS, Linux compatibility
- **Python versions**: 3.8, 3.9, 3.10, 3.11 support
- **Code quality**: Linting, formatting, security scans

### **Manual Testing**
- **MCP integration**: Claude Desktop compatibility
- **End-to-end**: Repository ingestion through PR creation
- **Performance**: Large repository handling
- **Error handling**: Graceful failure recovery

---

This structure provides a **production-ready, maintainable, and well-documented** GitHub repository suitable for open-source collaboration and enterprise deployment.
