# .github/scripts/generate_trending_and_script.py (GARDENING VERSION)
import os
import json
import re
import hashlib
from datetime import datetime
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

os.makedirs(TMP, exist_ok=True)
HISTORY_FILE = os.path.join(TMP, "content_history.json")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

try:
    models = genai.list_models()
    model_name = None
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            if '2.0-flash' in m.name or '2.5-flash' in m.name:
                model_name = m.name
                break
            elif '1.5-flash' in m.name and not model_name:
                model_name = m.name
    
    if not model_name:
        model_name = "models/gemini-1.5-flash"
    
    print(f"✅ Using model: {model_name}")
    model = genai.GenerativeModel(model_name)
except Exception as e:
    print(f"⚠️ Error listing models: {e}")
    model = genai.GenerativeModel("models/gemini-1.5-flash")

def load_history():
    """Load history from previous run (if available)"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
                print(f"📂 Loaded {len(history.get('topics', []))} topics from history")
                return history
        except Exception as e:
            print(f"⚠️ Could not load history: {e}")
            return {'topics': []}
    
    print("📂 No previous history found, starting fresh")
    return {'topics': []}

def save_to_history(topic, script_hash, title):
    """Save to history file"""
    history = load_history()
    
    history['topics'].append({
        'topic': topic,
        'title': title,
        'hash': script_hash,
        'date': datetime.now().isoformat()
    })
    
    history['topics'] = history['topics'][-100:]
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"💾 Saved to history ({len(history['topics'])} total topics)")

def get_content_hash(data):
    """Generate hash of content to detect duplicates"""
    content = json.dumps(data, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()

def load_trending():
    """Load trending topics from fetch_trending.py"""
    trending_file = os.path.join(TMP, "trending.json")
    if os.path.exists(trending_file):
        with open(trending_file, 'r') as f:
            return json.load(f)
    return None

def is_similar_topic(new_title, previous_titles, similarity_threshold=0.6):
    """Check if topic is too similar to previous ones with decay factor"""
    new_words = set(new_title.lower().split())
    
    for idx, prev_title in enumerate(reversed(previous_titles)):
        prev_words = set(prev_title.lower().split())
        
        intersection = len(new_words & prev_words)
        union = len(new_words | prev_words)
        
        if union > 0:
            base_similarity = intersection / union
            decay_factor = 1.0 / (1.0 + idx * 0.02)
            adjusted_threshold = similarity_threshold * decay_factor
            
            if base_similarity > adjusted_threshold:
                days_ago = idx // 1
                print(f"⚠️ Topic too similar ({base_similarity:.2f} > {adjusted_threshold:.2f}) to: {prev_title}")
                print(f"   (from {days_ago} days ago)")
                return True
    
    return False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_script_with_retry(prompt):
    response = model.generate_content(prompt)
    return response.text.strip()

# Load history and trending
history = load_history()
trending = load_trending()

# Get previous topics
previous_topics = [f"{t.get('topic', 'unknown')}: {t.get('title', '')}" for t in history['topics'][-15:]]
previous_titles = [t.get('title', '') for t in history['topics']]

# ✅ CRITICAL: Extract real trending gardening topics and FORCE their use
trending_topics = []
trending_summaries = []

if trending and trending.get('topics'):
    trending_topics = trending['topics'][:5]
    
    # Get full data if available
    full_data = trending.get('full_data', [])
    if full_data:
        for item in full_data[:5]:
            trending_summaries.append(f"• {item['topic_title']}: {item.get('summary', 'No summary')}")
    else:
        trending_summaries = [f"• {t}" for t in trending_topics]
    
    print(f"🌱 Loaded {len(trending_topics)} REAL trending gardening topics from web sources")
    print(f"   Source: {trending.get('source', 'unknown')}")
else:
    print("⚠️ No trending data found - will use fallback")

# Build mandatory trending section
if trending_topics:
    trending_mandate = f"""
⚠️⚠️⚠️ CRITICAL MANDATORY REQUIREMENT ⚠️⚠️⚠️

