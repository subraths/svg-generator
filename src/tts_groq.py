from groq import Groq

from src.config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

with open(
    "reports/mitocondrial_structure_and_function_20260605_142010_explanation.json", "r"
) as f:
    content = f.read()

speech_file_path = "orpheus-english.wav"
model = "canopylabs/orpheus-v1-english"
voice = "troy"
text = "Hi there how are you doing today"
response_format = "wav"

response = client.audio.speech.create(
    model=model, voice=voice, input=text, response_format=response_format
)

response.write_to_file(speech_file_path)
