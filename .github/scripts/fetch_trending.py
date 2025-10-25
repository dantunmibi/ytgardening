import json
import time
import random
from typing import List, Dict, Any
import os
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Configure using the same pattern as your working script
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Use the same model selection logic as your working script
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

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)


def get_google_trends_gardening() -> List[str]:
    """Get real trending gardening searches from Google Trends (FREE - no API key needed)"""
    try:
        from pytrends.request import TrendReq
        
        print(f"🌱 Fetching Google Trends (Gardening)...")
        
        # Simplified initialization - let pytrends handle its own defaults
        try:
            pytrends = TrendReq(hl='en-US', tz=360)
        except Exception as init_error:
            print(f"   ⚠️ PyTrends initialization failed: {init_error}")
            return []
        
        relevant_trends = []
        
        # Try specific gardening-related keyword searches
        gardening_topics = [
            'indoor plants', 
            'vegetable garden', 
            'plant propagation', 
            'houseplants',
            'gardening tips'
        ]
        
        for topic in gardening_topics:
            try:
                print(f"   🔍 Searching trends for: {topic}")
                pytrends.build_payload([topic], timeframe='now 7-d', geo='')
                related = pytrends.related_queries()
                
                if topic in related and 'top' in related[topic]:
                    top_queries = related[topic]['top']
                    if top_queries is not None and not top_queries.empty:
                        for query in top_queries['query'].head(5):
                            if len(query) > 10:  # Filter very short queries
                                relevant_trends.append(query)
                                print(f"      ✓ {query}")
                
                time.sleep(2)  # Rate limiting between requests
                
            except Exception as e:
                print(f"   ⚠️ Failed for '{topic}': {str(e)[:50]}...")
                continue
        
        print(f"✅ Found {len(relevant_trends)} gardening-related trends from Google")
        return relevant_trends[:15]
        
    except ImportError:
        print("⚠️ pytrends not installed - run: pip install pytrends")
        return []
    except Exception as e:
        print(f"⚠️ Google Trends failed: {e}")
        return []