YOU MUST CREATE A SCRIPT ABOUT ONE OF THESE REAL TRENDING GARDENING TOPICS:

{chr(10).join(trending_summaries)}

These are REAL trends from today ({datetime.now().strftime('%Y-%m-%d')}) collected from:
- Google Trends (real gardening search data)
- Gardening RSS feeds (latest headlines from Fine Gardening, Savvy Gardening, etc.)
- Reddit gardening communities (r/gardening, r/houseplants, etc.)

YOU MUST PICK ONE OF THE 5 TOPICS ABOVE. 
DO NOT create content about anything else.
DO NOT make up your own topic.
USE THE EXACT TREND and expand it into a viral gardening script.

If a trend is about "propagating pothos", your script MUST be about that specific plant propagation method.
If a trend is about "tomato blight solutions", your script MUST be about that exact problem and solution.
"""
else:
    trending_mandate = ""

# 🌱 GARDENING-SPECIFIC PROMPT WITH TRENDING ENFORCEMENT
prompt = f"""You are a viral gardening content creator with 20+ years of horticultural experience and millions of views.

CONTEXT:
- Current date: {datetime.now().strftime('%Y-%m-%d')}
- Current month: {datetime.now().strftime('%B')} (consider seasonal planting)
- Previously covered (DO NOT REPEAT THESE): 
{chr(10).join(f"  • {t}" for t in previous_topics) if previous_topics else '  None'}

{trending_mandate}

TASK: Create a trending, viral-worthy GARDENING script for a 45-75 second YouTube Short.

CRITICAL REQUIREMENTS:

✅ Focus on: Plant propagation, gardening hacks, pest solutions, container gardening, or seasonal planting
✅ Topic must be COMPLETELY DIFFERENT from previous topics above
✅ Hook must create INSTANT value or curiosity (Stop buying plants when... / This banana peel trick...)
✅ Include SPECIFIC plant names, measurements, or timeframes (not some fertilizer but 2 tablespoons Epsom salt)
✅ Use exact numbers and timelines (7 days not a few days, 1 inch not a small piece)
✅ Make it actionable - viewers should be able to DO this TODAY with items they have
✅ Avoid generic advice - be hyper-specific about methods
✅ CTA must be casual, helpful (Try this with celery next... not Subscribe...)
✅ Add 5-10 relevant hashtags including #gardening #planttok #shorts

CONTENT PILLARS (PICK ONE - BASED ON TRENDING SEARCHES):
1. **Orchid Care & Secrets (20%)** 🔥 HIGH DEMAND
   - "The secret to making orchids bloom nonstop"
   - "What to do with orchid aerial roots"
   - "Why your orchid won't bloom (and the fix)"
   - "Orchid ice cube watering trick that works"

2. **Raised Bed Gardening (20%)** 🔥 HIGH DEMAND
   - "7 raised bed gardening hacks pros use"
   - "Raised bed soil mixture that never fails"
   - "Maximize raised bed space: 3 secrets"
   - "Best vegetables for raised beds"

3. **Myth Busting & Testing (15%)** 🔥 VIRAL POTENTIAL
   - "Testing grow a garden myths you believed"
   - "Does Epsom salt really work for tomatoes?"
   - "Debunking 5 common gardening myths"
   - "I tested viral TikTok garden hacks"

4. **Must-Grow Plants (15%)** 🔥 LIST FORMAT
   - "9 plants you should always grow"
   - "Top 5 easiest vegetables for beginners"
   - "3 plants that pay for themselves"
   - "Perennials that come back year after year"

5. **Creative Gardening Ideas (10%)**
   - "Creative gardening ideas under $20"
   - "DIY vertical garden from pallets"
   - "Container garden combos that stun"
   - "Upcycle these into planters"

6. **Homestead & Self-Sufficiency (10%)**
   - "Homestead gardening tips for beginners"
   - "Grow 80% of your food in your backyard"
   - "Preserve your harvest: 3 easy methods"
   - "Seed saving for next year's garden"

