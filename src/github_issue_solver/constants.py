"""
Configuration constants for GitHub Issue Solver MCP Server.

This module centralizes all magic numbers and configuration values
to improve maintainability and make the system more configurable.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class FileProcessingConstants:
    """Constants for file processing and chunking."""

    # File size thresholds (in characters)
    SMALL_FILE_SIZE: int = 3000
    MEDIUM_FILE_SIZE: int = 10000
    LARGE_FILE_SIZE: int = 50000

    # Line limits for code extraction
    MAX_LINES_PER_FUNCTION: int = 50
    MIN_LINES_FOR_CLASS: int = 3

    # Priority file limits
    MAX_PRIORITY_FILES: int = 250
    MAX_SECONDARY_FILES: int = 150

    # Batch processing
    DEFAULT_BATCH_SIZE: int = 25
    MAX_BATCH_SIZE: int = 100


@dataclass
class IngestionConstants:
    """Constants for repository ingestion."""

    # Documentation limits
    MAX_README_FILES: int = 40
    MAX_DOC_FILES: int = 100
    MAX_WIKI_PAGES: int = 200

    # Issue and PR limits
    DEFAULT_MAX_ISSUES: int = 100
    DEFAULT_MAX_PRS: int = 15  # Reduced to prevent timeouts
    MAX_PR_LIMIT: int = 200  # Hard cap to prevent timeouts

    # Timeout and retry settings
    ASYNC_YIELD_INTERVAL: int = 5  # seconds
    MAX_INGESTION_TIME: int = 600  # 10 minutes

    # Progress tracking
    PROGRESS_LOG_FREQUENCY: int = 10  # Log every N items


@dataclass
class EmbeddingConstants:
    """Constants for embedding generation."""

    # Chunk sizes by provider
    FASTEMBED_MIN_CHUNK_SIZE: int = 8000
    FASTEMBED_MAX_CHUNK_SIZE: int = 10000
    FASTEMBED_CHUNK_OVERLAP: int = 400

    GOOGLE_MIN_CHUNK_SIZE: int = 4000
    GOOGLE_MAX_CHUNK_SIZE: int = 6000
    GOOGLE_CHUNK_OVERLAP: int = 200

    # Batch sizes by provider
    FASTEMBED_BATCH_SIZE: int = 100
    GOOGLE_BATCH_SIZE: int = 10

    # Chunk limits for different document types
    MAX_CHUNKS_PER_ISSUE: int = 1
    MAX_CHUNKS_PER_PR: int = 2
    MAX_CHUNKS_PER_DOC: int = 5
    MAX_CHUNKS_PER_CODE_FILE: int = 10

    # Retry settings
    MAX_EMBEDDING_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 60.0
    RETRY_EXPONENTIAL_BASE: float = 2.0


@dataclass
class ChromaDBConstants:
    """Constants for ChromaDB operations."""

    # Collection naming
    COLLECTION_PREFIX: str = "repo"

    # Default collection names
    DOCS_COLLECTION: str = "documentation"
    CODE_COLLECTION: str = "code"
    ISSUES_COLLECTION: str = "issues"
    PRS_COLLECTION: str = "prs"

    # Query settings
    DEFAULT_K: int = 5  # Number of similar documents to retrieve
    MAX_K: int = 20


@dataclass
class GitConstants:
    """Constants for Git operations."""

    # Clone settings
    CLONE_DEPTH: int = 1  # Shallow clone
    CLONE_TIMEOUT: int = 300  # 5 minutes

    # File extensions to process
    CODE_EXTENSIONS: set = None
    DOC_EXTENSIONS: set = None

    def __post_init__(self):
        if self.CODE_EXTENSIONS is None:
            self.CODE_EXTENSIONS = {
                '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c',
                '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift',
                '.kt', '.scala', '.r', '.m', '.dart', '.lua'
            }

        if self.DOC_EXTENSIONS is None:
            self.DOC_EXTENSIONS = {
                '.md', '.txt', '.rst', '.adoc', '.org', '.tex'
            }


@dataclass
class LicenseConstants:
    """Constants for license validation."""

    # License key format
    LICENSE_KEY_LENGTH: int = 32
    LICENSE_KEY_PATTERN: str = r'^[A-Z0-9]{8}-[A-Z0-9]{8}-[A-Z0-9]{8}-[A-Z0-9]{8}$'

    # License tiers
    TIER_FREE: str = "free"
    TIER_PERSONAL: str = "personal"
    TIER_TEAM: str = "team"
    TIER_ENTERPRISE: str = "enterprise"

    # Usage limits by tier
    LIMITS: Dict[str, Dict[str, int]] = None

    def __post_init__(self):
        if self.LIMITS is None:
            self.LIMITS = {
                self.TIER_FREE: {
                    'max_repositories': 3,
                    'max_analyses_per_month': 10,
                    'max_storage_gb': 1,
                },
                self.TIER_PERSONAL: {
                    'max_repositories': 10,
                    'max_analyses_per_month': 100,
                    'max_storage_gb': 10,
                },
                self.TIER_TEAM: {
                    'max_repositories': 50,
                    'max_analyses_per_month': 500,
                    'max_storage_gb': 100,
                },
                self.TIER_ENTERPRISE: {
                    'max_repositories': -1,  # Unlimited
                    'max_analyses_per_month': -1,  # Unlimited
                    'max_storage_gb': -1,  # Unlimited
                }
            }


# Create singleton instances
FILE_PROCESSING = FileProcessingConstants()
INGESTION = IngestionConstants()
EMBEDDING = EmbeddingConstants()
CHROMADB = ChromaDBConstants()
GIT = GitConstants()
LICENSE = LicenseConstants()


# Priority file patterns
PRIORITY_FILE_PATTERNS = [
    # Core files
    'main.*', 'app.*', 'index.*', 'server.*', 'client.*',
    # Configuration
    'config.*', 'settings.*', 'package.json', 'setup.py', 'Cargo.toml',
    # Important documentation
    'README.*', 'CONTRIBUTING.*', 'LICENSE', 'CHANGELOG.*',
    # Core directories
    'src/', 'lib/', 'core/', 'app/', 'main/'
]

EXCLUDED_PATTERNS = [
    # Dependencies
    'node_modules/', 'vendor/', 'third_party/', '.venv/', 'venv/',
    # Build artifacts
    'dist/', 'build/', 'target/', 'out/', '.next/',
    # Version control
    '.git/', '.svn/', '.hg/',
    # IDE
    '.idea/', '.vscode/', '.vs/',
    # Cache
    '__pycache__/', '.cache/', '.pytest_cache/',
    # OS
    '.DS_Store', 'Thumbs.db',
    # Compiled
    '*.pyc', '*.pyo', '*.so', '*.dll', '*.exe',
    # Minified
    '*.min.js', '*.min.css',
    # Large data
    '*.csv', '*.json.gz', '*.zip', '*.tar.gz'
]


def get_chunking_config(provider: str) -> dict:
    """
    Get chunking configuration based on embedding provider.

    Args:
        provider: Embedding provider ('fastembed' or 'google')

    Returns:
        Dictionary with chunking parameters
    """
    if provider == 'fastembed':
        return {
            'min_chunk_size': EMBEDDING.FASTEMBED_MIN_CHUNK_SIZE,
            'max_chunk_size': EMBEDDING.FASTEMBED_MAX_CHUNK_SIZE,
            'chunk_overlap': EMBEDDING.FASTEMBED_CHUNK_OVERLAP,
            'batch_size': EMBEDDING.FASTEMBED_BATCH_SIZE
        }
    else:  # google or default
        return {
            'min_chunk_size': EMBEDDING.GOOGLE_MIN_CHUNK_SIZE,
            'max_chunk_size': EMBEDDING.GOOGLE_MAX_CHUNK_SIZE,
            'chunk_overlap': EMBEDDING.GOOGLE_CHUNK_OVERLAP,
            'batch_size': EMBEDDING.GOOGLE_BATCH_SIZE
        }


def get_max_chunks_for_type(doc_type: str) -> int:
    """
    Get maximum chunks based on document type.

    Args:
        doc_type: Type of document ('issue', 'pr', 'doc', 'code')

    Returns:
        Maximum number of chunks
    """
    chunk_limits = {
        'issue': EMBEDDING.MAX_CHUNKS_PER_ISSUE,
        'pr': EMBEDDING.MAX_CHUNKS_PER_PR,
        'doc': EMBEDDING.MAX_CHUNKS_PER_DOC,
        'code': EMBEDDING.MAX_CHUNKS_PER_CODE_FILE
    }
    return chunk_limits.get(doc_type, EMBEDDING.MAX_CHUNKS_PER_CODE_FILE)
