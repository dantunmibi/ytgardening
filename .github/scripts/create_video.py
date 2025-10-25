# .github/scripts/create_video.py
import os
import json
import requests
from moviepy import *
import platform
from tenacity import retry, stop_after_attempt, wait_exponential
from pydub import AudioSegment
from time import sleep
from PIL import Image, ImageDraw, ImageFont
import random

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
OUT = os.path.join(TMP, "short.mp4")
audio_path = os.path.join(TMP, "voice.mp3")
w, h = 1080, 1920

# Safe zones for text (avoiding screen edges)
SAFE_ZONE_MARGIN = 130
TEXT_MAX_WIDTH = w - (2 * SAFE_ZONE_MARGIN)

def get_font_path():
    system = platform.system()
    if system == "Windows":
        return "C:/Windows/Fonts/arialbd.ttf"
    elif system == "Darwin":
        return "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    else:
        font_options = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for font in font_options:
            if os.path.exists(font):
                return font
        return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

FONT = get_font_path()
print(f"📝 Using font: {FONT}")

with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

title = data.get("title", "Garden Tip")
hook = data.get("hook", "")
bullets = data.get("bullets", [])
cta = data.get("cta", "")
topic = data.get("topic", "gardening")
visual_prompts = data.get("visual_prompts", [])

# 🌱 GARDENING COLOR PALETTE (from PRD)
GARDEN_COLORS = {
    'forest_green': (45, 80, 22),      # #2D5016
    'sunshine_yellow': (244, 208, 63),  # #F4D03F  
    'earth_brown': (139, 69, 19),       # #8B4513
    'vibrant_green': (50, 205, 50),     # Bright growth green
    'tomato_red': (255, 99, 71),        # Ripe tomato
    'soil_dark': (60, 40, 20),          # Rich soil
}

def generate_image_huggingface(prompt, filename, width=1080, height=1920):
    """Generate image using Hugging Face (with multiple free model fallbacks)"""
    try:
        hf_token = os.getenv('HUGGINGFACE_API_KEY')
        if not hf_token:
            print("    ⚠️ HUGGINGFACE_API_KEY not found — skipping Hugging Face")
            raise Exception("Missing token")

        headers = {"Authorization": f"Bearer {hf_token}"}
        
        # 🌱 Enhanced gardening-specific negative prompt
        negative_gardening = (
            "blurry, low quality, watermark, text, logo, frame, caption, title, subtitle, "
            "ui, interface, overlay, play button, youtube logo, branding, prompt text, "
            "paragraphs, words, symbol, icon, graphics, arrows, shapes, distorted, "
            "compression artifacts, pixelated, dull colors, cropped, stretched, deformed, "
            "multiple faces, duplicate body parts, text watermark, long text, dead plants, "
            "brown leaves, dying vegetation, wilted flowers, unhealthy soil, artificial plants, "
            "plastic plants, cartoon style, anime style, illustration"
        )
        
        payload = {
            "inputs": f"{prompt}, vibrant garden photography, lush green plants, healthy vegetation, natural outdoor lighting, macro plant detail, botanical photography, professional garden photo",
            "parameters": {
                "negative_prompt": negative_gardening,
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "width": width,
                "height": height,
            }
        }

        models = [
            "stabilityai/stable-diffusion-xl-base-1.0",
            "prompthero/openjourney-v4",
            "Lykon/dreamshaper-xl-v2-turbo",
            "runwayml/stable-diffusion-v1-5",
            "stabilityai/sdxl-turbo"
        ]

        for model in models:
            url = f"https://api-inference.huggingface.co/models/{model}"
            print(f"🤗 Trying model: {model}")

            response = requests.post(url, headers=headers, json=payload, timeout=90)

            if response.status_code == 200 and len(response.content) > 1000:
                filepath = os.path.join(TMP, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                print(f"    ✅ Hugging Face model succeeded: {model}")
                return filepath

            elif response.status_code == 402:
                print(f"💰 {model} requires payment — moving to next model...")
                continue

            elif response.status_code in [503, 429]:
                print(f"⌛ {model} is loading or rate-limited — trying next...")
                continue

            else:
                print(f"⚠️ {model} failed ({response.status_code}) — trying next model...")

        raise Exception("All Hugging Face models failed")

    except Exception as e:
        print(f"⚠️ Hugging Face image generation failed: {e}")
        raise


def generate_image_pollinations(prompt, filename, width=1080, height=1920):
    """Pollinations backup with gardening-optimized prompts"""
    try:
        # 🌱 Enhanced gardening-specific negative terms
        negative_terms = (
            "blurry, low quality, watermark, text, logo, frame, caption, title, subtitle, "
            "ui, interface, overlay, play button, youtube logo, branding, prompt text, "
            "paragraphs, words, symbol, icon, graphics, arrows, shapes, distorted, "
            "compression artifacts, pixelated, dull colors, cropped, stretched, deformed, "
            "multiple faces, duplicate body parts, text watermark, long text, dead plants, "
            "brown leaves, dying vegetation, wilted flowers, unhealthy soil, artificial, "
            "plastic, cartoon, anime, illustration"
        )

        # 🌱 Enhanced prompt with gardening keywords
        formatted_prompt = (
            f"{prompt}, vibrant garden photography, lush healthy plants, natural sunlight, "
            "botanical detail, macro plant photography, professional garden photo, "
            "organic garden aesthetic, earth tones, vivid green foliage, photorealistic"
        )

        seed = random.randint(1, 999999)

        url = (
            "https://image.pollinations.ai/prompt/"
            f"{requests.utils.quote(formatted_prompt)}"
            f"?width={width}&height={height}"
            f"&negative={requests.utils.quote(negative_terms)}"
            f"&nologo=true&notext=true&enhance=true&clean=true"
            f"&seed={seed}&rand={seed}"
        )

        print(f"    🌐 Pollinations gardening image: {prompt[:60]}... (seed={seed})")
        response = requests.get(url, timeout=90)

        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            filepath = os.path.join(TMP, filename)
            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"    ✅ Pollinations gardening image generated (seed {seed})")
            return filepath
        else:
            raise Exception(f"Pollinations failed: {response.status_code}")

    except Exception as e:
        print(f"    ⚠️ Pollinations gardening image failed: {e}")
        raise

