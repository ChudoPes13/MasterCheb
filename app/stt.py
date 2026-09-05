import logging
from threading import RLock
from .audio import pcm16_bytes_to_float32
from .config import Settings
log = logging.getLogger(__name__)

class WhisperStt:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None
        self._lock = RLock()

    @property
    def loaded(self):
        return self._model is not None

    def load(self):
        with self._lock:
            if self._model is not None:
                return
            from faster_whisper import WhisperModel
            local = self.settings.whisper_local_dir
            model_ref = str(local) if local.exists() and any(local.iterdir()) else self.settings.whisper_model
            self._model = WhisperModel(model_ref, device=self.settings.whisper_device,
                                       compute_type=self.settings.whisper_compute_type,
                                       download_root=str(local.parent))

    def transcribe_pcm16(self, pcm: bytes, language: str = 'ru'):
        # Thread-owned lock stays held even if its asyncio caller is cancelled.
        with self._lock:
            self.load()
            audio = pcm16_bytes_to_float32(pcm)
            if audio.size < self.settings.pcm_sample_rate * .25:
                return ''
            prompts = {'ru':'Мастер Чеб, Маша, ИИ-агент, подписка, внедрение, консультация, CRM.',
                       'en':'MasterCheb, Masha, AI agent, subscription, implementation, consultation.',
                       'zh':'人工智能助手，订阅，本地部署，咨询。'}
            segments, _ = self._model.transcribe(audio, language=language,
                beam_size=self.settings.whisper_beam_size, vad_filter=True,
                condition_on_previous_text=False, temperature=0.0,
                without_timestamps=True, initial_prompt=prompts.get(language))
            return ' '.join(seg.text.strip() for seg in segments).strip()
