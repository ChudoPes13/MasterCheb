"""Small multilingual BM25 retriever; no paid API or embedding service."""
import json
import math
import re
from collections import Counter
from pathlib import Path

def tokens(text: str):
    text = text.lower().replace("ё", "е")
    words = re.findall(r"[a-zа-я0-9]+", text)
    words = [w[:6] if re.search('[а-я]', w) and len(w) > 6 else w for w in words]
    for phrase in re.findall(r"[\u4e00-\u9fff]+", text):
        words.extend(phrase[i:i+2] for i in range(max(1, len(phrase)-1)))
    return words

class RagKnowledgeBase:
    def __init__(self, directory: Path):
        self.chunks = []
        for file in sorted(directory.glob('*.jsonl')):
            for line in file.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    self.chunks.append(json.loads(line))
        if not self.chunks or len({c['id'] for c in self.chunks}) != len(self.chunks):
            raise ValueError('Empty knowledge base or duplicate IDs')
        for c in self.chunks:
            for lang in ('ru', 'en', 'zh'):
                if not c['answers'].get(lang):
                    raise ValueError(f"Missing {lang} answer in {c['id']}")
        self.docs = [Counter(tokens(c['title'] + ' ' + ' '.join(c['queries']))) for c in self.chunks]
        self.df = Counter(t for d in self.docs for t in d)
        self.avg = sum(sum(d.values()) for d in self.docs) / len(self.docs)

    def search(self, query: str, limit: int = 3):
        qt = set(tokens(query))
        result = []
        for chunk, doc in zip(self.chunks, self.docs):
            score = 0.0
            for t in qt & doc.keys():
                idf = math.log(1 + (len(self.docs) - self.df[t] + .5) / (self.df[t] + .5))
                score += idf * doc[t] * 2.2 / (doc[t] + 1.2 * (.25 + .75 * sum(doc.values()) / self.avg))
            for alias in chunk['queries']:
                if len(alias) > 3 and alias.casefold() in query.casefold():
                    score += 5
            if score >= 1.4:
                result.append({**chunk, 'score': score})
        return sorted(result, key=lambda c: -c['score'])[:limit]
