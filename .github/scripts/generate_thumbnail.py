# .github/scripts/generate_thumbnail.py
import os
import json
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from io import BytesIO
import platform
from tenacity import retry, stop_after_attempt, wait_exponential
from time import sleep
import textwrap
import random

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

# 🌱 GARDENING COLOR PALETTE (from PRD)
GARDEN_COLORS = {
    'forest_green': (45, 80, 22),
    'sunshine_yellow': (244, 208, 63),
    'earth_brown': (139, 69, 19),
    'vibrant_green': (50, 205, 50),
    'tomato_red': (255, 99, 71),
}

def get_font_path(size=80, bold=True):
    system = platform.system()
    font_paths = []
    
    if system == "Windows":
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/impact.ttf",
        ]
    elif system == "Darwin":
        font_paths = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Impact.ttf",
        ]
    else:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                print(f"⚠️ Could not load font {font_path}: {e}")
    
    print("⚠️ Using default font")
    return ImageFont.load_default()

with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

title = data.get("title", "Garden Tip")
topic = data.get("topic", "gardening")
hook = data.get("hook", "")

# Use the shorter text between title and hook
if hook and len(hook) > 10:
    if len(hook) < len(title):
        display_text = hook
        print(f"🎯 Using SHORTER hook for gardening thumbnail: {display_text}")
    else:
        display_text = title
        print(f"🎯 Using SHORTER title for gardening thumbnail: {display_text}")
else:
    display_text = title
    print(f"📝 Using title for gardening thumbnail: {display_text}")

print(f"📊 Length comparison - Hook: {len(hook)} chars, Title: {len(title)} chars")

# Canvas dimensions
w = 720
h = 1280

display_text += '\n'

# Safe zones for text
SAFE_ZONE_MARGIN = 40
TEXT_MAX_WIDTH = w - (2 * SAFE_ZONE_MARGIN)

