import json
import re
from models import db
from models.site_setting import SiteSetting

HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

DEFAULT_CATEGORIES = [
    {
        'slug': 'meet',
        'label': 'Meet Pannalam',
        'icon': '🤝',
        'description': 'Meet new people and start conversations without the usual awkwardness.',
        'color': '#FF6B6B',
        'tags': ['Talk to Strangers', 'Mystery Meetup', 'Conversation Games', 'Stranger Hunt'],
        'cta_label': 'MEET PEOPLE →',
        'show_on_home': True,
        'enabled': True,
    },
    {
        'slug': 'vibe',
        'label': 'Vibe Pannalam',
        'icon': '⚡',
        'description': 'Games, challenges, creative activities, and unexpected fun.',
        'color': '#C8FF00',
        'tags': ['Game Nights', 'The Plot Twist', 'Creative Challenges', 'Stranger Hunt'],
        'cta_label': 'FIND THE VIBE →',
        'show_on_home': True,
        'enabled': True,
    },
    {
        'slug': 'explore',
        'label': 'Suththi Paakalam',
        'icon': '🗺️',
        'description': 'Explore local places and discover somewhere new with a small group.',
        'color': '#4DC8FF',
        'tags': ['Namma Ooru Walk', 'Day Trips', 'Nature Outings', 'Weekend Adventures'],
        'cta_label': 'EXPLORE PLACES →',
        'show_on_home': True,
        'enabled': True,
    },
    {
        'slug': 'chill',
        'label': 'Chill Pannalam',
        'icon': '🌅',
        'description': 'Slow down, enjoy conversations, and spend time with new people.',
        'color': '#FFB84D',
        'tags': ['Sunset Strangers', 'Beach Walks', 'Café Conversations', 'Photography Walks'],
        'cta_label': 'FIND MY CHILL →',
        'show_on_home': True,
        'enabled': True,
    },
    {
        'slug': 'mystery',
        'label': 'Mystery',
        'icon': '🎭',
        'description': 'Unexpected social experiences where details stay a surprise until you show up.',
        'color': '#BF7FFF',
        'tags': ['Mystery Meetup', 'Blind Plans'],
        'cta_label': 'TRY MYSTERY →',
        'show_on_home': False,
        'enabled': True,
    },
    {
        'slug': 'trip',
        'label': 'Trip',
        'icon': '🚌',
        'description': 'Group day trips and weekend getaways from your city.',
        'color': '#4DFF91',
        'tags': ['Day Trips', 'Weekend Getaways'],
        'cta_label': 'EXPLORE TRIPS →',
        'show_on_home': False,
        'enabled': True,
    },
]

