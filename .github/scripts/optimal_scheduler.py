# .github/scripts/optimal_scheduler.py (GARDENING VERSION)
import os
import json
from datetime import datetime, timedelta
import pytz

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

# Your timezone (Lagos, Nigeria)
LOCAL_TZ = pytz.timezone('Africa/Lagos')  # WAT (UTC+1)
current = datetime.now(tz=LOCAL_TZ)
weekday = current.weekday()
hour = current.hour

# GARDENING-SPECIFIC OPTIMAL POSTING SCHEDULE
# Based on research: Gardeners are most active on weekends (especially Saturday mornings)
# and weekday evenings after work (5-7 PM) when they check garden progress or plan activities
OPTIMAL_SCHEDULE = {
    0: [  # Monday - Low priority (back to work)
        {"time": "18:00", "priority": "medium", "content_type": "weekly_planning"},
        {"time": "20:00", "priority": "low", "content_type": "inspiration"}
    ],
    1: [  # Tuesday - Moderate (mid-week planning)
        {"time": "12:00", "priority": "medium", "content_type": "quick_tips"},
        {"time": "18:30", "priority": "medium", "content_type": "problem_solving"}
    ],
    2: [  # Wednesday - BEST WEEKDAY for general audience
        {"time": "16:00", "priority": "high", "content_type": "propagation"},
        {"time": "19:00", "priority": "high", "content_type": "trending_hack"}
    ],
    3: [  # Thursday - Planning for weekend gardening
        {"time": "17:00", "priority": "high", "content_type": "weekend_prep"},
        {"time": "19:30", "priority": "medium", "content_type": "seasonal_tips"}
    ],
    4: [  # Friday - Pre-weekend excitement
        {"time": "17:00", "priority": "medium", "content_type": "weekend_projects"},
        {"time": "19:00", "priority": "medium", "content_type": "inspiration"}
    ],
    5: [  # Saturday - PRIME DAY (morning gardeners + leisure time)
        {"time": "09:00", "priority": "highest", "content_type": "morning_routine"},
        {"time": "14:00", "priority": "highest", "content_type": "weekend_project"},
        {"time": "18:00", "priority": "high", "content_type": "harvest_showcase"}
    ],
    6: [  # Sunday - SECOND BEST (leisure + planning next week)
        {"time": "10:00", "priority": "highest", "content_type": "sunday_garden"},
        {"time": "15:00", "priority": "high", "content_type": "weekly_planning"},
        {"time": "19:00", "priority": "medium", "content_type": "relaxation"}
    ]
}

# GARDENING-SPECIFIC CONTENT RECOMMENDATIONS
CONTENT_RECOMMENDATIONS = {
    "morning_routine": "Quick garden check routines, watering schedules, morning harvests",
    "weekend_project": "DIY garden projects, planting guides, major gardening tasks",
    "propagation": "Plant propagation methods, cuttings, water propagation, free plants",
    "trending_hack": "Viral gardening hacks, kitchen scrap regrowing, budget solutions",
    "problem_solving": "Pest solutions, yellow leaves fixes, disease identification",
    "quick_tips": "Short actionable tips, fertilizer tricks, spacing guides",
    "seasonal_tips": "What to plant this month, seasonal care, climate-specific advice",
    "weekend_prep": "Shopping lists, seed starting, preparing beds for weekend",
    "harvest_showcase": "Show garden progress, harvest hauls, before/after transformations",
    "weekly_planning": "Plan upcoming week, seed ordering, garden calendar",
    "inspiration": "Beautiful garden tours, success stories, goal-setting",
    "weekend_projects": "Raised bed builds, vertical gardens, container combos",
    "sunday_garden": "Relaxing garden tours, harvest cooking, weekly recap",
    "relaxation": "Therapeutic gardening, sunset garden walks, planning content"
}

# GARDENING AUDIENCE INSIGHTS (from research)
AUDIENCE_INSIGHTS = {
    "demographics": {
        "age_primary": "35-44 years (typical gardener)",
        "age_growing": "18-34 years (29% millennials, fastest growing segment)",
        "gender": "54% female, 46% male",
        "income": "Above national average",
        "education": "Well-educated homeowners"
    },
    "behavior": {
        "weekend_gardeners": "Most active on Saturday mornings 9-11 AM",
        "evening_checkers": "Check gardens after work 5-7 PM on weekdays",
        "planning_time": "Sunday evenings for weekly garden planning",
        "research_time": "79% get gardening advice from online sources",
        "peak_seasons": "Spring (March-May) and Fall (Sept-Oct) highest activity"
    },
    "motivations": {
        "beauty": "55% - Create beautiful outdoor space",
        "food": "43% - Grow own food (35% of households grow food)",
        "exercise": "25% - Physical activity",
        "mental_health": "49% - Good for mental health",
        "family": "35% - Family activity"
    },
    "content_preferences": {
        "popular_topics": [
            "Propagation hacks (free plants)",
            "Regrow from kitchen scraps",
            "Pest/disease solutions",
            "Container gardening (urban dwellers)",
            "Seasonal planting guides",
            "Budget DIY projects",
            "Tomato growing tips (86% grow tomatoes)"
        ]
    }
}

