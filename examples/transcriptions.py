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

if __name__ == '__main__':
    palabra = PalabraAI()
    cfg = Config(
        source=SourceLang(
            EN,
            FileReader("speech/en.mp3"),
            print_translation
        ),
        targets=[
            TargetLang(
                ES,
                # you can use only transcription without audio writer if you want
                # FileWriter("./test_output.wav"),
                on_transcription=print_translation_async
            )
        ],
        silent=True,  # Set to True to disable verbose logging to console
    )
    palabra.run(cfg)
