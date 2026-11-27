import random
from datetime import datetime, timezone
from models.event import Event


CATEGORY_MAP = {
    'meet': ['meet', 'mystery'],
    'vibe': ['vibe', 'games'],
    'explore': ['explore', 'trip', 'outdoor'],
    'chill': ['chill', 'relaxed'],
}

SETTING_CATEGORY = {
    'indoors': ['meet', 'vibe'],
    'outdoors': ['explore', 'chill'],
    'cafe': ['chill', 'meet'],
    'destination': ['explore', 'trip'],
    'no_preference': None,
}


def score_event(event, answers):
    """
    Rule-based scoring for questionnaire results.
    answers: dict with keys: goal, setting, group_size, budget, availability
    Returns (integer score, list of reasons).
    """
    score = 0
    reasons = []

    goal = answers.get('goal', '')
    category_match = {
        'friendships': ['meet', 'chill'],
        'adventure': ['explore', 'vibe'],
        'relaxation': ['chill'],
        'conversations': ['meet', 'chill'],
        'unexpected': ['mystery', 'vibe'],
    }
    if goal and event.category in category_match.get(goal, []):
        score += 3
        reasons.append('Matches your vibe goal')

    setting = answers.get('setting', '')
    setting_cats = SETTING_CATEGORY.get(setting)
    if setting_cats is None or event.category in setting_cats:
        score += 2
        if setting_cats:
            reasons.append('Matches your preferred setting')

    budget = answers.get('budget', '')
    budget_ranges = {
        'under_300': (0, 300),
        '300_600': (300, 600),
        '600_1000': (600, 1000),
        'above_1000': (1000, 99999),
    }
    if budget and budget in budget_ranges:
        low, high = budget_ranges[budget]
        if low <= event.price <= high:
            score += 3
            reasons.append('Within your budget')
        elif event.price > high:
            return -999, []

    group = answers.get('group_size', '')
    group_ranges = {
        '4_6': (4, 6),
        '7_10': (7, 10),
        '11_15': (11, 15),
        'no_preference': None,
    }
    if group in group_ranges:
        grng = group_ranges[group]
        if grng is None or grng[0] <= event.capacity <= grng[1]:
            score += 2
            if grng:
                reasons.append('Comfortable group size for you')

    availability = answers.get('availability', '')
    day_map = {
        'weekday_evenings': [0, 1, 2, 3, 4],
        'saturday': [5],
        'sunday': [6],
        'flexible': None,
    }
    if availability in day_map:
        days = day_map[availability]
        if days is None or event.start_datetime.weekday() in days:
            score += 2
            if days:
                reasons.append('Available on your preferred day')

    return score, reasons


def get_recommendations(answers, city=None, limit=3):
    """Returns top matching events with scores and reasons."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = Event.query.filter(
        Event.published == True,
        Event.start_datetime > now,
    )
    if city:
        query = query.filter(Event.city == city)

    scored = []
    for event in query.all():
        if event.is_sold_out:
            continue
        sc, reasons = score_event(event, answers)
        if sc >= 0:
            scored.append((sc, event, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


def get_surprise_event(city=None, exclude_id=None):
    """Picks a random available published event for Surprise Me."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = Event.query.filter(
        Event.published == True,
        Event.start_datetime > now,
    )
    if city and city.lower() != 'all':
        query = query.filter(Event.city == city)
    if exclude_id:
        query = query.filter(Event.id != exclude_id)

    events = [e for e in query.all() if not e.is_sold_out]
    if not events and city and city.lower() != 'all':
        # Fallback across all cities if default city has no available events
        fallback_q = Event.query.filter(
            Event.published == True,
            Event.start_datetime > now,
        )
        if exclude_id:
            fallback_q = fallback_q.filter(Event.id != exclude_id)
        events = [e for e in fallback_q.all() if not e.is_sold_out]

    if not events:
        return None
    return random.choice(events)
