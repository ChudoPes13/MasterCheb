from __future__ import annotations

import json
import re
from pathlib import Path

from num2words import num2words


class RussianTextPreprocessor:
    """Normalize sales text before it reaches the Russian Silero model."""

    def __init__(self, pronunciations_path: Path | None = None):
        path = pronunciations_path or Path(__file__).resolve().parents[1] / "config" / "tts_pronunciations.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        rules = payload.get("rules")
        if not isinstance(rules, list):
            raise ValueError(f"Invalid TTS pronunciations file: {path}")
        self.pronunciation_rules = tuple(
            (str(rule["pattern"]), str(rule["replacement"]))
            for rule in rules
            if isinstance(rule, dict) and "pattern" in rule and "replacement" in rule
        )

    def preprocess(self, text: str) -> str:
        for pattern, replacement in self.pronunciation_rules:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return self._convert_numbers(text)

    def _convert_numbers(self, text: str) -> str:
        def num_to_words(match: re.Match[str]) -> str:
            num = match.group().replace(" ", "").replace("\u00a0", "")
            try:
                return num2words(int(num), lang="ru")
            except Exception:
                return num

        return re.sub(r"\b(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)\b", num_to_words, text)
