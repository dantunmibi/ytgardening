#!/usr/bin/env python3
"""
.github/scripts/generate_tts.py
Garden Glow Up - Robust Coqui TTS generation with gardening-specific cleaning
Primary model: tts_models/en/vctk/vits (speaker p226 recommended)
"""
import os
import json
import re
import math
from tenacity import retry, stop_after_attempt, wait_exponential
from TTS.api import TTS
from pydub import AudioSegment
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)
FULL_AUDIO_PATH = os.path.join(TMP, "voice.mp3")
AUDIO_METADATA = os.path.join(TMP, "audio_metadata.json")

# Config (can override via env)
PRIMARY_MODEL = os.getenv("GARDEN_VOICE_MODEL", "tts_models/en/vctk/vits")
PRIMARY_SPEAKER = os.getenv("GARDEN_VCTK_SPEAKER", "p226")
ALT_MODELS = ["tts_models/en/jenny/jenny", "tts_models/en/ljspeech/tacotron2-DDC"]

print(f"✅ TTS pipeline init — primary model: {PRIMARY_MODEL} speaker: {PRIMARY_SPEAKER}")

# -------------------------
# Text cleaning (gardening)
# -------------------------
def clean_text_for_tts(text: str) -> str:
    """Enhanced text preprocessing for natural TTS pronunciation (gardening-aware)."""
    if not text:
        return ""

    # Normalize whitespace
    text = text.strip()

    # Protect common abbreviations
    protected_patterns = {
        r'\bDr\.': 'Doctor',
        r'\bMr\.': 'Mister',
        r'\bMrs\.': 'Misses',
        r'\bMs\.': 'Miss',
        r'\bProf\.': 'Professor',
        r'\betc\.': 'etcetera',
        r'\be\.g\.': 'for example',
        r'\bi\.e\.': 'that is',
        r'\bvs\.': 'versus',
    }
    for pat, rep in protected_patterns.items():
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    # Replace ellipses with pause word (optional)
    text = text.replace("...", " pause ")

    # Treat periods as sentence ends only when followed by space + capital letter
    text = re.sub(r'\.(\s+[A-Z])', r' SENTENCE_END\1', text)
    # Remove remaining periods (mid-sentence)
    text = text.replace(".", "")
    # Restore sentence-end markers
    text = text.replace("SENTENCE_END", ".")

    # Special characters common in scripts
    replacements = {
        '%': ' percent',
        '&': ' and ',
        '+': ' plus ',
        '@': ' at ',
        '$': ' dollars ',
        '€': ' euros ',
        '£': ' pounds ',
        '#': ' hashtag ',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    # Gardening-specific measurement and term handling
    gardening_repls = {
        r'(\d+)\s*"\b': r'\1 inches',
        r'(\d+)\s*\'\b': r'\1 feet',
        r'\b(\d+)\s*in\b': r'\1 inches',
        r'\b(\d+)\s*ft\b': r'\1 feet',
        r'\b(\d+)\s*cm\b': r'\1 centimeters',
        r'\b(\d+)\s*mm\b': r'\1 millimeters',
        r'\b(\d+)\s*tbsp\b': r'\1 tablespoons',
        r'\b(\d+)\s*tsp\b': r'\1 teaspoons',
        r'\b(\d+)\s*ml\b': r'\1 milliliters',
        r'\b(\d+)\s*L\b': r'\1 liters',
        r'\b(\d+)\s*oz\b': r'\1 ounces',
        r'\b(\d+)\s*lb?s\b': r'\1 pounds',
        r'\b(\d+)\s*gal\b': r'\1 gallon',
        r'\b(\d+)\s*°C\b': r'\1 degrees Celsius',
        r'\b(\d+)\s*°F\b': r'\1 degrees Fahrenheit',
        r'\bPH\b': 'P H',
        r'\bpH\b': 'P H',
        r'\bNPK\b': 'N P K',
        r'\bEpsom\s+salt\b': 'Epsom salt',
    }
    for pat, rep in gardening_repls.items():
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    # Plant-name pronunciation hints (optional — add more as needed)
    plant_pronunciations = {
        r'\bPothos\b': 'POH-thos',
        r'\bMonstera\b': 'mon-STAIR-uh',
        r'\bPhilodendron\b': 'fil-oh-DEN-dron',
        r'\bSansevieria\b': 'san-suh-VEER-ee-uh',
        r'\bFuchsia\b': 'FYOO-shuh',
    }
    for pat, rep in plant_pronunciations.items():
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    # Acronyms (keep generic replacements, harmless)
    acronym_replacements = {
        r'\bDIY\b': 'D I Y',
        r'\bLED\b': 'L E D',
        r'\bUV\b': 'U V',
    }
    for pat, rep in acronym_replacements.items():
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    # Remove emojis
    emoji_pattern = re.compile("["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\u2600-\u26FF\u2700-\u27BF]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)

    # Collapse multiple whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Ensure final sentence punctuation for natural pause
    if text and text[-1] not in ".!?":
        text = text + "."

    return text

