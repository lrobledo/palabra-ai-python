from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from environs import Env
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    PrivateAttr,
    model_validator,
)

from palabra_ai.base.message import Message
from palabra_ai.exc import ConfigurationError
from palabra_ai.lang import Language
from palabra_ai.types import T_IN_PCM, T_ON_TRANSCRIPTION, T_OUT_PCM

env = Env(prefix="PALABRA_")
env.read_env()
DEBUG = env.bool("DEBUG", default=False)
LOG_FILE = env.path("LOG_FILE", default=None)


# Audio Processing Constants
CHUNK_SIZE = 16384
SAMPLE_RATE_DEFAULT = 48000
CHANNELS_MONO = 1

# Timing Constants
# if it will be small, publication stops too early and you can get non-finalized translated audio
SAFE_PUBLICATION_END_DELAY = 10.0

MONITOR_TIMEOUT = 0.1
DEFAULT_PROCESS_TIMEOUT = 300.0
TRACK_WAIT_TIMEOUT = 30.0
FINALIZE_WAIT_TIME = 5.0
SLEEP_INTERVAL_DEFAULT = 0.1
SLEEP_INTERVAL_LONG = 1.0
SLEEP_INTERVAL_BUFFER_CHECK = 5.0
QUEUE_READ_TIMEOUT = 1.0
QUEUE_WAIT_TIMEOUT = 0.5

# Retry and Counter Constants
TRACK_RETRY_MAX_ATTEMPTS = 30
TRACK_RETRY_DELAY = 1.0
GET_TASK_WAIT_TIMEOUT = 5.0

# Buffer and Queue Constants
THREADPOOL_MAX_WORKERS = 32
DEVICE_ID_HASH_LENGTH = 8
MONITOR_MESSAGE_PREVIEW_LENGTH = 100
AUDIO_PROGRESS_LOG_INTERVAL = 100000

# EOF and Completion Constants
EMPTY_MESSAGE_THRESHOLD = 10
EOF_DRAIN_TIMEOUT = 5.0
COMPLETION_WAIT_TIMEOUT = 2.0
STATS_LOG_INTERVAL = 1.0

# Preprocessing Constants
MIN_SENTENCE_CHARACTERS_DEFAULT = 80
MIN_SENTENCE_SECONDS_DEFAULT = 4
MIN_SPLIT_INTERVAL_DEFAULT = 0.6
CONTEXT_SIZE_DEFAULT = 30
SEGMENTS_AFTER_RESTART_DEFAULT = 15
STEP_SIZE_DEFAULT = 5
MAX_STEPS_WITHOUT_EOS_DEFAULT = 3
FORCE_END_OF_SEGMENT_DEFAULT = 0.5

# Filler Phrases Constants
MIN_TRANSCRIPTION_LEN_DEFAULT = 40
MIN_TRANSCRIPTION_TIME_DEFAULT = 3
PHRASE_CHANCE_DEFAULT = 0.5

# TTS Constants
F0_VARIANCE_FACTOR_DEFAULT = 1.2
ENERGY_VARIANCE_FACTOR_DEFAULT = 1.5
SPEECH_TEMPO_ADJUSTMENT_FACTOR_DEFAULT = 0.75

# Queue Config Constants
DESIRED_QUEUE_LEVEL_MS_DEFAULT = 8000
MAX_QUEUE_LEVEL_MS_DEFAULT = 24000

# TranscriptionMessage Constants
MIN_ALIGNMENT_SCORE_DEFAULT = 0.2
MAX_ALIGNMENT_CER_DEFAULT = 0.8
SEGMENT_CONFIRMATION_SILENCE_THRESHOLD_DEFAULT = 0.7

# VAD Constants
VAD_THRESHOLD_DEFAULT = 0.5
VAD_LEFT_PADDING_DEFAULT = 1
VAD_RIGHT_PADDING_DEFAULT = 1


def validate_language(v):
    if isinstance(v, str):
        return Language.get_by_bcp47(v)
    return v


def serialize_language(lang: Language) -> str:
    return lang.bcp47


LanguageField = Annotated[
    Language, BeforeValidator(validate_language), PlainSerializer(serialize_language)
]


class Stream(BaseModel):
    content_type: str = "audio"


class InputStream(Stream):
    source: dict[str, str] = {"type": "livekit"}


class OutputStream(Stream):
    target: dict[str, str] = {"type": "livekit"}


class Preprocessing(BaseModel):
    enable_vad: bool = True
    vad_threshold: float = VAD_THRESHOLD_DEFAULT
    vad_left_padding: int = VAD_LEFT_PADDING_DEFAULT
    vad_right_padding: int = VAD_RIGHT_PADDING_DEFAULT
    pre_vad_denoise: bool = False
    pre_vad_dsp: bool = True
    record_tracks: list[str] = []
    auto_tempo: bool = False


