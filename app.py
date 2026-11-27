import os
from datetime import datetime, timezone
from flask import Flask, render_template
from config import config
from models import db, bcrypt, login_manager, csrf


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Extensions
    db.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'admin.login'
    login_manager.login_message = 'Please log in to access the admin panel.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        from models import AdminUser
        try:
            user = db.session.get(AdminUser, int(user_id))
        except (ValueError, TypeError):
            return None
        if user and user.is_active:
            return user
        return None

    # Blueprints
    from routes.public import public
    from routes.admin import admin
    app.register_blueprint(public)
    app.register_blueprint(admin)

    # Context processor: inject dynamic customization settings into all templates
    @app.context_processor
    def inject_site_settings():
        from services.settings_service import get_site_settings, get_categories, get_category_map
        return {
            'site': get_site_settings(),
            'site_categories': get_categories(include_disabled=False),
            'all_categories': get_categories(include_disabled=True),
            'category_map': get_category_map(),
            'current_year': datetime.now(timezone.utc).year,
        }

    # Jinja2 filters
    @app.template_filter('rupees')
    def rupees_filter(value):
        if value is None or value == 0:
            return 'Free'
        return f'₹{int(value):,}'

    @app.template_filter('datetime_display')
    def datetime_display_filter(dt):
        if dt is None:
            return ''
        return dt.strftime('%a, %d %b %Y • %I:%M %p')

    @app.template_filter('date_display')
    def date_display_filter(dt):
        if dt is None:
            return ''
        return dt.strftime('%d %b %Y')

    @app.template_filter('category_label')
    def category_label_filter(cat):
        if not cat:
            return ''
        from services.settings_service import get_category_map
        cmap = get_category_map()
        if cat in cmap:
            return cmap[cat]['label']
        return str(cat).title()

    @app.template_filter('category_icon')
    def category_icon_filter(cat):
        if not cat:
            return '✨'
        from services.settings_service import get_category_map
        cmap = get_category_map()
        if cat in cmap:
            return cmap[cat]['icon']
        return '✨'

    @app.template_filter('category_color')
    def category_color_filter(cat):
        from services.settings_service import get_category_map
        cmap = get_category_map()
        if cat in cmap:
            return cmap[cat]['color']
        return '#C8FF00'

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('500.html'), 500

    # CLI helper to create/update an admin account
    @app.cli.command('create-admin')
    def create_admin_cmd():
        """Create or update the admin account from environment variables."""
        _seed_admin(app, update_existing=True)

    return app


def init_db(app):
    """Create missing tables and seed initial data without touching existing rows."""
    with app.app_context():
        db.create_all()
        _seed_admin(app, update_existing=False)
        _seed_sample_data()


def _seed_admin(app, update_existing=False):
    from models import AdminUser
    email = os.environ.get('ADMIN_EMAIL', 'admin@nxtup.in').strip().lower()
    name = os.environ.get('ADMIN_NAME', 'NXTUP Admin').strip() or 'NXTUP Admin'
    password = os.environ.get('ADMIN_PASSWORD', '')

    if not email or '@' not in email:
        print("⚠  Invalid ADMIN_EMAIL in .env — skipping admin setup.")
        return

    if not password:
        print("⚠  ADMIN_PASSWORD not set in .env — skipping admin creation.")
        return

    existing = AdminUser.query.filter_by(email=email).first()
    if not existing:
        admin_user = AdminUser(name=name, email=email, is_active=True)
        admin_user.set_password(password)
        db.session.add(admin_user)
        db.session.commit()
        print(f"✓ Admin account created: {email}")
    elif update_existing:
        existing.name = name
        existing.is_active = True
        existing.set_password(password)
        db.session.commit()
        print(f"✓ Admin account updated: {email}")
    else:
        print(f"✓ Admin account already exists: {email}")