ignore_schedule = '${{ github.event.inputs.ignore_schedule }}' == 'true'
          
if ignore_schedule:
    print('⚠️ Schedule check BYPASSED by user input')
    should_post = True
    priority = 'manual'
elif weekday in optimal_times:
    if hour in optimal_times[weekday]:
        should_post = True
        priority = 'highest' if (weekday == 1 and hour == 13) else 'high'
        print(f'✅ Within optimal window: {current.strftime("%A %I:%M %p WAT")}')
    else:
        print(f'⏳ Not optimal time. Current: {current.strftime("%A %I:%M %p WAT")}')
else:
    print(f'⏸️ Weekend - lower priority time')
    should_post = weekday >= 5  # Allow weekend posts
    priority = 'low'

def get_next_optimal_time(current_time=None):
    """
    Calculate the next optimal posting time for gardening content.
    Returns datetime object of next optimal slot.
    """
    if current_time is None:
        current_time = datetime.now(LOCAL_TZ)
    
    current_weekday = current_time.weekday()
    
    # Check if there's an optimal time today after current time
    today_slots = OPTIMAL_SCHEDULE.get(current_weekday, [])
    
    for slot in today_slots:
        slot_time = datetime.strptime(slot["time"], "%H:%M").time()
        slot_datetime = current_time.replace(
            hour=slot_time.hour,
            minute=slot_time.minute,
            second=0,
            microsecond=0
        )
        
        if slot_datetime > current_time:
            return {
                "datetime": slot_datetime,
                "priority": slot["priority"],
                "content_type": slot["content_type"],
                "recommendation": CONTENT_RECOMMENDATIONS[slot["content_type"]]
            }
    
    # No more slots today, find next day's first slot
    days_ahead = 1
    while days_ahead < 8:
        next_day = (current_weekday + days_ahead) % 7
        next_slots = OPTIMAL_SCHEDULE.get(next_day, [])
        
        if next_slots:
            first_slot = next_slots[0]
            slot_time = datetime.strptime(first_slot["time"], "%H:%M").time()
            
            next_datetime = current_time + timedelta(days=days_ahead)
            next_datetime = next_datetime.replace(
                hour=slot_time.hour,
                minute=slot_time.minute,
                second=0,
                microsecond=0
            )
            
            return {
                "datetime": next_datetime,
                "priority": first_slot["priority"],
                "content_type": first_slot["content_type"],
                "recommendation": CONTENT_RECOMMENDATIONS[first_slot["content_type"]]
            }
        
        days_ahead += 1
    
    # Fallback: Default to Saturday 9 AM next week
    days_until_saturday = (5 - current_weekday) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    
    next_saturday = current_time + timedelta(days=days_until_saturday)
    next_saturday = next_saturday.replace(hour=9, minute=0, second=0, microsecond=0)
    
    return {
        "datetime": next_saturday,
        "priority": "highest",
        "content_type": "morning_routine",
        "recommendation": CONTENT_RECOMMENDATIONS["morning_routine"]
    }


def should_post_now(tolerance_minutes=30):
    """
    Check if current time is within an optimal gardening posting window.
    Returns (should_post: bool, slot_info: dict)
    """
    current_time = datetime.now(LOCAL_TZ)
    current_weekday = current_time.weekday()
    
    today_slots = OPTIMAL_SCHEDULE.get(current_weekday, [])
    
    for slot in today_slots:
        slot_time = datetime.strptime(slot["time"], "%H:%M").time()
        slot_datetime = current_time.replace(
            hour=slot_time.hour,
            minute=slot_time.minute,
            second=0,
            microsecond=0
        )
        
        time_diff = abs((current_time - slot_datetime).total_seconds() / 60)
        
        if time_diff <= tolerance_minutes:
            return True, {
                "time": slot["time"],
                "priority": slot["priority"],
                "content_type": slot["content_type"],
                "recommendation": CONTENT_RECOMMENDATIONS[slot["content_type"]],
                "minutes_off": int(time_diff)
            }
    
    return False, None


def get_weekly_schedule():
    """Get the full weekly optimal gardening schedule"""
    schedule = {}
    
    for day, slots in OPTIMAL_SCHEDULE.items():
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        schedule[day_names[day]] = [
            {
                "time": slot["time"],
                "priority": slot["priority"],
                "content_type": slot["content_type"],
                "recommendation": CONTENT_RECOMMENDATIONS[slot["content_type"]]
            }
            for slot in slots
        ]
    
    return schedule