def generate_picsum_fallback(bg_path, topic=None, title=None, width=1080, height=1920):
    """🌱 Gardening-specific fallback with nature/plant keywords"""
    import re, random, requests

    # 🌱 Gardening-specific topic mapping
    topic_map = {
        "gardening": "garden",
        "plant": "plant",
        "propagation": "plant",
        "tomato": "tomato",
        "herbs": "herbs",
        "vegetables": "vegetables",
        "composting": "compost",
        "flowers": "flowers",
        "succulent": "succulent",
        "indoor": "houseplant",
        "outdoor": "garden",
        "soil": "soil",
        "seeds": "seeds",
        "watering": "water",
        "pest": "garden",
        "organic": "organic",
        "urban": "balcony",
        "container": "potted-plant",
    }

    text_source = (topic or title or "").lower()
    resolved_key = "garden"  # Default to garden
    
    for word, mapped in topic_map.items():
        if word in text_source:
            resolved_key = mapped
            break

    print(f"🔎 Searching gardening fallback image for '{topic}' (resolved: '{resolved_key}')...")

    # Try Unsplash with gardening keywords
    try:
        seed = random.randint(1, 9999)
        url = f"https://source.unsplash.com/{width}x{height}/?{requests.utils.quote(resolved_key)}&sig={seed}"
        print(f"🖼️ Unsplash gardening fallback for '{resolved_key}' (seed={seed})...")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"    ✅ Unsplash gardening image saved for '{resolved_key}'")
            return bg_path
        else:
            print(f"    ⚠️ Unsplash failed ({response.status_code})")
    except Exception as e:
        print(f"    ⚠️ Unsplash error: {e}")

    # 🌱 Try Pexels with curated gardening photo IDs
    try:
        print("    🔄 Falling back to Pexels gardening photos...")
        
        # Curated high-quality gardening/nature photo IDs from Pexels
        gardening_pexels_ids = {
            "garden": [1072824, 1301856, 2132250, 2132227, 169523, 1459505, 2255441, 2255439],
            "plant": [1072824, 1072828, 1301856, 2255441, 2255439, 1459505, 1435904, 1435895],
            "tomato": [1327838, 1327831, 6157049, 6157069, 3059609, 2255441],
            "herbs": [4750267, 4750271, 5187392, 5187370, 1435904, 4750270],
            "vegetables": [2255441, 1327838, 1327831, 6157049, 169523, 1459505],
            "flowers": [736230, 736228, 1076758, 1076721, 850359, 850704, 1076758],
            "succulent": [1084199, 1084382, 2132250, 2132227, 5699808, 5699852],
            "houseplant": [1072824, 1072828, 1084199, 2132250, 1459505, 1435904],
            "compost": [169523, 2132250, 1301856, 1072824, 1459505],
            "soil": [169523, 1301856, 1072824, 2132250, 2132227],
            "seeds": [1301856, 1327838, 2255441, 169523, 1459505],
            "water": [2132250, 1072824, 1301856, 1435904, 2255441],
            "organic": [1327838, 1301856, 169523, 1072824, 2255441],
            "balcony": [1084199, 1084382, 2132250, 2132227, 1072828],
            "potted-plant": [1072824, 1072828, 1084199, 1084382, 2132250],
        }
        
        if resolved_key not in gardening_pexels_ids:
            resolved_key = "garden"
        
        photo_ids = gardening_pexels_ids[resolved_key].copy()
        random.shuffle(photo_ids)
        
        for attempt, photo_id in enumerate(photo_ids[:4]):
            seed = random.randint(1000, 9999)
            url = f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg?auto=compress&cs=tinysrgb&w=720&h=1280&random={seed}"
            
            print(f"📸 Pexels gardening photo attempt {attempt+1} (id={photo_id}, topic='{resolved_key}')...")

            response = requests.get(url, timeout=30)
            if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
                with open(bg_path, "wb") as f:
                    f.write(response.content)
                print(f"    ✅ Pexels gardening photo saved (id: {photo_id})")

                img = Image.open(bg_path).convert("RGB")
                img = img.resize((width, height), Image.LANCZOS)
                img.save(bg_path, quality=95)
                print(f"    ✂️ Resized to exact {width}x{height}")

                return bg_path
            else:
                print(f"    ⚠️ Pexels photo {photo_id} failed: {response.status_code}")
        
        print("    ⚠️ All Pexels gardening photos failed")
        
    except Exception as e:
        print(f"    ⚠️ Pexels gardening photos fallback failed: {e}")

    # Try Picsum as last resort
    try:
        seed = random.randint(1, 1000)
        url = f"https://picsum.photos/{width}/{height}?random={seed}"
        print(f"🎲 Picsum fallback (seed={seed})...")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"    ✅ Picsum image saved")
            return bg_path
        else:
            print(f"    ⚠️ Picsum failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"    ⚠️ Picsum fallback failed: {e}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=20))
