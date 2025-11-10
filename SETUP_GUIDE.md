# GitHub Issue Solver MCP - Setup Guide

## What You'll Get
- AI-powered GitHub issue analysis and resolution
- Automatic code patch generation
- Repository knowledge base with RAG
- 10 repositories, 100 analyses/month (personal tier)
- License valid for 30 days

---

## Prerequisites

### 1. Install Docker Desktop
- **Mac**: https://www.docker.com/products/docker-desktop
- **Windows**: https://www.docker.com/products/docker-desktop
- Install and start Docker Desktop

### 2. Install Claude Desktop
- Download from: https://claude.ai/download
- Install and open it once

---

## Step-by-Step Setup

### Step 1: Get Your API Keys

#### A. Google API Key (Free)
1. Go to: https://aistudio.google.com/app/apikey
2. Sign in with Google
3. Click "Create API Key"
4. Copy the key (starts with `AIza...`)

#### B. GitHub Personal Access Token (Free)
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Name it: `github-issue-solver-mcp`
4. Select these scopes:
   - ✅ `repo` (all)
   - ✅ `read:org`
   - ✅ `read:user`
5. Click "Generate token"
6. Copy the token (starts with `ghp_...`)

**Save both keys somewhere safe - you'll need them in Step 3!**

---

### Step 2: Setup License File

You should have received:
- License key: `PERS-XXXXXXXX-XXXXXXXX-XXXXXXXX`
- File: `licenses.json`

**On Mac:**
```bash
# Create directory
mkdir -p ~/.github_issue_solver

# Copy the licenses.json file to this directory
# (You can drag the file or use Finder)
cp ~/Downloads/licenses.json ~/.github_issue_solver/licenses.json
```

**On Windows:**
```bash
# Open PowerShell and run:
mkdir $HOME\.github_issue_solver

# Copy the licenses.json file to this directory
copy %USERPROFILE%\Downloads\licenses.json %USERPROFILE%\.github_issue_solver\licenses.json
```

**Verify it's there:**
```bash
# Mac
ls -la ~/.github_issue_solver/licenses.json

# Windows
dir %USERPROFILE%\.github_issue_solver\licenses.json
```

---

### Step 3: Pull Docker Image

**REPLACE `YOUR_DOCKERHUB_USERNAME` with the actual username!**

```bash
docker pull YOUR_DOCKERHUB_USERNAME/github-issue-solver:latest
```

This will download ~1.6 GB (takes 2-5 minutes depending on internet speed).

**Wait for it to complete** - you should see:
```
Status: Downloaded newer image for YOUR_DOCKERHUB_USERNAME/github-issue-solver:latest
```

---

### Step 4: Configure Claude Desktop

#### A. Find Your Username

**Mac:**
```bash
whoami
```

**Windows:**
```bash
echo %USERNAME%
```

Save this - you'll need it below!

#### B. Open Claude Desktop Config

**Mac:**
```bash
open ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```bash
notepad %APPDATA%\Claude\claude_desktop_config.json
```

#### C. Add This Configuration

**IMPORTANT: Replace these 5 things:**
1. `YOUR_MAC_USERNAME` → output from `whoami` command
2. `YOUR_GOOGLE_API_KEY` → Google API key from Step 1A
3. `YOUR_GITHUB_TOKEN` → GitHub token from Step 1B
4. `YOUR_LICENSE_KEY` → License key received (e.g., `PERS-XXXXXXXX-XXXXXXXX-XXXXXXXX`)
5. `YOUR_DOCKERHUB_USERNAME` → The Docker Hub username

**Mac Config:**
```json
{
  "mcpServers": {
    "github-issue-solver": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-v", "github-issue-solver-data:/data",
        "-v", "/Users/YOUR_MAC_USERNAME/.github_issue_solver:/root/.github_issue_solver:ro",
        "-e", "GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY",
        "-e", "GITHUB_TOKEN=YOUR_GITHUB_TOKEN",
        "-e", "ALLOW_NO_LICENSE=false",
        "-e", "LICENSE_KEY=YOUR_LICENSE_KEY",
        "-e", "USER_ID=your_name",
        "-e", "EMBEDDING_PROVIDER=fastembed",
        "-e", "LOG_LEVEL=INFO",
        "-e", "MCP_TRANSPORT=stdio",
        "devdattatalele/github-issue-solver:latest"
      ]
    }
  }
}
```

**Windows Config:**
```json
{
  "mcpServers": {
    "github-issue-solver": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-v", "github-issue-solver-data:/data",
        "-v", "C:/Users/YOUR_WINDOWS_USERNAME/.github_issue_solver:/root/.github_issue_solver:ro",
        "-e", "GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY",
        "-e", "GITHUB_TOKEN=YOUR_GITHUB_TOKEN",
        "-e", "ALLOW_NO_LICENSE=false",
        "-e", "LICENSE_KEY=YOUR_LICENSE_KEY",
        "-e", "USER_ID=your_name",
        "-e", "EMBEDDING_PROVIDER=fastembed",
        "-e", "LOG_LEVEL=INFO",
        "-e", "MCP_TRANSPORT=stdio",
        "devdattatalele/github-issue-solver:latest"
      ]
    }
  }
}
```

**Example (Mac) - After replacing:**
```json
{
  "mcpServers": {
    "github-issue-solver": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-v", "github-issue-solver-data:/data",
        "-v", "/Users/john/.github_issue_solver:/root/.github_issue_solver:ro",
        "-e", "GOOGLE_API_KEY=AIzaSyDXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "-e", "GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "-e", "ALLOW_NO_LICENSE=false",
        "-e", "LICENSE_KEY=PERS-12345678-ABCDEFGH-CHECKSUM",
        "-e", "USER_ID=john",
        "-e", "EMBEDDING_PROVIDER=fastembed",
        "-e", "LOG_LEVEL=INFO",
        "-e", "MCP_TRANSPORT=stdio",
        "devdatta/github-issue-solver:latest"
      ]
    }
  }
}
```

**Save the file** (Cmd+S on Mac, Ctrl+S on Windows)

---

### Step 5: Start Claude Desktop

1. **Quit Claude Desktop completely** (not just close the window)
   - Mac: Cmd+Q
   - Windows: Right-click taskbar → Quit

2. **Open Claude Desktop again**

3. **Look for the 🔨 hammer icon** in the bottom-right corner

4. **Click the hammer icon** - you should see "github-issue-solver" listed with available tools

---

### Step 6: Test It Works

In Claude Desktop, type:

```
Use get_health_status_tool to check the MCP server
```

**Expected response:**
```json
{
  "status": "healthy",
  "server_info": {
    "version": "2.0",
    "uptime_seconds": 5,
    "license_tier": "personal"
  }
}
```

If you see this, **it's working!** 🎉

---

## Troubleshooting

### Issue: "MCP failed to load"

**1. Check Docker is running:**
```bash
docker ps
```
If you see an error, start Docker Desktop.

**2. Test the Docker image manually:**
```bash
docker run --rm -i \
  -v /Users/YOUR_USERNAME/.github_issue_solver:/root/.github_issue_solver:ro \
  -e GOOGLE_API_KEY=your_key \
  -e GITHUB_TOKEN=your_token \
  -e ALLOW_NO_LICENSE=false \
  -e LICENSE_KEY=PERS-XXXXXXXX-XXXXXXXX-XXXXXXXX \
  devdattatalele/github-issue-solver:latest