7. **Plant Propagation & Growing (10%)**
   - Propagate in water, soil, or division
   - Grow from kitchen scraps
   - Turn cuttings into plants
   - Free plant multiplication

PROVEN VIRAL FORMULAS (BASED ON TRENDING SEARCHES):
- "Regrow [Plant] From [Unexpected Source]"
- "Stop [Mistake] - Do This Instead"
- "This [Ingredient] Trick [Amazing Result]"
- "3 Signs Your [Plant] Is [Problem] (Fix It Now)"
- "Grow [Plant] in [Small Space/Container]"
- "[Number] Plants You Should Always Grow"
- "The Secret to Making Your [Plant] [Result]"

CTA GUIDELINES:
❌ BAD: Comment which one..., Subscribe for more, Click the link
✅ GOOD: Try this with celery next, Save this before planting season, Tag me when yours sprouts

🔥 **HIGH-DEMAND TOPICS:**
- "The Secret to Making Your [Plant] [Result]" - orchids bloom nonstop, roses thrive
- "[Number] [Category] Hacks" - 7 raised bed hacks, 5 composting tricks
- "What to Do With [Plant Problem]" - orchid aerial roots, yellow leaves, leggy seedlings
- "Testing [Garden Myths/Hacks]" - TikTok trends, old wives' tales
- "[Number] Plants You Should Always Grow" - must-haves, never fails
- "[Category] Gardening Tips" - homestead tips, beginner tips, budget tips

🌱 **PROVEN FORMULAS:**
- "Regrow [Plant] From [Unexpected Source]" - grocery store scraps, kitchen waste
- "Stop [Mistake] - Do This Instead" - watering errors, fertilizing mistakes
- "This [Ingredient] Trick [Amazing Result]" - banana peels triple tomato harvest
- "3 Signs Your [Plant] Is [Problem] (Fix It Now)" - yellowing leaves, root rot
- "Grow [Plant] in [Small Space/Container]" - 50 pounds of potatoes in bucket
- "Why [Gardeners] Never [Common Practice]" - pros avoid top watering
- "Creative [Gardening] Ideas Under $[Budget]" - DIY projects, upcycling

SPECIFICITY RULES (VERY IMPORTANT):
DO NOT INCLUDE SPECIAL CHARACTERS OR QUOTES IN THE OUTPUT

❌ VAGUE: This fertilizer trick works wonders
✅ SPECIFIC: Mix 2 tablespoons Epsom salt per gallon of water for tomatoes

❌ VAGUE: Cut the plant and place in water
✅ SPECIFIC: Cut 4-6 inch stem below a node and place in filtered water

❌ VAGUE: Wait a few days for roots

✅ SPECIFIC: Roots appear in 7-10 days with daily water changes



❌ VAGUE: Plant in spring
✅ SPECIFIC: Plant tomatoes outdoors after last frost in mid-May

OUTPUT FORMAT (JSON ONLY - NO OTHER TEXT):
{{
  "title": "Specific, value-driven title with plant names (under 100 chars)",
  "topic": "gardening",
  "hook": "Immediate value or problem statement with specifics (under 12 words)",
  "bullets": [
    "First step - SPECIFIC with plant name, measurement, or timeline (15-20 words)",
    "Second step - SPECIFIC with plant name, measurement, or timeline (15-20 words)",
    "Third step - SPECIFIC with plant name, measurement, or timeline (15-20 words)"
  ],
  "cta": "Natural, helpful next step (under 15 words)",
  "hashtags": ["#gardening", "#planttok", "#gardentips", "#urbanfarming", "#shorts"],
  "description": "2-3 sentences with specific plant names and searchable keywords for YouTube",
  "visual_prompts": [
    "Vibrant close-up of healthy plant or garden scene for hook, natural lighting, macro photography",
    "Hands demonstrating step 1 with clear plant detail, close-up, natural outdoor setting",
    "Close-up of step 2 showing growth or technique, macro shot, bright natural light",
    "Final result showing thriving plant or harvest, satisfaction shot, vibrant colors"
  ]
}}

