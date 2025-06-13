# Palabra AI Python SDK

[![Tests](https://github.com/PalabraAI/palabra-ai-python/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/PalabraAI/palabra-ai-python/actions/workflows/test.yml)
[![Release](https://github.com/PalabraAI/palabra-ai-python/actions/workflows/release.yml/badge.svg)](https://github.com/PalabraAI/palabra-ai-python/actions/workflows/release.yml)
[![Python Versions](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/PalabraAI/palabra-ai-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![codecov](https://codecov.io/gh/PalabraAI/palabra-ai-python/branch/main/graph/badge.svg?token=HRQAJ5VFY7)](https://codecov.io/gh/PalabraAI/palabra-ai-python)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/PalabraAI/palabra-ai-python/pkgs/container/palabra-ai-python)
[![PyPI version](https://badge.fury.io/py/palabra-ai.svg)](https://badge.fury.io/py/palabra-ai)
<!-- Uncomment when will available:
[![Downloads](https://pepy.tech/badge/palabra-ai)](https://pepy.tech/projects/palabra-ai)
-->

<!-- Uncomment after setting up Codecov:
[![codecov](https://codecov.io/gh/PalabraAI/palabra-ai-python/branch/main/graph/badge.svg?token=YOUR_TOKEN)](https://codecov.io/gh/PalabraAI/palabra-ai-python)
-->

Python SDK for Palabra AI's real-time speech-to-speech translation API. Break down language barriers and enable seamless communication across 25+ languages.

## Overview

The Palabra AI SDK enables you to integrate real-time speech translation into your Python applications. Whether you're building a new application, enhancing an existing product, or streamlining business processes, this SDK gives you the tools to:

- **Real-Time Speech-to-Speech Translation**: Instantly translate live speech, making conversations feel smooth and natural
- **Voice Cloning & Management**: Preserve the original speaker's voice and emotional nuances in translated speech
- **Text-to-Speech Conversion**: Convert written text into natural-sounding speech in multiple languages
- **Audio & Video Dubbing**: Automate content dubbing to reach global audiences

## Installation

### From PyPI (Coming Soon)
```bash
pip install palabra-ai
```

## Quick Start

### Real-time microphone translation

```python
from palabra_ai import PalabraAI, Config, SourceLang, TargetLang, DeviceManager, EN, ES

# Initialize and select audio devices
palabra = PalabraAI()
devman = DeviceManager()
mic, speaker = devman.select_devices_interactive()

# Configure real-time translation
config = Config(
    source=SourceLang(EN, mic),
    targets=[TargetLang(ES, speaker)]
)

# Start translating
palabra.run(config)
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
reader = FileReader("./input.mp3")
writer = FileWriter("./output_spanish.wav")
cfg = Config(SourceLang(EN, reader), [TargetLang(ES, writer)])
palabra.run(cfg)
```

### Multiple target languages

```python
from palabra_ai import PalabraAI, Config, SourceLang, TargetLang, FileReader, FileWriter, EN, ES, FR, DE

config = Config(
    source=SourceLang(EN, FileReader("presentation.mp3")),
    targets=[
        TargetLang(ES, FileWriter("spanish.wav")),
        TargetLang(FR, FileWriter("french.wav")),
        TargetLang(DE, FileWriter("german.wav"))
    ]
)

palabra = PalabraAI()
palabra.run(config)
```

### Integration with FFmpeg (streaming)

```python
import subprocess
import io
from palabra_ai import (PalabraAI, Config, SourceLang, TargetLang,
                        BufferReader, BufferWriter, PipeWrapper, AR, EN)

# Launch FFmpeg to convert input to PCM16 mono 48kHz
ffmpeg_cmd = [
    'ffmpeg',
    '-i', 'input.mp3',
    '-f', 's16le',      # 16-bit PCM
    '-acodec', 'pcm_s16le',
    '-ar', '48000',     # 48kHz
    '-ac', '1',         # mono
    '-'                 # output to stdout
]

# Start FFmpeg process
ffmpeg_process = subprocess.Popen(
    ffmpeg_cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL
)

# Wrap pipe to make it seekable
pipe_buffer = PipeWrapper(ffmpeg_process.stdout)
output_buffer = io.BytesIO()

# Run Palabra AI translation
palabra = PalabraAI()
reader = BufferReader(pipe_buffer)
writer = BufferWriter(output_buffer)
cfg = Config(SourceLang(AR, reader), [TargetLang(EN, writer)])
palabra.run(cfg)

# Save translated audio
with open("translated.wav", "wb") as f:
    f.write(output_buffer.getbuffer())
```

### Using default audio devices

```python
from palabra_ai import PalabraAI, Config, SourceLang, TargetLang, DeviceManager, EN, ES

devman = DeviceManager()
reader, writer = devman.get_default_readers_writers()

if reader and writer:
    config = Config(
        source=SourceLang(EN, reader),
        targets=[TargetLang(ES, writer)]
    )
    palabra = PalabraAI()
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
- **PipeWrapper**: Work with pipes (e.g., FFmpeg stdout)

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
pipe = PipeWrapper(ffmpeg_process.stdout)
config = Config(
    source=SourceLang(EN, BufferReader(pipe)),
    targets=[TargetLang(ES, speaker)]
)

# File to multiple speakers (if you have multiple audio devices)
speaker1 = devman.get_speaker_by_name("Speaker 1")
speaker2 = devman.get_speaker_by_name("Speaker 2")

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
# Interactive selection
mic, speaker = devman.select_devices_interactive()

# Get devices by name
mic = devman.get_mic_by_name("Blue Yeti")
speaker = devman.get_speaker_by_name("MacBook Pro Speakers")

# List all devices
input_devices = devman.get_input_devices()
output_devices = devman.get_output_devices()
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