class SplitterAdvanced(BaseModel):
    min_sentence_characters: int = MIN_SENTENCE_CHARACTERS_DEFAULT
    min_sentence_seconds: int = MIN_SENTENCE_SECONDS_DEFAULT
    min_split_interval: float = MIN_SPLIT_INTERVAL_DEFAULT
    context_size: int = CONTEXT_SIZE_DEFAULT
    segments_after_restart: int = SEGMENTS_AFTER_RESTART_DEFAULT
    step_size: int = STEP_SIZE_DEFAULT
    max_steps_without_eos: int = MAX_STEPS_WITHOUT_EOS_DEFAULT
    force_end_of_segment: float = FORCE_END_OF_SEGMENT_DEFAULT


class Splitter(BaseModel):
    enabled: bool = True
    splitter_model: str = "auto"
    advanced: SplitterAdvanced = Field(default_factory=SplitterAdvanced)


class Verification(BaseModel):
    verification_model: str = "auto"
    allow_verification_glossaries: bool = True
    auto_transcription_correction: bool = False
    transcription_correction_style: str | None = None


class FillerPhrases(BaseModel):
    enabled: bool = False
    min_transcription_len: int = MIN_TRANSCRIPTION_LEN_DEFAULT
    min_transcription_time: int = MIN_TRANSCRIPTION_TIME_DEFAULT
    phrase_chance: float = PHRASE_CHANCE_DEFAULT


class TranscriptionAdvanced(BaseModel):
    filler_phrases: FillerPhrases = Field(default_factory=FillerPhrases)
    ignore_languages: list[str] = []


class Transcription(BaseModel):
    detectable_languages: list[str] = []
    asr_model: str = "auto"
    denoise: str = "none"
    allow_hotwords_glossaries: bool = True
    supress_numeral_tokens: bool = False
    diarize_speakers: bool = False
    priority: str = "normal"
    min_alignment_score: float = MIN_ALIGNMENT_SCORE_DEFAULT
    max_alignment_cer: float = MAX_ALIGNMENT_CER_DEFAULT
    segment_confirmation_silence_threshold: float = (
        SEGMENT_CONFIRMATION_SILENCE_THRESHOLD_DEFAULT
    )
    only_confirm_by_silence: bool = False
    batched_inference: bool = False
    force_detect_language: bool = False
    calculate_voice_loudness: bool = False
    sentence_splitter: Splitter = Field(default_factory=Splitter)
    verification: Verification = Field(default_factory=Verification)
    advanced: TranscriptionAdvanced = Field(default_factory=TranscriptionAdvanced)


class TimbreDetection(BaseModel):
    enabled: bool = False
    high_timbre_voices: list[str] = ["default_high"]
    low_timbre_voices: list[str] = ["default_low"]


class TTSAdvanced(BaseModel):
    f0_variance_factor: float = F0_VARIANCE_FACTOR_DEFAULT
    energy_variance_factor: float = ENERGY_VARIANCE_FACTOR_DEFAULT
    with_custom_stress: bool = True


class SpeechGen(BaseModel):
    tts_model: str = "auto"
    voice_cloning: bool = False
    voice_cloning_mode: str = "static_10"
    denoise_voice_samples: bool = True
    voice_id: str = "default_low"
    voice_timbre_detection: TimbreDetection = Field(default_factory=TimbreDetection)
    speech_tempo_auto: bool = True
    speech_tempo_timings_factor: int = 0
    speech_tempo_adjustment_factor: float = SPEECH_TEMPO_ADJUSTMENT_FACTOR_DEFAULT
    advanced: TTSAdvanced = Field(default_factory=TTSAdvanced)


class Translation(BaseModel):
    allowed_source_languages: list[str] = []
    translation_model: str = "auto"
    allow_translation_glossaries: bool = True
    style: str | None = None
    translate_partial_transcriptions: bool = False
    speech_generation: SpeechGen = Field(default_factory=SpeechGen)


class QueueConfig(BaseModel):
    desired_queue_level_ms: int = DESIRED_QUEUE_LEVEL_MS_DEFAULT
    max_queue_level_ms: int = MAX_QUEUE_LEVEL_MS_DEFAULT


class QueueConfigs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    global_: QueueConfig = Field(alias="global", default_factory=QueueConfig)