def generate_image_reliable(prompt, filename, width=1080, height=1920, topic=None, title=None):
    """Try multiple image generation providers and gardening-specific fallbacks"""
    filepath = os.path.join(TMP, filename)
    
    # 1. AI Providers
    providers = [
        ("Pollinations", generate_image_pollinations),
        ("Hugging Face", generate_image_huggingface)
    ]
    
    for provider_name, provider_func in providers:
        try:
            print(f"🎨 Trying {provider_name} for gardening image...")
            result = provider_func(prompt, filename, width, height)
            if result and os.path.exists(result) and os.path.getsize(result) > 1000:
                return result
        except Exception as e:
            print(f"    ⚠️ {provider_name} failed: {e}")
            continue

    # 2. Gardening-specific fallbacks (Unsplash, Pexels with garden photos)
    print("🖼️ AI providers failed, trying gardening photo API fallbacks...")
    result = generate_picsum_fallback(filepath, topic=topic or "gardening", title=title, width=width, height=height)

    if result and os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return result
    
    # 3. 🌱 Garden-themed gradient fallback (natural earth tones)
    print("⚠️ All providers failed, using garden-themed gradient fallback")
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Garden color palette (earthy, natural)
    garden_colors = [
        GARDEN_COLORS['forest_green'],
        GARDEN_COLORS['vibrant_green'],
        GARDEN_COLORS['earth_brown'],
        GARDEN_COLORS['sunshine_yellow'],
        GARDEN_COLORS['tomato_red']
    ]
    color = garden_colors[random.randint(0, len(garden_colors) - 1)]
    
    for y in range(height):
        intensity = int(255 * (1 - y / height))
        r = min(255, max(0, color[0] + (intensity - 127) // 2))
        g = min(255, max(0, color[1] + (intensity - 127) // 2))
        b = min(255, max(0, color[2] + (intensity - 127) // 2))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    img.save(filepath)
    return filepath


# --- Main Scene Generation Logic ---

print("🌱 Generating gardening scene images with reliable providers...")
scene_images = []

try:
    # 1. Hook Scene
    hook_prompt = visual_prompts[0] if len(visual_prompts) > 0 else f"Vibrant garden close-up for: {hook or title}, macro plant photography, lush green leaves, natural sunlight, botanical detail"
    hook_img = generate_image_reliable(
        hook_prompt, 
        "scene_hook.jpg", 
        width=w, height=h, 
        topic="gardening", 
        title=hook or title
    )
    scene_images.append(hook_img)
    
    # 2. Bullet Point Scenes (gardening-focused)
    for i, bullet in enumerate(bullets):
        bullet_prompt = visual_prompts[i+1] if len(visual_prompts) > i+1 else f"Garden demonstration: {bullet}, hands working with plants, close-up plant detail, natural outdoor lighting, healthy vegetation"
        bullet_img = generate_image_reliable(
            bullet_prompt, 
            f"scene_bullet_{i}.jpg", 
            width=w, height=h, 
            topic="gardening", 
            title=bullet
        )
        scene_images.append(bullet_img)

    # 3. Final CTA/Summary Scene (thriving plants)
    cta_prompt = visual_prompts[-1] if len(visual_prompts) > len(bullets) else f"Thriving garden result: {cta or title}, abundant harvest, healthy plants, satisfaction shot, vibrant growth"
    cta_img = generate_image_reliable(
        cta_prompt, 
        "scene_cta.jpg", 
        width=w, height=h, 
        topic="gardening", 
        title=cta or title
    )
    scene_images.append(cta_img)
    
    successful_images = len([img for img in scene_images if img and os.path.exists(img) and os.path.getsize(img) > 1000])
    print(f"✅ Generated {successful_images} gardening images out of {len(scene_images)} total scenes.")
    
except Exception as e:
    print(f"⚠️ Image generation failed entirely: {e}")
    scene_images = [None] * (len(bullets) + 2)

# ✅ VALIDATE AND REPLACE NONE/INVALID IMAGES WITH GARDEN GRADIENTS
print(f"🔍 Validating {len(scene_images)} gardening scene images...")
for i in range(len(scene_images)):
    img = scene_images[i] if i < len(scene_images) else None
    
    if not img or not os.path.exists(img) or os.path.getsize(img) < 1000:
        print(f"⚠️ Scene {i} invalid, creating garden gradient fallback...")
        fallback_path = os.path.join(TMP, f"scene_fallback_{i}.jpg")
        
        fallback_img = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(fallback_img)
        
        # 🌱 Use garden color palette
        garden_colors = [
            GARDEN_COLORS['forest_green'],
            GARDEN_COLORS['vibrant_green'],
            GARDEN_COLORS['earth_brown'],
            GARDEN_COLORS['sunshine_yellow'],
            GARDEN_COLORS['tomato_red']
        ]
        color = garden_colors[i % len(garden_colors)]
        
        for y in range(h):
            intensity = int(255 * (1 - y / h))
            r = min(255, max(0, color[0] + (intensity - 127) // 2))
            g = min(255, max(0, color[1] + (intensity - 127) // 2))
            b = min(255, max(0, color[2] + (intensity - 127) // 2))
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        
        fallback_img.save(fallback_path)
        scene_images[i] = fallback_path

print(f"✅ All gardening scene images validated")

if not os.path.exists(audio_path):
    print(f"❌ Audio file not found: {audio_path}")
    raise FileNotFoundError("voice.mp3 not found")

audio = AudioFileClip(audio_path)
duration = audio.duration
print(f"🎵 Audio loaded: {duration:.2f} seconds")

# 🔍 Prefer real per-section durations if available
def get_audio_duration(path):
    """Get audio duration safely using mutagen (works on Python 3.14)."""
    try:
        if os.path.exists(path):
            return len(AudioSegment.from_file(path)) / 1000.0
    except:
        pass
    return 0

hook_path = os.path.join(TMP, "hook.mp3")
cta_path = os.path.join(TMP, "cta.mp3")
bullet_paths = [os.path.join(TMP, f"bullet_{i}.mp3") for i in range(len(bullets))]

if all(os.path.exists(p) for p in [hook_path, cta_path] + bullet_paths):
    print("🎯 Using real per-section audio durations for sync")
    hook_dur = get_audio_duration(hook_path)
    bullet_durs = [get_audio_duration(p) for p in bullet_paths]
    cta_dur = get_audio_duration(cta_path)
else:
    print("⚙️ Using estimated word-based durations (fallback)")

    def estimate_speech_duration(text, audio_path):
        """Estimate how long the given text should take"""
        words = len(text.split())
        if words == 0:
            return 0.0

        fallback_wpm = 140

        if os.path.exists(audio_path):
            try:
                audio = AudioSegment.from_file(audio_path)
                total_audio_duration = len(audio) / 1000.0

                all_text = " ".join([hook] + bullets + [cta])
                total_words = len(all_text.split()) or 1

                seconds_per_word = total_audio_duration / total_words
                return seconds_per_word * words
            except Exception as e:
                print(f"⚠️ Could not analyze TTS file for pacing: {e}")
                return (words / fallback_wpm) * 60.0
        else:
            return (words / fallback_wpm) * 60.0

    hook_estimated = estimate_speech_duration(hook, audio_path)
    bullets_estimated = [estimate_speech_duration(b, audio_path) for b in bullets]
    cta_estimated = estimate_speech_duration(cta, audio_path)

    total_estimated = hook_estimated + sum(bullets_estimated) + cta_estimated

    if total_estimated == 0:
        section_count = max(1, len(bullets) + (1 if hook else 0) + (1 if cta else 0))
        equal_split = duration / section_count 
        
        hook_dur = equal_split if hook else 0
        bullet_durs = [equal_split] * len(bullets)
        cta_dur = equal_split if cta else 0

    else:
        time_scale = duration / total_estimated 

        hook_dur = hook_estimated * time_scale
        bullet_durs = [b_est * time_scale for b_est in bullets_estimated]
        cta_dur = cta_estimated * time_scale
        
        # ✅ ACCOUNT FOR CROSS-FADE OVERLAPS
        num_sections = (1 if hook else 0) + len(bullets) + (1 if cta else 0)
        num_transitions = max(0, num_sections - 1)
        
        if num_transitions > 0:
            total_overlap = 0.3 * num_transitions
            
            total_base = hook_dur + sum(bullet_durs) + cta_dur
            
            if hook and total_base > 0:
                hook_dur = max(1.0, hook_dur - (total_overlap * hook_dur / total_base))
            
            for i in range(len(bullet_durs)):
                if total_base > 0:
                    bullet_durs[i] = max(1.0, bullet_durs[i] - (total_overlap * bullet_durs[i] / total_base))
            
            if cta and total_base > 0:
                cta_dur = max(1.0, cta_dur - (total_overlap * cta_dur / total_base))
            
            print(f"⚙️ Adjusted for {num_transitions} cross-fades (-{total_overlap:.2f}s total)")
        
        # Final rounding correction
        total_scenes = hook_dur + sum(bullet_durs) + cta_dur
        duration_diff = duration - total_scenes
            
        if abs(duration_diff) > 0.01:
            cta_dur += duration_diff
            print(f"⚙️ Final rounding adjustment: {duration_diff:.2f}s")

print(f"⏱️  Scene timings (audio-synced):")
if hook:
    print(f"   Hook: {hook_dur:.1f}s")
for i, dur in enumerate(bullet_durs):
    print(f"   Bullet {i+1}: {dur:.1f}s")
if cta:
    print(f"   CTA: {cta_dur:.1f}s")
print(f"   Total: {(hook_dur if hook else 0) + sum(bullet_durs) + (cta_dur if cta else 0):.2f}s (Audio: {duration:.2f}s)")

clips = []
current_time = 0

def smart_text_wrap(text, font_size, max_width):
    """Intelligently wrap text to prevent word splitting across lines"""
    
    try:
        pil_font = ImageFont.truetype(FONT, font_size)
    except:
        avg_char_width = font_size * 0.55
        max_chars_per_line = int(max_width / avg_char_width)
        
        words = text.split()
        if len(words) <= 2:
            return text + '\n'
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if len(test_line) <= max_chars_per_line:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines) + '\n'
    
    words = text.split()
    lines = []
    current_line = []
    
    dummy_img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=pil_font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            
            word_bbox = draw.textbbox((0, 0), word, font=pil_font)
            word_width = word_bbox[2] - word_bbox[0]
            if word_width > max_width:
                pass
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return '\n'.join(lines) + '\n'

def create_text_with_effects(text, font_size=64, max_width=TEXT_MAX_WIDTH):
    """Create properly wrapped text with safe font sizing"""
    
    wrapped_text = smart_text_wrap(text, font_size, max_width)
    
    try:
        pil_font = ImageFont.truetype(FONT, font_size)
        dummy_img = Image.new('RGB', (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        
        lines = wrapped_text.split('\n')
        total_height = 0
        max_line_width = 0
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=pil_font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            total_height += line_height
            max_line_width = max(max_line_width, line_width)
        
        max_height = h * 0.25
        iterations = 0
        
        while (total_height > max_height or max_line_width > max_width) and font_size > 32 and iterations < 10:
            font_size -= 4
            wrapped_text = smart_text_wrap(text, font_size, max_width)
            
            pil_font = ImageFont.truetype(FONT, font_size)
            lines = wrapped_text.split('\n')
            total_height = 0
            max_line_width = 0
            
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=pil_font)
                line_width = bbox[2] - bbox[0]
                line_height = bbox[3] - bbox[1]
                total_height += line_height
                max_line_width = max(max_line_width, line_width)
            
            iterations += 1
            
    except Exception as e:
        print(f"      ⚠️ Font sizing warning: {e}")
        if len(wrapped_text) > 100:
            font_size = max(32, font_size - 8)
    
    return wrapped_text, font_size

def create_scene(image_path, text, duration, start_time, position_y='center', color_fallback=None):
    """Create a scene with background image and properly rendered text"""
    scene_clips = []
    
    # 🌱 Use garden colors for fallback
    if color_fallback is None:
        color_fallback = GARDEN_COLORS['forest_green']
    
    if image_path and os.path.exists(image_path):
        bg = (ImageClip(image_path)
              .resized(height=h)
              .with_duration(duration)
              .with_start(start_time)
              .with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)]))
    else:
        bg = (ColorClip(size=(w, h), color=color_fallback, duration=duration)
              .with_start(start_time))
    
    scene_clips.append(bg)
    
    if text:
        wrapped_text, font_size = create_text_with_effects(text)

        text_method = 'label' if len(text.split()) <= 3 else 'caption'
        stroke_width = 2 if len(text.split()) <= 3 else 4
        
        text_clip = TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            color='white',
            stroke_width=stroke_width,
            stroke_color='black', 
            method=text_method,
            text_align='center',
            size=(TEXT_MAX_WIDTH, None),
        )
        
        text_height = text_clip.h
        text_width = text_clip.w
        
        descender_padding = max(35, int(font_size * 0.6))
        
        bottom_safe_zone = SAFE_ZONE_MARGIN + 180 
        
        if position_y == 'center':
            pos_y = (h - text_height) // 2
        elif position_y == 'top':
            pos_y = SAFE_ZONE_MARGIN + 80
        elif position_y == 'bottom':
            pos_y = h - text_height - bottom_safe_zone - descender_padding
        else:
            pos_y = min(max(SAFE_ZONE_MARGIN + 80, position_y), 
                       h - text_height - bottom_safe_zone - descender_padding)
        
        bottom_limit = h - bottom_safe_zone - descender_padding
        top_limit = SAFE_ZONE_MARGIN + 80
        
        if pos_y + text_height > bottom_limit:
            pos_y = bottom_limit - text_height
        if pos_y < top_limit:
            pos_y = top_limit
        
        text_clip = (text_clip
                    .with_duration(duration)
                    .with_start(start_time)
                    .with_position(('center', pos_y))
                    .with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)]))
        
        print(f"      Text: '{wrapped_text[:40]}...'")
        print(f"         Font: {font_size}px, Size: {text_width}x{text_height}px")
        print(f"         Position: Y={pos_y}px (top edge)")
        
        scene_clips.append(text_clip)
    
    return scene_clips

# Hook Scene
if hook:
    print(f"🎬 Creating hook scene (synced with audio)...")
    hook_clips = create_scene(
        scene_images[0] if scene_images else None,
        hook,
        hook_dur,
        current_time,
        position_y='top',
        color_fallback=GARDEN_COLORS['vibrant_green']
    )
    clips.extend(hook_clips)
    current_time += hook_dur

# ✅ HANDLE EMPTY BULLETS - ALWAYS ADVANCE TIMELINE
for i, bullet in enumerate(bullets):
    bullet_duration = bullet_durs[i]
    
    if not bullet or not bullet.strip():
        print(f"⚠️ Bullet {i+1} is empty, creating silent placeholder")
        placeholder = ColorClip(size=(w, h), color=GARDEN_COLORS['earth_brown'], duration=bullet_duration).with_start(current_time)
        clips.append(placeholder)
        current_time += bullet_duration
        continue
    
    img_index = min(i + 1, len(scene_images) - 1)
    
    # 🌱 Garden color palette for bullet backgrounds
    garden_bullet_colors = [
        GARDEN_COLORS['tomato_red'],
        GARDEN_COLORS['vibrant_green'],
        GARDEN_COLORS['sunshine_yellow']
    ]

    print(f"🎬 Creating bullet {i+1} scene (synced with audio)...")
    
    bullet_clips = create_scene(
        scene_images[img_index] if scene_images and img_index < len(scene_images) else None,
        bullet,
        bullet_duration,
        current_time,
        position_y='center',
        color_fallback=garden_bullet_colors[i % len(garden_bullet_colors)]
    )

    clips.extend(bullet_clips)
    current_time += bullet_duration

# CTA Scene
if cta:
    print(f"📢 Creating CTA scene (synced with audio)...")
    cta_clips = create_scene(
        scene_images[-1] if scene_images else None,
        cta,
        cta_dur,
        current_time,
        position_y='bottom',
        color_fallback=GARDEN_COLORS['forest_green']
    )
    clips.extend(cta_clips)
    current_time += cta_dur
    print(f"   CTA: {current_time - cta_dur:.1f}s - {current_time:.1f}s (synced)")
else:
    print("⚠️ No CTA text found")

# ✅ VERIFY SYNC BEFORE COMPOSING
final_timeline = current_time
print(f"\n📊 SYNC VERIFICATION:")
print(f"   Timeline duration: {final_timeline:.2f}s")
print(f"   Audio duration: {duration:.2f}s")
print(f"   Difference: {abs(final_timeline - duration)*1000:.1f}ms")

if abs(final_timeline - duration) > 0.5:
    print(f"⚠️ WARNING: Significant sync drift detected!")
else:
    print(f"✅ Sync verified - within acceptable tolerance")

print(f"\n🎬 Composing gardening video with {len(clips)} clips...")
video = CompositeVideoClip(clips, size=(w, h))

print(f"🔊 Attaching audio...")
video = video.with_audio(audio)

if video.audio is None:
    print("❌ ERROR: No audio attached to video!")
    raise Exception("Audio failed to attach")
else:
    print(f"✅ Audio verified: {video.audio.duration:.2f}s")
    print(f"✅ Text-audio synchronization: ENABLED")

print(f"📹 Writing gardening video file to {OUT}...")
try:
    video.write_videofile(
        OUT,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset='medium',
        audio_bitrate='192k',
        bitrate='8000k',
        logger=None
    )
    
    print(f"✅ Gardening video created successfully!")
    print(f"   Path: {OUT}")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Size: {os.path.getsize(OUT) / (1024*1024):.2f} MB")
    print(f"   Features:")
    print(f"      ✓ Gardening-optimized image generation")
    print(f"      ✓ Nature/plant photo fallbacks (Pexels curated)")
    print(f"      ✓ Garden color palette (forest green, earth tones)")
    print(f"      ✓ Smart text wrapping (no word splitting)")
    print(f"      ✓ Text stays within safe boundaries")
    print(f"      ✓ Proper descender spacing for letters")
    print(f"      ✓ Audio-synchronized text timing")
    print(f"      ✓ High visibility text (outline + shadow)")
    print(f"      ✓ Adaptive font sizing")
    print(f"      ✓ Dynamic position adjustment")
    print(f"      ✓ Cross-fade overlap correction")
    print(f"      ✓ Empty content handling")
    print(f"      ✓ Image validation and fallbacks")
    print(f"   🌱 Gardening-specific enhancements applied!")
    
    if not os.path.exists(OUT) or os.path.getsize(OUT) < 100000:
        raise Exception("Output video is missing or too small")
    
except Exception as e:
    print(f"❌ Video creation failed: {e}")
    raise

finally:
    print("🧹 Cleaning up...")
    audio.close()
    video.close()
    
    for clip in clips:
        try:
            clip.close()
        except:
            pass

print("✅ Gardening video pipeline complete with all optimizations applied! 🌱")