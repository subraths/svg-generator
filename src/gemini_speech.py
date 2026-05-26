import base64
import io
import json
import wave
from pathlib import Path

from src.config import GEMINI_API_KEY, GEMINI_TTS_MODEL, GEMINI_TTS_VOICE


def _extract_audio_bytes(response) -> bytes:
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline_data = getattr(part, "inline_data", None)
            data = getattr(inline_data, "data", None)
            if isinstance(data, bytes):
                return data
            if isinstance(data, str):
                return base64.b64decode(data)
    raise ValueError("Gemini TTS response did not contain inline audio data.")


def _wav_duration_seconds(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


def synthesize_segment_with_gemini(segment_text: str) -> tuple[bytes, float]:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_TTS_MODEL,
        contents=segment_text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=GEMINI_TTS_VOICE
                    )
                )
            ),
        ),
    )
    wav_bytes = _extract_audio_bytes(response)
    duration = _wav_duration_seconds(wav_bytes)
    return wav_bytes, duration


def _concat_wav_bytes(chunks: list[bytes]) -> bytes:
    if not chunks:
        return b""

    first = wave.open(io.BytesIO(chunks[0]), "rb")
    params = first.getparams()
    frames = [first.readframes(first.getnframes())]
    first.close()

    for chunk in chunks[1:]:
        with wave.open(io.BytesIO(chunk), "rb") as wf:
            if (
                wf.getnchannels() != params.nchannels
                or wf.getsampwidth() != params.sampwidth
                or wf.getframerate() != params.framerate
            ):
                raise ValueError("Gemini audio segment format mismatch.")
            frames.append(wf.readframes(wf.getnframes()))

    out = io.BytesIO()
    with wave.open(out, "wb") as wf_out:
        wf_out.setnchannels(params.nchannels)
        wf_out.setsampwidth(params.sampwidth)
        wf_out.setframerate(params.framerate)
        for frame_block in frames:
            wf_out.writeframes(frame_block)
    return out.getvalue()


def build_segment_timeline(explanation_plan: dict, segment_durations: list[float]) -> dict:
    segments = explanation_plan.get("segments", [])
    if len(segments) != len(segment_durations):
        raise ValueError("Segment count and duration count must match.")

    t = 0.0
    timed = []
    for segment, duration in zip(segments, segment_durations):
        t0 = round(t, 3)
        t += float(duration)
        t1 = round(t, 3)
        timed.append(
            {
                "seg_id": segment["seg_id"],
                "text": segment["text"],
                "t0": t0,
                "t1": t1,
                "highlights": segment.get("highlights", []),
            }
        )

    return {
        "lesson_title": explanation_plan.get("lesson_title"),
        "learning_goals": explanation_plan.get("learning_goals", []),
        "segments": timed,
    }


def synthesize_explanation_plan(
    explanation_plan: dict, output_dir: str | Path
) -> tuple[str, str, dict]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    segment_wavs = []
    durations = []

    for segment in explanation_plan.get("segments", []):
        wav_bytes, duration = synthesize_segment_with_gemini(segment["text"])
        segment_wavs.append(wav_bytes)
        durations.append(duration)

    full_audio = _concat_wav_bytes(segment_wavs)
    if not full_audio:
        raise ValueError("No audio was generated from explanation segments.")

    audio_path = out_dir / "narration.wav"
    with open(audio_path, "wb") as f:
        f.write(full_audio)

    timeline = build_segment_timeline(explanation_plan, durations)
    timeline_path = out_dir / "timeline.json"
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2)

    return str(audio_path), str(timeline_path), timeline
