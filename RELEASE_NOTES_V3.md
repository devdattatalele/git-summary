# GitHub Issue Solver MCP - v3.0.0 Release Notes

**Release Date:** November 17, 2025
**Docker Image:** `devdattatalele/github-issue-solver:v3.0.0`

---

## 🎉 What's New in v3.0.0

### 🔒 Major Feature: Trial Tracking & Enforcement System

**Complete trial user management with server-side enforcement:**

- ✅ **Hardware-based Machine ID**: Persistent across Docker reinstalls
- ✅ **Trial Limits Enforced**:
  - 3 repositories maximum
  - 10 analyses maximum (includes patch generation)
  - 10-day trial period
- ✅ **Usage Tracking**: All trial actions tracked in Supabase
- ✅ **Reinstall Prevention**: Machine ID prevents bypass by reinstalling
- ✅ **Admin Analytics**: 5 SQL queries for trial monitoring

**New MCP Tool:**
- `get_trial_usage()` - Shows trial users their current usage statistics

**Technical Implementation:**
- Robust machine ID generation (MAC + hostname + hardware UUID)
- Server-side limit checks before allowing actions
- Automatic usage tracking and counter updates
- Trial user table in Supabase database

---

## 🐛 Critical Bug Fixes

### 1. KeyError('details') Fixed ✅
**Problem:** Analysis and patch generation failed with `KeyError('details')`
**Root Cause:** Fallback analysis returned dict instead of JSON string
**Solution:** Fixed return type in `analyze.py` line 310

### 2. total_documents Always 0 Fixed ✅
**Problem:** Patch generation failed with "no ingested data" despite successful ingestion
**Root Cause:** Old document count read AFTER setting new value
**Solution:** Get old count BEFORE update in `state_manager.py` lines 187-207

### 3. Patch Embedding Provider Mismatch Fixed ✅
**Problem:** Patch generation quota exceeded even with FastEmbed ingestion
**Root Cause:** Patch code hardcoded to use Gemini embeddings for querying
**Solution:** Match embedding provider between ingestion and querying in `patch.py` lines 62-114

**RAG Architecture (Fixed):**
```
Query → FastEmbed (vector search, 0 API calls) → ChromaDB
      → Gemini LLM (reasoning, minimal API calls) → Patch
```

---

## 📊 Database Schema Updates

**New Table:** `trial_users`

```sql
CREATE TABLE trial_users (
  id UUID PRIMARY KEY,
  machine_id TEXT UNIQUE NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  repositories_used INT DEFAULT 0,
  analyses_used INT DEFAULT 0,
  is_expired BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Existing Tables Updated:**
- `license_usage` - Now tracks trial users with `license_key='TRIAL-MODE'`

---

## 🔧 Configuration Changes

### No Changes Required for Users!

**Supabase credentials are hardcoded** (public anon key):
- URL: `https://obrwsclermqxtipcauoz.supabase.co`
- Anon Key: Built into Docker image

**Users only need:**
```bash
docker pull devdattatalele/github-issue-solver:v3.0.0

# Free Trial:
docker run -e GOOGLE_API_KEY=xxx -e GITHUB_TOKEN=xxx devdattatalele/github-issue-solver:v3.0.0

# Paid License:
docker run -e GOOGLE_API_KEY=xxx -e GITHUB_TOKEN=xxx -e LICENSE_KEY=xxx devdattatalele/github-issue-solver:v3.0.0
```

---

## 📦 Files Modified

### Core System Files
1. **src/github_issue_solver/license.py** (lines 66-532)
   - Robust machine ID generation
   - Trial limit enforcement (`check_trial_limits()`)
   - Usage tracking (`track_usage()`, `_update_trial_counters()`)
   - Trial stats API (`get_trial_usage_stats()`)

2. **src/github_issue_solver/config.py** (lines 72, 164-169)
   - Added `machine_id` attribute
   - Get machine_id for trial users during setup

3. **src/github_issue_solver/server.py** (lines 154-162, 207-236, 312-340, 415-464)
   - Trial limit checks before ingestion/analysis/patch
   - Usage tracking after successful actions
   - New `get_trial_usage()` MCP tool

4. **src/github_issue_solver/services/state_manager.py** (lines 187-207)
   - Fixed total_documents calculation bug

5. **issue_solver/patch.py** (lines 62-114)
   - Fixed embedding provider detection for RAG

6. **issue_solver/analyze.py** (line 310)
   - Fixed fallback analysis return type

### Database & Setup
7. **supabase_schema.sql**
   - Added `trial_users` table with triggers and indexes
   - Added RLS policies for trial access

8. **SETUP.md** (NEW)
   - Complete setup and testing guide
   - 6 detailed trial system tests
   - 5 analytics SQL queries
   - Troubleshooting section

