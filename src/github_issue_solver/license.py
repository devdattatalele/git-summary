"""
License validation system using Supabase.

This module handles license validation via Supabase database,
trial period management, and usage tracking.
"""

import os
import uuid
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from loguru import logger

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("Supabase client not installed. Install with: pip install supabase")

from .constants import LICENSE
from .exceptions import ConfigurationError


@dataclass
class LicenseInfo:
    """License information."""
    license_key: str
    tier: str
    user_id: str
    max_repositories: int
    max_analyses_per_month: int
    max_storage_gb: int
    issued_at: datetime
    expires_at: Optional[datetime] = None
    is_trial: bool = False
    metadata: Dict[str, Any] = None

    def is_valid(self) -> bool:
        """Check if license is valid and not expired."""
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def days_remaining(self) -> Optional[int]:
        """Get days remaining until expiration."""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert datetime to string
        if isinstance(data['issued_at'], datetime):
            data['issued_at'] = data['issued_at'].isoformat()
        if data.get('expires_at') and isinstance(data['expires_at'], datetime):
            data['expires_at'] = data['expires_at'].isoformat()
        return data


def get_machine_id() -> str:
    """
    Generate a unique and persistent machine identifier.

    Uses multiple hardware identifiers to create a unique ID that persists
    across reinstalls. This prevents trial bypass by reinstalling.

    Identifiers used:
    - MAC address (primary network interface)
    - Machine UUID (if available on Linux/Mac)
    - Platform info (OS + architecture)
    """
    import socket
    import platform
    import subprocess

    identifiers = []

    try:
        # 1. MAC address (most reliable, hardware-based)
        mac = uuid.getnode()
        identifiers.append(f"mac:{mac}")

        # 2. Hostname (can change but adds uniqueness)
        hostname = socket.gethostname()
        identifiers.append(f"host:{hostname}")

        # 3. Machine UUID (Linux: /etc/machine-id, macOS: IOPlatformUUID)
        try:
            if platform.system() == "Linux":
                # Read Linux machine-id (persistent across reinstalls)
                with open("/etc/machine-id", "r") as f:
                    machine_uuid = f.read().strip()
                    identifiers.append(f"uuid:{machine_uuid}")
            elif platform.system() == "Darwin":  # macOS
                # Get IOPlatformUUID (hardware UUID)
                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if "IOPlatformUUID" in result.stdout:
                    for line in result.stdout.split('\n'):
                        if "IOPlatformUUID" in line:
                            machine_uuid = line.split('"')[3]
                            identifiers.append(f"uuid:{machine_uuid}")
                            break
        except Exception as e:
            logger.debug(f"Could not read machine UUID: {e}")

        # 4. Platform info (OS + architecture for additional uniqueness)
        platform_info = f"{platform.system()}-{platform.machine()}"
        identifiers.append(f"platform:{platform_info}")

        # Combine all identifiers
        if len(identifiers) < 2:
            # If we couldn't get enough identifiers, this is suspicious
            logger.error(f"WARNING: Only {len(identifiers)} machine identifiers found. Trial tracking may be unreliable.")

        machine_str = "|".join(identifiers)
        machine_id = hashlib.sha256(machine_str.encode()).hexdigest()[:24]  # Longer hash for more security

        logger.debug(f"Machine ID generated from {len(identifiers)} identifiers")
        return machine_id

    except Exception as e:
        logger.error(f"CRITICAL: Failed to generate machine ID: {e}")
        # IMPORTANT: Don't use random fallback - this creates trial bypass loophole!
        # Instead, use a minimal but deterministic ID
        try:
            # Last resort: Just use MAC address
            mac = uuid.getnode()
            fallback_id = hashlib.sha256(f"fallback-{mac}".encode()).hexdigest()[:24]
            logger.warning("Using fallback machine ID based on MAC address only")
            return fallback_id
        except:
            # Absolute last resort: Use a fixed ID (all users share same trial)
            logger.error("CRITICAL: Cannot generate any machine ID. Using fixed ID (shared trial).")
            return "SHARED_TRIAL_ID_0001"


