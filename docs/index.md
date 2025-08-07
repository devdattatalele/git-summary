# GitHub Issue Resolution MCP Server

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Welcome to the comprehensive documentation for the **GitHub Issue Resolution MCP Server** - an advanced AI-powered system that enables intelligent analysis and automated resolution of GitHub issues using the Model Context Protocol (MCP).

## 🌟 What is this?

This MCP server provides a complete solution for:

- **🔍 Repository Analysis**: Deep understanding of codebases through RAG (Retrieval Augmented Generation)
- **🤖 Issue Intelligence**: AI-powered analysis of GitHub issues with context awareness
- **🛠️ Automated Solutions**: Generation of code patches and pull requests
- **🔄 Multi-Repository Support**: Seamless handling of multiple projects with isolated knowledge bases

## 🚀 Key Features

### **Repository-Specific RAG**
Each repository gets its own isolated knowledge base containing:
- Documentation and README files
- Source code with function-level analysis  
- Issue history and discussions
- Pull request patterns and solutions

### **AI-Powered Analysis**
- **LangChain Agents**: Advanced reasoning for complex issues
- **Google Gemini Integration**: State-of-the-art language understanding
- **Context-Aware Solutions**: Leverages repository history for better recommendations
- **Complexity Assessment**: Automatic difficulty rating and similar issue detection

### **Automated Patch Generation**
- **Smart Code Changes**: Generates specific file modifications
- **GitHub Integration**: Creates pull requests automatically
- **Unified Diff Format**: Standard patch format for easy review
- **Branch Management**: Handles Git workflows seamlessly

## 🎯 Quick Start

Get up and running in minutes:

```bash
# 1. Clone and install
git clone https://github.com/your-username/github-issue-mcp-server.git
cd github-issue-mcp-server
pip install -r requirements.txt

# 2. Configure environment  
cp env.template .env
# Edit .env with your API keys

# 3. Setup and test
python setup_mcp_server.py
python test_mcp_server.py

# 4. Integrate with Claude Desktop
# Configuration automatically generated!
```

## 📖 Documentation Structure

### **Getting Started**
- **[Quick Start](getting_started/quickstart.md)** - Get running in 5 minutes
- **[Installation](getting_started/installation.md)** - Detailed setup guide
- **[Configuration](getting_started/configuration.md)** - Environment setup
- **[Claude Desktop Setup](getting_started/claude_setup.md)** - MCP integration

### **Core Concepts**  
- **[MCP Overview](concepts/mcp_overview.md)** - Understanding Model Context Protocol
- **[Architecture](concepts/architecture.md)** - System design and components
- **[RAG System](concepts/rag_system.md)** - Repository knowledge base
- **[Workflow](concepts/workflow.md)** - Complete process flow

### **Usage Guide**
- **[Repository Ingestion](usage/ingestion.md)** - Building knowledge bases
- **[Issue Analysis](usage/analysis.md)** - AI-powered understanding
- **[Patch Generation](usage/patching.md)** - Automated solutions
- **[Multi-Repository](usage/multi_repo.md)** - Managing multiple projects
- **[Advanced Features](usage/advanced.md)** - Power user techniques

### **API Reference**
Complete documentation of all modules, functions, and MCP tools.

### **Examples**
Real-world usage patterns and integration examples.

### **Troubleshooting**
Common issues, performance optimization, and debugging guides.

## 🛠️ Available Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `ingest_repository_tool` | Build knowledge base | `Ingest the microsoft/vscode repository` |
| `analyze_github_issue_tool` | AI issue analysis | `Analyze https://github.com/microsoft/vscode/issues/123` |
| `generate_code_patch_tool` | Create fix patches | `Generate patches for the analyzed issue` |
| `create_github_pr_tool` | Create Pull Requests | `Create a GitHub PR with the generated patches` |
| `list_ingested_repositories` | Show all repos | `List all ingested repositories` |
| `clear_repository_data` | Clean specific repo | `Clear repository data for old-repo/name` |

## 🔧 Technology Stack

- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** - AI tool integration protocol
- **[FastMCP](https://github.com/jlowin/fastmcp)** - Python MCP server framework
- **[LangChain](https://langchain.com/)** - AI agent orchestration
- **[Google Gemini](https://ai.google.dev/)** - Advanced language model
- **[ChromaDB](https://www.trychroma.com/)** - Vector database for RAG
- **[PyGithub](https://github.com/PyGithub/PyGithub)** - GitHub API integration

## 📊 Performance

### Repository Processing Times
- **Small repos** (< 1K files): ~6 minutes
- **Medium repos** (1K-10K files): ~18 minutes  
- **Large repos** (> 10K files): ~50 minutes

### Analysis Speed
- **Issue Analysis**: 30-60 seconds
- **Patch Generation**: 1-3 minutes
- **PR Creation**: 10-30 seconds

## 🤝 Contributing

We welcome contributions! See our **[Contributing Guide](contributing/development.md)** for:

- Development setup
- Code style guidelines  
- Testing procedures
- Documentation standards

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](../LICENSE) file for details.

## 🙏 Acknowledgments

Special thanks to:
- **[Model Context Protocol](https://modelcontextprotocol.io/)** team
- **[Anthropic](https://www.anthropic.com/)** for Claude and MCP support
- **[Google](https://ai.google.dev/)** for Gemini API
- **[LangChain](https://langchain.com/)** community

---

**Ready to revolutionize your GitHub workflow?** Start with our **[Quick Start Guide](getting_started/quickstart.md)** and join the AI-powered development revolution! 🚀