### Documentation Cleanup
9. **Deleted 15 redundant MD files**
10. **Kept only:**
    - README.md
    - SETUP.md (comprehensive guide)
    - CHANGES.md
    - CONTRIBUTING.md

---

## 🧪 Testing Checklist

Before deploying to production, verify:

- ✅ Supabase `trial_users` table created
- ✅ Trial user can ingest max 3 repositories
- ✅ Trial user can perform max 10 analyses
- ✅ Trial limits block after reaching max
- ✅ Machine ID persists across container restarts
- ✅ Reinstalling container doesn't reset limits
- ✅ `get_trial_usage()` tool returns correct stats
- ✅ Paid license users have no limits
- ✅ Patch generation uses correct embedding provider
- ✅ Total documents counted correctly after ingestion

**Full testing guide:** See `SETUP.md` sections 3.1 - 3.6

---

## 🔐 Security Improvements

### Trial System Security

**What Users CANNOT Bypass:**
- ❌ Reinstall MCP to reset trial
- ❌ Recreate Docker container to reset
- ❌ Delete local state files
- ❌ Use --no-cache Docker builds

**Machine ID is based on:**
- Hardware MAC address (requires hardware change)
- OS machine UUID (requires root to change)
  - Linux: `/etc/machine-id`
  - macOS: IOPlatformUUID
- Platform info (OS + architecture)

**To bypass, users would need:**
- Change MAC address (requires root/admin privileges)
- Change machine-id file (requires root on Linux)
- Change IOPlatformUUID (very difficult on macOS)
- Use different physical hardware

---

## 📈 Analytics & Monitoring

### Admin Queries (Supabase SQL Editor)

**1. View All Trial Users:**
```sql
SELECT machine_id, repositories_used, analyses_used,
       EXTRACT(DAY FROM (expires_at - NOW())) as days_remaining
FROM trial_users
ORDER BY started_at DESC;
```

**2. Trial Activity Log:**
```sql
SELECT lu.action, lu.repository, lu.timestamp,
       tu.repositories_used, tu.analyses_used
FROM license_usage lu
LEFT JOIN trial_users tu ON lu.metadata->>'machine_id' = tu.machine_id
WHERE lu.license_key = 'TRIAL-MODE'
ORDER BY lu.timestamp DESC LIMIT 100;
```

**3. Conversion Metrics:**
```sql
SELECT COUNT(*) as total_trials,
       AVG(repositories_used) as avg_repos,
       COUNT(CASE WHEN repositories_used >= 3 THEN 1 END) as hit_repo_limit
FROM trial_users;
```

See `SETUP.md` section 5 for all 5 analytics queries.

---

## 🔄 Migration from v2.x.x

### For Users:

**No migration needed!** Just pull the new version:

```bash
docker pull devdattatalele/github-issue-solver:v3.0.0
docker run -e GOOGLE_API_KEY=xxx -e GITHUB_TOKEN=xxx devdattatalele/github-issue-solver:v3.0.0
```

**Existing data:**
- ChromaDB data is preserved (same directory structure)
- Existing licenses remain valid
- No configuration changes required

### For Admins:

**Run SQL migration:**

```sql
-- In Supabase SQL Editor, execute:
-- (Copy entire supabase_schema.sql and run)
```

This creates the `trial_users` table and updates RLS policies.

---

## 🐛 Known Issues

None at this time.

---

## 💡 Upgrade Recommendations

**Free Trial Users:**
- Upgrade before hitting limits (3 repos / 10 analyses)
- Use `get_trial_usage()` to check remaining quota

**v2.x.x Users:**
- Upgrade immediately to get bug fixes
- Patch generation now works with FastEmbed
- Total documents correctly tracked

**Self-Hosted Users:**
- Update Supabase schema (run `supabase_schema.sql`)
- Rebuild Docker image with new code

---

## 📞 Support

**Issues or Questions:**
- GitHub Issues: [Your repo URL]
- Email: [Your support email]
- Documentation: See `SETUP.md` and `README.md`

**For Trial Users:**
- Check usage: `get_trial_usage()` tool
- Upgrade: Contact admin for license key

**For Admins:**
- Analytics: See `SETUP.md` section 5
- License generation: `python generate_license.py`

---

## 🎯 Roadmap (v3.1.0)

Planned features for next release:

- [ ] Automatic trial expiration check (daily cron job)
- [ ] Email notifications for trial users nearing limits
- [ ] Trial user dashboard in Supabase
- [ ] Conversion tracking (trial → paid)
- [ ] Usage analytics API endpoint

---

## 📚 Additional Resources

- **Complete Setup Guide:** `SETUP.md`
- **Changelog:** `CHANGES.md`
- **Database Schema:** `supabase_schema.sql`
- **Contributing:** `CONTRIBUTING.md`

---

**Built with ❤️ by the GitHub Issue Solver Team**

**Version:** 3.0.0
**Released:** November 17, 2025
**License:** MIT