DEFAULT_SETTINGS = {
    # Branding
    'site_name': 'NXTUP',
    'site_name_prefix': 'NXT',
    'site_name_accent': 'UP',
    'tagline': 'Namma People. Pudhu Stories.',
    'brand_tagline_secondary': 'Your Next Story Starts Here.',
    'default_city': 'Vellore',
    'contact_email': 'hello@nxtup.in',
    'logo_filename': '',

    # Theme colors
    'primary_bg': '#0B0B0B',
    'secondary_bg': '#171717',
    'accent_color': '#C8FF00',
    'text_color': '#F5F5F5',

    # Announcements
    'announcement_enabled': 'false',
    'announcement_text': '',
    'announcement_link': '',
    'announcement_link_label': 'Check it out →',

    # Hero
    'hero_eyebrow': "Vellore's Social Experience Platform",
    'hero_heading_line1': 'NAMMA',
    'hero_heading_line2': 'PEOPLE.',
    'hero_heading_accent': 'PUDHU',
    'hero_heading_line4': 'STORIES.',
    'hero_subtitle': 'Bored of the same routine?',
    'hero_description': "Meet strangers. Make plans. Explore new places.\nYour next favourite memory could start with someone you've never met.",
    'hero_cta_primary': 'FIND YOUR NEXT PLAN →',
    'hero_cta_secondary': 'HOW NXTUP WORKS',
    'hero_image': 'hero_group_sunset.jpg',

    # Homepage sections
    'show_categories_section': 'true',
    'categories_eyebrow': 'Pick Your Vibe',
    'categories_title': 'ENNA PLAN INNIKU?',
    'categories_subtitle': "We'll help you find the right experience.",

    'show_upcoming_section': 'true',
    'upcoming_eyebrow': 'Happening Near You',
    'upcoming_title': 'PLANS THAT NEED YOU.',
    'upcoming_subtitle': 'Something interesting is happening near you.',

    'show_featured_section': 'true',
    'featured_eyebrow': 'Handpicked',
    'featured_title': 'FEATURED EXPERIENCES.',
    'featured_event_ids': '[]',

    'show_firsttimer_section': 'true',
    'show_surprise_section': 'true',
    'show_howitworks_section': 'true',
    'show_vibe_section': 'true',
    'show_stories_section': 'true',
    'show_safety_section': 'true',

    # Navigation labels
    'nav_home': 'Home',
    'nav_explore': 'Explore',
    'nav_trips': 'Trips',
    'nav_stories': 'Stories',
    'nav_about': 'About',
    'nav_my_plans': 'My Plans',
    'nav_cta': 'Find a Plan',

    # Footer
    'footer_tagline': 'Namma people. Pudhu stories.\nStranger meetups, social experiences & group trips in Vellore, Tamil Nadu.',
    'footer_copyright': '© 2026 NXTUP. Vellore, Tamil Nadu. All rights reserved.',
    'footer_made_in': 'Made with ❤️ for Vellore.',
    'social_instagram': 'https://www.instagram.com/nxtup.hub?cnvx=Y2w4Y3N5cHJvc2J3',
    'social_twitter': '',
    'social_whatsapp': 'https://chat.whatsapp.com/LFAlnQaLLiT4pW1Md2wF42?fbclid=PAT01DUAV2OiZleHRuA2FlbQIxMABwZG9mAnNydGMGYXBwX2lkDzU2NzA2NzM0MzM1MjQyNwABp8rHWqlNb24z435bGymc4GQeCFbR7FGaSlc-G8SMMob1cDxOfJFvL0aICL0i_aem_YJbBhAbSgCK5oG8xzOxwXw',

    # Categories JSON
    'categories_json': json.dumps(DEFAULT_CATEGORIES),
}


def is_safe_url(url):
    """Allow empty string, relative paths starting with '/', or http(s) URLs."""
    if not url:
        return True
    u = url.strip()
    if u.startswith('/') and not u.startswith('//'):
        return True
    return u.startswith('https://') or u.startswith('http://')


def is_valid_hex_color(value):
    return bool(value and HEX_COLOR_RE.match(value.strip()))


def hex_to_rgba(hex_color, alpha=0.12):
    """Convert #RRGGBB to rgba(r,g,b,alpha) CSS string."""
    if not is_valid_hex_color(hex_color):
        hex_color = '#C8FF00'
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'


def lighten_hex(hex_color, factor=0.15):
    """Slightly lighten a hex color for hover states."""
    if not is_valid_hex_color(hex_color):
        return '#d4ff33'
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f'#{r:02x}{g:02x}{b:02x}'


def _parse_bool(val, default=False):
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    return str(val).strip().lower() in ('true', '1', 'yes', 'on')


def get_raw_settings():
    """Fetch all settings merged with defaults."""
    merged = dict(DEFAULT_SETTINGS)
    try:
        rows = SiteSetting.query.all()
        for row in rows:
            if row.key in merged and row.value is not None:
                merged[row.key] = row.value
    except Exception:
        # Table may not exist yet during initial setup/migration
        pass
    return merged