EXAMPLES OF GOOD GARDENING SCRIPTS:

Example 1:
{{
  "title": "Regrow Green Onions Forever From Grocery Store Scraps",
  "topic": "gardening",
  "hook": "Stop buying green onions when you can regrow them infinitely for free",
  "bullets": [
    "Cut the bottom one inch off store bought green onions with roots intact and place in a glass with water",
    "Change the water every two to three days and keep on a sunny windowsill for optimal photosynthesis and growth",
    "Harvest the green tops after seven days and they regrow continuously giving you free green onions forever"
  ],
  "cta": "Try this with celery and romaine lettuce next - same exact method works",
  "hashtags": ["#gardening", "#foodwaste", "#urbangarden", "#gardenhacks", "#shorts"]
}}

Example 2:
{{
  "title": "Eggshells Plus Coffee Grounds: The Ultimate Free Fertilizer",
  "topic": "gardening",
  "hook": "This kitchen waste combo makes plants grow twice as fast",
  "bullets": [
    "Crush five eggshells into small pieces and mix with two tablespoons of used coffee grounds in a mason jar",
    "Add one gallon of water and let steep for 48 hours to extract calcium and nitrogen nutrients",
    "Pour diluted mixture around tomato and pepper plants every two weeks for explosive growth and bigger yields"
  ],
  "cta": "Save your eggshells starting today - your plants will thank you",
  "hashtags": ["#gardening", "#composting", "#organicgarden", "#gardenhacks", "#shorts"]
}}

