# .github/scripts/manage_playlists.py
import os
import json
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from collections import defaultdict
import re
import difflib

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
PLAYLIST_CONFIG_FILE = os.path.join(TMP, "playlist_config.json")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")

# ---- Authenticate YouTube API ----
def get_youtube_client():
    """Authenticate and return YouTube API client"""
    try:
        creds = Credentials(
            None,
            refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/youtube"]
        )
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        print("✅ YouTube API authenticated")
        return youtube
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        raise

# ---- Gardening Playlist Configuration ----
PLAYLIST_RULES = {
    "gardening": {
        "propagation": {
            "title": "🌱 Plant Propagation & Multiplication",
            "description": "Learn how to multiply your plants for free! Propagation methods, cuttings, division, and seed starting.",
            "keywords": [
                "propagate", "propagation", "cuttings", "division", "seeds", "seed starting",
                "multiply plants", "free plants", "plant babies", "rooting", "water propagation",
                "soil propagation", "air layering", "pups", "offsets", "regrow", "grow from cuttings",
                "clone plants", "vegetative propagation", "stem cuttings", "leaf cuttings"
            ]
        },
        "hacks": {
            "title": "🛠️ Gardening Hacks & Life Tips",
            "description": "Shortcuts, DIY solutions, and clever gardening tricks that save time and money.",
            "keywords": [
                "hack", "tip", "trick", "diy", "life hack", "shortcut", "clever", "smart gardening",
                "budget gardening", "money saving", "repurpose", "upcycle", "homemade", "natural solution",
                "coffee grounds", "eggshells", "banana peel", "epsom salt", "vinegar", "baking soda",
                "household items", "free fertilizer", "water hack", "space saving", "organization"
            ]
        },
        "pests": {
            "title": "🐛 Pest & Disease Solutions",
            "description": "Identify, prevent, and treat common garden pests and plant diseases naturally.",
            "keywords": [
                "pest", "disease", "aphids", "spider mites", "mealybugs", "fungus gnats", "root rot",
                "yellow leaves", "brown spots", "wilting", "mold", "mildew", "treatment", "prevention",
                "natural pest control", "organic spray", "neem oil", "dish soap", "beneficial insects",
                "save plant", "rescue", "diagnose", "plant doctor", "symptoms", "healthy plants"
            ]
        },
        "urban": {
            "title": "🏙️ Urban & Small Space Gardening",
            "description": "Grow food and plants in apartments, balconies, and small spaces. Container gardening solutions.",
            "keywords": [
                "urban gardening", "small space", "apartment", "balcony", "container", "pot", "vertical",
                "indoors", "windowsill", "limited space", "city gardening", "rental gardening", "portable",
                "compact", "space efficient", "grow bags", "hanging baskets", "wall garden", "herb garden",
                "microgreens", "sprouts", "indoor vegetables", "patio gardening"
            ]
        },
        "seasonal": {
            "title": "📅 Seasonal Planting Guides",
            "description": "What to plant when - monthly and seasonal gardening guides for maximum harvest.",
            "keywords": [
                "seasonal", "planting guide", "what to plant", "monthly", "spring", "summer", "fall", "winter",
                "garden calendar", "planting schedule", "timing", "frost date", "growing season", "zone",
                "annuals", "perennials", "vegetables", "herbs", "flowers", "bulbs", "seeds", "transplant",
                "harvest", "succession planting", "crop rotation"
            ]
        },
        "vegetables": {
            "title": "🍅 Vegetable & Herb Growing",
            "description": "Grow your own food! Tomato, pepper, lettuce, herb and vegetable growing guides.",
            "keywords": [
                "vegetable", "herb", "tomato", "pepper", "lettuce", "basil", "mint", "rosemary", "cilantro",
                "cucumber", "zucchini", "carrot", "radish", "green onion", "spinach", "kale", "potato",
                "onion", "garlic", "edible garden", "kitchen garden", "grow food", "homegrown", "organic",
                "harvest", "yield", "fruit", "leafy greens", "root vegetables"
            ]
        },
        "soil": {
            "title": "🌿 Soil Health & Composting",
            "description": "Build healthy soil, make compost, and create the perfect growing environment.",
            "keywords": [
                "soil", "compost", "fertilizer", "nutrients", "ph", "drainage", "aeration", "organic matter",
                "worm castings", "compost tea", "mulch", "topsoil", "potting mix", "soil recipe", "amendments",
                "perlite", "vermiculite", "coco coir", "peat moss", "manure", "bone meal", "blood meal",
                "soil test", "microbes", "mycorrhizae", "healthy roots"
            ]
        },
        "flowers": {
            "title": "💐 Flower Care & Landscaping",
            "description": "Beautiful flowers, flowering plants, and landscape design tips for stunning gardens.",
            "keywords": [
                "flower", "bloom", "blossom", "petal", "annual flowers", "perennial flowers", "rose", "lavender",
                "sunflower", "marigold", "petunia", "geranium", "succulent", "cactus", "orchid", "peace lily",
                "pothos", "monstera", "snake plant", "landscaping", "garden design", "color scheme", "arrangement",
                "cut flowers", "bouquet", "pruning", "deadheading", "flowering", "bloom boost"
            ]
        }
    }
}

