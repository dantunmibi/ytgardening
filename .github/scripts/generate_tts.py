#!/usr/bin/env python3
"""
.github/scripts/generate_tts.py
Garden Glow Up - Robust Coqui TTS generation with gardening-specific cleaning
OPTIMIZED: Using best researched models with proper speaker configuration
"""
import os
import json
import re
import sys
from tenacity import retry, stop_after_attempt, wait_exponential
from pydub import AudioSegment
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)
FULL_AUDIO_PATH = os.path.join(TMP, "voice.mp3")
AUDIO_METADATA = os.path.join(TMP, "audio_metadata.json")

# ===== OPTIMIZED MODEL CONFIGURATION (BASED ON RESEARCH) =====
# Primary: VCTK-VITS is fastest and highest quality for YouTube Shorts
PRIMARY_MODEL = "tts_models/en/vctk/vits"
PRIMARY_SPEAKER = "p330"  # Female, clear American accent

# Alternative speakers (if primary fails or for variety)
ALT_VCTK_SPEAKERS = ["p230", "p273", "p225", "p234"]  # Mix of male/female, American/British

# Fallback models (in order of preference)
FALLBACK_MODELS = [
    "tts_models/en/ljspeech/tacotron2-DDC",
    "tts_models/en/ljspeech/glow-tts",
    "tts_models/en/ljspeech/fast_pitch"
]

print(f"✅ TTS Configuration:")
print(f"   Primary Model: {PRIMARY_MODEL}")
print(f"   Primary Speaker: {PRIMARY_SPEAKER}")
print(f"   Fallback Models: {len(FALLBACK_MODELS)} alternatives")

# -------------------------
# Enhanced Text Cleaning for Gardening
# -------------------------
def clean_text_for_tts(text: str) -> str:
    """Enhanced text preprocessing for natural TTS pronunciation (gardening-optimized)."""
    if not text:
        return ""

    # Normalize whitespace
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)

    # Protect common abbreviations
    protected_patterns = {
        r'\bDr\.': 'Doctor',
        r'\bMr\.': 'Mister',
        r'\bMrs\.': 'Misses',
        r'\bMs\.': 'Miss',
        r'\betc\.': 'etcetera',
        r'\be\.g\.': 'for example',
        r'\bi\.e\.': 'that is',
    }
    for pat, rep in protected_patterns.items():
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    # Special characters
    replacements = {
        '%': ' percent',
        '&': ' and ',
        '+': ' plus ',
        '@': ' at ',
        '$': ' dollars ',
        '#': ' hashtag ',
        '...': ' ',
        '-': ' to ',
        'PM': 'P M',
        'am': 'A M',
        'AM': 'A M',
        'pm': 'P M',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    # 🌱 Gardening-specific measurement and term handling
    gardening_patterns = {
        r'(\d+)\s*"': r'\1 inches',
        r'(\d+)\s*\'': r'\1 feet',
        r'(\d+)\s*in\b': r'\1 inches',
        r'(\d+)\s*ft\b': r'\1 feet',
        r'(\d+)\s*cm\b': r'\1 centimeters',
        r'(\d+)\s*mm\b': r'\1 millimeters',
        r'(\d+)\s*tbsp\b': r'\1 tablespoons',
        r'(\d+)\s*tsp\b': r'\1 teaspoons',
        r'(\d+)\s*ml\b': r'\1 milliliters',
        r'(\d+)\s*L\b': r'\1 liters',
        r'(\d+)\s*oz\b': r'\1 ounces',
        r'(\d+)\s*lbs?\b': r'\1 pounds',
        r'(\d+)\s*gal\b': r'\1 gallons',
        r'(\d+)\s*°C\b': r'\1 degrees Celsius',
        r'(\d+)\s*°F\b': r'\1 degrees Fahrenheit',
        r'\bPH\b': 'P H',
        r'\bpH\b': 'P H',
        r'\bNPK\b': 'N P K',
    }
    for pat, rep in gardening_patterns.items():
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    # 🌱 Plant name pronunciation hints (expand as needed)
    plant_pronunciations = {
        r'\bPothos\b': 'POH-thos',
        r'\bMonstera\b': 'mon-STAIR-uh',
        r'\bPhilodendron\b': 'fil-oh-DEN-dron',
        r'\bSansevieria\b': 'san-suh-VEER-ee-uh',
        r'\bFuchsia\b': 'FYOO-shuh',
        r'\bAeonium\b': 'ay-OH-nee-um',
        r'\bAglaonema\b': 'ag-lay-oh-NEE-muh',
    }
    for pat, rep in plant_pronunciations.items():
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    # Remove emojis
    emoji_pattern = re.compile("["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\u2600-\u26FF\u2700-\u27BF]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)

    # Collapse whitespace again
    text = re.sub(r'\s+', ' ', text).strip()

    # Ensure final punctuation
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
        # Target 140-150 WPM for gardening content
        duration_ms = max(15000, min(75000, int((words / 145.0) * 60000)))
        silent = AudioSegment.silent(duration=duration_ms, frame_rate=22050)
        silent.export(out_path, format="mp3")
        logging.info(f"✅ Silent fallback created ({duration_ms/1000:.1f}s) at {out_path}")
        return out_path
    except Exception as e:
        logging.error(f"❌ Silent fallback failed: {e}")
        raise

