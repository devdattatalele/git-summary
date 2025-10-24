# Quick Start: Ingesting curl/curl Repository

## TL;DR - Just Run These Commands

```python
# In Claude Desktop after MCP server is running:

# Step 1: Initialize
start_repository_ingestion('curl/curl')

# Step 2: Ingest Docs
ingest_repository_docs('curl/curl')

# Step 3: Ingest Code
ingest_repository_code('curl/curl')

# Step 4: Ingest Issues
ingest_repository_issues('curl/curl', max_issues=100)

# Step 5: Ingest PRs (NEW: safe defaults)
ingest_repository_prs('curl/curl')  # Uses max_prs=15 by default

# Done! 🎉
```

## Expected Timing (with FastEmbed)

| Step | Estimated Time | Notes |
|------|---------------|-------|
| 1. Initialize | 5-10s | Validates repo |
| 2. Docs | 30-60s | ~40 docs → ~80 chunks |
| 3. Code | 60-120s | ~250 files → ~300 chunks |
| 4. Issues | 90-150s | 100 issues → ~100 chunks |
| 5. PRs | **120-180s** | **~12-15 PRs → ~50 chunks** |
| **TOTAL** | **~6-9 minutes** | **All steps combined** |

## What Changed for PRs?

### Before (Would Timeout):
```
ingest_repository_prs('curl/curl', max_prs=25)
❌ Fetching PR history: 308it [04:46, 1.06s/it]
❌ MCP error -32001: Request timed out
```

### After (Safe):
```
ingest_repository_prs('curl/curl')  # Uses default max_prs=15
✅ Fetching PR history: 150it [02:30, 1.0s/it]
⚠️ Examined 150 PRs, collected 12 merged PRs. Stopping to prevent timeout.
✅ PR fetching complete: 12 merged PRs
⚡ FASTEMBED: Embedded 50 chunks in 3.8s
✅ Step 4 Complete!
```

## Why Fewer PRs?

**curl/curl has 6,000+ PRs** (mostly open/unmerged). Finding merged PRs is like finding needles in a haystack:
- Examining **308 PRs** to find **25 merged** = 4m46s ❌ (timeout)
- Examining **150 PRs** to find **12-15 merged** = 2m30s ✅ (safe)

**12-15 merged PRs is still plenty for AI analysis!** The system learns from:
- Code patterns from merged PRs
- Issue resolution strategies
- Common fixes and changes

## If You Need More PRs

### Option 1: Increase the limit (risky on large repos)
```python
# Try 20 PRs (might timeout on curl/curl)
ingest_repository_prs('curl/curl', max_prs=20)

# Try 10 PRs (safer)
ingest_repository_prs('curl/curl', max_prs=10)
```

### Option 2: Use environment variable
```bash
# In .env file
MAX_PRS=20  # Default for all repos
```

### Option 3: Run multiple times with filters (future feature)
```python
# Not implemented yet - future enhancement
# Could filter by date, author, labels, etc.
```

## Troubleshooting

### Problem: "Examined 150 PRs, collected only 5 merged PRs"
**Cause**: The repo has very few merged PRs in recent history
**Solution**: 
- ✅ Accept the 5 PRs (still valuable!)
- OR increase `max_prs` (but watch for timeout)
- OR wait for future filtering features

### Problem: "PR fetching exceeded 240s limit"
**Cause**: The hard limit kicked in before examining limit was reached
**Solution**:
- Reduce `max_prs` to 10 or 5
- The repo is extremely large

### Problem: Still getting timeouts
**Cause**: Your repo might be even larger than curl/curl
**Solution**:
```python
# Ultra-safe mode
ingest_repository_prs('mega/repo', max_prs=5)
```

## Monitoring Progress

### Check Status Anytime
```python
get_repository_status('curl/curl')
```

### Watch Logs
Look for these indicators in Claude Desktop logs:
```
✅ Good signs:
   "Fetching up to 15 merged PRs (will examine max 150 total PRs)..."
   "PR fetching completed successfully in 150.5s"
   "FASTEMBED: Embedded 50 chunks in 3.8s"

⚠️ Warnings (OK):
   "Examined 150 PRs, collected 12 merged PRs. Stopping to prevent timeout."
   → This is NORMAL for large repos! You got 12 PRs safely.

❌ Errors (problem):
   "PR fetching exceeded 240s limit"
   → Reduce max_prs further
```

## Full Example Session

```python
# 1. Initialize
>>> start_repository_ingestion('curl/curl')
🚀 Repository Ingestion Started Successfully!
📂 Repository: curl/curl
✅ Repository validated and ready for ingestion!

# 2. Run all 4 steps
>>> ingest_repository_docs('curl/curl')
✅ Step 1 Complete: Documentation Ingested!
📚 Documents Stored: 78 chunks
⏱️ Processing Time: 45.3s

>>> ingest_repository_code('curl/curl')
✅ Step 2 Complete: Source Code Analyzed!
💻 Code Chunks Stored: 312 chunks
⏱️ Processing Time: 98.7s

>>> ingest_repository_issues('curl/curl')
✅ Step 3 Complete: Issues History Ingested!
🐛 Issues Processed: 100 issues → 104 chunks
⏱️ Processing Time: 129.3s

>>> ingest_repository_prs('curl/curl')
🔄 PR fetching started in background thread with periodic yielding...
⏱️ PR fetching in progress... (5s elapsed)
⏱️ PR fetching in progress... (10s elapsed)
...
⚠️ Examined 150 PRs, collected 13 merged PRs. Stopping to prevent timeout.
✅ PR fetching completed successfully in 155.2s
⚡ FASTEMBED MODE: Estimated time ~52s (13 batches × ~4s each)
⚡ FASTEMBED: Embedded 50 chunks in 4.1s
✅ Step 4 Complete!

🎉 INGESTION COMPLETE! All 4 Steps Finished!
🎯 Total Knowledge Base Size: 544 searchable chunks
🚀 Ready for AI-powered issue resolution!

# 3. Analyze an issue
>>> analyze_github_issue_tool('https://github.com/curl/curl/issues/15678')
[AI analysis with context from 544 chunks of knowledge...]
```

## Summary

- ✅ **Default is safe**: `max_prs=15` works for curl/curl
- ✅ **No timeout**: Hard limits prevent MCP connection loss
- ✅ **Good enough**: 12-15 PRs provides plenty of learning data
- ✅ **Configurable**: Can adjust if needed
- ✅ **Fast with FastEmbed**: Embedding takes ~3-4s per batch

**Just run it with defaults - it works! 🚀**

