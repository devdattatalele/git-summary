# Common Issues & Solutions

This guide covers the most frequently encountered issues and their solutions.

## 🔧 Setup Issues

### "Server disconnected" in Claude Desktop

**Symptoms:**
- Claude Desktop shows "Server disconnected"
- MCP server appears to start but immediately fails

**Solutions:**

1. **Check Python Path**
   ```bash
   # Verify the Python path in config
   cat config/claude_desktop_config.json
   
   # Find correct Python path
   which python3
   ```

2. **Verify MCP Installation**
   ```bash
   # Check if MCP is installed
   pip show mcp
   
   # Reinstall if needed
   pip install mcp
   ```

3. **Test Server Manually**
   ```bash
   # Run server directly to see errors
   python github_issue_mcp_server.py
   ```

### "Module not found" Errors

**Symptoms:**
- `ModuleNotFoundError: No module named 'mcp'`
- Import errors during startup

**Solutions:**

1. **Install Missing Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Check Virtual Environment**
   ```bash
   # Ensure you're in the right environment
   which python
   pip list | grep mcp
   ```

3. **Update PYTHONPATH**
   ```bash
   # In config/claude_desktop_config.json
   "env": {
     "PYTHONPATH": "/absolute/path/to/project"
   }
   ```

## 🔑 Authentication Issues

### GitHub API Access Denied

**Symptoms:**
- "Repository not found or not accessible"
- 403 Forbidden errors

**Solutions:**

1. **Verify Token Permissions**
   ```bash
   # Test token
   curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
   ```

2. **Check Token Scopes**
   - Go to GitHub Settings > Developer settings > Personal access tokens
   - Ensure `repo` and `read:user` scopes are enabled

3. **Update Token in .env**
   ```env
   GITHUB_TOKEN=ghp_your_new_token_here
   ```

### Google API Quota Exceeded

**Symptoms:**
- "429 Too Many Requests"
- "Quota exceeded" errors

**Solutions:**

1. **Check API Usage**
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to APIs & Services > Quotas

2. **Enable Fallback Mode**
   - The system automatically uses fallback analysis when quotas are exceeded
   - Reduce `MAX_ISSUES` and `MAX_PRS` in `.env`

3. **Request Quota Increase**
   - Follow Google's quota increase process
   - Consider upgrading to paid tier

## 💾 Database Issues

### ChromaDB Permission Errors

**Symptoms:**
- "Read-only file system" errors
- "Permission denied" when creating database

**Solutions:**

1. **Set Absolute Path**
   ```env
   # In .env file
   CHROMA_PERSIST_DIR=/absolute/path/to/chroma_db
   ```

2. **Check Directory Permissions**
   ```bash
   # Ensure directory is writable
   chmod 755 /path/to/chroma_db
   ```

3. **Clear and Recreate**
   ```bash
   # Remove corrupted database
   rm -rf chroma_db/
   
   # Recreate with proper permissions
   mkdir -p chroma_db
   ```

### Database Corruption

**Symptoms:**
- SQLite errors
- Inconsistent query results

**Solutions:**

1. **Clear Specific Repository**
   ```
   # In Claude Desktop
   Clear repository data for owner/repo (with confirm=True)
   ```

2. **Rebuild Database**
   ```bash
   # Remove all data
   rm -rf chroma_db/
   
   # Re-ingest repositories
   python -c "
   import asyncio
   from github_issue_mcp_server import ingest_repository_tool
   asyncio.run(ingest_repository_tool('your/repo'))
   "
   ```

## 🚀 Performance Issues

### Slow Repository Ingestion

**Symptoms:**
- Ingestion takes much longer than expected
- Timeout errors during processing

**Solutions:**

1. **Adjust Batch Sizes**
   ```python
   # In issue_solver/ingest.py (for developers)
   batch_size = 25  # Reduce from default 50
   ```

2. **Limit Processing**
   ```env
   # In .env file
   MAX_ISSUES=50
   MAX_PRS=25
   ```

3. **Skip Heavy Operations**
   ```
   # In Claude Desktop
   Ingest the repo/name repository (skip_code=True, skip_prs=True)
   ```

### Memory Issues

**Symptoms:**
- Out of memory errors
- System slowdown during processing

**Solutions:**

1. **Increase Virtual Memory**
   ```bash
   # On macOS/Linux
   ulimit -v 4194304  # 4GB limit
   ```

2. **Process in Smaller Batches**
   ```python
   # Reduce batch sizes in configuration
   BATCH_SIZE = 10
   ```

## 🌐 Network Issues

### Connection Timeouts

**Symptoms:**
- GitHub API timeouts
- Network connection errors

**Solutions:**

1. **Check Network Connectivity**
   ```bash
   # Test GitHub connection
   curl -I https://api.github.com
   
   # Test Google API
   curl -I https://generativelanguage.googleapis.com
   ```

2. **Configure Proxy (if needed)**
   ```env
   # In .env file
   HTTP_PROXY=http://proxy.company.com:8080
   HTTPS_PROXY=http://proxy.company.com:8080
   ```

3. **Retry with Exponential Backoff**
   - The system automatically retries failed requests
   - Wait and try again if issues persist

## 🔍 Debugging Tips

### Enable Debug Logging

```bash
# Run with debug logging
python github_issue_mcp_server.py --log-level DEBUG
```

### Check Claude Desktop Logs

**macOS:**
```bash
tail -f ~/Library/Logs/Claude/mcp-server-github-issue-resolver.log
```

**Windows:**
```bash
type %APPDATA%\Claude\logs\mcp-server-github-issue-resolver.log
```

### Validate Configuration

```bash
# Run comprehensive validation
python setup_mcp_server.py

# Test specific functionality
python test_mcp_server.py
```

## 📞 Getting Help

### Before Asking for Help

1. **Check this guide** for your specific issue
2. **Search existing issues** on GitHub
3. **Run diagnostic commands** provided above
4. **Collect relevant logs** and error messages

### Where to Get Help

- **[GitHub Issues](https://github.com/your-username/github-issue-mcp-server/issues)** - Bug reports
- **[GitHub Discussions](https://github.com/your-username/github-issue-mcp-server/discussions)** - Questions
- **[Documentation](../index.md)** - Comprehensive guides

### What to Include in Bug Reports

```markdown
**Environment:**
- OS: [e.g., macOS 12.0]
- Python version: [e.g., 3.9.0]
- MCP version: [output of `pip show mcp`]

**Error details:**
- Full error message
- Steps to reproduce
- Relevant log excerpts

**Configuration:**
- Anonymized .env contents
- claude_desktop_config.json structure
```

## 🔄 Recovery Procedures

### Complete Reset

If all else fails, perform a complete reset:

```bash
# 1. Backup any important data
cp .env .env.backup

# 2. Clean everything
rm -rf chroma_db/ config/ __pycache__/

# 3. Reinstall dependencies
pip uninstall -y -r requirements.txt
pip install -r requirements.txt

# 4. Reconfigure
cp env.template .env
# Edit .env with your settings

# 5. Setup again
python setup_mcp_server.py
```

---

**Still having issues?** Don't hesitate to [open an issue](https://github.com/your-username/github-issue-mcp-server/issues) with detailed information!
