## 004 — Whisper hallucinates transcriptions from silence

**Date discovered:** 2026-03-24  
**Severity:** Functional  
**Components:** Speaches, Whisper Large V3, microphone streaming pipeline

**Symptoms:**

While building a live transcription pipeline that streams microphone audio in chunks to the Whisper API, the model returned confident, grammatically correct transcriptions even when no one was speaking. Silence produced outputs like "Thank you for watching", "Subscribe to our channel", and fragments of what appeared to be YouTube video outros. The transcriptions were fluent enough that without a human in the loop, a downstream system would have no reason to discard them.

**Root cause:**

Whisper was trained on large volumes of web audio, including YouTube videos with recurring phrases in intros, outros, and filler segments. When given near-silent audio, the model doesn't return an empty string — it pattern-matches against its training data and generates the most probable text for low-signal input. There is no internal confidence threshold or silence detection; the model always produces output. It treats silence as a prediction problem, not an absence-of-input signal.

This is a general property of autoregressive sequence models: they are trained to always produce the next token. They have no mechanism to say "there is nothing here." The absence of signal is just another input distribution that gets mapped to the most statistically likely output.

**Fix applied:**

Added client-side voice activity detection (VAD) before sending audio to the API. Each recorded chunk is checked for energy level (root mean square amplitude), and only chunks above a configurable threshold are sent for transcription:

```python
def get_rms(data):
    count = len(data) // 2
    shorts = struct.unpack(f"{count}h", data)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)

# Only transcribe if audio energy exceeds threshold
if get_rms(raw_audio) < SILENCE_THRESHOLD:
    return None
```

The threshold requires tuning per microphone and environment. Too low and background noise triggers false transcriptions; too high and quiet speech gets dropped.

**Considered but deferred:**

- **Server-side VAD in Speaches** — Speaches supports a WebRTC endpoint with built-in voice activity detection, but it requires a browser-based client. Not usable from a Python script or CLI tool.
- **Post-hoc filtering with an LLM** — Run each transcription through a classifier to detect hallucinated filler. Adds latency and cost to every chunk, and the failure mode is subtle (hallucinated text is grammatically valid).
- **Whisper's `no_speech_threshold` parameter** — Some Whisper implementations expose a logprob threshold for silence detection. The Speaches/faster-whisper API didn't surface this, and relying on model-internal confidence for a problem that's trivially solved at the input stage felt backwards.

**Lesson:**

Generative models don't distinguish between "I have input to process" and "I have no input." They always produce output — that's what they're trained to do. Any pipeline that feeds real-world sensor data (microphone, camera, document stream) into a generative model needs an input validation gate that's independent of the model. The model cannot be trusted to report the absence of meaningful input, because from its perspective, there is no such thing. Silence is just another prompt.