def calculate_delay_until_optimal():
    """Calculate seconds until next optimal gardening posting time"""
    next_slot = get_next_optimal_time()
    current_time = datetime.now(LOCAL_TZ)
    
    delay = (next_slot["datetime"] - current_time).total_seconds()
    
    return {
        "delay_seconds": int(delay),
        "delay_hours": delay / 3600,
        "delay_days": delay / 86400,
        "next_post_time": next_slot["datetime"].isoformat(),
        "priority": next_slot["priority"],
        "content_type": next_slot["content_type"],
        "recommendation": next_slot["recommendation"]
    }


def main():
    """Main execution for gardening posting scheduler"""
    print("🌱 Gardening YouTube Shorts Optimal Posting Scheduler")
    print("=" * 60)
    
    current_time = datetime.now(LOCAL_TZ)
    print(f"📅 Current Time: {current_time.strftime('%A, %B %d, %Y %I:%M %p WAT')}")
    print()
    
    # Check if should post now
    should_post, slot_info = should_post_now(tolerance_minutes=30)
    
    if should_post:
        print("✅ OPTIMAL GARDENING POSTING WINDOW - POST NOW!")
        print(f"   Time Slot: {slot_info['time']} WAT")
        print(f"   Priority: {slot_info['priority'].upper()}")
        print(f"   Content Type: {slot_info['content_type']}")
        print(f"   Recommendation: {slot_info['recommendation']}")
        print(f"   Timing: {slot_info['minutes_off']} minutes from optimal")
        
        # Set output for GitHub Actions
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write(f"should_post=true\n")
            f.write(f"priority={slot_info['priority']}\n")
            f.write(f"content_type={slot_info['content_type']}\n")
    else:
        print("⏳ NOT IN OPTIMAL WINDOW - Calculating next slot...")
        
        next_slot = get_next_optimal_time()
        delay_info = calculate_delay_until_optimal()
        
        print(f"\n📌 Next Optimal Time:")
        print(f"   Date/Time: {next_slot['datetime'].strftime('%A, %B %d, %Y %I:%M %p WAT')}")
        print(f"   Priority: {next_slot['priority'].upper()}")
        print(f"   Content Type: {next_slot['content_type']}")
        print(f"   Recommendation: {next_slot['recommendation']}")
        print(f"\n⏱️  Time Until Next Slot:")
        print(f"   {delay_info['delay_hours']:.1f} hours ({delay_info['delay_days']:.1f} days)")
        
        # Set output for GitHub Actions
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write(f"should_post=false\n")
            f.write(f"next_post_time={next_slot['datetime'].isoformat()}\n")
            f.write(f"delay_hours={delay_info['delay_hours']:.1f}\n")
    
    # Print weekly schedule
    print("\n" + "=" * 60)
    print("🌿 WEEKLY GARDENING OPTIMAL SCHEDULE")
    print("=" * 60)
    
    weekly = get_weekly_schedule()
    for day, slots in weekly.items():
        print(f"\n{day}:")
        for slot in slots:
            priority_emoji = {
                "highest": "🌟🌟🌟",
                "high": "🌟🌟",
                "medium": "🌟",
                "low": "○"
            }[slot["priority"]]
            
            print(f"  {priority_emoji} {slot['time']} WAT - {slot['content_type']}")
            print(f"     → {slot['recommendation']}")
    
    # Print audience insights
    print("\n" + "=" * 60)
    print("👥 GARDENING AUDIENCE INSIGHTS")
    print("=" * 60)
    
    print("\n🎯 Target Demographics:")
    for key, value in AUDIENCE_INSIGHTS["demographics"].items():
        print(f"   • {key.replace('_', ' ').title()}: {value}")
    
    print("\n🕐 Behavior Patterns:")
    for key, value in AUDIENCE_INSIGHTS["behavior"].items():
        print(f"   • {key.replace('_', ' ').title()}: {value}")
    
    print("\n💚 Top Motivations:")
    for key, value in AUDIENCE_INSIGHTS["motivations"].items():
        print(f"   • {key.title()}: {value}")
    
    # Save schedule to file
    schedule_file = os.path.join(TMP, "posting_schedule.json")
    schedule_data = {
        "current_time": current_time.isoformat(),
        "should_post_now": should_post,
        "next_optimal_slot": get_next_optimal_time(),
        "weekly_schedule": get_weekly_schedule(),
        "audience_insights": AUDIENCE_INSIGHTS,
        "timezone": "Africa/Lagos (WAT/UTC+1)",
        "niche": "gardening"
    }
    
    with open(schedule_file, 'w') as f:
        json.dump(schedule_data, f, indent=2, default=str)
    
    print(f"\n💾 Schedule saved to: {schedule_file}")
    print("\n💡 Gardening Tips:")
    print("   • Saturday 9 AM is PRIME TIME (weekend gardeners)")
    print("   • Sunday 10 AM is SECOND BEST (leisure + planning)")
    print("   • Wednesday 4-7 PM is BEST WEEKDAY (mid-week engagement)")
    print("   • Avoid Monday mornings (back-to-work low engagement)")
    print("   • Post propagation/hack content on weekends for max virality")


if __name__ == "__main__":
    main()