# ---- Core Functions ----

def fetch_and_map_existing_playlists(youtube, niche, config):
    """Fetch your existing channel playlists and map them to categories if titles match"""
    print("🔄 Fetching existing playlists from channel...")
    existing_playlists = {}
    nextPageToken = None
    while True:

        response = youtube.playlists().list(

            part="snippet",

            mine=True,

            maxResults=50,

            pageToken=nextPageToken

        ).execute()

        for item in response.get("items", []):

            existing_playlists[item["snippet"]["title"].lower()] = item["id"]

        nextPageToken = response.get("nextPageToken")

        if not nextPageToken:

            break



    # Map to your categories using fuzzy matching

    for category, rules in PLAYLIST_RULES[niche].items():

        key = f"{niche}_{category}"

        match = None

        for title, pid in existing_playlists.items():

            ratio = difflib.SequenceMatcher(None, rules["title"].lower(), title).ratio()

            if ratio > 0.6:

                match = pid

                break

        if match:

            if key in config and config[key] != match:

                print(f"♻️ Updated stale playlist ID for '{rules['title']}' -> {match}")

            else:

                print(f"✅ Mapped existing playlist '{rules['title']}' -> {match}")

            config[key] = match



            print(f"✅ Mapped existing playlist '{rules['title']}' -> {match}")

    return config


def load_upload_history():
    """Load video upload history"""
    if os.path.exists(UPLOAD_LOG):
        try:
            with open(UPLOAD_LOG, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def load_playlist_config():
    """Load existing playlist IDs"""
    if os.path.exists(PLAYLIST_CONFIG_FILE):
        try:
            with open(PLAYLIST_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_playlist_config(config):
    """Save playlist configuration"""
    with open(PLAYLIST_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"💾 Saved playlist config: {len(config)} playlists")

def get_or_create_playlist(youtube, niche, category, config):
    """
    Get existing playlist ID from config or create a new playlist if it doesn't exist.
    """
    playlist_key = f"{niche}_{category}"

    if playlist_key in config:
        print(f"✅ Using existing playlist: {playlist_key} (ID: {config[playlist_key]})")
        return config[playlist_key]

    # Create new playlist
    try:
        playlist_info = PLAYLIST_RULES[niche][category]
        title = playlist_info.get("title", "Untitled Playlist")
        description = playlist_info.get("description", "")
        
        # Add channel branding to description
        full_description = f"{description}\n\n🌱 Garden Glow Up - Daily gardening hacks that actually work!\nFollow for more plant tips and garden transformations."
        tags = playlist_info.get("tags", [])

        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": full_description,
                    "tags": tags
                },
                "status": {"privacyStatus": "public"}
            }
        )
        response = request.execute()
        playlist_id = response["id"]

        config[playlist_key] = playlist_id
        save_playlist_config(config)
        print(f"🎉 Created new playlist: {title} (ID: {playlist_id})")
        return playlist_id

    except Exception as e:
        print(f"❌ Failed to create playlist: {e}")
        return None

def categorize_video(video_metadata, niche):
    """Smart categorization for Gardening Shorts: fuzzy + keyword matching"""
    text = " ".join([
        video_metadata.get("title", ""),
        video_metadata.get("description", ""),
        video_metadata.get("topic", ""),
        " ".join(video_metadata.get("hashtags", []))
    ]).lower()

    if niche not in PLAYLIST_RULES:
        return None

    scores = {}
    for category, rules in PLAYLIST_RULES[niche].items():
        score = 0
        # Exact keyword matches
        for kw in rules["keywords"]:
            kw = kw.lower()
            if kw in text:
                score += 3
            # Partial matches and related terms
            for word in kw.split():
                if len(word) > 3:  # Only consider words longer than 3 characters
                    if word in text:
                        score += 2
                    else:
                        # Fuzzy matching for similar words
                        for text_word in text.split():
                            if len(text_word) > 3:
                                match_ratio = difflib.SequenceMatcher(None, word, text_word).ratio()
                                if match_ratio > 0.8:
                                    score += 1
        
        # Bonus points for category-specific plant names
        category_plants = {
            "propagation": ["pothos", "spider plant", "succulent", "monstera", "philodendron"],
            "vegetables": ["tomato", "pepper", "lettuce", "basil", "cucumber", "carrot"],
            "flowers": ["rose", "lavender", "sunflower", "marigold", "orchid", "petunia"],
            "pests": ["aphid", "mite", "mealybug", "fungus", "mold", "rot"],
            "urban": ["apartment", "balcony", "container", "vertical", "indoor"],
            "seasonal": ["spring", "summer", "fall", "winter", "month", "season"],
            "soil": ["compost", "fertilizer", "soil", "nutrient", "ph"],
            "hacks": ["hack", "trick", "tip", "diy", "homemade"]
        }
        
        if category in category_plants:
            for plant in category_plants[category]:
                if plant in text:
                    score += 2
        
        if score > 0:
            scores[category] = score

    if scores:
        best_category = max(scores, key=scores.get)
        print(f"   📂 Categorized as: {best_category} (score: {scores[best_category]})")
        return best_category

    print("   ⚠️ No category match found, defaulting to 'hacks'")
    return "hacks"  # Default category for gardening content

