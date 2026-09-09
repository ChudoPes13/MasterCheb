from dataclasses import replace

import numpy as np

from app.config import settings
from app.vad import VadSegmenter, VadSettings


def test_speech_onset_is_not_duplicated(monkeypatch):
    monkeypatch.setattr(VadSegmenter, '_load_silero', lambda self: None)
    monkeypatch.setattr(VadSegmenter, '_crop_with_silero', lambda self, raw: raw)
    segmenter = VadSegmenter(settings, VadSettings.from_settings(settings))
    chunk = np.full(4800, 2000, dtype='<i2').tobytes()
    segmenter.accept_pcm16(chunk)
    assert segmenter.flush() == chunk