```

You should see:
```
✅ Configuration loaded successfully
✅ License validated: personal tier
```

Press Ctrl+C to exit.

**3. Check Claude Desktop logs:**

Mac:
```bash
tail -f ~/Library/Logs/Claude/mcp-server-github-issue-solver.log
```

Windows:
```bash
type %APPDATA%\Claude\logs\mcp-server-github-issue-solver.log
```

Look for errors and check:
- License file is in the right place
- License key is correct
- Docker Hub username is correct

### Issue: "License key invalid"

**Check these:**

1. **License file exists:**
   ```bash
   # Mac
   cat ~/.github_issue_solver/licenses.json

   # Windows
   type %USERPROFILE%\.github_issue_solver\licenses.json
   ```

2. **License key matches:**
   - Open `licenses.json`
   - Find your license key
   - Make sure it matches what's in Claude Desktop config

3. **Volume mount is correct:**
   - Mac: `-v "/Users/YOUR_USERNAME/.github_issue_solver:/root/.github_issue_solver:ro"`
   - Windows: `-v "C:/Users/YOUR_USERNAME/.github_issue_solver:/root/.github_issue_solver:ro"`
   - Replace `YOUR_USERNAME` with actual username

### Issue: "Docker image not found"

```bash
# Check if image exists
docker images | grep github-issue-solver

# If not, pull again
docker pull devdattatalele/github-issue-solver:latest
```

### Issue: JSON validation error

- Go to https://jsonlint.com
- Copy your Claude Desktop config
- Click "Validate JSON"
- Fix any syntax errors (missing commas, quotes, etc.)

---

## What You Can Do

### Ingest a Repository
```
Ingest the repository owner/repo-name into the knowledge base
```

### Analyze an Issue
```
Analyze this GitHub issue: https://github.com/owner/repo/issues/123
```

### Generate Code Patch
```
Generate a code patch for issue #123 in owner/repo
```

### Check Status
```
What repositories have been ingested?
```

---

## License Information

**Your license:**
- **Tier:** Personal
- **Valid for:** 30 days
- **Max repositories:** 10
- **Max analyses/month:** 100
- **Storage:** 10 GB

**To check expiration:**
Contact the person who gave you the license.

---

## Need Help?

If you encounter issues:

1. **Check Docker Desktop is running**
2. **Check Claude Desktop logs** (commands above)
3. **Verify all 5 replacements were made in config:**
   - Mac username / Windows username
   - Google API key
   - GitHub token
   - License key
   - Docker Hub username
4. **Contact the person who shared this with you**

---

## Summary Checklist

- [ ] Docker Desktop installed and running
- [ ] Claude Desktop installed
- [ ] Google API key obtained
- [ ] GitHub token obtained
- [ ] `licenses.json` file copied to `~/.github_issue_solver/`
- [ ] Docker image pulled successfully
- [ ] Claude Desktop config updated with your info
- [ ] All 5 placeholders replaced in config
- [ ] Claude Desktop restarted
- [ ] 🔨 hammer icon visible
- [ ] `get_health_status_tool` test passed

**If all checkboxes are checked, you're ready to use the MCP! 🚀**
