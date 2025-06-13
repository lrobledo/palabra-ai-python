import subprocess
import io

from palabra_ai import (PalabraAI, Config, SourceLang, TargetLang,
                        BufferReader, BufferWriter, AR, EN)
from palabra_ai import PipeWrapper

if __name__ == "__main__":
    # Launch FFmpeg to convert ar.mp3 to PCM16 mono 48kHz
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', 'speech/ar.mp3',
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
        stderr=subprocess.DEVNULL  # hide FFmpeg logs
    )

    # Wrap pipe to make it seekable
    pipe_buffer = PipeWrapper(ffmpeg_process.stdout)
    es_buffer = io.BytesIO()

    # Run Palabra AI translation
    palabra = PalabraAI()
    reader = BufferReader(pipe_buffer)
    writer = BufferWriter(es_buffer)
    cfg = Config(SourceLang(AR, reader), [TargetLang(EN, writer)])
    palabra.run(cfg)

    # Wait for FFmpeg to finish
    ffmpeg_process.wait()

    print(f"Translated audio written to buffer with size: {es_buffer.getbuffer().nbytes} bytes")
    with open("./ar2en_out.wav", "wb") as f:
        f.write(es_buffer.getbuffer())