def generate_thumbnail_huggingface(prompt):
    """🌱 Generate gardening thumbnail using Hugging Face"""
    try:
        hf_token = os.getenv('HUGGINGFACE_API_KEY')
        if not hf_token:
            print("⚠️ No HUGGINGFACE_API_KEY found")
            raise Exception("Missing token")

        headers = {"Authorization": f"Bearer {hf_token}"}
        
        # 🌱 Enhanced gardening-specific negative prompt
        negative_gardening = (
            "blurry, low quality, watermark, text, logo, frame, ugly, dull, "
            "dead plants, brown leaves, dying vegetation, wilted flowers, "
            "unhealthy soil, artificial plants, plastic plants, cartoon, anime"
        )
        
        payload = {
            "inputs": f"{prompt}, vibrant garden photography, lush plants, natural lighting, professional botanical photo",
            "parameters": {
                "negative_prompt": negative_gardening,
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "width": 720,
                "height": 1280,
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

            response = requests.post(url, headers=headers, json=payload, timeout=120)

            if response.status_code == 200 and len(response.content) > 1000:
                print(f"✅ Hugging Face model succeeded: {model}")
                return response.content
            elif response.status_code == 402:
                print(f"💰 {model} requires payment")
                continue
            elif response.status_code in [503, 429]:
                print(f"⌛ {model} is loading or rate-limited")
                continue
            else:
                print(f"⚠️ {model} failed ({response.status_code})")

        raise Exception("All Hugging Face models failed")

    except Exception as e:
        print(f"⚠️ Hugging Face thumbnail generation failed: {e}")
        raise

def generate_thumbnail_pollinations(prompt):
    """🌱 Pollinations backup for gardening thumbnails"""
    try:
        negative_terms = (
            "youtube logo, play button, watermark, ui, interface, overlay, "
            "branding, text, caption, words, title, subtitle, watermarking, "
            "frame, icon, symbol, graphics, arrows, shapes, low quality, distorted, "
            "dead plants, wilted, brown leaves, dying, unhealthy, artificial, plastic"
        )

        formatted_prompt = (
            f"{prompt}, vibrant garden photography, lush healthy plants, "
            "natural sunlight, botanical detail, professional photo, "
            "no text, no logos, no overlays"
        )

        seed = random.randint(1, 999999)

        url = (
            "https://image.pollinations.ai/prompt/"
            f"{requests.utils.quote(formatted_prompt)}"
            f"?width=720&height=1280"
            f"&negative={requests.utils.quote(negative_terms)}"
            f"&nologo=true&notext=true&enhance=true&clean=true"
            f"&seed={seed}&rand={seed}"
        )

        print(f"🌐 Pollinations gardening thumbnail (seed={seed})")
        response = requests.get(url, timeout=120)

        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            print(f"✅ Pollinations image generated")
            return response.content
        else:
            raise Exception(f"Pollinations failed: {response.status_code}")

    except Exception as e:
        print(f"⚠️ Pollinations thumbnail failed: {e}")
        raise

def generate_picsum_fallback(bg_path, topic=None, title=None):
    """🌱 Gardening-specific fallback with nature/plant photos"""
    import re, random, requests

    # 🌱 Always default to gardening keywords
    resolved_key = "garden"
    
    # Check for specific plant types in title
    if title:
        title_lower = title.lower()
        if any(word in title_lower for word in ["tomato", "vegetable", "herb"]):
            resolved_key = "vegetable"
        elif any(word in title_lower for word in ["flower", "bloom", "blossom"]):
            resolved_key = "flowers"
        elif any(word in title_lower for word in ["succulent", "cactus"]):
            resolved_key = "succulent"
        elif any(word in title_lower for word in ["houseplant", "indoor"]):
            resolved_key = "houseplant"

    print(f"🔎 Searching gardening fallback for '{resolved_key}'...")

    # Try Unsplash with gardening keywords
    try:
        seed = random.randint(1, 9999)
        url = f"https://source.unsplash.com/720x1280/?{requests.utils.quote(resolved_key)}&sig={seed}"
        print(f"🖼️ Unsplash gardening fallback (seed={seed})")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"✅ Unsplash gardening image saved")
            return bg_path
    except Exception as e:
        print(f"⚠️ Unsplash error: {e}")

    # 🌱 Try Pexels with curated gardening photo IDs
    try:
        gardening_pexels = {
            "garden": [1072824, 1301856, 2132250, 169523, 1459505, 2255441],
            "vegetable": [1327838, 6157049, 2255441, 169523, 1459505],
            "flowers": [736230, 1076758, 850359, 850704, 736228],
            "succulent": [1084199, 2132250, 5699808, 1084382],
            "houseplant": [1072824, 1084199, 2132250, 1459505, 1435904],
        }
        
        photo_ids = gardening_pexels.get(resolved_key, gardening_pexels["garden"])
        photo_id = random.choice(photo_ids)
        
        url = f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg?auto=compress&cs=tinysrgb&w=720&h=1280"
        print(f"📸 Pexels gardening photo (id={photo_id})")
        response = requests.get(url, timeout=30)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            
            img = Image.open(bg_path).convert("RGB")
            img = img.resize((720, 1280), Image.LANCZOS)
            img.save(bg_path, quality=95)
            print(f"✅ Pexels gardening image saved")
            return bg_path
    except Exception as e:
        print(f"⚠️ Pexels error: {e}")

    # Picsum fallback
    try:
        seed = random.randint(1, 1000)
        url = f"https://picsum.photos/720/1280?random={seed}"
        print(f"🎲 Picsum fallback (seed={seed})")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200:
            with open(bg_path, "wb") as f:
                f.write(response.content)
            return bg_path
    except Exception as e:
        print(f"⚠️ Picsum fallback failed: {e}")
        return None

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=4, max=20))
def generate_thumbnail_bg(topic, title):
    """🌱 Generate gardening thumbnail background"""
    bg_path = os.path.join(TMP, "thumb_bg.png")
    
    prompt = f"Vibrant garden thumbnail, {topic}, lush healthy plants, macro plant detail, natural sunlight, botanical photography, professional garden photo, high contrast, eye-catching, seed={random.randint(1000,9999)}"
    
    providers = [
        ("Pollinations", generate_thumbnail_pollinations),
        ("Hugging Face", generate_thumbnail_huggingface)
    ]
    
    for provider_name, provider_func in providers:
        try:
            print(f"🎨 Trying {provider_name} for gardening thumbnail")
            image_content = provider_func(prompt)
            with open(bg_path, "wb") as f:
                f.write(image_content)
            
            if os.path.getsize(bg_path) > 1000:
                print(f"✅ {provider_name} succeeded")
                return bg_path
                
        except Exception as e:
            print(f"⚠️ {provider_name} failed: {e}")
            continue

    print("🖼️ AI providers failed, trying gardening photo APIs")
    result = generate_picsum_fallback(bg_path, topic=topic, title=title)
    
    if result and os.path.exists(bg_path) and os.path.getsize(bg_path) > 1000:
        return bg_path
    
    # 🌱 Garden-themed gradient fallback
    print("⚠️ All providers failed, using garden gradient")
    img = Image.new("RGB", (720, 1280), (0, 0, 0))
    draw_grad = ImageDraw.Draw(img)
    
    # Forest green to vibrant green gradient
    color_top = GARDEN_COLORS['forest_green']
    color_bottom = GARDEN_COLORS['vibrant_green']
    
    for y in range(1280):
        ratio = y / 1280
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        draw_grad.line([(0, y), (720, y)], fill=(r, g, b))
    
    img.save(bg_path)
    return bg_path

# Generate gardening background
print("🌱 Generating gardening thumbnail background...")
bg_path = generate_thumbnail_bg(topic, title)
img = Image.open(bg_path).convert("RGB")

# Ensure exact dimensions
if img.size != (720, 1280):
    print(f"⚠️ Background is {img.size}, resizing to 720x1280...")
    img = img.resize((720, 1280), Image.LANCZOS)

