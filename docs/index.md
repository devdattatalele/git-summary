# GitHub Issue Resolution MCP Server

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Support](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

Welcome to the comprehensive documentation for the **GitHub Issue Resolution MCP Server** - a revolutionary **dual-MCP server architecture** that combines specialized AI analysis with powerful GitHub automation using the Model Context Protocol (MCP).

## 🌟 What is this?

This dual-server system provides a complete enterprise-grade solution:

### 🧠 Analysis Server (`github-issue-resolver`)
**The "Brain"** - Custom AI-powered analysis and patch generation:
- **🔍 4-Step Repository Ingestion**: Optimized knowledge base building
- **🤖 RAG-Powered Analysis**: Intelligent issue understanding with context
- **🛠️ Smart Patch Generation**: Code fixes with repository awareness
- **📊 Performance Optimized**: Reduced chunk explosion and timeout prevention

### ✋ GitHub Server (`github/github-mcp-server`)
**The "Hands"** - Official Docker-based GitHub operations:
- **🔄 Complete GitHub API**: Enterprise-grade GitHub integration
- **🐳 Docker Deployment**: Reliable containerized execution
- **⚡ High Performance**: Go implementation for robust operations
- **🔒 Production Ready**: Official GitHub server for mission-critical tasks

## 🚀 Key Features

### **🏗️ Dual-Server Orchestration**
Revolutionary architecture that separates concerns for optimal performance:
- **🧠 Specialized Brain**: Custom analysis server for AI intelligence
- **✋ Powerful Hands**: Official GitHub server for robust operations
- **🔄 Seamless Integration**: Perfect coordination through Claude Desktop
- **📈 Scalable Design**: Enterprise-ready architecture

### **🔍 Advanced Repository Intelligence**
- **4-Step Ingestion Process**: Optimized workflow (docs → code → issues → PRs)
- **Repository-Specific RAG**: Each repository gets isolated knowledge base
- **Smart Prioritization**: Important content processed first
- **Performance Optimized**: 60-70% chunk reduction, timeout prevention

### **🤖 AI-Powered Analysis**
- **RAG Chain Processing**: Non-verbose, reliable LangChain analysis
- **Google Gemini 2.5-Flash**: Latest language model for superior understanding
- **Context-Aware Solutions**: Leverages repository history for targeted fixes
- **Complexity Assessment**: Automatic difficulty rating and similar issue detection

### **🛠️ Intelligent Automation**
- **Smart Patch Generation**: Context-aware code modifications
- **Dual-Server Workflow**: Analysis server generates, GitHub server applies
- **Professional Standards**: Unified diff format for enterprise review
- **Error-Free Communication**: Resolved JSON parsing for reliable operation

## 🎯 Quick Start

Get up and running in minutes with our dual-server architecture:

```bash
# 1. Prerequisites
# - Python 3.8+
# - Docker (for GitHub server)
# - Claude Desktop

# 2. Clone and install
git clone https://github.com/your-username/github-issue-mcp-server.git
cd github-issue-mcp-server
pip install -r requirements.txt

# 3. Configure environment  
cp env.template .env
# Edit .env with your API keys (GITHUB_TOKEN, GOOGLE_API_KEY)

# 4. Automated dual-server setup
python setup_mcp_server.py
# This will:
# ✅ Setup both analysis and GitHub servers
# ✅ Configure Docker for official GitHub server
# ✅ Generate Claude Desktop configuration
# ✅ Test dual-server functionality

# 5. Restart Claude Desktop
# Both servers will be available!
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

### 🧠 Analysis Server (`github-issue-resolver`)

| Tool | Purpose | Example |
|------|---------|---------|
| `start_repository_ingestion` | Initialize 4-step process | `Start ingesting microsoft/vscode` |
| `ingest_repository_docs` | Step 1: Documentation | `Ingest docs for microsoft/vscode` |
| `ingest_repository_code` | Step 2: Source code | `Ingest code for microsoft/vscode` |
| `ingest_repository_issues` | Step 3: Issues history | `Ingest issues for microsoft/vscode` |
| `ingest_repository_prs` | Step 4: PR history | `Ingest PRs for microsoft/vscode` |
| `analyze_github_issue_tool` | AI issue analysis | `Analyze https://github.com/microsoft/vscode/issues/123` |
| `generate_code_patch_tool` | Create fix patches | `Generate patches for the analyzed issue` |
| `get_repository_status` | Check progress | `Check status of microsoft/vscode` |
| `list_ingested_repositories` | Show all repos | `List all ingested repositories` |

### ✋ GitHub Server (`github`)

| Tool | Purpose | Example |
|------|---------|---------|
| `github:createPullRequest` | **Create PRs** | Use with generated patches |
| `github:createBranch` | Create branches | Create feature branches |
| `github:commitFiles` | Commit changes | Apply file modifications |
| `github:getIssue` | Fetch issues | Get issue details |
| `github:updateIssue` | Update issues | Modify issue content |
| *...and dozens more* | **Complete GitHub control** | Full GitHub API access |

## 🔧 Technology Stack

### Analysis Server (Brain) Technologies
- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** - AI tool integration protocol
- **[FastMCP](https://github.com/jlowin/fastmcp)** - Python MCP server framework
- **[LangChain](https://langchain.com/)** - RAG chain orchestration (non-verbose)
- **[Google Gemini 2.5-Flash](https://ai.google.dev/)** - Latest language model
- **[ChromaDB](https://www.trychroma.com/)** - Vector database for repository RAG
- **[PyGithub](https://github.com/PyGithub/PyGithub)** - GitHub API integration

### GitHub Server (Hands) Technologies
- **[Official GitHub MCP Server](https://github.com/github/github-mcp-server)** - Production GitHub server
- **[Docker](https://www.docker.com/)** - Containerized deployment
- **Go Implementation** - High-performance GitHub operations
- **Complete GitHub API** - Full GitHub functionality

## 📊 Performance

### Optimized 4-Step Processing (v2.0)
- **Small repos** (< 1K files): ~4 minutes (⬇️33% faster)
- **Medium repos** (1K-10K files): ~14 minutes (⬇️22% faster)
- **Large repos** (> 10K files): ~40 minutes (⬇️20% faster)

### Performance Improvements
- **🚀 Chunk Reduction**: 60-70% fewer chunks via intelligent processing
- **⚡ Timeout Prevention**: Smart yielding prevents Claude timeouts
- **📦 Batch Optimization**: Larger batches for faster embedding

### Analysis & Operation Speed
- **Issue Analysis**: 15-45 seconds (RAG chain optimization)
- **Patch Generation**: 30-90 seconds (context-aware)
- **PR Creation**: 5-15 seconds (official GitHub server)

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