# -------------------------
# Fallback helpers
# -------------------------
def generate_tts_fallback(text: str, out_path: str) -> str:
    """Fallback to gTTS (requires internet). Returns path on success."""
    try:
        logging.info("🔄 Using gTTS fallback...")
        from gtts import gTTS
        t = gTTS(text=text, lang='en', slow=False)
        t.save(out_path)
        logging.info(f"✅ gTTS fallback saved to {out_path}")
        return out_path
    except Exception as e:
        logging.warning(f"⚠️ gTTS fallback failed: {e}")
        return generate_silent_audio_fallback(text, out_path)

def generate_silent_audio_fallback(text: str, out_path: str) -> str:
    """Create silent audio with duration estimated from word count."""
    try:
        words = len(text.split())
        duration_ms = max(15000, min(75000, int((words / 150.0) * 60000)))
        silent = AudioSegment.silent(duration=duration_ms, frame_rate=22050)
        silent.export(out_path, format="mp3")
        logging.info(f"✅ Silent fallback created ({duration_ms/1000:.1f}s) at {out_path}")
        return out_path
    except Exception as e:
        logging.error(f"❌ Silent fallback failed: {e}")
        raise

# -------------------------
# TTS helpers
# -------------------------
def _tts_to_file(tts_obj, text: str, out_path: str, speaker: str = None):
    """
    Robust wrapper around TTS.tts_to_file:
    - Tries with speaker param if provided (multi-speaker models)
    - Falls back to calling without speaker argument
    """
    try:
        if speaker:
            # some models accept 'speaker' — try with it
            tts_obj.tts_to_file(text=text, file_path=out_path, speaker=speaker)
        else:
            tts_obj.tts_to_file(text=text, file_path=out_path)
    except TypeError:
        # If model doesn't accept speaker keyword, try without
        tts_obj.tts_to_file(text=text, file_path=out_path)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def generate_sectional_tts():
    """
    Attempt sectional generation using primary model (VCTK recommended).
    Falls back to alternative local model(s) and ultimately to gTTS.
    Returns list of section paths.
    """
    sections = [("hook", hook)] + [(f"bullet_{i}", b) for i, b in enumerate(bullets)] + [("cta", cta)]
    section_paths = []

    # Try primary model first
    try:
        logging.info(f"🔊 Loading Coqui model: {PRIMARY_MODEL}")
        tts = TTS(model_name=PRIMARY_MODEL, progress_bar=False)
        use_speaker = False
        try:
            available_speakers = getattr(tts, "speakers", None)
            if available_speakers and PRIMARY_SPEAKER in available_speakers:
                use_speaker = True
        except Exception:
            use_speaker = False

        logging.info(f"   -> model loaded. speaker supported: {use_speaker}")

        for name, text in sections:
            if not text.strip():
                continue
            clean = clean_text_for_tts(text)
            out_path = os.path.join(TMP, f"{name}.mp3")
            logging.info(f"🎧 Generating section '{name}' ({len(clean)} chars)...")
            # If section is long, split by sentences to avoid model issues
            # but we can just pass in the clean section (coqui handles moderate lengths)
            _tts_to_file(tts, clean, out_path, speaker=(PRIMARY_SPEAKER if use_speaker else None))

            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                section_paths.append(out_path)
                logging.info(f"   ✅ saved {out_path}")
            else:
                raise Exception(f"Section file missing or too small: {out_path}")

        # Combine sections with short pauses (gardening needs slightly longer pauses for clarity)
        combined = AudioSegment.silent(duration=0)
        for i, path in enumerate(section_paths):
            part = AudioSegment.from_file(path)
            pause_ms = 200 if i < len(section_paths) - 1 else 0
            combined += part + AudioSegment.silent(duration=pause_ms)

        combined.export(FULL_AUDIO_PATH, format="mp3")
        logging.info(f"✅ Combined TTS exported to {FULL_AUDIO_PATH}")
        return section_paths

    except Exception as primary_err:
        logging.warning(f"⚠️ Primary model failed: {primary_err}")

    # Try alternative local models
    for alt in ALT_MODELS:
        try:
            logging.info(f"🔁 Trying alternative model: {alt}")
            tts_alt = TTS(model_name=alt, progress_bar=False)
            section_paths = []
            for name, text in sections:
                if not text.strip():
                    continue
                clean = clean_text_for_tts(text)
                out_path = os.path.join(TMP, f"{name}.mp3")
                logging.info(f"🎧 Generating with alt model '{alt}': {name}")
                _tts_to_file(tts_alt, clean, out_path, speaker=None)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                    section_paths.append(out_path)
                else:
                    raise Exception(f"Alt model failed creating {out_path}")
            # Combine
            combined = AudioSegment.silent(duration=0)
            for i, path in enumerate(section_paths):
                part = AudioSegment.from_file(path)
                pause_ms = 200 if i < len(section_paths) - 1 else 0
                combined += part + AudioSegment.silent(duration=pause_ms)
            combined.export(FULL_AUDIO_PATH, format="mp3")
            logging.info(f"✅ Combined (alt) TTS exported to {FULL_AUDIO_PATH}")
            return section_paths
        except Exception as e:
            logging.warning(f"⚠️ Alt model {alt} failed: {e}")
            continue

    # Final fallback: generate single full audio with gTTS and split proportionally
    logging.info("🔄 Falling back to gTTS / split-on-proportion approach")
    fallback_path = generate_tts_fallback(spoken, FULL_AUDIO_PATH)
    if not os.path.exists(fallback_path) or os.path.getsize(fallback_path) < 1000:
        raise Exception("Final fallback audio not created")

    full_audio = AudioSegment.from_file(fallback_path)
    total_ms = len(full_audio)
    section_texts = [(name, text) for name, text in sections if text.strip()]
    total_words = sum(len(t.split()) for _, t in section_texts) or 1

    current_pos = 0
    section_paths = []
    for name, text in section_texts:
        words = len(text.split())
        proportion = words / total_words
        dur_ms = max(500, int(total_ms * proportion))
        seg = full_audio[current_pos:current_pos + dur_ms]
        out_path = os.path.join(TMP, f"{name}.mp3")
        seg.export(out_path, format="mp3")
        section_paths.append(out_path)
        current_pos += dur_ms

    # Recombine to main file
    combined = AudioSegment.silent(duration=0)
    for i, path in enumerate(section_paths):
        part = AudioSegment.from_file(path)
        pause_ms = 200 if i < len(section_paths) - 1 else 0
        combined += part + AudioSegment.silent(duration=pause_ms)
    combined.export(FULL_AUDIO_PATH, format="mp3")

    logging.info("✅ Sections created from fallback gTTS and combined")
    return section_paths

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    # Load script.json
    script_path = os.path.join(TMP, "script.json")
    if not os.path.exists(script_path):
        logging.error(f"❌ Missing script file: {script_path}")
        raise SystemExit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hook = data.get("hook", "")
    bullets = data.get("bullets", [])
    cta = data.get("cta", "")

    # Build spoken text
    spoken_parts = [p.strip() for p in [hook] + bullets + [cta] if p and p.strip()]
    spoken = ". ".join(spoken_parts)
    logging.info(f"🎙️ Preparing TTS for {len(spoken)} chars. Preview: {spoken[:120]}...")

    try:
        section_paths = generate_sectional_tts()

        # Verify final audio
        if not os.path.exists(FULL_AUDIO_PATH):
            raise Exception("Final audio not produced")

        audio = AudioSegment.from_file(FULL_AUDIO_PATH)
        actual_duration = audio.duration_seconds
        file_size_kb = os.path.getsize(FULL_AUDIO_PATH) / 1024.0

        # Duration checks tuned to PRD: target 45-75s for gardening shorts
        if actual_duration > 75:
            logging.warning(f"⚠️ Audio too long ({actual_duration:.1f}s) — forcing fallback gTTS")
            generate_tts_fallback(spoken, FULL_AUDIO_PATH)
            audio = AudioSegment.from_file(FULL_AUDIO_PATH)
            actual_duration = audio.duration_seconds

        words = len(spoken.split())
        estimated_duration = (words / 150.0) * 60.0

        metadata = {
            "text": spoken,
            "words": words,
            "estimated_duration": estimated_duration,
            "actual_duration": actual_duration,
            "file_size_kb": round(file_size_kb, 2),
            "tts_provider": PRIMARY_MODEL,
            "model_info": {
                "selected_primary": PRIMARY_MODEL,
                "speaker": PRIMARY_SPEAKER
            },
            "content_type": "gardening",
            "optimal_duration_met": 45 <= actual_duration <= 75
        }

        with open(AUDIO_METADATA, "w", encoding="utf-8") as mf:
            json.dump(metadata, mf, indent=2)

        logging.info(f"📊 Audio duration: {actual_duration:.1f}s  words: {words}  file: {FULL_AUDIO_PATH}")
        logging.info(f"✅ TTS generation complete; metadata saved: {AUDIO_METADATA}")
    except Exception as e:
        logging.error(f"❌ TTS generation failed: {e}")
        raise SystemExit(1)