class SourceLang(BaseModel):
    lang: LanguageField
    transcription: Transcription = Field(default_factory=Transcription)

    _in_pcm: T_IN_PCM = PrivateAttr(default=None)
    _on_transcription: T_ON_TRANSCRIPTION | None = PrivateAttr(default=None)

    def __init__(
        self,
        lang: LanguageField,
        in_pcm: T_IN_PCM,
        /,
        on_transcription: T_ON_TRANSCRIPTION | None = None,
        **kwargs,
    ):
        super().__init__(lang=lang, **kwargs)
        self._in_pcm = in_pcm
        self._on_transcription = on_transcription

    def merge_transcription(self, other: Transcription | None):
        if other:
            self.transcription = self.transcription.model_copy(
                update=other.model_dump(exclude_unset=True)
            )


class TargetLang(BaseModel):
    lang: LanguageField
    translation: Translation = Field(default_factory=Translation)

    # TODO: get sync and async callback and run in loop/thread automatically
    _out_pcm: T_OUT_PCM | None = PrivateAttr(default=None)
    _on_transcription: T_ON_TRANSCRIPTION | None = PrivateAttr(
        default=None
    )  # TODO: DO IT!

    def __init__(
        self,
        lang: LanguageField,
        /,
        out_pcm: T_OUT_PCM = None,
        on_transcription: T_ON_TRANSCRIPTION = None,
        **kwargs,
    ):
        super().__init__(lang=lang, **kwargs)
        if not any([out_pcm, on_transcription]):
            raise ConfigurationError(
                f"Use translated audio or transcription for lang: {self.lang}"
            )
        self._out_pcm = out_pcm
        self._on_transcription = on_transcription

    def merge_translation(self, other: Translation | None):
        if other:
            self.translation = self.translation.model_copy(
                update=other.model_dump(exclude_unset=True)
            )


class Config(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source: SourceLang
    targets: list[TargetLang]  # TODO: SIMULTANEOUS TRANSLATION!!!

    input_stream: InputStream = Field(default_factory=InputStream)
    output_stream: OutputStream = Field(default_factory=OutputStream)
    preprocessing: Preprocessing = Field(default_factory=Preprocessing)
    translation_queue_configs: QueueConfigs = Field(default_factory=QueueConfigs)
    allowed_message_types: list[str] = [mt.value for mt in Message.ALLOWED_TYPES]

    log_file: Path | str | None = Field(default=None, exclude=True)
    debug: bool = Field(default=DEBUG, exclude=True)

    def __init__(
        self, source: SourceLang, targets: list[TargetLang] | TargetLang, **kwargs
    ):
        if isinstance(targets, TargetLang):
            targets = [targets]
        super().__init__(source=source, targets=targets, **kwargs)

    def model_post_init(self, context: Any, /) -> None:
        if isinstance(self.targets, TargetLang):
            self.targets = [self.targets]
        super().model_post_init(context)

    @model_validator(mode="before")
    @classmethod
    def reconstruct_from_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Extract pipeline if exists
        if "pipeline" in data:
            pipeline = data.pop("pipeline")
            data.update(pipeline)

        # Reconstruct src if not present
        if "src" not in data and "transcription" in data:
            trans_data = data.pop("transcription")
            source_lang = trans_data.pop("source_language", None)
            if source_lang:
                data["src"] = {"lang": source_lang, "transcription": trans_data}

        # Reconstruct targets if not present
        if "targets" not in data and "translations" in data:
            translations = data.pop("translations")
            targets = []
            for trans in translations:
                target_lang = trans.pop("target_language", None)
                if target_lang:
                    targets.append({"lang": target_lang, "translation": trans})
            data["targets"] = targets

        return data

    def model_dump(self, by_alias=True, exclude_none=False, **kwargs) -> dict[str, Any]:
        # Get base dump
        data = super().model_dump(
            by_alias=by_alias, exclude_none=exclude_none, **kwargs
        )

        # Extract source and targets
        source = data.pop("source")
        targets = data.pop("targets")

        # Build transcription with source_language
        transcription = source["transcription"].copy()
        transcription["source_language"] = source["lang"]

        # Build translations with target_language
        translations = []
        for target in targets:
            translation = target["translation"].copy()
            translation["target_language"] = target["lang"]
            translations.append(translation)

        # Build pipeline structure
        pipeline = {
            "preprocessing": data.pop("preprocessing"),
            "transcription": transcription,
            "translations": translations,
            "translation_queue_configs": data.pop("translation_queue_configs"),
            "allowed_message_types": data.pop("allowed_message_types"),
        }

        # Final structure
        result = {
            "input_stream": data.pop("input_stream"),
            "output_stream": data.pop("output_stream"),
            "pipeline": pipeline,
        }

        # Add any remaining fields
        result.update(data)

        return result

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def to_json(self, indent=2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, data: str | dict) -> Config:
        if isinstance(data, str):
            data = json.loads(data)
        return cls.model_validate(data)

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        return cls.from_json(data)
