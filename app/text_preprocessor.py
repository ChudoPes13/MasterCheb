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
        adjective = {'': 'виртуальный', 'а': 'виртуального', 'у': 'виртуальному',
                     'ом': 'виртуальным', 'е': 'виртуальном', 'ы': 'виртуальные', 'и': 'виртуальные',
                     'ов': 'виртуальных', 'ам': 'виртуальным', 'ами': 'виртуальными', 'ах': 'виртуальных'}
        text = re.sub(r'\bИИ[- ](консультант|помощник|агент)(ами|ам|ах|ов|ом|у|а|е|ы|и)?\b',
                      lambda m: adjective[(m[2] or '').lower()] + ' ' + m[1].lower() + (m[2] or '').lower(), text, flags=re.I)
        text = re.sub(r'\bв ИИ\b', 'в искусственном интеллекте', text, flags=re.I)
        text = re.sub(r'\bоб ИИ\b', 'об искусственном интеллекте', text, flags=re.I)
        text = re.sub(r'\bс ИИ\b', 'с искусственным интеллектом', text, flags=re.I)
        text = re.sub(r'\bна\s+1\s*[–—-]\s*3\s+дня', 'на срок от одного до трёх дней', text)
        text = re.sub(r'(?<!\w)1\s*[–—-]\s*3\s+недел[ьи]', 'от одной до трёх недель', text)
        text = re.sub(r'(?<!\w)1\s*[–—-]\s*3\s+дня', 'от одного до трёх дней', text)
        text = re.sub(r'\bот\s+50[ \u00a0]?000\s*(?:рублей|₽)', 'от пятидесяти тысяч рублей', text, flags=re.I)
        text = re.sub(r'\bот\s+250[ \u00a0]?000\s*(?:рублей|₽)', 'от двухсот пятидесяти тысяч рублей', text, flags=re.I)
        # Contact details remain visible and clickable; spellings are not natural speech.
        text = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', 'электронной почте, указанной в чате', text)
        text = re.sub(r'(?<!\w)@[a-zA-Z][\w]+', 'контакт, указанный в чате', text)
        text = re.sub(r'\+7[ (\d)\-–]{10,20}\d', 'номеру, указанному в чате', text)
        text = text.replace('по почте электронной почте', 'по электронной почте').replace('или почте электронной почте', 'или электронной почте')
        text = text.replace('по телефону номеру', 'по номеру')
        text = re.sub(r'On-Prem означает установку агента', 'Локальное размещение означает установку агента', text, flags=re.I)
        for pattern, replacement in self.pronunciation_rules:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return self._convert_numbers(text).replace('₽', ' рублей').replace('/месяц', ' в месяц')

    def _convert_numbers(self, text: str) -> str:
        def num_to_words(match: re.Match[str]) -> str:
            num = match.group().replace(" ", "").replace("\u00a0", "")
            try:
                return num2words(int(num), lang="ru")
            except Exception:
                return num

        return re.sub(r"\b(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)\b", num_to_words, text)
