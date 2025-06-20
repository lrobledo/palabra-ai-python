# Palabra AI Python SDK

[![Tests](https://github.com/PalabraAI/palabra-ai-python/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/PalabraAI/palabra-ai-python/actions/workflows/test.yml)
[![Release](https://github.com/PalabraAI/palabra-ai-python/actions/workflows/release.yml/badge.svg)](https://github.com/PalabraAI/palabra-ai-python/actions/workflows/release.yml)
[![Python Versions](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/PalabraAI/palabra-ai-python)
[![PyPI version](https://img.shields.io/pypi/v/palabra-ai.svg?color=blue)](https://pypi.org/project/palabra-ai/)
[![Downloads](https://pepy.tech/badge/palabra-ai)](https://pepy.tech/projects/palabra-ai)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/PalabraAI/palabra-ai-python/pkgs/container/palabra-ai-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[//]: # ([![codecov]&#40;https://codecov.io/gh/PalabraAI/palabra-ai-python/graph/badge.svg?token=HRQAJ5VFY7&#41;]&#40;https://codecov.io/gh/PalabraAI/palabra-ai-python&#41;)

Python SDK for Palabra AI's real-time speech-to-speech translation API. Break down language barriers and enable seamless communication across 25+ languages.

## Overview

The Palabra AI Python SDK provides a high-level API for integrating real-time speech-to-speech translation into your Python applications. While the Palabra.ai platform offers comprehensive features like voice cloning, text-to-speech, and audio/video dubbing, this SDK specifically focuses on making real-time translation simple and accessible. Using WebRTC and WebSockets under the hood, the SDK abstracts away all complexity — you just configure your source and target languages with input/output adapters, and the SDK handles the entire pipeline: session management, connection to Palabra translation rooms, audio streaming, and language processing. Your speech is automatically transcribed, translated, and synthesized into the target language in real-time, delivering an audio stream ready for immediate playback with just a few lines of code.


## Installation

### From PyPI (Coming Soon)
```bash
pip install palabra-ai
```

## Quick Start

### Real-time microphone translation

```python
from palabra_ai import (PalabraAI, Config, SourceLang, TargetLang,
                        EN, ES, DeviceManager)

palabra = PalabraAI()
dm = DeviceManager()
mic, speaker = dm.select_devices_interactive()
cfg = Config(SourceLang(EN, mic), [TargetLang(ES, speaker)])
palabra.run(cfg)
```

Set your API credentials as environment variables:
```bash
export PALABRA_API_KEY=your_api_key
export PALABRA_API_SECRET=your_api_secret
```

## Examples

### File-to-file translation

```python
from palabra_ai import (PalabraAI, Config, SourceLang, TargetLang,
                        FileReader, FileWriter, EN, ES)

palabra = PalabraAI()
reader = FileReader("./speech/es.mp3")
writer = FileWriter("./es2en_out.wav")
cfg = Config(SourceLang(ES, reader), [TargetLang(EN, writer)])
palabra.run(cfg)
```

### Multiple target languages

```python
from palabra_ai import (PalabraAI, Config, SourceLang, TargetLang,
                        FileReader, FileWriter, EN, ES, FR, DE)

palabra = PalabraAI()
config = Config(
    source=SourceLang(EN, FileReader("presentation.mp3")),
    targets=[
        TargetLang(ES, FileWriter("spanish.wav")),
        TargetLang(FR, FileWriter("french.wav")),
        TargetLang(DE, FileWriter("german.wav"))
    ]
)
palabra.run(config)
```

### Working with transcriptions

You can optionally get transcriptions of the source and translated speech. Output can be configured to provide audio only, transcriptions only, or both:

```python
from palabra_ai import (
    PalabraAI,
    Config,
    SourceLang,
    TargetLang,
    FileReader,
    EN,
    ES,
)
from palabra_ai.base.message import TranscriptionMessage


async def print_translation_async(msg: TranscriptionMessage):
    print(repr(msg))

def print_translation(msg: TranscriptionMessage):
    print(str(msg))

palabra = PalabraAI()
cfg = Config(
    source=SourceLang(
        EN,
        FileReader("speech/en.mp3"),
        print_translation  # Callback for source transcriptions
    ),
    targets=[
        TargetLang(
            ES,
            # You can use only transcription without audio writer if you want
            # FileWriter("./test_output.wav"),  # Optional: audio output
            on_transcription=print_translation_async  # Callback for translated transcriptions
        )
    ],
    silent=True,  # Set to True to disable verbose logging to console
)
palabra.run(cfg)
```

#### Transcription output options:

1. **Audio only** (default):
```python
TargetLang(ES, FileWriter("output.wav"))
```

2. **Transcription only**:
```python
TargetLang(ES, on_transcription=your_callback_function)
```

3. **Both audio and transcription**:
```python
TargetLang(ES, FileWriter("output.wav"), on_transcription=your_callback_function)
```

The transcription callbacks receive `TranscriptionMessage` objects containing the transcribed text and metadata. Callbacks can be either synchronous or asynchronous functions.

### Integration with FFmpeg (streaming)

```python
import io
from palabra_ai import (PalabraAI, Config, SourceLang, TargetLang,
                        BufferReader, BufferWriter, AR, EN, RunAsPipe)

ffmpeg_cmd = [
    'ffmpeg',
    '-i', 'speech/ar.mp3',
    '-f', 's16le',      # 16-bit PCM
    '-acodec', 'pcm_s16le',
    '-ar', '48000',     # 48kHz
    '-ac', '1',         # mono
    '-'                 # output to stdout
]

pipe_buffer = RunAsPipe(ffmpeg_cmd)
es_buffer = io.BytesIO()

palabra = PalabraAI()
reader = BufferReader(pipe_buffer)
writer = BufferWriter(es_buffer)
cfg = Config(SourceLang(AR, reader), [TargetLang(EN, writer)])
palabra.run(cfg)

print(f"Translated audio written to buffer with size: {es_buffer.getbuffer().nbytes} bytes")
with open("./ar2en_out.wav", "wb") as f:
    f.write(es_buffer.getbuffer())
```

### Using buffers

```python
import io
from palabra_ai import (PalabraAI, Config, SourceLang, TargetLang,
                        BufferReader, BufferWriter, AR, EN)
from palabra_ai.internal.audio import convert_any_to_pcm16

en_buffer, es_buffer = io.BytesIO(), io.BytesIO()
with open("speech/ar.mp3", "rb") as f:
    en_buffer.write(convert_any_to_pcm16(f.read()))
palabra = PalabraAI()
reader = BufferReader(en_buffer)
writer = BufferWriter(es_buffer)
cfg = Config(SourceLang(AR, reader), [TargetLang(EN, writer)])
palabra.run(cfg)
print(f"Translated audio written to buffer with size: {es_buffer.getbuffer().nbytes} bytes")
with open("./ar2en_out.wav", "wb") as f:
    f.write(es_buffer.getbuffer())
```

### Using default audio devices

```python
from palabra_ai import PalabraAI, Config, SourceLang, TargetLang, DeviceManager, EN, ES

dm = DeviceManager()
reader, writer = dm.get_default_readers_writers()

if reader and writer:
    palabra = PalabraAI()
    config = Config(
        source=SourceLang(EN, reader),
        targets=[TargetLang(ES, writer)]
    )
    palabra.run(config)
```

### Async API

```python
import asyncio
from palabra_ai import PalabraAI, Config, SourceLang, TargetLang, FileReader, FileWriter, EN, ES

async def translate():
    palabra = PalabraAI()
    config = Config(
        source=SourceLang(EN, FileReader("input.mp3")),
        targets=[TargetLang(ES, FileWriter("output.wav"))]
    )
    await palabra.run(config)

asyncio.run(translate())
```

## I/O Adapters & Mixing

The SDK provides flexible I/O adapters that can be mixed in any combination:

### Available Adapters

- **FileReader/FileWriter**: Read from and write to audio files
- **DeviceReader/DeviceWriter**: Use microphones and speakers
- **BufferReader/BufferWriter**: Work with in-memory buffers
- **RunAsPipe**: Run command and represent as pipe (e.g., FFmpeg stdout)

### Mixing Examples

You can combine any input adapter with any output adapter:

```python
# Microphone to file - record translations
config = Config(
    source=SourceLang(EN, mic),
    targets=[TargetLang(ES, FileWriter("recording_es.wav"))]
)

# File to speaker - play translations
config = Config(
    source=SourceLang(EN, FileReader("presentation.mp3")),
    targets=[TargetLang(ES, speaker)]
)

# Microphone to multiple outputs - real-time translation with recording
config = Config(
    source=SourceLang(EN, mic),
    targets=[
        TargetLang(ES, speaker),  # Play Spanish through speaker
        TargetLang(ES, FileWriter("spanish.wav")),  # Save Spanish to file
        TargetLang(FR, FileWriter("french.wav"))    # Save French to file
    ]
)

# Buffer to buffer - for integration with other systems
input_buffer = io.BytesIO(audio_data)
output_buffer = io.BytesIO()

config = Config(
    source=SourceLang(EN, BufferReader(input_buffer)),
    targets=[TargetLang(ES, BufferWriter(output_buffer))]
)

# FFmpeg pipe to speaker - stream processing
pipe = RunAsPipe(ffmpeg_process.stdout)
config = Config(
    source=SourceLang(EN, BufferReader(pipe)),
    targets=[TargetLang(ES, speaker)]
)

# File to multiple speakers (if you have multiple audio devices)
dm = DeviceManager()
speaker1 = dm.get_speaker_by_name("Speaker 1")
speaker2 = dm.get_speaker_by_name("Speaker 2")

config = Config(
    source=SourceLang(EN, FileReader("input.mp3")),
    targets=[
        TargetLang(ES, speaker1),  # Spanish on speaker 1
        TargetLang(FR, speaker2)   # French on speaker 2
    ]
)
```

## Features

### Real-time Translation
Translate audio streams in real-time with minimal latency. Perfect for live conversations, conferences, and meetings.

### Voice Cloning
Preserve the original speaker's voice characteristics in translations by enabling voice cloning in the configuration.

### Device Management
Easy device selection with interactive prompts or programmatic access:

```python
dm = DeviceManager()

# Interactive selection
mic, speaker = dm.select_devices_interactive()

# Get devices by name
mic = dm.get_mic_by_name("Blue Yeti")
speaker = dm.get_speaker_by_name("MacBook Pro Speakers")

# List all devices
input_devices = dm.get_input_devices()
output_devices = dm.get_output_devices()
```

## Supported Languages

### Speech Recognition Languages
🇸🇦 Arabic (AR), 🇨🇳 Chinese (ZH), 🇨🇿 Czech (CS), 🇩🇰 Danish (DA), 🇳🇱 Dutch (NL), 🇬🇧 English (EN), 🇫🇮 Finnish (FI), 🇫🇷 French (FR), 🇩🇪 German (DE), 🇬🇷 Greek (EL), 🇮🇱 Hebrew (HE), 🇭🇺 Hungarian (HU), 🇮🇹 Italian (IT), 🇯🇵 Japanese (JA), 🇰🇷 Korean (KO), 🇵🇱 Polish (PL), 🇵🇹 Portuguese (PT), 🇷🇺 Russian (RU), 🇪🇸 Spanish (ES), 🇹🇷 Turkish (TR), 🇺🇦 Ukrainian (UK)

### Translation Languages
🇸🇦 Arabic (AR), 🇧🇬 Bulgarian (BG), 🇨🇳 Chinese Mandarin (ZH), 🇨🇿 Czech (CS), 🇩🇰 Danish (DA), 🇳🇱 Dutch (NL), 🇬🇧 English UK (EN_GB), 🇺🇸 English US (EN_US), 🇫🇮 Finnish (FI), 🇫🇷 French (FR), 🇩🇪 German (DE), 🇬🇷 Greek (EL), 🇮🇱 Hebrew (HE), 🇭🇺 Hungarian (HU), 🇮🇩 Indonesian (ID), 🇮🇹 Italian (IT), 🇯🇵 Japanese (JA), 🇰🇷 Korean (KO), 🇵🇱 Polish (PL), 🇵🇹 Portuguese (PT), 🇧🇷 Portuguese Brazilian (PT_BR), 🇷🇴 Romanian (RO), 🇷🇺 Russian (RU), 🇸🇰 Slovak (SK), 🇪🇸 Spanish (ES), 🇲🇽 Spanish Mexican (ES_MX), 🇸🇪 Swedish (SV), 🇹🇷 Turkish (TR), 🇺🇦 Ukrainian (UK), 🇻🇳 Vietnamese (VN)

### Available Language Constants

```python
from palabra_ai import (
    # English variants - 1.5+ billion speakers (including L2)
    EN, EN_AU, EN_CA, EN_GB, EN_US,

    # Chinese - 1.3+ billion speakers
    ZH,

    # Hindi - 600+ million speakers
    HI,

    # Spanish variants - 500+ million speakers
    ES, ES_MX,

    # Arabic variants - 400+ million speakers
    AR, AR_AE, AR_SA,

    # French variants - 280+ million speakers
    FR, FR_CA,

    # Portuguese variants - 260+ million speakers
    PT, PT_BR,

    # Russian - 260+ million speakers
    RU,

    # Japanese & Korean - 200+ million speakers combined
    JA, KO,

    # Southeast Asian languages - 400+ million speakers
    ID, VN, TA, MS, FIL,

    # Germanic languages - 150+ million speakers
    DE, NL, SV, NO, DA,

    # Other European languages - 300+ million speakers
    TR, IT, PL, UK, RO, EL, HU, CS, BG, SK, FI, HR,

    # Other languages - 40+ million speakers
    AZ, HE
)
```

## Development Status

### Current Status
- ✅ Core SDK functionality
- ✅ GitHub Actions CI/CD
- ✅ Docker packaging
- ✅ Python 3.11, 3.12, 3.13 support
- ✅ PyPI publication (coming soon)
- ⏳ Code coverage reporting (setup required)
- ⏳ Documentation site (coming soon)

### Current Dev Roadmap
- ⏳ TODO: global timeout support for long-running tasks
- ⏳ TODO: support for multiple source languages in a single run
- ⏳ TODO: fine cancelling on cancel_all_tasks()
- ⏳ TODO: error handling improvements

### Build Status
- **Tests**: Running on Python 3.11, 3.12, 3.13
- **Release**: Automated releases with Docker images
- **Coverage**: Tests implemented, reporting setup needed

## Requirements

- Python 3.11+
- Palabra AI API credentials (get them at [palabra.ai](https://palabra.ai))

## Support

- Documentation: [https://docs.palabra.ai](https://docs.palabra.ai)
- API Reference: [https://docs.palabra.ai/api](https://docs.palabra.ai/api)
- Issues: [GitHub Issues](https://github.com/PalabraAI/palabra-ai-python/issues)
- Email: info@palabra.ai

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

© Palabra.ai, 2025 | Breaking down language barriers with AI