class LicenseValidator:
    """
    License validation using Supabase database.
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize license validator with Supabase connection.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase anonymous key
        """
        if not SUPABASE_AVAILABLE:
            raise ConfigurationError(
                "Supabase client not installed. Install with: pip install supabase"
            )

        self.supabase: Client = create_client(supabase_url, supabase_key)
        logger.info("Connected to Supabase for license validation")

    def validate_license_key(self, license_key: str) -> LicenseInfo:
        """
        Validate a license key via Supabase.

        Args:
            license_key: License key to validate

        Returns:
            LicenseInfo if valid

        Raises:
            ConfigurationError: If license is invalid or expired
        """
        try:
            # Query license from Supabase
            response = self.supabase.table('licenses') \
                .select('*') \
                .eq('license_key', license_key) \
                .eq('is_active', True) \
                .execute()

            if not response.data or len(response.data) == 0:
                raise ConfigurationError(
                    f"License key not found or inactive.\n"
                    f"Please contact support or check your license key.\n"
                    f"License key provided: {license_key[:10]}..."
                )

            license_data = response.data[0]

            # Parse datetime strings
            issued_at = datetime.fromisoformat(license_data['issued_at'].replace('Z', '+00:00'))
            expires_at = None
            if license_data.get('expires_at'):
                expires_at = datetime.fromisoformat(license_data['expires_at'].replace('Z', '+00:00'))

            # Create LicenseInfo object
            license_info = LicenseInfo(
                license_key=license_data['license_key'],
                tier=license_data['tier'],
                user_id=license_data['user_id'],
                max_repositories=license_data['max_repositories'],
                max_analyses_per_month=license_data['max_analyses_per_month'],
                max_storage_gb=license_data['max_storage_gb'],
                issued_at=issued_at,
                expires_at=expires_at,
                is_trial=license_data.get('is_trial', False),
                metadata=license_data.get('metadata', {})
            )

            # Check expiration
            if not license_info.is_valid():
                days_expired = (datetime.now(timezone.utc) - expires_at).days if expires_at else 0
                raise ConfigurationError(
                    f"License key has expired {days_expired} days ago.\n"
                    f"Expired on: {expires_at.strftime('%Y-%m-%d') if expires_at else 'N/A'}\n"
                    f"Please renew your license to continue using this product.\n"
                    f"Contact: support@github-issue-solver.com"
                )

            # Log successful validation
            days_left = license_info.days_remaining()
            if days_left is not None:
                logger.info(f"License validated: {license_info.tier} tier, expires in {days_left} days")
            else:
                logger.info(f"License validated: {license_info.tier} tier, lifetime license")

            return license_info

        except ConfigurationError:
            raise
        except Exception as e:
            logger.error(f"License validation error: {e}")
            raise ConfigurationError(
                f"Failed to validate license: {str(e)}\n"
                f"Please check your internet connection and Supabase configuration."
            )

    def get_or_create_trial(self, machine_id: str) -> LicenseInfo:
        """
        Get existing trial or create new 10-day trial for this machine.

        Args:
            machine_id: Unique machine identifier

        Returns:
            LicenseInfo for trial

        Raises:
            ConfigurationError: If trial expired
        """
        try:
            # Check if trial exists for this machine
            response = self.supabase.table('trial_users') \
                .select('*') \
                .eq('machine_id', machine_id) \
                .execute()

            if response.data and len(response.data) > 0:
                # Trial exists - check if expired
                trial_data = response.data[0]
                started_at = datetime.fromisoformat(trial_data['started_at'].replace('Z', '+00:00'))
                expires_at = datetime.fromisoformat(trial_data['expires_at'].replace('Z', '+00:00'))

                if datetime.now(timezone.utc) > expires_at:
                    # Trial expired
                    days_expired = (datetime.now(timezone.utc) - expires_at).days

                    # Mark as expired in database
                    self.supabase.table('trial_users') \
                        .update({'is_expired': True}) \
                        .eq('machine_id', machine_id) \
                        .execute()

                    raise ConfigurationError(
                        f"🔒 Free trial expired {days_expired} days ago!\n\n"
                        f"Trial period: 10 days\n"
                        f"Started: {started_at.strftime('%Y-%m-%d')}\n"
                        f"Expired: {expires_at.strftime('%Y-%m-%d')}\n\n"
                        f"To continue using GitHub Issue Solver:\n"
                        f"1. Purchase a license key\n"
                        f"2. Email: support@github-issue-solver.com\n"
                        f"3. Add LICENSE_KEY to your environment\n\n"
                        f"Pricing:\n"
                        f"- Personal: $9/month (10 repos, 100 analyses)\n"
                        f"- Team: $29/month (50 repos, 500 analyses)\n"
                        f"- Enterprise: Custom pricing"
                    )

                # Trial still valid
                days_remaining = (expires_at - datetime.now(timezone.utc)).days
                logger.warning(
                    f"🔓 Running in FREE TRIAL mode. "
                    f"Expires in {days_remaining} days (on {expires_at.strftime('%Y-%m-%d')})"
                )

                return LicenseInfo(
                    license_key='TRIAL-MODE',
                    tier=LICENSE.TIER_FREE,
                    user_id=f'trial_{machine_id}',
                    max_repositories=3,
                    max_analyses_per_month=10,
                    max_storage_gb=1,
                    issued_at=started_at,
                    expires_at=expires_at,
                    is_trial=True
                )

            else:
                # Create new trial (10 days)
                started_at = datetime.now(timezone.utc)
                expires_at = started_at + timedelta(days=10)

                # Insert into database
                self.supabase.table('trial_users').insert({
                    'machine_id': machine_id,
                    'started_at': started_at.isoformat(),
                    'expires_at': expires_at.isoformat(),
                    'repositories_used': 0,
                    'analyses_used': 0,
                    'is_expired': False
                }).execute()

                logger.warning(
                    f"✅ Free 10-day trial started!\n"
                    f"Started: {started_at.strftime('%Y-%m-%d')}\n"
                    f"Expires: {expires_at.strftime('%Y-%m-%d')}\n"
                    f"Limits: 3 repositories, 10 analyses"
                )

                return LicenseInfo(
                    license_key='TRIAL-MODE',
                    tier=LICENSE.TIER_FREE,
                    user_id=f'trial_{machine_id}',
                    max_repositories=3,
                    max_analyses_per_month=10,
                    max_storage_gb=1,
                    issued_at=started_at,
                    expires_at=expires_at,
                    is_trial=True
                )

        except ConfigurationError:
            raise
        except Exception as e:
            logger.error(f"Trial management error: {e}")
            raise ConfigurationError(
                f"Failed to manage trial: {str(e)}\n"
                f"Please check your internet connection."
            )

    def track_usage(
        self,
        license_key: str,
        action: str,
        repository: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        machine_id: Optional[str] = None
    ) -> None:
        """
        Track usage in Supabase for both paid and trial users.

        Args:
            license_key: License key (or 'TRIAL-MODE' for trial users)
            action: Action performed ('ingest', 'analyze', 'patch')
            repository: Repository name (optional)
            metadata: Additional metadata (optional)
            machine_id: Machine ID for trial users (optional)
        """
        try:
            # Track in license_usage table (for all users including trials)
            usage_data = {
                'license_key': license_key,
                'action': action,
                'repository': repository,
                'metadata': metadata or {}
            }

            # Add machine_id to metadata for trial users
            if license_key == 'TRIAL-MODE' and machine_id:
                usage_data['metadata']['machine_id'] = machine_id

            self.supabase.table('license_usage').insert(usage_data).execute()

            logger.debug(f"Usage tracked: {action} for {license_key[:10]}...")

            # For trial users, also update trial_users counters
            if license_key == 'TRIAL-MODE' and machine_id:
                self._update_trial_counters(machine_id, action, repository)

        except Exception as e:
            # Don't fail if usage tracking fails
            logger.warning(f"Failed to track usage: {e}")

    def _update_trial_counters(self, machine_id: str, action: str, repository: Optional[str] = None) -> None:
        """
        Update trial user counters in trial_users table.

        Args:
            machine_id: Machine ID
            action: Action performed
            repository: Repository name (optional)
        """
        try:
            # Get current trial data
            response = self.supabase.table('trial_users') \
                .select('repositories_used, analyses_used') \
                .eq('machine_id', machine_id) \
                .execute()

            if response.data and len(response.data) > 0:
                current = response.data[0]
                updates = {}

                # Increment appropriate counter
                if action == 'ingest' and repository:
                    # Count unique repositories
                    updates['repositories_used'] = current.get('repositories_used', 0) + 1
                elif action in ['analyze', 'patch']:
                    updates['analyses_used'] = current.get('analyses_used', 0) + 1

                # Update if we have changes
                if updates:
                    self.supabase.table('trial_users') \
                        .update(updates) \
                        .eq('machine_id', machine_id) \
                        .execute()

                    logger.debug(f"Trial counters updated for machine {machine_id[:8]}...: {updates}")

        except Exception as e:
            logger.warning(f"Failed to update trial counters: {e}")

    def check_trial_limits(self, machine_id: str, action: str) -> tuple[bool, str]:
        """
        Check if trial user has exceeded their limits.

        Args:
            machine_id: Machine ID
            action: Action being performed ('ingest', 'analyze', 'patch')

        Returns:
            Tuple of (allowed: bool, message: str)
        """
        try:
            # Get current trial data
            response = self.supabase.table('trial_users') \
                .select('repositories_used, analyses_used, expires_at, is_expired') \
                .eq('machine_id', machine_id) \
                .execute()

            if not response.data or len(response.data) == 0:
                # No trial found - should not happen, but allow (will create trial)
                return True, ""

            trial = response.data[0]

            # Check if expired
            if trial.get('is_expired', False):
                return False, "🔒 Trial expired. Please purchase a license to continue."

            # Check limits based on action
            if action == 'ingest':
                repos_used = trial.get('repositories_used', 0)
                if repos_used >= 3:
                    return False, (
                        f"🔒 Trial limit reached: {repos_used}/3 repositories used.\n"
                        f"Please purchase a license to ingest more repositories.\n"
                        f"Personal: $9/month (10 repos) | Team: $29/month (50 repos)"
                    )
            elif action in ['analyze', 'patch']:
                analyses_used = trial.get('analyses_used', 0)
                if analyses_used >= 10:
                    return False, (
                        f"🔒 Trial limit reached: {analyses_used}/10 analyses used.\n"
                        f"Please purchase a license to perform more analyses.\n"
                        f"Personal: $9/month (100 analyses) | Team: $29/month (500 analyses)"
                    )

            # Within limits
            return True, ""

        except Exception as e:
            logger.error(f"Error checking trial limits: {e}")
            # On error, allow (fail open)
            return True, ""

    def get_trial_usage_stats(self, machine_id: str) -> Dict[str, Any]:
        """
        Get usage statistics for a trial user.

        Args:
            machine_id: Machine ID

        Returns:
            Dictionary with usage stats
        """
        try:
            response = self.supabase.table('trial_users') \
                .select('*') \
                .eq('machine_id', machine_id) \
                .execute()

            if not response.data or len(response.data) == 0:
                return {"error": "Trial not found"}

            trial = response.data[0]
            expires_at = datetime.fromisoformat(trial['expires_at'].replace('Z', '+00:00'))
            days_remaining = max(0, (expires_at - datetime.now(timezone.utc)).days)

            return {
                "repositories_used": trial.get('repositories_used', 0),
                "repositories_limit": 3,
                "analyses_used": trial.get('analyses_used', 0),
                "analyses_limit": 10,
                "days_remaining": days_remaining,
                "started_at": trial['started_at'],
                "expires_at": trial['expires_at'],
                "is_expired": trial.get('is_expired', False)
            }

        except Exception as e:
            logger.error(f"Error getting trial stats: {e}")
            return {"error": str(e)}


