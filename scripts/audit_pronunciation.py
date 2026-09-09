"""Audit only public assistant copy; never read user sessions or microphone audio."""
import argparse
import io
import json
import re
import time
import wave
from dataclasses import replace
from pathlib import Path

import numpy as np

from app.config import settings
from app.dialog import TEXT
from app.rag import RagKnowledgeBase
from app.text_preprocessor import RussianTextPreprocessor
from app.tts import SileroTts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--synthesize', action='store_true')
    args = parser.parse_args()
    out = Path('output/pronunciation-audit')
    out.mkdir(parents=True, exist_ok=True)
    corpus = {f'dialog-{key}': value for key, value in TEXT['ru'].items()}
    corpus.update({f'faq-{c["id"]}': c['answers']['ru'] for c in RagKnowledgeBase(settings.rag_dir).chunks})
    # Public strings from the RU site dictionary. Parse string literals, never execute TS.
    site = Path('frontend/src/i18n.ts').read_text(encoding='utf-8').split('ru: {', 1)[1].split('\nen: {', 1)[0]
    for key in ('intro', 'demoIntro', 'offlineText', 'howIntro', 'customNote', 'onpremDesc', 'priceNote', 'demoFreeText', 'founderText'):
        match = re.search(r'\b' + key + r':("(?:[^"\\]|\\.)*")', site)
        if match:
            corpus[f'site-{key}'] = json.loads(match[1])
    corpus['edge-words'] = 'В России, информация о компании, интеграции, ИИ-помощник, CRM, Telegram, email, МастерЧеб.'
    preprocessor = RussianTextPreprocessor(settings.tts_pronunciations_path)
    synth = SileroTts(replace(settings, silero_tts_device='cpu', tts_enabled=True))
    if args.synthesize:
        import torch
        torch.set_num_threads(4)
    records = []
    for key, original in corpus.items():
        normalized = preprocessor.preprocess(original)
        item = {'id': key, 'text': original, 'spoken_text': normalized,
                'latin_remaining': re.findall(r'[A-Za-z]+', normalized),
                'listening_status': 'requires_human_review'}
        if args.synthesize:
            start = time.perf_counter()
            try:
                audio = synth.synthesize_wav(original)
                with wave.open(io.BytesIO(audio)) as wav:
                    samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2')
                    item.update(duration_seconds=round(len(samples) / wav.getframerate(), 2),
                                sample_rate=wav.getframerate(), peak=int(np.abs(samples.astype(np.int32)).max()),
                                synthesis_seconds=round(time.perf_counter()-start, 2))
                assert len(samples) and item['peak'] > 0
                (out / f'{key}.wav').write_bytes(audio)
            except Exception as exc:
                item['error'] = f'{type(exc).__name__}: {exc}'
        records.append(item)
        print(key, 'ERROR' if 'error' in item else 'OK', flush=True)
    (out / 'report.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = ''.join('<tr><td>' + r['id'] + '</td><td><audio controls src="' + r['id'] + '.wav"></audio></td><td>' +
                   __import__('html').escape(r['spoken_text']) + '</td></tr>' for r in records)
    (out / 'index.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Проверка произношения Маши</title><style>body{font:18px system-ui;margin:32px;max-width:1200px}td{padding:16px;border-bottom:1px solid #ddd}audio{width:280px}</style><h1>Проверка произношения Маши</h1><p>Публичные фразы, голос kseniya. Техническая проверка не заменяет прослушивание. Аудио посетителей не использовалось.</p><table>'+rows+'</table></html>', encoding='utf-8')
    print(json.dumps({'phrases': len(records), 'errors': sum('error' in r for r in records), 'latin_remaining': sum(bool(r['latin_remaining']) for r in records)}))


if __name__ == '__main__':
    main()