def get_gardening_news_rss() -> List[str]:
    """Scrape latest gardening news from RSS feeds (FREE)"""
    try:
        print("🌿 Fetching gardening news from RSS feeds...")
        
        # Working gardening RSS feeds (verified October 2024)
        rss_sources = [
            'https://www.finegardening.com/feed',
            'https://savvygardening.com/feed/',
            'https://empressofdirt.net/feed/',
            'https://plantcaretoday.com/feed',
            'https://www.gardenersworld.com/feed/',
            'https://www.gardeningchannel.com/feed/',
            'https://growagoodlife.com/feed/',

        ]
        
        headlines = []
        
        for feed_url in rss_sources:
            try:
                print(f"   📡 Fetching {feed_url}...")
                response = requests.get(feed_url, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                
                if response.status_code != 200:
                    print(f"      ⚠️ Status {response.status_code}")
                    continue
                
                # Try both XML and HTML parsing
                try:
                    soup = BeautifulSoup(response.content, 'xml')
                except:
                    soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try multiple title tag patterns
                items = soup.find_all('item')
                if not items:
                    items = soup.find_all('entry')  # Atom format
                
                print(f"      Found {len(items)} items")
                
                for item in items[:15]:
                    title = None
                    
                    # Try different title extraction methods
                    if item.find('title'):
                        title = item.find('title').text.strip()
                    elif item.find('content'):
                        title = item.find('content').text.strip()[:100]
                    
                    if title and len(title) > 15:
                        # More permissive filtering
                        gardening_words = [
                            'plant', 'grow', 'garden', 'seed', 'soil', 'water',
                            'flower', 'vegetable', 'herb', 'tree', 'pest', 'fertilizer',
                            'compost', 'prune', 'harvest', 'propagat', 'cutting', 'root',
                            'tips', 'how to', 'guide', 'best', 'easy'
                        ]
                        
                        headline_lower = title.lower()
                        if any(kw in headline_lower for kw in gardening_words):
                            headlines.append(title)
                            print(f"      ✓ {title[:60]}...")
                
            except Exception as e:
                print(f"   ⚠️ Failed to fetch {feed_url}: {str(e)[:50]}...")
                continue
        
        print(f"✅ Found {len(headlines)} relevant gardening headlines")
        return headlines[:15]
        
    except Exception as e:
        print(f"⚠️ RSS feed scraping failed: {e}")
        return []


def get_reddit_gardening_trends() -> List[str]:
    """Get trending posts from gardening subreddits (FREE - no API key)"""
    try:
        print("🌺 Fetching Reddit gardening trends...")
        
        subreddits = ['gardening', 'houseplants', 'vegetablegardening', 'indoorgarden', 'proplifting']
        trends = []
        
        for subreddit in subreddits:
            try:
                url = f'https://www.reddit.com/r/{subreddit}/hot.json?limit=20'
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                
                print(f"   📱 Fetching r/{subreddit}...")
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    posts_found = 0
                    
                    for post in data['data']['children'][:15]:
                        title = post['data']['title']
                        
                        # STRICT filtering: Only accept informational/tutorial content
                        good_phrases = [
                            'how to', 'how i', 'guide to', 'tips for', 'method for',
                            'update:', 'progress:', 'before and after', 'success:',
                            'hack:', 'technique', 'tutorial', 'diy', 'made this'
                        ]
                        
                        # Reject questions and help requests
                        bad_phrases = [
                            '?', 'help', 'dying', 'is this', 'what is', 'should i',
                            'why is', 'can i', 'will this', 'does this', 'am i',
                            'please', 'worried', 'concerned', 'wrong with', 'problem'
                        ]
                        
                        title_lower = title.lower()
                        
                        # Must have good phrase AND no bad phrases
                        has_good = any(phrase in title_lower for phrase in good_phrases)
                        has_bad = any(phrase in title_lower for phrase in bad_phrases)
                        
                        if has_good and not has_bad:
                            trends.append(title)
                            posts_found += 1
                            print(f"      ✓ {title[:70]}...")
                    
                    print(f"      Found {posts_found} tutorial/guide posts")
                else:
                    print(f"      ⚠️ Status {response.status_code}")
                
                time.sleep(2)  # Respectful rate limiting
                
            except Exception as e:
                print(f"   ⚠️ Failed to fetch r/{subreddit}: {e}")
                continue
        
        print(f"✅ Found {len(trends)} trending gardening topics from Reddit")
        return trends[:15]
        
    except Exception as e:
        print(f"⚠️ Reddit scraping failed: {e}")
        return []


def get_real_gardening_trends() -> List[str]:
    """Combine multiple FREE sources for real gardening trending topics"""
    
    print("\n" + "="*60)
    print("🌱 FETCHING REAL-TIME GARDENING TRENDS (FREE SOURCES)")
    print("="*60)
    
    all_trends = []
    
    # Source 1: Google Trends (gardening-specific)
    google_trends = get_google_trends_gardening()
    all_trends.extend(google_trends)
    
    # Source 2: Gardening News RSS
    gardening_news = get_gardening_news_rss()
    all_trends.extend(gardening_news)
    
    # Source 3: Reddit Gardening Communities
    reddit_trends = get_reddit_gardening_trends()
    all_trends.extend(reddit_trends)
    
    # Deduplicate and prioritize
    seen = set()
    unique_trends = []
    for trend in all_trends:
        trend_clean = trend.lower().strip()
        if trend_clean not in seen and len(trend) > 10:
            seen.add(trend_clean)
            unique_trends.append(trend)
    
    print(f"\n📊 Total unique gardening trends found: {len(unique_trends)}")
    
    return unique_trends[:25]  # Return top 25


def filter_and_rank_gardening_trends(trends: List[str], user_query: str) -> List[Dict[str, str]]:
    """Use Gemini to filter and rank gardening trends for viral potential"""
    
    if not trends:
        print("⚠️ No trends to filter, using fallback...")
        return get_fallback_gardening_ideas()
    
    print(f"\n🤖 Using Gemini to rank {len(trends)} real gardening trends for viral potential...")
    
    # Define the structure for the JSON output
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "selected_topics": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "reason": {"type": "STRING"},
                        "viral_score": {"type": "NUMBER"}
                    }
                },
                "description": "Top 5 gardening topics ranked by viral potential"
            }
        },
        "required": ["selected_topics"]
    }
    
    current_month = time.strftime('%B')
    
    prompt = f"""You are a viral gardening content strategist. Here are REAL trending gardening topics from today:

REAL TRENDING GARDENING TOPICS (from Google Trends, RSS, Reddit):
{chr(10).join(f"{i+1}. {t}" for i, t in enumerate(trends[:25]))}

CURRENT MONTH: {current_month}

TASK: Select the TOP 5 topics that would make the MOST VIRAL YouTube Shorts for gardeners.

SELECTION CRITERIA:
✅ Must be surprising, helpful, or solve a common problem
✅ Must have visual transformation potential for short-form video
✅ Must be currently trending (these are all real trends from today)
✅ Must appeal to home gardeners, plant parents, or urban farmers
✅ Must have "wow factor" - quick results, dramatic before/after, or mind-blowing hacks
✅ Prefer specific plant names and actionable techniques over general advice

FOCUS AREAS: {user_query}

OUTPUT FORMAT (JSON ONLY):
{{
  "selected_topics": [
    {{
      "title": "Specific catchy title with plant names or technique",
      "reason": "Why gardeners will love this and share it",
      "viral_score": 95
    }}
  ]
}}

GOOD EXAMPLES:
- "Propagate Pothos in 7 Days: The Paper Towel Trick"
- "Regrow Romaine Lettuce Forever From One Head"
- "Kill Spider Mites in 24 Hours With This Kitchen Ingredient"

Select 5 topics, ranked by viral_score (highest first)."""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            )
            
            result_text = response.text.strip()
            
            # Extract JSON if wrapped
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)
            
            data = json.loads(result_text)
            
            # Convert to expected format
            trending_ideas = []
            for item in data.get('selected_topics', [])[:5]:
                trending_ideas.append({
                    "topic_title": item.get('title', 'Unknown'),
                    "summary": item.get('reason', 'High viral potential for gardeners'),
                    "category": "Gardening",
                    "viral_score": item.get('viral_score', 90)
                })
            
            print(f"✅ Gemini ranked {len(trending_ideas)} viral gardening topics from real trends")
            return trending_ideas
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    # Fallback: Just use first 5 trends
    print("⚠️ Gemini ranking failed, using raw trends...")
    return [
        {
            "topic_title": trend,
            "summary": "Currently trending in gardening community",
            "category": "Gardening"
        }
        for trend in trends[:5]
    ]


