# Installation

Follow these steps to set up the dual-MCP server architecture on your local machine.

## Prerequisites

Before installing, ensure you have the following:

- **Python 3.8+** - For the analysis server
- **Docker** - For the official GitHub MCP server
- **Claude Desktop** - MCP client for orchestration
- **GitHub Personal Access Token** - With `repo` scope
- **Google API Key** - For Gemini language model

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/your-github/issue-solver.git
cd issue-solver
```

### 2. Create a Virtual Environment

It's recommended to use a virtual environment to manage dependencies.

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

### 3. Install Dependencies

Install all the required Python packages from the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 4. Install Docker

The official GitHub MCP server runs via Docker. Install Docker if you haven't already:

**macOS:**
```bash
# Install Docker Desktop from https://docker.com/products/docker-desktop
# Or via Homebrew:
brew install --cask docker
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install docker.io
sudo systemctl start docker
sudo systemctl enable docker
```

**Windows:**
Download and install Docker Desktop from [https://docker.com/products/docker-desktop](https://docker.com/products/docker-desktop)

### 5. Configure Environment Variables

Create and configure your environment variables. See the [Configuration](configuration.md) guide for details.

### 6. Automated Setup

Run the automated setup script to configure both servers:

```bash
python setup_mcp_server.py
```

This will:
- ✅ Validate your environment and dependencies
- ✅ Setup the official GitHub MCP server (Docker)
- ✅ Configure both servers in Claude Desktop
- ✅ Test dual-server functionality
- ✅ Generate optimized configurations

### 7. Verify Installation

Test that both servers are working:

```bash
# Test analysis server
timeout 5 python github_issue_mcp_server.py

# Test GitHub server (Docker)
docker run --rm ghcr.io/github/github-mcp-server --help
```

### 8. Claude Desktop Integration

The setup script automatically installs the configuration. Simply restart Claude Desktop to load both servers.

## Troubleshooting

### Docker Issues
```bash
# Verify Docker is running
docker --version
docker ps

# Pull the official image manually if needed
docker pull ghcr.io/github/github-mcp-server
```

### Python Environment Issues
```bash
# Verify Python and packages
python --version
pip show mcp fastmcp langchain

# Reinstall if needed
pip install -r requirements.txt
```

For more troubleshooting help, see our [Troubleshooting Guide](../troubleshooting/common_issues.md). 