REMEMBER: 
- YOU MUST USE ONE OF THE 5 TRENDING GARDENING TOPICS PROVIDED ABOVE!
- Be SPECIFIC with plant names, measurements, and timeframes!
- Make it COMPLETELY DIFFERENT from previous topics!
- Make it so valuable viewers NEED to save and try it!
- Focus on what viewers can DO TODAY with what they have!"""

# Try generating script with multiple attempts
max_attempts = 5
attempt = 0

while attempt < max_attempts:
    try:
        attempt += 1
        print(f"🌱 Generating viral gardening script from REAL trends (attempt {attempt}/{max_attempts})...")
        
        raw_text = generate_script_with_retry(prompt)
        print(f"🔍 Raw output length: {len(raw_text)} chars")
        
        # Extract JSON
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
            print("✅ Extracted JSON from code block")
        else:
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                print("✅ Extracted JSON directly")
            else:
                raise ValueError("No JSON found in response")
        
        data = json.loads(json_text)
        
        # Validate required fields
        required_fields = ["title", "topic", "hook", "bullets", "cta"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # ✅ VALIDATE: Check if script actually uses one of the trending gardening topics
        if trending_topics:
            script_text = f"{data['title']} {data['hook']} {' '.join(data['bullets'])}".lower()
            
            # Check if ANY trending topic keyword appears in the script
            trend_keywords = []
            for topic in trending_topics:
                # Extract key words from trending topic (remove common words)
                words = [w for w in topic.lower().split() if len(w) > 4 and w not in [
                    'this', 'that', 'with', 'from', 'will', 'just', 'grow', 'plant',
                    'your', 'the', 'how', 'best', 'easy', 'tips', 'guide'
                ]]
                trend_keywords.extend(words)
            
            # Check if at least 2 trending keywords appear
            matches = sum(1 for kw in trend_keywords if kw in script_text)
            
            if matches < 2:
                print(f"⚠️ Script doesn't use trending gardening topics! Only {matches} keyword matches.")
                print(f"   Trending keywords: {trend_keywords[:10]}")
                print(f"   Script text: {script_text[:200]}...")
                raise ValueError("Script ignores trending topics - regenerating...")
        
        # Force topic to be gardening
        data["topic"] = "gardening"
        
        # Add optional fields with defaults
        if "hashtags" not in data:
            data["hashtags"] = ["#gardening", "#planttok", "#gardenhacks", "#urbangarden", "#shorts"]
        
        if "description" not in data:
            data["description"] = f"{data['title']} - {data['hook']} #gardening #planttips #shorts"
        
        if "visual_prompts" not in data or len(data["visual_prompts"]) < 4:
            data["visual_prompts"] = [
                f"Vibrant garden scene or plant close-up for: {data['hook']}, natural lighting, macro photography, lush green",
                f"Hands working with plants demonstrating: {data['bullets'][0]}, close-up, outdoor setting, natural light",
                f"Plant growth or technique showing: {data['bullets'][1]}, macro detail, bright natural lighting",
                f"Thriving plant or harvest result: {data['bullets'][2]}, satisfaction shot, vibrant colors, healthy growth"
            ]
        
        if not isinstance(data["bullets"], list) or len(data["bullets"]) < 3:
            raise ValueError("bullets must be a list with at least 3 items")
        
        # Check for duplicates
        content_hash = get_content_hash(data)
        if content_hash in [t.get('hash') for t in history['topics']]:
            print("⚠️ Generated duplicate content (exact match), regenerating...")
            raise ValueError("Duplicate content detected")
        
        # Check for similar topics
        if is_similar_topic(data['title'], previous_titles):
            print("⚠️ Topic too similar to previous, regenerating...")
            raise ValueError("Similar topic detected")
        
        # Success! Save to history
        save_to_history(data['topic'], content_hash, data['title'])
        
        print("✅ Gardening script generated successfully from REAL trending data")
        print(f"   Title: {data['title']}")
        print(f"   Topic: {data['topic']}")
        print(f"   Hook: {data['hook']}")
        print(f"   Hashtags: {', '.join(data['hashtags'][:5])}")
        
        break  # Success, exit loop
        
    except Exception as e:
        print(f"❌ Attempt {attempt} failed: {e}")
        
        if attempt >= max_attempts:
            print("⚠️ Max attempts reached, using gardening fallback script...")
            data = {
                "title": "Regrow Green Onions Forever From Grocery Store Scraps",
                "topic": "gardening",
                "hook": "Stop buying green onions when you can regrow them infinitely for free",
                "bullets": [
                    "Cut the bottom one inch off store bought green onions with roots intact and place in a glass with water",
                    "Change the water every two to three days and keep on a sunny windowsill for optimal photosynthesis and growth",
                    "Harvest the green tops after seven days and they regrow continuously giving you free green onions forever"
                ],
                "cta": "Try this with celery and romaine lettuce next - same exact method works",
                "hashtags": ["#gardening", "#foodwaste", "#urbangarden", "#gardenhacks", "#shorts"],
                "description": "Regrow green onions infinitely from grocery store scraps. Cut bottom inch with roots, place in water, change water every 2-3 days. Harvest tops after 7 days for continuous free green onions. #gardening #foodwaste #planttok",
                "visual_prompts": [
                    "Fresh green onions on wooden cutting board next to clear glass of water, bright kitchen setting, natural morning light, vibrant colors",
                    "Hands cutting bottom inch of green onion showing white roots, close-up macro photography, sharp focus on roots and bulb detail",
                    "Green onion roots in clear glass with water on sunny windowsill, growth progress visible, time-lapse style, condensation on glass",
                    "Fully regrown green onions being harvested with kitchen scissors, vibrant green tops, satisfaction shot, abundant growth"
                ]
            }
            
            # Save fallback to history too
            fallback_hash = get_content_hash(data)
            save_to_history(data['topic'], fallback_hash, data['title'])

# Save script to file
os.makedirs(TMP, exist_ok=True)
script_path = os.path.join(TMP, "script.json")

with open(script_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"✅ Saved gardening script to {script_path}")
print(f"📊 Total topics in history: {len(history['topics'])}")
print(f"📝 Script preview:")
print(f"   Title: {data['title']}")
print(f"   Bullets: {len(data['bullets'])} points")
print(f"   Visual prompts: {len(data['visual_prompts'])} images")

if trending:
    print(f"\n🌐 Source: {trending.get('source', 'Unknown')}")
    print(f"   Trending gardening topics used: {', '.join(trending_topics[:3])}...")