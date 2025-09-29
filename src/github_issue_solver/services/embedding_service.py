"""
Embedding service for the GitHub Issue Solver MCP Server.

Handles the initialization and provision of different embedding models,
allowing for flexible switching between cloud-based (Google) and local
(FastEmbed) providers.
"""

from loguru import logger
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.embeddings import FastEmbedEmbeddings
from ..config import Config
from ..exceptions import ConfigurationError

class EmbeddingService:
    """Factory class to create and provide the configured embedding model."""

    def __init__(self, config: Config):
        self.config = config
        self._embeddings = None
        logger.info(f"Initializing embedding service with provider: '{self.config.embedding_provider}'")

    def get_embeddings(self):
        """Get or create the configured embeddings instance."""
        if self._embeddings is None:
            provider = self.config.embedding_provider
            if provider == "google":
                self._embeddings = self._create_google_embeddings()
            elif provider == "fastembed":
                self._embeddings = self._create_fastembed_embeddings()
            else:
                raise ConfigurationError(
                    f"Unsupported embedding provider: '{provider}'",
                    details={"suggestion": "Choose 'google' or 'fastembed' for EMBEDDING_PROVIDER"}
                )
        return self._embeddings

    def _create_google_embeddings(self) -> GoogleGenerativeAIEmbeddings:
        """Create an instance of Google's embedding model."""
        try:
            logger.info(f"Using Google embedding model: '{self.config.gemini_embedding_model}'")
            embeddings = GoogleGenerativeAIEmbeddings(
                model=self.config.gemini_embedding_model,
                google_api_key=self.config.google_api_key
            )
            logger.success("Google Generative AI embeddings client initialized successfully.")
            return embeddings
        except Exception as e:
            logger.error(f"Failed to initialize Google embeddings client: {e}")
            raise ConfigurationError(
                "Failed to initialize Google embeddings client.",
                details={"error": str(e), "suggestion": "Check your GOOGLE_API_KEY and network connection."}
            )

    def _create_fastembed_embeddings(self) -> FastEmbedEmbeddings:
        """Create an instance of a local FastEmbed model."""
        try:
            model_name = self.config.embedding_model_name
            logger.info(f"Using local offline embedding model: '{model_name}'")
            logger.info("This may trigger a one-time download of the model...")
            
            # FastEmbed handles model caching automatically.
            embeddings = FastEmbedEmbeddings(model_name=model_name)
            
            logger.success(f"FastEmbed client with model '{model_name}' initialized successfully.")
            return embeddings
        except Exception as e:
            logger.error(f"Failed to initialize FastEmbed client: {e}")
            raise ConfigurationError(
                "Failed to initialize FastEmbed client.",
                details={"error": str(e), "suggestion": "Ensure 'fastembed' and its dependencies are installed correctly."}
            )