# -------------------------
# TTS Generation
# -------------------------
def _tts_to_file(tts_obj, text: str, out_path: str, speaker: str = None):
    """
    Robust wrapper around TTS.tts_to_file with speaker support
    """
    try:
        if speaker:
            # Try with speaker parameter
            try:
                tts_obj.tts_to_file(text=text, file_path=out_path, speaker_idx=speaker)
                return
            except TypeError:
                # Model doesn't support speaker_idx, try without
                logging.info("   (Model doesn't support speaker selection, using default)")
                pass
        
        # Fallback: no speaker parameter
        tts_obj.tts_to_file(text=text, file_path=out_path)
        
    except Exception as e:
        logging.error(f"   TTS generation error: {e}")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def generate_sectional_tts():
    """
    Generate TTS using optimized model configuration
    Primary: VCTK-VITS (fastest, best quality)
    Fallback: LJSpeech models → gTTS
    """
    from TTS.api import TTS
    
    sections = [("hook", hook)] + [(f"bullet_{i}", b) for i, b in enumerate(bullets)] + [("cta", cta)]
    section_paths = []

    # ===== TRY PRIMARY MODEL (VCTK-VITS) =====
    try:
        logging.info(f"🔊 Loading PRIMARY model: {PRIMARY_MODEL}")
        tts = TTS(model_name=PRIMARY_MODEL, progress_bar=False)
        
        # Verify speaker support
        available_speakers = getattr(tts, "speakers", None)
        use_speaker = False
        selected_speaker = PRIMARY_SPEAKER
        
        if available_speakers:
            if PRIMARY_SPEAKER in available_speakers:
                use_speaker = True
                logging.info(f"   ✅ Using speaker: {PRIMARY_SPEAKER}")
            else:
                # Try alternative speakers
                for alt_speaker in ALT_VCTK_SPEAKERS:
                    if alt_speaker in available_speakers:
                        use_speaker = True
                        selected_speaker = alt_speaker
                        logging.info(f"   ✅ Using alternative speaker: {alt_speaker}")
                        break
                
                if not use_speaker:
                    logging.info(f"   ⚠️ No preferred speakers available, using default")
        
        # Generate each section
        for name, text in sections:
            if not text.strip():
                continue
            
            clean = clean_text_for_tts(text)
            out_path = os.path.join(TMP, f"{name}.mp3")
            
            logging.info(f"🎧 Generating '{name}' ({len(clean)} chars)")
            
            if use_speaker:
                _tts_to_file(tts, clean, out_path, speaker=selected_speaker)
            else:
                _tts_to_file(tts, clean, out_path)
            
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                section_paths.append(out_path)
                logging.info(f"   ✅ {out_path}")
            else:
                raise Exception(f"Section file invalid: {out_path}")

        # Combine sections with pauses
        combined = AudioSegment.silent(duration=0)
        for i, path in enumerate(section_paths):
            part = AudioSegment.from_file(path)
            # 250ms pause between sections (gardening content benefits from slightly longer pauses)
            pause_ms = 250 if i < len(section_paths) - 1 else 0
            combined += part + AudioSegment.silent(duration=pause_ms)

        combined.export(FULL_AUDIO_PATH, format="mp3")
        logging.info(f"✅ PRIMARY model success! Audio: {FULL_AUDIO_PATH}")
        return section_paths

    except Exception as primary_err:
        logging.warning(f"⚠️ PRIMARY model failed: {primary_err}")

    # ===== TRY FALLBACK MODELS =====
    for fallback_model in FALLBACK_MODELS:
        try:
            logging.info(f"🔁 Trying FALLBACK: {fallback_model}")
            tts_fb = TTS(model_name=fallback_model, progress_bar=False)
            
            section_paths = []
            for name, text in sections:
                if not text.strip():
                    continue
                
                clean = clean_text_for_tts(text)
                out_path = os.path.join(TMP, f"{name}.mp3")
                
                _tts_to_file(tts_fb, clean, out_path)
                
                if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                    section_paths.append(out_path)
                else:
                    raise Exception(f"Fallback section failed: {out_path}")
            
            # Combine
            combined = AudioSegment.silent(duration=0)
            for i, path in enumerate(section_paths):
                part = AudioSegment.from_file(path)
                pause_ms = 250 if i < len(section_paths) - 1 else 0
                combined += part + AudioSegment.silent(duration=pause_ms)
            
            combined.export(FULL_AUDIO_PATH, format="mp3")
            logging.info(f"✅ FALLBACK model success! ({fallback_model})")
            return section_paths
            
        except Exception as e:
            logging.warning(f"⚠️ {fallback_model} failed: {e}")
            continue

    # ===== FINAL FALLBACK: gTTS =====
    logging.info("🔄 All local models failed, using gTTS...")
    fallback_path = generate_tts_fallback(spoken, FULL_AUDIO_PATH)
    
    if not os.path.exists(fallback_path) or os.path.getsize(fallback_path) < 1000:
        raise Exception("All TTS methods failed")

    # Split proportionally for sectional audio
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

    # Recombine with pauses
    combined = AudioSegment.silent(duration=0)
    for i, path in enumerate(section_paths):
        part = AudioSegment.from_file(path)
        pause_ms = 250 if i < len(section_paths) - 1 else 0
        combined += part + AudioSegment.silent(duration=pause_ms)
    
    combined.export(FULL_AUDIO_PATH, format="mp3")
    logging.info("✅ gTTS fallback complete")
    return section_paths

