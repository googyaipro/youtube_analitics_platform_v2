from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=32)
def load_prompt(filename: str) -> str:
    """Load prompt template from file with caching."""
    file_path = PROMPTS_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt template '{filename}' not found at {file_path}")
    return file_path.read_text(encoding="utf-8").strip()
