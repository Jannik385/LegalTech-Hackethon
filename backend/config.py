import os
from dotenv import load_dotenv

load_dotenv()

# AI model — swap here to change the model for all services
MODEL = "anthropic/claude-haiku-5.5"

# OpenRouter API key — loaded from .env
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

if not OPENROUTER_API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY is not set. "
        "Copy .env.example to .env and add your key from https://openrouter.ai/keys"
    )
