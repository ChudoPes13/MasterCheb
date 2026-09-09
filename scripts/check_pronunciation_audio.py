"""Secondary ASR check of generated public-copy fixtures, not of customer audio."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from faster_whisper import WhisperModel

from app.config import settings


def main():
    directory = Path('output/pronunciation-audit')
    records = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
    model = WhisperModel(str(settings.whisper_local_dir), device=settings.whisper_device,
                         compute_type=settings.whisper_compute_type, local_files_only=True)
    results = []
    for record in records:
        path = directory / (record['id'] + '.wav')
        segments, _ = model.transcribe(str(path), language='ru', beam_size=3, vad_filter=False,
                                       condition_on_previous_text=False)
        recognized = ' '.join(s.text.strip() for s in segments)
        normalize = lambda text: re.sub(r'[^а-яa-z0-9]', '', text.lower().replace('ё', 'е'))
        similarity = SequenceMatcher(None, normalize(record['spoken_text']), normalize(recognized), autojunk=False).ratio()
        results.append({'id': record['id'], 'spoken_text': record['spoken_text'], 'recognized': recognized,
                        'character_similarity': round(similarity, 3), 'human_listening_required': True})
        print(record['id'], round(similarity, 3), flush=True)
    (directory / 'asr-check.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Finished:', len(results), 'public phrases. ASR similarity is not a pronunciation score.')


if __name__ == '__main__':
    main()
