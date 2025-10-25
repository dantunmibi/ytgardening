# .github/scripts/upload_youtube.py
import os
import json
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from tenacity import retry, stop_after_attempt, wait_exponential
from PIL import Image
import re 

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
VIDEO = os.path.join(TMP, "short.mp4")
THUMB = os.path.join(TMP, "thumbnail.png")
READY_VIDEO = os.path.join(TMP, "short_ready.mp4")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")

# 🌱 GARDENING CHANNEL CONFIG
CHANNEL_NAME = "Sprout Snap"
CHANNEL_TAGLINE = "Rapid gardening wins under 60 seconds 🌱"

# ---- Load Global Metadata ONCE ----
try:
    with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print("❌ Error: script.json not found.")
    raise

title = data.get("title", "Garden Tip")
description = data.get("description", f"{title}")
hashtags = data.get("hashtags", ["#gardening", "#planttok", "#shorts"])
topic = data.get("topic", "gardening")

# ---- Step 1: Validate video ----
if not os.path.exists(VIDEO):
    raise FileNotFoundError(f"Video file not found: {VIDEO}")

video_size_mb = os.path.getsize(VIDEO) / (1024 * 1024)
print(f"📹 Gardening video file found: {VIDEO} ({video_size_mb:.2f} MB)")
if video_size_mb < 0.1:
    raise ValueError("Video file is too small, likely corrupted")

# ---- Step 2: Rename video to safe filename ----
safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
video_output_path = os.path.join(TMP, f"{safe_title}.mp4")

if VIDEO != video_output_path:
    if os.path.exists(VIDEO):
        try:
            os.rename(VIDEO, video_output_path)
            VIDEO = video_output_path
            print(f"🎬 Final gardening video renamed to: {video_output_path}")
        except Exception as e:
            print(f"⚠️ Renaming failed: {e}. Using original path.")
    else:
        print("⚠️ Video file not found before rename.")
else:
    print("🎬 Video already has the correct filename.")

