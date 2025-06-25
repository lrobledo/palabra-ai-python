# nanopalabra 🎤

A minimal (~300 lines) Python client for [Palabra AI](https://palabra.ai) real-time speech translation. Perfect for quick prototyping and understanding the core API.

## What is this?

This is a lightweight example demonstrating Palabra AI's real-time translation capabilities without the overhead of a full SDK. It captures audio from your microphone, translates it to your target language, and plays back the translation through your speakers - all in under 300 lines of code.

## Features

- 🎤 **Real-time microphone capture** - Speak in your native language
- 🌐 **Instant translation** - Powered by Palabra AI's WebRTC API
- 🔊 **Audio playback** - Hear translations through your speakers
- 📝 **Live transcription** - See what's being said and translated
- 🚀 **Minimal dependencies** - Just 5 packages needed
- 💻 **Single file** - Everything in one `nanopalabra.py`

## Quick Start

### 1. Install dependencies

```bash
# Using uv (recommended)
uv venv && . .venv/bin/activate && uv sync

# Or using pip
pip install httpx livekit numpy sounddevice websockets
```

### 2. Set your API credentials

Get your credentials from [Palabra AI API](https://palabra.ai/api/keys):

```bash
export PALABRA_CLIENT_ID=your_client_id
export PALABRA_CLIENT_SECRET=your_client_secret
```

### 3. Run the example

```bash
python nanopalabra.py
```

That's it! Start speaking and hear your words translated in real-time.

## How it works

The client follows the [Palabra AI Quick Start](https://docs.palabra.ai/docs/quick-start) flow:

1. **Creates a session** with your API credentials
2. **Connects to a WebRTC room** using LiveKit
3. **Publishes your microphone audio** to the room
4. **Receives translated audio** and plays it back
5. **Shows live transcriptions** in the console

## Configuration

By default, the example translates from English to Spanish. To change languages, modify the `MINIMAL_SETTINGS` in the code:

```python
"transcription": {"source_language": "en"},  # Change source language
"translations": [
    {
        "target_language": "es",  # Change target language
        # Add more target languages here
    }
]
```

## Why use this?

- **Learning** - Understand Palabra AI's WebRTC API without SDK abstractions
- **Prototyping** - Quickly test translation in your projects
- **Customization** - Easy to modify and extend for your needs
- **Debugging** - See exactly what's happening under the hood

## Need the full SDK?

For production use cases, check out the [official Palabra AI Python SDK](https://github.com/PalabraAI/palabra-ai-python) with:

- Multiple I/O adapters (files, buffers, devices)
- Comprehensive error handling
- Async/await patterns
- Type hints and documentation
- Production-ready architecture

## Support

- 📚 [Documentation](https://docs.palabra.ai)
- 🐛 [Issues](https://github.com/PalabraAI/palabra-ai-python/issues)
- 📧 Email: info@palabra.ai

---

Made with ❤️ by [Palabra AI](https://palabra.ai) - Breaking down language barriers with AI
