from palabra_ai import (PalabraAI, Config, SourceLang, TargetLang,
                        EN, ES, DeviceManager)

if __name__ == "__main__":
    palabra = PalabraAI()
    dm = DeviceManager()
    mic, speaker = dm.select_devices_interactive()
    cfg = Config(SourceLang(EN, mic), [TargetLang(ES, speaker)])
    palabra.run(cfg)
