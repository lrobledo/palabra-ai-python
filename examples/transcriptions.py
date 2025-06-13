from palabra_ai import (
    PalabraAI,
    Config,
    SourceLang,
    TargetLang,
    FileReader,
    FileWriter,
    EN,
    ES,
)
from palabra_ai.base.message import TranscriptionMessage


def print_translation(msg: TranscriptionMessage):
    print(str(msg))


if __name__ == '__main__':
    palabra = PalabraAI()
    cfg = Config(
        source=SourceLang(
            EN,
            FileReader("speech/en.mp3"),
            on_transcription=print_translation
        ),
        targets=[
            TargetLang(
                ES,
                FileWriter("./test_output.wav"),
                on_transcription=print_translation
            )
        ]
    )
    palabra.run(cfg)
