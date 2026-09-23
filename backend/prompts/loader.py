import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=32)
def load_prompt(filename: str) -> str:
    """Load prompt template from file with caching."""
    file_path = PROMPTS_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt template '{filename}' not found at {file_path}")
    return file_path.read_text(encoding="utf-8").strip()


def render_prompt(filename: str, **kwargs: Any) -> str:
    """Load prompt template and replace {{key}} or {{ key }} placeholders with values."""
    template = load_prompt(filename)
    for key, value in kwargs.items():
        val_str = str(value) if value is not None else ""
        template = re.sub(rf"\{{\{{\s*{re.escape(key)}\s*\}}\}}", lambda _, s=val_str: s, template)
    return template