def get_categories(include_disabled=False):
    """Return parsed list of category dicts."""
    raw = get_raw_settings().get('categories_json', '')
    cats = None
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                cats = parsed
        except (ValueError, TypeError):
            cats = None
    if not cats:
        cats = [dict(c) for c in DEFAULT_CATEGORIES]

    result = []
    for c in cats:
        if not isinstance(c, dict) or not c.get('slug'):
            continue
        enabled = bool(c.get('enabled', True))
        if not include_disabled and not enabled:
            continue
        item = {
            'slug': str(c['slug']).strip().lower(),
            'label': str(c.get('label') or c['slug'].title()).strip(),
            'icon': str(c.get('icon') or '✨').strip(),
            'description': str(c.get('description') or '').strip(),
            'color': c['color'] if is_valid_hex_color(c.get('color', '')) else '#C8FF00',
            'tags': [str(t).strip() for t in (c.get('tags') or []) if str(t).strip()],
            'cta_label': str(c.get('cta_label') or 'EXPLORE →').strip(),
            'show_on_home': bool(c.get('show_on_home', False)),
            'enabled': enabled,
        }
        item['color_dim'] = hex_to_rgba(item['color'], 0.14)
        item['color_border'] = hex_to_rgba(item['color'], 0.30)
        item['color_glow'] = hex_to_rgba(item['color'], 0.06)
        result.append(item)
    return result


def get_category_map():
    """Return {slug: category_dict}."""
    return {c['slug']: c for c in get_categories(include_disabled=True)}


def get_featured_event_ids():
    """Return list of integer event IDs marked as featured."""
    raw = get_raw_settings().get('featured_event_ids', '[]')
    try:
        ids = json.loads(raw)
        if isinstance(ids, list):
            return [int(x) for x in ids if str(x).isdigit()]
    except (ValueError, TypeError):
        pass
    return []


def get_site_settings():
    """Return structured dict ready for templates & context processor."""
    raw = get_raw_settings()
    accent = raw['accent_color'] if is_valid_hex_color(raw['accent_color']) else DEFAULT_SETTINGS['accent_color']
    primary_bg = raw['primary_bg'] if is_valid_hex_color(raw['primary_bg']) else DEFAULT_SETTINGS['primary_bg']
    secondary_bg = raw['secondary_bg'] if is_valid_hex_color(raw['secondary_bg']) else DEFAULT_SETTINGS['secondary_bg']
    text_color = raw['text_color'] if is_valid_hex_color(raw['text_color']) else DEFAULT_SETTINGS['text_color']

    settings = dict(raw)
    settings.update({
        'primary_bg': primary_bg,
        'secondary_bg': secondary_bg,
        'accent_color': accent,
        'accent_dim': hex_to_rgba(accent, 0.12),
        'accent_border': hex_to_rgba(accent, 0.28),
        'accent_hover': lighten_hex(accent, 0.18),
        'accent_shadow': hex_to_rgba(accent, 0.15),
        'text_color': text_color,
        'announcement_enabled': _parse_bool(raw.get('announcement_enabled'), False),
        'show_categories_section': _parse_bool(raw.get('show_categories_section'), True),
        'show_upcoming_section': _parse_bool(raw.get('show_upcoming_section'), True),
        'show_featured_section': _parse_bool(raw.get('show_featured_section'), True),
        'show_firsttimer_section': _parse_bool(raw.get('show_firsttimer_section'), True),
        'show_surprise_section': _parse_bool(raw.get('show_surprise_section'), True),
        'show_howitworks_section': _parse_bool(raw.get('show_howitworks_section'), True),
        'show_vibe_section': _parse_bool(raw.get('show_vibe_section'), True),
        'show_stories_section': _parse_bool(raw.get('show_stories_section'), True),
        'show_safety_section': _parse_bool(raw.get('show_safety_section'), True),
        'featured_event_ids_list': get_featured_event_ids(),
    })
    return settings


def save_settings(updates):
    """Persist validated key-value pairs into site_settings table."""
    for key, val in updates.items():
        if key not in DEFAULT_SETTINGS:
            continue
        row = SiteSetting.query.filter_by(key=key).first()
        if row is None:
            row = SiteSetting(key=key, value=str(val) if val is not None else '')
            db.session.add(row)
        else:
            row.value = str(val) if val is not None else ''
    db.session.commit()