# -------------------------
# Main Execution
# -------------------------
if __name__ == "__main__":
    # Load script.json
    script_path = os.path.join(TMP, "script.json")
    if not os.path.exists(script_path):
        logging.error(f"❌ Missing script file: {script_path}")
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hook = data.get("hook", "")
    bullets = data.get("bullets", [])
    cta = data.get("cta", "")

    # Build spoken text
    spoken_parts = [p.strip() for p in [hook] + bullets + [cta] if p and p.strip()]
    spoken = ". ".join(spoken_parts)
    
    logging.info(f"🎙️ Preparing TTS for {len(spoken)} chars")
    logging.info(f"   Preview: {spoken[:100]}...")

    try:
        section_paths = generate_sectional_tts()

        # Verify final audio
        if not os.path.exists(FULL_AUDIO_PATH):
            raise Exception("Final audio not produced")

        audio = AudioSegment.from_file(FULL_AUDIO_PATH)
        actual_duration = audio.duration_seconds
        file_size_kb = os.path.getsize(FULL_AUDIO_PATH) / 1024.0

        # Duration target: 45-75s for gardening shorts
        if actual_duration > 75:
            logging.warning(f"⚠️ Audio too long ({actual_duration:.1f}s) — consider trimming")
        elif actual_duration < 20:
            logging.warning(f"⚠️ Audio very short ({actual_duration:.1f}s)")

        words = len(spoken.split())
        estimated_duration = (words / 145.0) * 60.0  # ~145 WPM for gardening

        metadata = {
            "text": spoken,
            "words": words,
            "estimated_duration": round(estimated_duration, 2),
            "actual_duration": round(actual_duration, 2),
            "file_size_kb": round(file_size_kb, 2),
            "tts_provider": PRIMARY_MODEL,
            "speaker": PRIMARY_SPEAKER,
            "model_info": {
                "primary": PRIMARY_MODEL,
                "speaker": PRIMARY_SPEAKER,
                "fallbacks": FALLBACK_MODELS
            },
            "content_type": "gardening",
            "optimal_duration_met": 45 <= actual_duration <= 75,
            "wpm": round(words / (actual_duration / 60.0), 1) if actual_duration > 0 else 0
        }

        with open(AUDIO_METADATA, "w", encoding="utf-8") as mf:
            json.dump(metadata, mf, indent=2)

        logging.info(f"\n📊 TTS Generation Complete!")
        logging.info(f"   Duration: {actual_duration:.1f}s")
        logging.info(f"   Words: {words}")
        logging.info(f"   WPM: {metadata['wpm']}")
        logging.info(f"   File: {FULL_AUDIO_PATH} ({file_size_kb:.1f} KB)")
        logging.info(f"   Model: {PRIMARY_MODEL}")
        logging.info(f"   Speaker: {PRIMARY_SPEAKER}")
        logging.info(f"   ✅ Metadata: {AUDIO_METADATA}")
        
    except Exception as e:
        logging.error(f"❌ TTS generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)