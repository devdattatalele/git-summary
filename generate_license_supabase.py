#!/usr/bin/env python3
"""
License Generator for Supabase - LOCAL USE ONLY

This script generates license keys and stores them in Supabase.
DO NOT include this in Docker image!

Usage:
    python generate_license_supabase.py --email john@example.com --tier personal --days 30
    python generate_license_supabase.py --email jane@example.com --tier personal  # Lifetime
    python generate_license_supabase.py --list
    python generate_license_supabase.py --validate PERS-XXXXXXXX-XXXXXXXX-XXXXXXXX
"""

import os
import sys
import argparse
import secrets
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    from supabase import create_client
except ImportError:
    print("❌ Error: supabase package not installed")
    print("Install with: pip install supabase")
    sys.exit(1)

# Load environment
load_dotenv()

# Supabase credentials (from your .env file)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')  # Use service role key, not anon key!

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY required in .env")
    print("\nYour .env file should contain:")
    print("SUPABASE_URL=https://xxxxx.supabase.co")
    print("SUPABASE_SERVICE_KEY=eyJhbGciOi...  # Service role key!")
    sys.exit(1)

# Initialize Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# License limits
LICENSE_LIMITS = {
    'free': {
        'max_repositories': 3,
        'max_analyses_per_month': 10,
        'max_storage_gb': 1,
    },
    'personal': {
        'max_repositories': 10,
        'max_analyses_per_month': 100,
        'max_storage_gb': 10,
    },
    'team': {
        'max_repositories': 50,
        'max_analyses_per_month': 500,
        'max_storage_gb': 100,
    },
    'enterprise': {
        'max_repositories': -1,  # Unlimited
        'max_analyses_per_month': -1,
        'max_storage_gb': -1,
    }
}


def generate_license_key(tier: str) -> str:
    """Generate a cryptographically secure license key."""
    # Generate random component
    random_part = secrets.token_hex(12).upper()

    # Create structured key: TIER-RANDOM1-RANDOM2-CHECKSUM
    tier_code = tier[:4].upper()
    key_data = f"{tier_code}-{random_part[:8]}-{random_part[8:16]}"

    # Generate checksum
    checksum = hashlib.sha256(key_data.encode()).hexdigest()[:8].upper()
    license_key = f"{key_data}-{checksum}"

    return license_key