def get_license_from_env() -> Optional[str]:
    """Get license key from environment variable."""
    return os.getenv('LICENSE_KEY')


def validate_and_get_license_info(
    supabase_url: str,
    supabase_key: str
) -> LicenseInfo:
    """
    Validate license from environment and return license info.

    Args:
        supabase_url: Supabase project URL
        supabase_key: Supabase anonymous key

    Returns:
        LicenseInfo

    Raises:
        ConfigurationError: If license is invalid
    """
    # Check development mode FIRST (before validating license format)
    if os.getenv('ALLOW_NO_LICENSE', '').lower() == 'true':
        logger.warning("🔓 Running without license validation (development mode)")
        return LicenseInfo(
            license_key='DEV-MODE-NO-LICENSE',
            tier=LICENSE.TIER_FREE,
            user_id='dev_user',
            max_repositories=3,
            max_analyses_per_month=10,
            max_storage_gb=1,
            issued_at=datetime.now(timezone.utc),
            is_trial=True
        )

    validator = LicenseValidator(supabase_url, supabase_key)

    # Try to get license key from environment
    license_key = get_license_from_env()

    if license_key:
        # Validate provided license key
        logger.info("Validating provided license key...")
        return validator.validate_license_key(license_key)
    else:
        # No license key - use free trial
        logger.info("No license key provided, checking free trial status...")
        machine_id = get_machine_id()
        logger.info(f"Machine ID: {machine_id}")
        return validator.get_or_create_trial(machine_id)
