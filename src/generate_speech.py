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


content = "The Agentic AI framework for customer support automates the entire resolution pipeline — from query intake and classification, through context retrieval, planning, and specialist agent execution, to validation, auto-resolution or human escalation, and feedback-driven learning. The system uses a multi-agent architecture where specialized agents (FAQ, Action, Technical) run in parallel under an orchestrator, a HITL layer ensures reliability for uncertain or sensitive cases, and a feedback loop continuously improves the model. This results in faster resolution, lower cost, 24/7 availability, and higher customer satisfaction compared to traditional support systems. Key enabling technologies include LangGraph for workflow orchestration, RAG for knowledge retrieval, CRM APIs for tool use, and confidence-based HITL routing."


client = genai.Client(api_key=GEMINI_API_KEY)


response = client.models.generate_content(
    model="gemini-3.1-flash-tts-preview",
    contents=content,
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

data = response.candidates[0].content.parts[0].inline_data.data
print(response)

file_name = "out.wav"
wave_file(file_name, data)  # Saves the file to current directory