# ---- Step 3: Authenticate ----
try:
    creds = Credentials(
        None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    print("✅ YouTube API authenticated")
except Exception as e:
    print(f"❌ Authentication failed: {e}")
    raise

# ---- Step 4: 🌱 Prepare GARDENING-OPTIMIZED metadata ----
# Enhanced description with gardening-specific CTAs and keywords
enhanced_description = f"""{description}

{' '.join(hashtags)}

🌱 {CHANNEL_TAGLINE}

---
📅 New gardening tips daily!
🌿 Grow smarter, greener, and faster with daily plant hacks.
💚 Follow {CHANNEL_NAME} for more plant care hacks
🌱 Topics: Plant Care • Propagation • Urban Gardening • Garden Hacks

Follow Sprout Snap:
YouTube   : @SproutSnap
Instagram : @SproutSnap
TikTok    : @SproutSnap
Facebook  : Sprout Snap

Created: {datetime.now().strftime('%Y-%m-%d')}
Category: Gardening & Home
"""

# 🌱 GARDENING-SPECIFIC TAGS (optimized for discovery)
gardening_base_tags = [
    "gardening",
    "gardening tips",
    "plant care",
    "garden hacks",
    "urban gardening",
    "container gardening",
    "houseplants",
    "propagation",
    "grow your own food",
    "organic gardening",
    "garden shorts",
    "planttok",
    "plant parent"
]

# Combine with script hashtags
tags = gardening_base_tags.copy()
if hashtags:
    tags.extend([tag.replace('#', '').lower() for tag in hashtags[:10]])
tags.append("shorts")
tags.append("viral")

# Remove duplicates and limit to 15 tags (YouTube limit is 500 chars, ~15 tags is safe)
tags = list(dict.fromkeys(tags))[:15]

print(f"📝 Gardening metadata ready:")
print(f"   Title: {title}")
print(f"   Channel: {CHANNEL_NAME}")
print(f"   Tags: {', '.join(tags[:10])}...")
print(f"   Hashtags: {' '.join(hashtags[:5])}...")

snippet = {
    "title": title[:100],  # YouTube limit
    "description": enhanced_description[:5000],  # YouTube limit
    "tags": tags,
    "categoryId": "26"  # 🌱 Category 26 = "Howto & Style" (better for gardening than 28-Science)
}

body = {
    "snippet": snippet,
    "status": {
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": False,
        "madeForKids": False
    }
}

print(f"📤 Uploading gardening video to YouTube...")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
def upload_video(youtube_client, video_path, metadata):
    media = MediaFileUpload(
        video_path,
        chunksize=1024*1024,
        resumable=True,
        mimetype="video/mp4"
    )
    
    request = youtube_client.videos().insert(
        part="snippet,status",
        body=metadata,
        media_body=media
    )
    
    response = None
    last_progress = 0
    
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            if progress != last_progress and progress % 10 == 0:
                print(f"⏳ Upload progress: {progress}%")
                last_progress = progress
    return response

try:
    print("🚀 Starting gardening video upload...")
    result = upload_video(youtube, VIDEO, body)
    video_id = result["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    shorts_url = f"https://www.youtube.com/shorts/{video_id}"
    
    print(f"✅ Gardening video uploaded successfully!")
    print(f"   Video ID: {video_id}")
    print(f"   Watch URL: {video_url}")
    print(f"   Shorts URL: {shorts_url}")

except HttpError as e:
    print(f"❌ HTTP error during upload: {e}")
    error_content = e.content.decode() if hasattr(e, 'content') else str(e)
    print(f"   Error details: {error_content}")
    raise
except Exception as e:
    print(f"❌ Upload failed: {e}")
    raise

# ---- Step 6: Set thumbnail (desktop view) ----
if os.path.exists(THUMB):
    try:
        print("🖼️ Setting gardening thumbnail for desktop views...")
        thumb_size_mb = os.path.getsize(THUMB) / (1024*1024)
        if thumb_size_mb > 2:
            print(f"⚠️ Compressing thumbnail ({thumb_size_mb:.2f}MB)...")
            img = Image.open(THUMB)
            # 🌱 Optimize thumbnail with good quality for garden imagery
            img.save(THUMB, quality=90, optimize=True)
        
        youtube.thumbnails().set(
            videoId=video_id, 
            media_body=MediaFileUpload(THUMB)
        ).execute()
        print("✅ Gardening thumbnail set successfully (desktop view).")
    except Exception as e:
        print(f"⚠️ Thumbnail upload failed: {e}")
else:
    print("⚠️ No thumbnail file found, skipping thumbnail set.")

# ---- Step 7: 🌱 Save upload history with gardening analytics ----
upload_metadata = {
    "video_id": video_id,
    "title": title,
    "topic": topic,
    "channel": CHANNEL_NAME,
    "upload_date": datetime.now().isoformat(),
    "video_url": video_url,
    "shorts_url": shorts_url,
    "hashtags": hashtags,
    "file_size_mb": round(video_size_mb, 2),
    "tags": tags,
    "category": "Gardening & Home",
    "content_type": "gardening_short"
}

history = []
if os.path.exists(UPLOAD_LOG):
    try:
        with open(UPLOAD_LOG, 'r') as f:
            history = json.load(f)
    except:
        history = []

history.append(upload_metadata)
history = history[-100:]  # Keep last 100 uploads

with open(UPLOAD_LOG, 'w') as f:
    json.dump(history, f, indent=2)

# 🌱 Analytics summary
total_uploads = len(history)
print(f"\n📊 Channel Stats: {total_uploads} gardening videos uploaded total")

print("\n" + "="*70)
print("🎉 GARDENING VIDEO UPLOAD COMPLETE!")
print("="*70)
print(f"🌱 Channel: {CHANNEL_NAME}")
print(f"📹 Title: {title}")
print(f"🏷️  Topic: {topic}")
print(f"🆔 Video ID: {video_id}")
print(f"🔗 Shorts URL: {shorts_url}")
print(f"#️⃣  Hashtags: {' '.join(hashtags[:5])}")
print(f"🏷️  Tags: {', '.join(tags[:8])}...")
print("="*70)
print("\n💡 Gardening Channel Tips:")
print("   • Best posting time: 6-8 AM (morning gardeners) or 6-8 PM (evening)")
print("   • Peak season: March-May (spring planting)")
print("   • Engage with comments within 2 hours for algorithm boost")
print("   • Cross-post to TikTok 2 hours after YouTube")
print(f"\n🔗 Share this URL: {shorts_url}")
print("🌱 Keep growing! 🌿")