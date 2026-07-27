import audiobook_maker.audio as audio
from audiobook_maker.common import Settings


def test_voice_identifier_uses_exact_display_name(monkeypatch):
    class Synthesizer:
        @staticmethod
        def availableVoices():
            return ["voice-one", "voice-two"]

        @staticmethod
        def attributesForVoice_(identifier):
            return {
                "VoiceName": {
                    "voice-one": "Daniel",
                    "voice-two": "Daniel (English (UK))",
                }[identifier]
            }

    monkeypatch.setattr(audio, "NSSpeechSynthesizer", Synthesizer)
    audio._speech_voice_identifier.cache_clear()

    assert audio._speech_voice_identifier("Daniel (English (UK))") == "voice-two"

    audio._speech_voice_identifier.cache_clear()


def test_speech_audio_falls_back_to_say_without_pyobjc(tmp_path, monkeypatch):
    text_file = tmp_path / "chapter.txt"
    text_file.write_text("Example chapter.", encoding="utf-8")
    aiff_file = tmp_path / "chapter.aiff"
    commands = []

    monkeypatch.setattr(audio, "NSSpeechSynthesizer", None)
    monkeypatch.setattr(
        audio,
        "run_command",
        lambda command, description: commands.append((command, description)),
    )
    audio._speech_voice_identifier.cache_clear()

    audio._create_speech_audio(
        text_file,
        aiff_file,
        Settings(voice="Daniel", rate=300),
    )

    assert commands == [
        (
            [
                "say",
                "-v",
                "Daniel",
                "-r",
                "300",
                "-o",
                str(aiff_file),
                "-f",
                str(text_file),
            ],
            "Creating speech audio: chapter.aiff",
        )
    ]

    audio._speech_voice_identifier.cache_clear()
