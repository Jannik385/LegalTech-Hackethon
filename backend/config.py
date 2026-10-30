import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# AI model — swap here to change the model for all services
MODEL = "anthropic/claude-haiku-5.5"

# OpenRouter API key — loaded from .env
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

if not OPENROUTER_API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY is not set. "
        "Copy .env.example to .env and add your key from https://openrouter.ai/keys"
    )

# ---------------------------------------------------------------------------
# RAG configuration
# ---------------------------------------------------------------------------

_BASE = Path(__file__).parent  # backend/

# Local ChromaDB persistence directory
CHROMA_PATH = str(_BASE / ".chromadb")

# Sentence-transformers model for embeddings (multilingual, handles German well)
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"

# Directory containing Mietrecht law text files
LAW_TEXTS_PATH = str(_BASE / "law_texts")