def _seed_sample_data():
    """Seeds clearly-labelled SAMPLE events for Vellore if events table is empty."""
    from models import Event, Review
    from datetime import timedelta

    if Event.query.count() > 0:
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    sample_events = [
        {
            'title': 'Sunset Strangers — Vellore',
            'slug': 'sunset-strangers-vellore',
            'short_description': 'Watch the sunset with 8 strangers at Vellore Fort. Zero awkwardness guaranteed.',
            'description': (
                '[SAMPLE DATA] A relaxed golden-hour gathering at Vellore Fort lake. '
                'Meet 7–8 new people as the sun goes down. Activities include conversation cards, '
                'a short walk, and an optional group photo. No phone-staring allowed.'
            ),
            'category': 'chill',
            'city': 'Vellore',
            'location_name': 'Vellore Fort Lake View',
            'location_details': 'Meet at the main entrance of Vellore Fort. Coordinates will be shared on booking.',
            'start_datetime': now + timedelta(days=5, hours=11.5),
            'duration_minutes': 120,
            'price': 199,
            'capacity': 10,
            'what_included': 'Conversation card game · Host · Welcome refreshments',
            'what_not_included': 'Transport · Personal expenses',
            'what_to_bring': 'Comfortable footwear · Water bottle · Good mood',
            'safety_info': 'All participants are age-verified adults. A host is present at all times.',
            'cancellation_terms': 'Full refund if cancelled 48 hours before the event.',
            'image_filename': 'hero_group_sunset.jpg',
            'published': True,
            'is_mystery': False,
            'is_trip': False,
        },
        {
            'title': 'Mystery Meetup — What Happens, Happens',
            'slug': 'mystery-meetup-vellore',
            'short_description': "You won't know what you're doing until you arrive. That's the whole point.",
            'description': (
                "[SAMPLE DATA] A completely mystery social experience in Vellore. "
                "You'll know the time, the area, and the price. Nothing else. "
                "Past mystery meetups have included rooftop games, scavenger hunts, "
                "and unexpected culinary adventures. Your comfort is always respected."
            ),
            'category': 'mystery',
            'city': 'Vellore',
            'location_name': 'Vellore Town (exact location shared on booking)',
            'location_details': 'Meeting point revealed 2 hours before via email.',
            'start_datetime': now + timedelta(days=8, hours=15),
            'duration_minutes': 180,
            'price': 349,
            'capacity': 12,
            'what_included': 'Mystery activity · Host · Post-activity chai',
            'what_not_included': 'Transport · Personal expenses',
            'what_to_bring': 'An open mind · Comfortable clothes · Full phone battery',
            'safety_info': 'Activity details shared with emergency contacts on request. Host present throughout.',
            'cancellation_terms': 'Full refund if cancelled 72 hours before. No refund after meeting point is revealed.',
            'image_filename': 'cafe_meetup.jpg',
            'published': True,
            'is_mystery': True,
            'is_trip': False,
        },
        {
            'title': 'Talk to Strangers — Café Edition',
            'slug': 'talk-to-strangers-cafe',
            'short_description': 'Structured conversation games with 6 strangers at a cozy café in Vellore.',
            'description': (
                '[SAMPLE DATA] A fun, low-pressure meetup at a local café. '
                'Six strangers sit down together with conversation-starter cards. '
                'No awkward silences. No judgement. Just real conversations with people '
                "you'd never normally meet."
            ),
            'category': 'meet',
            'city': 'Vellore',
            'location_name': 'Central Vellore Café (name shared on booking)',
            'location_details': 'Central area, walking distance from Vellore bus stand.',
            'start_datetime': now + timedelta(days=3, hours=14),
            'duration_minutes': 90,
            'price': 149,
            'capacity': 8,
            'what_included': 'Conversation card game · Host · One beverage per person',
            'what_not_included': 'Additional food/drinks',
            'what_to_bring': 'Nothing — just yourself',
            'safety_info': 'Indoor venue. Host present throughout.',
            'cancellation_terms': 'Full refund 24 hours before event.',
            'image_filename': 'cafe_meetup.jpg',
            'published': True,
            'is_mystery': False,
            'is_trip': False,
        },
        {
            'title': 'Namma Ooru Walk — Vellore Old Town',
            'slug': 'namma-ooru-walk-vellore',
            'short_description': "Explore the hidden stories of Vellore's old town with 8 curious strangers.",
            'description': (
                "[SAMPLE DATA] A guided walk through Vellore's old town — historic streets, "
                "local architecture, street food stops, and unexpected discoveries. "
                "Led by a local host who knows the lanes. Small group, big stories."
            ),
            'category': 'explore',
            'city': 'Vellore',
            'location_name': 'Vellore Fort Main Gate',
            'location_details': 'Meet outside the main gate of Vellore Fort at 7:00 AM sharp.',
            'start_datetime': now + timedelta(days=6, hours=1.5),
            'duration_minutes': 150,
            'price': 249,
            'capacity': 10,
            'what_included': 'Local guide · Breakfast snack stop · Group photo',
            'what_not_included': 'Transport to start point · Personal purchases',
            'what_to_bring': 'Comfortable walking shoes · Water · Camera',
            'safety_info': 'Daylight activity. Public spaces throughout.',
            'cancellation_terms': 'Full refund 48 hours before event.',
            'image_filename': 'group_exploration.jpg',
            'published': True,
            'is_mystery': False,
            'is_trip': False,
        },
        {
            'title': 'The Plot Twist — Game Night',
            'slug': 'plot-twist-game-night',
            'short_description': 'Social deduction games, icebreaker challenges, and unexpected twists with strangers.',
            'description': (
                '[SAMPLE DATA] An evening of social games with 10–12 strangers. '
                'Expect Mafia, Werewolf, Skribbl, and some surprise challenges. '
                'Hosts keep energy high and awkwardness low.'
            ),
            'category': 'vibe',
            'city': 'Vellore',
            'location_name': 'Indoor venue, Vellore (shared on booking)',
            'location_details': 'Central Vellore. Easy auto/cab access.',
            'start_datetime': now + timedelta(days=10, hours=13),
            'duration_minutes': 180,
            'price': 299,
            'capacity': 14,
            'what_included': 'All games · Host · Snacks',
            'what_not_included': 'Transport · Dinner',
            'what_to_bring': 'Energy · Competitive spirit',
            'safety_info': 'Private indoor venue. Adults only.',
            'cancellation_terms': 'Full refund 48 hours before event.',
            'image_filename': 'vellore_group.jpg',
            'published': True,
            'is_mystery': False,
            'is_trip': False,
        },
        {
            'title': 'Day Trip — Yelagiri Hills with Strangers',
            'slug': 'day-trip-yelagiri',
            'short_description': 'A short group day trip to Yelagiri Hills from Vellore. Good views, better company.',
            'description': (
                '[SAMPLE DATA] A curated one-day trip to Yelagiri Hills with a small group of '
                'Vellore strangers. Shared transport, nature trail, local lunch, and back by evening. '
                'Perfect for people who want a quick escape without the hassle of planning.'
            ),
            'category': 'explore',
            'city': 'Vellore',
            'location_name': 'Vellore Bus Stand (Departure)',
            'location_details': 'Shared vehicle departs at 6:30 AM. Return by 7:00 PM approximately.',
            'start_datetime': now + timedelta(days=15, hours=1),
            'duration_minutes': 720,
            'price': 799,
            'capacity': 12,
            'what_included': 'Transport (shared) · Host · Nature trail entry',
            'what_not_included': 'Personal meals · Shopping',
            'what_to_bring': 'ID proof · Water · Light snacks · Sunscreen · Comfortable shoes',
            'transport_info': 'Shared vehicle from Vellore. Seat confirmed on booking.',
            'physical_level': 'moderate',
            'safety_info': 'Host present. Emergency contact required at registration.',
            'cancellation_terms': 'Full refund 5 days before trip. 50% refund 3 days before. No refund after that.',
            'image_filename': 'group_exploration.jpg',
            'published': True,
            'is_mystery': False,
            'is_trip': True,
        },
        {
            'title': 'Stranger Hunt — Vellore Edition',
            'slug': 'stranger-hunt-vellore',
            'short_description': 'A city-wide scavenger hunt where you team up with strangers you just met.',
            'description': (
                '[SAMPLE DATA] Teams of 3 strangers compete in a guided city scavenger hunt '
                'across Vellore. Clues, challenges, and small prizes. '
                'The best part: you meet your teammates only at the start.'
            ),
            'category': 'vibe',
            'city': 'Vellore',
            'location_name': 'Vellore Fort Area',
            'location_details': 'Starting point shared 1 hour before via email.',
            'start_datetime': now + timedelta(days=12, hours=10),
            'duration_minutes': 150,
            'price': 399,
            'capacity': 15,
            'what_included': 'Hunt kit · Host coordination · Prize for winners',
            'what_not_included': 'Transport between locations',
            'what_to_bring': 'Phone · Comfortable shoes · Team spirit',
            'safety_info': 'All locations are public areas in Vellore. Host available via phone.',
            'cancellation_terms': 'Full refund 48 hours before event.',
            'image_filename': 'vellore_group.jpg',
            'published': True,
            'is_mystery': False,
            'is_trip': False,
        },
        {
            'title': 'Café Conversations — Slow Sunday',
            'slug': 'cafe-conversations-sunday',
            'short_description': 'A slow Sunday morning of real conversations with 6 strangers over good coffee.',
            'description': (
                '[SAMPLE DATA] No games. No ice-breaker challenges. Just coffee, a table, '
                'and six people having an honest conversation. Guided gently by a host with '
                'thoughtful questions. For people who love depth over small talk.'
            ),
            'category': 'chill',
            'city': 'Vellore',
            'location_name': 'A quiet café in Vellore (shared on booking)',
            'location_details': 'Central area. Walking distance from main bus stand.',
            'start_datetime': now + timedelta(days=9, hours=4),
            'duration_minutes': 90,
            'price': 129,
            'capacity': 8,
            'what_included': 'Host · One beverage included',
            'what_not_included': 'Additional food',
            'what_to_bring': 'Just yourself',
            'safety_info': 'Public café. Adults only.',
            'cancellation_terms': 'Full refund 24 hours before.',
            'image_filename': 'cafe_meetup.jpg',
            'published': True,
            'is_mystery': False,
            'is_trip': False,
        },
    ]

    for data in sample_events:
        db.session.add(Event(**data))

    sample_reviews = [
        {
            'reviewer_name': 'Aravind S.',
            'reviewer_initial': 'A',
            'city': 'Vellore',
            'story': (
                "[SAMPLE] I almost didn't register because I was nervous about "
                "going alone. But the host made it so easy. Ended up talking to "
                "someone for three hours. Didn't expect that."
            ),
            'rating': 5,
            'experience_type': 'Talk to Strangers',
            'approved': True,
            'is_sample': True,
        },
        {
            'reviewer_name': 'Priya M.',
            'reviewer_initial': 'P',
            'city': 'Vellore',
            'story': (
                "[SAMPLE] The Namma Ooru Walk showed me parts of Vellore I'd "
                "lived near for years but never explored. Plus I made a friend "
                "who recommends books like crazy. 10/10."
            ),
            'rating': 5,
            'experience_type': 'Namma Ooru Walk',
            'approved': True,
            'is_sample': True,
        },
        {
            'reviewer_name': 'Karthik R.',
            'reviewer_initial': 'K',
            'city': 'Vellore',
            'story': (
                "[SAMPLE] Mystery meetup was actually mysterious. I still don't "
                "want to spoil what happened. Just go."
            ),
            'rating': 4,
            'experience_type': 'Mystery Meetup',
            'approved': True,
            'is_sample': True,
        },
    ]

    for data in sample_reviews:
        db.session.add(Review(**data))

    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    init_db(app)
    app.run(
        debug=app.config.get('DEBUG', False),
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', 5000)),
    )