def get_fallback_gardening_ideas() -> List[Dict[str, str]]:
    """Fallback gardening ideas if all methods fail"""
    current_month = time.strftime('%B')
    return [
        {
            "topic_title": "Propagate Snake Plants in Water: Zero-Fail Method",
            "summary": "Easy propagation technique perfect for beginners wanting to multiply their houseplants for free",
            "category": "Propagation"
        },
        {
            "topic_title": "Regrow Lettuce Forever From One Grocery Store Head",
            "summary": "Kitchen scrap gardening hack that gives you infinite salad from one purchase",
            "category": "Food Waste"
        },
        {
            "topic_title": "Coffee Grounds + Banana Peels: The Ultimate Free Fertilizer",
            "summary": "Turn kitchen waste into powerful plant food that rivals expensive fertilizers",
            "category": "Soil Health"
        },
        {
            "topic_title": f"What to Plant in {current_month} for Maximum Harvest",
            "summary": f"Seasonal planting guide for {current_month} to optimize your garden's productivity",
            "category": "Seasonal"
        },
        {
            "topic_title": "Kill Fungus Gnats in 24 Hours: Hydrogen Peroxide Trick",
            "summary": "Fast, natural solution to the most annoying houseplant pest using household items",
            "category": "Pest Control"
        }
    ]


if __name__ == "__main__":        
    # 🌱 Gardening-focused topic query
    topic_focus = "Gardening tips, plant propagation, container gardening, urban farming, composting, pest control, vegetable growing, herb gardens, flower care, seasonal planting guides, garden hacks, indoor plants, houseplant care, regrow from scraps for Ultra Engaging Youtube Shorts"
    
    # Get real trending gardening topics from free sources
    real_trends = get_real_gardening_trends()
    
    if real_trends:
        # Use Gemini to filter and rank for viral potential
        trending_ideas = filter_and_rank_gardening_trends(real_trends, topic_focus)
    else:
        print("⚠️ Could not fetch real gardening trends, using fallback...")
        trending_ideas = get_fallback_gardening_ideas()
    
    if trending_ideas:
        print(f"\n" + "="*60)
        print(f"🌱 TOP VIRAL GARDENING IDEAS (FROM REAL DATA)")
        print("="*60)
        
        for i, idea in enumerate(trending_ideas):
            print(f"\nIdea {i + 1}:")
            print(f"  Title: {idea['topic_title']}")
            print(f"  Category: {idea['category']}")
            print(f"  Summary: {idea['summary']}")
            if 'viral_score' in idea:
                print(f"  Viral Score: {idea['viral_score']}/100")
        
        # Save to file for use by other scripts
        trending_data = {
            "topics": [idea["topic_title"] for idea in trending_ideas],
            "full_data": trending_ideas,
            "generated_at": time.time(),
            "query": topic_focus,
            "niche": "gardening",
            "source": "google_trends + gardening_rss + reddit + gemini_ranking"
        }
        
        trending_file = os.path.join(TMP, "trending.json")
        with open(trending_file, "w") as f:
            json.dump(trending_data, f, indent=2)
        
        print(f"\n💾 Saved trending gardening data to: {trending_file}")
        print(f"🌿 Data sources: Google Trends (Gardening) + RSS Feeds + Reddit (100% FREE)")
    else:
        print("\n❌ Could not retrieve any trending gardening ideas.")