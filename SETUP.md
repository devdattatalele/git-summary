# GitHub Issue Solver MCP - Complete Setup Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [1. Supabase Database Setup](#1-supabase-database-setup)
- [2. Docker Setup](#2-docker-setup)
- [3. Testing Trial System](#3-testing-trial-system)
- [4. Generating Licenses](#4-generating-licenses)
- [5. Monitoring & Analytics](#5-monitoring--analytics)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:
- ✅ Docker installed
- ✅ Supabase account (free tier works)
- ✅ Google API key (for Gemini)
- ✅ GitHub personal access token

---

## 1. Supabase Database Setup

### Step 1.1: Access Your Supabase Project

1. Go to https://supabase.com and create a new project (or use existing)
2. Navigate to **SQL Editor** in the left sidebar
3. Click **New Query**

### Step 1.2: Run the Schema SQL

Copy and paste the entire contents of `supabase_schema.sql` into the SQL Editor and click **Run**.

This creates:
- ✅ `licenses` table - Stores paid license keys
- ✅ `license_usage` table - Tracks all usage (trial + paid)
- ✅ `trial_users` table - **NEW!** Tracks trial users and enforces limits
- ✅ Indexes for performance
- ✅ RLS policies for security
- ✅ Triggers for automatic timestamps

### Step 1.3: Verify Tables Created

Run this query to verify:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('licenses', 'license_usage', 'trial_users');
```

**Expected output:**
```
table_name
--------------
licenses
license_usage
trial_users
```

### Step 1.4: Get Your Supabase Credentials

**NOTE:** Your Supabase credentials are **already hardcoded** in the Docker image:
- URL: `https://obrwsclermqxtipcauoz.supabase.co`
- Anon Key: Built into `config.py`

✅ **Users don't need to provide these!**

---

## 2. Docker Setup

### Step 2.1: Build the Docker Image

```bash
# Navigate to project directory
cd /path/to/github-issue-solver

# Build the image
docker build -t github-issue-solver:latest .
```

### Step 2.2: Test Locally (Free Trial)

```bash
docker run -it --rm \
  -e GOOGLE_API_KEY=your_google_api_key \
  -e GITHUB_TOKEN=your_github_token \
  github-issue-solver:latest
```

**What happens:**
1. MCP starts ✅
2. License validation runs
3. No license key found → **Trial mode activated** ✅
4. Machine ID generated (hardware-based)
5. Trial user created in Supabase `trial_users` table
6. Trial limits: **3 repos, 10 analyses, 10 days**

### Step 2.3: Test with Paid License

```bash
docker run -it --rm \
  -e GOOGLE_API_KEY=your_google_api_key \
  -e GITHUB_TOKEN=your_github_token \
  -e LICENSE_KEY=PERS-XXXX-XXXX-XXXX \
  github-issue-solver:latest
```

**What happens:**
1. License key validated against Supabase `licenses` table ✅
2. If valid → Full access, no limits ✅
3. Usage tracked in `license_usage` table (for analytics)

---

## 3. Testing Trial System

### Test 3.1: Verify Machine ID Generation

**Start MCP and check logs:**

```bash
docker run -it --rm \
  -e GOOGLE_API_KEY=xxx \
  -e GITHUB_TOKEN=xxx \
  github-issue-solver:latest
```

**Expected logs:**
```
✅ License validated: free tier
Trial user - Machine ID: abc12345...
Trial limits: 3 repositories, 10 analyses, 10 days remaining
```

### Test 3.2: Check Trial User in Supabase

Go to Supabase → **Table Editor** → `trial_users`

**You should see:**
| machine_id | started_at | expires_at | repositories_used | analyses_used | is_expired |
|------------|------------|------------|-------------------|---------------|------------|
| abc12345... | 2025-11-17... | 2025-11-27... | 0 | 0 | false |

### Test 3.3: Test Repository Ingestion (Limit: 3)

In Claude Desktop with MCP connected:

```
1. start_repository_ingestion('owner/repo1')
2. ingest_repository_docs('owner/repo1')
3. ingest_repository_code('owner/repo1')
4. ingest_repository_issues('owner/repo1')
5. ingest_repository_prs('owner/repo1')  ← Final step, tracks usage
```

**Check Supabase:**
- `trial_users` table: `repositories_used` = 1 ✅
- `license_usage` table: New row with `action='ingest'`, `license_key='TRIAL-MODE'`

**Repeat for repo2 and repo3:**
- Repo 2: ✅ Works, `repositories_used` = 2
- Repo 3: ✅ Works, `repositories_used` = 3

**Try repo4:**
```
start_repository_ingestion('owner/repo4')
```

**Expected response:**
```
❌ 🔒 Trial limit reached: 3/3 repositories used.
Please purchase a license to ingest more repositories.
```

✅ **Limit enforcement working!**

### Test 3.4: Test Analysis Limit (Limit: 10)

```
analyze_github_issue_tool('https://github.com/owner/repo/issues/1')
```

**After each successful analysis:**
- `trial_users.analyses_used` increments
- `license_usage` table gets new row

**After 10th analysis:**
```
analyze_github_issue_tool('https://github.com/owner/repo/issues/11')
```

**Expected response:**
```
❌ 🔒 Trial limit reached: 10/10 analyses used.
Please purchase a license to perform more analyses.
```

✅ **Limit enforcement working!**

### Test 3.5: Test Reinstall Prevention

**Critical security test:**

```bash
# Note the machine ID from logs
# Machine ID: abc12345...

# Stop and remove container
docker stop <container_id>
docker rm <container_id>

# Start fresh container
docker run -it --rm \
  -e GOOGLE_API_KEY=xxx \
  -e GITHUB_TOKEN=xxx \
  github-issue-solver:latest
```

**Check logs:**
```
Trial user - Machine ID: abc12345...  ← SAME ID!
Trial limits: 3 repositories, 10 analyses, X days remaining
```

**Verify in Supabase:**
- Same `machine_id` in `trial_users` table
- `repositories_used` and `analyses_used` **unchanged** ✅
- User cannot reset trial by reinstalling! ✅

### Test 3.6: Test Trial Usage Stats Tool

In Claude Desktop:

```
get_trial_usage()
```

**Expected response:**
```
📊 Trial Usage Statistics

✅ Trial Active

🗂️ Repositories: 3/3 used
   ⚠️ Limit reached!

📝 Analyses: 10/10 used
   ⚠️ Limit reached!

⏰ Trial Period:
   • Days Remaining: 7 days
   • Started: 2025-11-17
   • Expires: 2025-11-27

💡 Upgrade to unlock unlimited access:
   • Personal: $9/month (10 repos, 100 analyses)
   • Team: $29/month (50 repos, 500 analyses)
```

---

## 4. Generating Licenses

### Step 4.1: Generate a Test License

**On your local machine (NOT in Docker):**

```bash
python generate_license.py \
  --email user@example.com \
  --tier personal \
  --days 30
```

**Expected output:**
```
✅ License created successfully!

License Key: PERS-ABC12345-DEF67890-GHI12345
Tier: personal
User: user@example.com
Expires: 2025-12-17
```

### Step 4.2: Verify License in Supabase

Go to Supabase → **Table Editor** → `licenses`

**You should see:**
| license_key | tier | user_email | max_repositories | max_analyses_per_month | expires_at | is_active |
|-------------|------|------------|------------------|------------------------|------------|-----------|
| PERS-... | personal | user@... | 10 | 100 | 2025-12-17... | true |

### Step 4.3: Test License Activation

```bash
docker run -it --rm \
  -e GOOGLE_API_KEY=xxx \
  -e GITHUB_TOKEN=xxx \
  -e LICENSE_KEY=PERS-ABC12345-DEF67890-GHI12345 \
  github-issue-solver:latest
```

**Expected logs:**
```
✅ License validated: personal tier
User ID: user_abc123
✅ All services initialized successfully
```

**No trial limits!** User can now:
- Ingest 10 repositories (personal tier)
- Perform 100 analyses per month
- No trial expiration

---

## 5. Monitoring & Analytics

### Query 5.1: View All Trial Users

```sql
SELECT
    machine_id,
    started_at,
    expires_at,
    repositories_used,
    analyses_used,
    is_expired,
    CASE
        WHEN is_expired THEN 'Expired'
        WHEN repositories_used >= 3 THEN 'Repo Limit Reached'
        WHEN analyses_used >= 10 THEN 'Analysis Limit Reached'
        ELSE 'Active'
    END as status,
    EXTRACT(DAY FROM (expires_at - NOW())) as days_remaining
FROM trial_users
ORDER BY started_at DESC;
```

### Query 5.2: Trial Activity Log

```sql
SELECT
    lu.license_key,
    lu.action,
    lu.repository,
    lu.timestamp,
    lu.metadata->>'machine_id' as machine_id,
    tu.repositories_used,
    tu.analyses_used
FROM license_usage lu
LEFT JOIN trial_users tu ON lu.metadata->>'machine_id' = tu.machine_id
WHERE lu.license_key = 'TRIAL-MODE'
ORDER BY lu.timestamp DESC
LIMIT 100;
```

### Query 5.3: Trial Conversion Metrics

```sql
SELECT
    COUNT(*) as total_trials,
    COUNT(CASE WHEN is_expired = true THEN 1 END) as expired_trials,
    COUNT(CASE WHEN is_expired = false THEN 1 END) as active_trials,
    AVG(repositories_used) as avg_repos_used,
    AVG(analyses_used) as avg_analyses_used,
    COUNT(CASE WHEN repositories_used >= 3 THEN 1 END) as hit_repo_limit,
    COUNT(CASE WHEN analyses_used >= 10 THEN 1 END) as hit_analysis_limit
FROM trial_users;
```

### Query 5.4: Most Active Trial Users

```sql
SELECT
    t.machine_id,
    t.started_at,
    t.repositories_used,
    t.analyses_used,
    COUNT(lu.id) as total_actions,
    STRING_AGG(DISTINCT lu.repository, ', ') as repositories
FROM trial_users t
LEFT JOIN license_usage lu ON lu.metadata->>'machine_id' = t.machine_id
WHERE lu.license_key = 'TRIAL-MODE'
GROUP BY t.machine_id, t.started_at, t.repositories_used, t.analyses_used
ORDER BY total_actions DESC
LIMIT 20;
```

### Query 5.5: Daily Trial Signups

```sql
SELECT
    DATE(started_at) as signup_date,
    COUNT(*) as new_trials,
    AVG(repositories_used) as avg_repos,
    AVG(analyses_used) as avg_analyses
FROM trial_users
GROUP BY DATE(started_at)
ORDER BY signup_date DESC
LIMIT 30;
```

---

## Troubleshooting

### Issue 1: "trial_users table does not exist"

**Solution:** Run the `supabase_schema.sql` in Supabase SQL Editor.

Verify:
```sql
SELECT * FROM trial_users LIMIT 1;
```

### Issue 2: Trial limits not enforced

**Check logs for:**
```
Trial user - Machine ID: ...
```

If missing, the license validation may have failed.

**Verify:**
1. Supabase URL and anon key are correct in `config.py`
2. RLS policies are enabled
3. Network access to Supabase

### Issue 3: Machine ID changes on every restart

**This should NOT happen.** Machine ID is hardware-based.

**Check:**
- Are you running on the same physical machine?
- Linux: Does `/etc/machine-id` exist and is readable?
- macOS: Can `ioreg` command run?

**Fallback behavior:**
- If machine ID generation fails, uses fixed ID
- All failed machines share same trial limits (security fallback)

### Issue 4: License validation fails

**Check:**
1. License key format: `TIER-XXXX-XXXX-XXXX`
2. License exists in Supabase `licenses` table
3. `is_active = true`
4. Not expired (if `expires_at` is set)

**Verify:**
```sql
SELECT * FROM licenses WHERE license_key = 'YOUR-KEY-HERE';
```

### Issue 5: Docker build fails

**Common issues:**
- Missing `requirements.txt` → **Fixed in Nov 16**
- Dependency conflicts → **Fixed in Nov 15**

**Clean rebuild:**
```bash
docker build --no-cache -t github-issue-solver:latest .
```

---

## What's New (Nov 17, 2025)

### ✅ Trial Tracking System (Complete)

**Security Features:**
- 🔒 Hardware-based machine ID (persistent across reinstalls)
- 🔒 Server-side limit enforcement
- 🔒 No random fallback (prevents bypass)
- 🔒 Trial usage tracked in Supabase

**Trial Limits:**
- 3 repositories
- 10 analyses (includes patch generation)
- 10 days trial period

**New MCP Tool:**
- `get_trial_usage()` - Shows users their current trial stats

**Files Modified:**
- `supabase_schema.sql` - Added `trial_users` table with `updated_at`
- `src/github_issue_solver/license.py` - Robust machine ID + trial enforcement
- `src/github_issue_solver/config.py` - Store machine_id for trial users
- `src/github_issue_solver/server.py` - Enforce limits before actions

### ✅ Bug Fixes (Nov 16-17)

1. **KeyError('details')** - Fixed fallback analysis return type
2. **total_documents always 0** - Fixed state manager calculation
3. **Patch embedding mismatch** - Now uses same provider as ingestion
4. **License usage tracking** - Automatic tracking after ingestion
5. **AnalysisService AttributeError** - Fixed service reference

---

## Support

For issues or questions:
- Check logs: `docker logs <container_id>`
- Review `CHANGES.md` for recent fixes
- Check Supabase tables for data integrity

**Admin Only:**
- License generation: `generate_license.py`
- Analytics: See Query 5.1-5.5 above
- Trial metrics: Supabase dashboard

---

## Security Notes

### What's Safe to Share

✅ **Public (in Docker image):**
- Supabase URL
- Supabase anon key (public credentials)
- Trial limits (3 repos, 10 analyses)

❌ **Never in Docker:**
- License generation scripts
- Database service role key
- `.env` files
- User API keys (Google, GitHub)

### Trial Security

Users **cannot** bypass trial limits by:
- ❌ Reinstalling MCP
- ❌ Recreating Docker container
- ❌ Clearing local data
- ❌ Using --no-cache builds

Machine ID persists because it's based on:
- Hardware MAC address
- OS machine UUID (/etc/machine-id on Linux)
- IOPlatformUUID on macOS

**To bypass, users would need to:**
- Change MAC address (requires root)
- Change machine-id file (requires root on Linux)
- Change IOPlatformUUID (very difficult on macOS)
- Use different physical hardware

---

**✅ Setup Complete! Your MCP server is production-ready with trial tracking.**