def create_license(
    email: str,
    tier: str,
    days: int = None
) -> str:
    """
    Create a new license in Supabase.

    Args:
        email: User email
        tier: License tier (personal, team, enterprise)
        days: Expiration in days (None = lifetime)

    Returns:
        Generated license key
    """
    if tier not in LICENSE_LIMITS:
        raise ValueError(f"Invalid tier: {tier}. Choose from: {list(LICENSE_LIMITS.keys())}")

    # Generate license key
    license_key = generate_license_key(tier)

    # Generate user ID from email
    user_id = hashlib.sha256(email.encode()).hexdigest()[:16]

    # Calculate expiration
    issued_at = datetime.now()
    expires_at = issued_at + timedelta(days=days) if days else None

    # Get limits for tier
    limits = LICENSE_LIMITS[tier]

    # Insert into Supabase
    try:
        response = supabase.table('licenses').insert({
            'license_key': license_key,
            'tier': tier,
            'user_id': user_id,
            'user_email': email,
            'max_repositories': limits['max_repositories'],
            'max_analyses_per_month': limits['max_analyses_per_month'],
            'max_storage_gb': limits['max_storage_gb'],
            'issued_at': issued_at.isoformat(),
            'expires_at': expires_at.isoformat() if expires_at else None,
            'is_trial': False,
            'is_active': True,
            'metadata': {'created_by': 'generate_license_supabase.py'}
        }).execute()

        print("\n" + "="*60)
        print("✅ LICENSE GENERATED SUCCESSFULLY")
        print("="*60)
        print(f"\nLicense Key: {license_key}")
        print(f"\nEmail: {email}")
        print(f"Tier: {tier.upper()}")
        print(f"Max Repositories: {limits['max_repositories'] if limits['max_repositories'] != -1 else 'Unlimited'}")
        print(f"Max Analyses/Month: {limits['max_analyses_per_month'] if limits['max_analyses_per_month'] != -1 else 'Unlimited'}")
        print(f"Issued: {issued_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if expires_at:
            print(f"Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Valid for: {days} days")
        else:
            print(f"Expires: NEVER (Lifetime license)")

        print("\n" + "="*60)
        print("📧 EMAIL TEMPLATE FOR USER:")
        print("="*60)
        print(f"""
Subject: Your GitHub Issue Solver License Key

Hello,

Thank you for purchasing GitHub Issue Solver!

Your License Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
License Key: {license_key}
Tier: {tier.upper()}
Valid Until: {expires_at.strftime('%B %d, %Y') if expires_at else 'Lifetime'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Setup Instructions:
1. Open your Claude Desktop config file
2. Add this environment variable to your MCP server configuration:
   -e LICENSE_KEY={license_key}
3. Restart Claude Desktop
4. Your MCP server will automatically validate the license

Your Plan Includes:
- {limits['max_repositories'] if limits['max_repositories'] != -1 else 'Unlimited'} repositories
- {limits['max_analyses_per_month'] if limits['max_analyses_per_month'] != -1 else 'Unlimited'} analyses per month
- {limits['max_storage_gb'] if limits['max_storage_gb'] != -1 else 'Unlimited'} GB storage

Need help? Reply to this email or visit our documentation.

Best regards,
GitHub Issue Solver Team
        """)
        print("="*60)

        return license_key

    except Exception as e:
        print(f"\n❌ Error creating license: {e}")
        sys.exit(1)


def list_licenses():
    """List all licenses in Supabase."""
    try:
        response = supabase.table('licenses') \
            .select('*') \
            .order('created_at', desc=True) \
            .execute()

        if not response.data:
            print("\n📋 No licenses found.")
            return

        print("\n" + "="*80)
        print("📋 ALL LICENSES")
        print("="*80)

        for lic in response.data:
            issued = datetime.fromisoformat(lic['issued_at'].replace('Z', '+00:00'))
            expires = None
            if lic.get('expires_at'):
                expires = datetime.fromisoformat(lic['expires_at'].replace('Z', '+00:00'))

            status = "✅ ACTIVE" if lic['is_active'] else "❌ INACTIVE"
            expired = ""
            if expires and datetime.now() > expires:
                expired = " (EXPIRED)"
                status = "⏰ EXPIRED"

            print(f"\nKey: {lic['license_key']}")
            print(f"  Email: {lic.get('user_email', 'N/A')}")
            print(f"  Tier: {lic['tier'].upper()}")
            print(f"  Issued: {issued.strftime('%Y-%m-%d')}")
            print(f"  Expires: {expires.strftime('%Y-%m-%d') if expires else 'LIFETIME'}{expired}")
            print(f"  Status: {status}")

        print("\n" + "="*80)
        print(f"Total licenses: {len(response.data)}")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n❌ Error listing licenses: {e}")


def validate_license(license_key: str):
    """Validate a license key."""
    try:
        response = supabase.table('licenses') \
            .select('*') \
            .eq('license_key', license_key) \
            .execute()

        if not response.data:
            print(f"\n❌ License key not found: {license_key}\n")
            return

        lic = response.data[0]
        issued = datetime.fromisoformat(lic['issued_at'].replace('Z', '+00:00'))
        expires = None
        if lic.get('expires_at'):
            expires = datetime.fromisoformat(lic['expires_at'].replace('Z', '+00:00'))

        is_valid = lic['is_active'] and (not expires or datetime.now() <= expires)

        print("\n" + "="*60)
        if is_valid:
            print("✅ LICENSE IS VALID")
        else:
            print("❌ LICENSE IS INVALID")
        print("="*60)

        print(f"\nKey: {license_key}")
        print(f"Email: {lic.get('user_email', 'N/A')}")
        print(f"Tier: {lic['tier'].upper()}")
        print(f"Issued: {issued.strftime('%Y-%m-%d')}")
        print(f"Expires: {expires.strftime('%Y-%m-%d') if expires else 'LIFETIME'}")
        print(f"Active: {'YES' if lic['is_active'] else 'NO'}")

        if expires:
            if datetime.now() > expires:
                days_expired = (datetime.now() - expires).days
                print(f"Status: ❌ EXPIRED {days_expired} days ago")
            else:
                days_remaining = (expires - datetime.now()).days
                print(f"Status: ✅ VALID ({days_remaining} days remaining)")
        else:
            print(f"Status: ✅ VALID (Lifetime)")

        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error validating license: {e}\n")


def deactivate_license(license_key: str):
    """Deactivate a license key."""
    try:
        response = supabase.table('licenses') \
            .update({'is_active': False}) \
            .eq('license_key', license_key) \
            .execute()

        if not response.data:
            print(f"\n❌ License key not found: {license_key}\n")
            return

        print(f"\n✅ License deactivated: {license_key}\n")

    except Exception as e:
        print(f"\n❌ Error deactivating license: {e}\n")


def main():
    """CLI interface for license management."""
    parser = argparse.ArgumentParser(
        description='License Generator for GitHub Issue Solver (Supabase)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 30-day personal license
  python generate_license_supabase.py --email john@example.com --tier personal --days 30

  # Generate lifetime personal license
  python generate_license_supabase.py --email john@example.com --tier personal

  # Generate team license for 365 days
  python generate_license_supabase.py --email team@company.com --tier team --days 365

  # List all licenses
  python generate_license_supabase.py --list

  # Validate a license
  python generate_license_supabase.py --validate PERS-XXXXXXXX-XXXXXXXX-XXXXXXXX

  # Deactivate a license
  python generate_license_supabase.py --deactivate PERS-XXXXXXXX-XXXXXXXX-XXXXXXXX
        """
    )

    parser.add_argument('--email', help='User email address')
    parser.add_argument('--tier', choices=['personal', 'team', 'enterprise'],
                       help='License tier')
    parser.add_argument('--days', type=int, help='Expiration in days (omit for lifetime)')
    parser.add_argument('--list', action='store_true', help='List all licenses')
    parser.add_argument('--validate', help='Validate a license key')
    parser.add_argument('--deactivate', help='Deactivate a license key')

    args = parser.parse_args()

    if args.list:
        list_licenses()
    elif args.validate:
        validate_license(args.validate)
    elif args.deactivate:
        deactivate_license(args.deactivate)
    elif args.email and args.tier:
        create_license(args.email, args.tier, args.days)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