# Enhance image (slightly more vibrant for gardening)
enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(1.4)  # Slightly higher for vibrant plants

enhancer = ImageEnhance.Color(img)
img = enhancer.enhance(1.3)  # More saturation for lush greens

img = img.convert("RGBA")

# Vignette
vignette = Image.new("RGBA", img.size, (0, 0, 0, 0))
vd = ImageDraw.Draw(vignette)

center_x, center_y = w // 2, h // 2
max_radius = int((w**2 + h**2)**0.5) // 2

for radius in range(0, max_radius, 20):
    alpha = int(100 * (radius / max_radius))
    vd.ellipse(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        outline=(0, 0, 0, alpha),
        width=30
    )

img = Image.alpha_composite(img, vignette)
draw = ImageDraw.Draw(img)

# Text wrapping logic (same as original)
dummy_img = Image.new('RGB', (1, 1))
dummy_draw = ImageDraw.Draw(dummy_img)

def smart_text_wrap(text, font_obj, max_width, draw_obj):
    """Wrap text based on actual rendered pixel width"""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw_obj.textbbox((0, 0), test_line, font=font_obj)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

# Find optimal font size
font_size = 75
min_font_size = 35
max_height = h * 0.35
text_lines = []

print(f"🎯 Finding optimal font size for gardening text...")

while font_size >= min_font_size:
    test_font = get_font_path(font_size, bold=True)
    wrapped_lines = smart_text_wrap(display_text, test_font, TEXT_MAX_WIDTH, dummy_draw)
    
    total_height = 0
    max_line_width = 0
    
    for line in wrapped_lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=test_font)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        total_height += line_height
        max_line_width = max(max_line_width, line_width)
    
    if len(wrapped_lines) > 1:
        total_height += (len(wrapped_lines) - 1) * 18
    
    if total_height <= max_height and max_line_width <= TEXT_MAX_WIDTH:
        text_lines = wrapped_lines
        print(f"✅ Font {font_size}px: {len(wrapped_lines)} lines")
        break
    
    font_size -= 3

if not text_lines:
    font_size = min_font_size
    test_font = get_font_path(font_size, bold=True)
    text_lines = smart_text_wrap(display_text, test_font, TEXT_MAX_WIDTH, dummy_draw)

main_font = get_font_path(font_size, bold=True)
print(f"📝 Final gardening thumbnail font: {font_size}px for {len(text_lines)} lines")

# Position text at top
top_limit = SAFE_ZONE_MARGIN + 80
start_y = int(h * 0.15)
start_y = max(start_y, top_limit)

# Draw text with shadows and stroke
line_spacing = 18
current_y = start_y

for i, line in enumerate(text_lines):
    bbox = draw.textbbox((0, 0), line, font=main_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x = (w - text_w) // 2
    y = current_y
    
    if x < SAFE_ZONE_MARGIN:
        x = SAFE_ZONE_MARGIN
    if x + text_w > w - SAFE_ZONE_MARGIN:
        x = w - SAFE_ZONE_MARGIN - text_w
    
    # Shadow
    shadow_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_overlay)
    
    for offset in [5, 4, 3, 2]:
        shadow_alpha = int(160 * (offset / 5))
        sd.text((x + offset, y + offset), line, font=main_font, fill=(0, 0, 0, shadow_alpha))
    
    img = Image.alpha_composite(img, shadow_overlay)
    
    # Stroke
    stroke_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    so = ImageDraw.Draw(stroke_overlay)
    
    stroke_width = 4
    for sx in range(-stroke_width, stroke_width + 1):
        for sy in range(-stroke_width, stroke_width + 1):
            if sx != 0 or sy != 0:
                so.text((x + sx, y + sy), line, font=main_font, fill=(0, 0, 0, 240))
    
    img = Image.alpha_composite(img, stroke_overlay)
    
    # White text
    text_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    to = ImageDraw.Draw(text_overlay)
    to.text((x, y), line, font=main_font, fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, text_overlay)
    
    current_y += text_h + line_spacing

# Save thumbnail
thumb_path = os.path.join(TMP, "thumbnail.png")
final_img = img.convert("RGB")

if final_img.size != (720, 1280):
    final_img = final_img.resize((720, 1280), Image.LANCZOS)

final_img = final_img.filter(ImageFilter.SHARPEN)
final_img.save(thumb_path, quality=95, optimize=True)

saved_img = Image.open(thumb_path)
print(f"✅ Saved gardening thumbnail to {thumb_path}")
print(f"   Size: {os.path.getsize(thumb_path) / 1024:.1f} KB")
print(f"   Dimensions: {saved_img.size}")
print(f"   Text lines: {len(text_lines)}")
print(f"   Text content: {text_lines}")
print(f"   Font size: {font_size}px")
print(f"🌱 Gardening thumbnail ready for upload!")