def add_video_to_playlist(youtube, video_id, playlist_id):
    """
    Add video to playlist only if it's not already there.
    Handles newly created playlists with retry logic.
    """
    import time
    
    # Get existing videos in playlist with retry for newly created playlists
    existing_videos = set()
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            nextPageToken = None
            while True:
                request = youtube.playlistItems().list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=nextPageToken
                )
                response = request.execute()
                for item in response.get("items", []):
                    existing_videos.add(item["snippet"]["resourceId"]["videoId"])
                nextPageToken = response.get("nextPageToken")
                if not nextPageToken:
                    break
            # Success - break out of retry loop
            break
            
        except HttpError as e:
            if e.resp.status == 404 and attempt < max_retries - 1:
                # Playlist not found - likely just created, wait and retry
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"      ⏳ Playlist not ready yet, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                # Final attempt failed or different error
                print(f"      ⚠️ Could not check existing videos: {e}")
                # Continue anyway to try adding the video
                break

    if video_id in existing_videos:
        print("      ℹ️ Video already in playlist, skipping")
        return False

    # Add video with retry logic
    for attempt in range(max_retries):
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id}
                    }
                }
            ).execute()
            print("      ✅ Added to playlist")
            return True

        except HttpError as e:
            if e.resp.status == 404 and attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"      ⏳ Playlist not ready, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"      ❌ Failed to add video: {e}")
                return False
        except Exception as e:
            print(f"      ❌ Failed to add video: {e}")
            return False
    
    return False

def organize_playlists(youtube, history, config, niche):
    """Main function to organize videos into playlists"""
    print(f"\n🎬 Organizing {len(history)} videos into playlists...")
    print(f"   Niche: {niche}")
    
    stats = {
        "total_videos": len(history),
        "categorized": 0,
        "added_to_playlists": 0,
        "already_in_playlists": 0,
        "failed": 0
    }
    
    for video in history:
        video_id = video.get("video_id")
        title = video.get("title", "Unknown")
        
        if not video_id:
            continue
        
        print(f"\n📹 Processing: {title}")
        
        # Determine category
        category = categorize_video(video, niche)
        
        if not category:
            stats["failed"] += 1
            continue
        
        stats["categorized"] += 1
        
        # Get or create playlist
        playlist_id = get_or_create_playlist(youtube, niche, category, config)
        
        if not playlist_id:
            stats["failed"] += 1
            continue
        
        # Add video to playlist
        success = add_video_to_playlist(youtube, video_id, playlist_id)
        
        if success:
            stats["added_to_playlists"] += 1
        else:
            stats["already_in_playlists"] += 1
    
    return stats

def print_playlist_summary(config, niche):
    """Print summary of all playlists"""
    print("\n" + "="*60)
    print("📋 GARDENING PLAYLIST SUMMARY")
    print("="*60)
    
    if niche in PLAYLIST_RULES:
        for category, rules in PLAYLIST_RULES[niche].items():
            playlist_key = f"{niche}_{category}"
            
            if playlist_key in config:
                playlist_id = config[playlist_key]
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                
                print(f"\n{rules['title']}")
                print(f"   📍 Category: {category}")
                print(f"   🔗 URL: {playlist_url}")
                print(f"   📝 Description: {rules['description'][:80]}...")
            else:
                print(f"\n⚠️ {rules['title']}")
                print(f"   Status: Not yet created (will be auto-created)")

# ---- Main Execution ----
if __name__ == "__main__":
    print("🌿 Garden Glow Up - YouTube Playlist Auto-Organizer")
    print("="*60)
    
    # Set niche to gardening
    niche = "gardening"
    print(f"🎯 Channel Niche: {niche}")
    
    # Load data
    history = load_upload_history()
    config = load_playlist_config()
    
    if not history:
        print("⚠️ No upload history found. Upload some gardening videos first!")
        exit(0)
    
    print(f"📂 Found {len(history)} gardening videos in history")
    
    # Authenticate
    youtube = get_youtube_client()

    # Map existing playlists from your channel
    config = fetch_and_map_existing_playlists(youtube, niche, config)
    save_playlist_config(config)
    
    # Organize videos
    stats = organize_playlists(youtube, history, config, niche)
    
    # Print results
    print("\n" + "="*60)
    print("📊 ORGANIZATION RESULTS")
    print("="*60)
    print(f"🌱 Total videos processed: {stats['total_videos']}")
    print(f"✅ Successfully categorized: {stats['categorized']}")
    print(f"📥 Added to playlists: {stats['added_to_playlists']}")
    print(f"📋 Already in playlists: {stats['already_in_playlists']}")
    print(f"❌ Failed/Skipped: {stats['failed']}")
    
    # Print playlist summary
    print_playlist_summary(config, niche)
    
    print("\n✅ Gardening playlist organization complete!")
    print("\n💡 Tip: Your playlists will automatically grow with each new gardening video upload!")
    print("   This helps viewers discover more of your content and boosts watch time! 🌟")