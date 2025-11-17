-- ============================================================
-- Supabase Schema for GitHub Issue Solver License Management
-- ============================================================
-- Run this SQL in your Supabase SQL Editor
-- Project URL: https://obrwsclermqxtipcauoz.supabase.co

-- Create licenses table
CREATE TABLE IF NOT EXISTS licenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_key TEXT UNIQUE NOT NULL,
  tier TEXT NOT NULL CHECK (tier IN ('free', 'personal', 'team', 'enterprise')),
  user_id TEXT NOT NULL,
  user_email TEXT,
  max_repositories INT NOT NULL,
  max_analyses_per_month INT NOT NULL,
  max_storage_gb INT NOT NULL,
  issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  is_trial BOOLEAN DEFAULT false,
  is_active BOOLEAN DEFAULT true,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create usage tracking table
CREATE TABLE IF NOT EXISTS license_usage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_key TEXT NOT NULL REFERENCES licenses(license_key),
  action TEXT NOT NULL CHECK (action IN ('ingest', 'analyze', 'patch')),
  repository TEXT,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}',
  CONSTRAINT fk_license FOREIGN KEY (license_key) REFERENCES licenses(license_key) ON DELETE CASCADE
);

-- Create trial tracking table (for free tier without license key)
CREATE TABLE IF NOT EXISTS trial_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  machine_id TEXT UNIQUE NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  repositories_used INT DEFAULT 0,
  analyses_used INT DEFAULT 0,
  is_expired BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_licenses_key ON licenses(license_key);
CREATE INDEX IF NOT EXISTS idx_licenses_active ON licenses(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_usage_license_timestamp ON license_usage(license_key, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trial_machine ON trial_users(machine_id);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS update_licenses_updated_at ON licenses;
CREATE TRIGGER update_licenses_updated_at
    BEFORE UPDATE ON licenses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_trial_users_updated_at ON trial_users;
CREATE TRIGGER update_trial_users_updated_at
    BEFORE UPDATE ON trial_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE license_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE trial_users ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Allow read access for all users" ON licenses;
DROP POLICY IF EXISTS "Allow read access for trial users" ON trial_users;
DROP POLICY IF EXISTS "Allow insert for trial users" ON trial_users;
DROP POLICY IF EXISTS "Allow update for trial users" ON trial_users;
DROP POLICY IF EXISTS "Allow insert for usage tracking" ON license_usage;

-- Create policy for read access (allow all reads with anon key)
CREATE POLICY "Allow read access for all users" ON licenses
    FOR SELECT USING (true);

CREATE POLICY "Allow read access for trial users" ON trial_users
    FOR SELECT USING (true);

-- Create policy for insert access (trial users can create their own trial)
CREATE POLICY "Allow insert for trial users" ON trial_users
    FOR INSERT WITH CHECK (true);

-- Create policy for update access (trial users can update their own usage)
CREATE POLICY "Allow update for trial users" ON trial_users
    FOR UPDATE USING (true);

-- Create policy for usage tracking (allow inserts)
CREATE POLICY "Allow insert for usage tracking" ON license_usage
    FOR INSERT WITH CHECK (true);

-- ============================================================
-- Verification Queries
-- ============================================================
-- Run these to verify the schema was created correctly:

-- Check tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('licenses', 'license_usage', 'trial_users');

-- Check indexes
SELECT indexname FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN ('licenses', 'license_usage', 'trial_users');

-- Check RLS is enabled
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('licenses', 'license_usage', 'trial_users');

-- ============================================================
-- COMPLETED! Your Supabase database is ready.
-- Next steps:
-- 1. Update your .env file with Supabase credentials
-- 2. Run the application to test license validation
-- ============================================================
