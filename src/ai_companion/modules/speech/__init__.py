from .speech_to_text import SpeechToText

# TextToSpeech (ElevenLabs) is optional — the ANGC assistant only needs STT
# (Groq Whisper) for voice notes. Guard the import so a slim deploy without
# the elevenlabs package can still import SpeechToText.
try:
    from .text_to_speech import TextToSpeech

    __all__ = ["SpeechToText", "TextToSpeech"]
except ModuleNotFoundError:
    __all__ = ["SpeechToText"]
