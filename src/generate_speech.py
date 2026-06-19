from google import genai
from google.genai import types
import wave

from src.config import GEMINI_API_KEY


# Set up the wave file to save the output:
def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


with open("reports/photosynthesis_20260605_152420_explanation.json", "r") as f:
    content = f.read()


client = genai.Client(api_key=GEMINI_API_KEY)


response = client.models.generate_content(
    model="gemini-3.1-flash-tts-preview",
    contents="Hi how are you today",
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore",
                )
            )
        ),
    ),
)

print(response)
data = response.candidates[0].content.parts[0].inline_data.data

file_name = "out.wav"
wave_file(file_name, data)  # Saves the file to current directory
