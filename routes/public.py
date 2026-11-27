import re
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, url_for, jsonify
from sqlalchemy import extract
from models import db, Event, Review, ContactMessage
from services.booking_service import create_booking, get_booking_by_reference
from services.recommendation_service import get_surprise_event
from services.settings_service import get_site_settings, get_categories, get_featured_event_ids

public = Blueprint('public', __name__)

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _is_valid_email(email):
    return bool(email and len(email) <= 200 and EMAIL_RE.match(email))


@public.route('/')
def index():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    settings = get_site_settings()
    default_city = settings.get('default_city', 'Vellore')

    # Featured events (if configured in admin)
    featured_ids = get_featured_event_ids()
    featured_events = []
    if featured_ids:
        found = Event.query.filter(
            Event.id.in_(featured_ids),
            Event.published == True,
            Event.start_datetime > now,
        ).all()
        by_id = {e.id: e for e in found}
        featured_events = [by_id[eid] for eid in featured_ids if eid in by_id]

    # Upcoming events (prefer default city, fallback to all cities if none)
    upcoming_q = Event.query.filter(
        Event.published == True,
        Event.start_datetime > now,
    )
    upcoming = upcoming_q.filter(Event.city == default_city).order_by(Event.start_datetime).limit(6).all()
    if not upcoming:
        upcoming = upcoming_q.order_by(Event.start_datetime).limit(6).all()

    approved_reviews = Review.query.filter_by(approved=True).order_by(
        Review.created_at.desc()
    ).limit(6).all()

    home_categories = [c for c in get_categories(include_disabled=False) if c.get('show_on_home')]

    return render_template(
        'index.html',
        upcoming_events=upcoming,
        featured_events=featured_events,
        home_categories=home_categories,
        reviews=approved_reviews,
        now=now,
    )


@public.route('/explore')
def explore():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    search = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    city = request.args.get('city', '').strip()
    budget = request.args.get('budget', '').strip()
    availability = request.args.get('availability', '').strip()
    sort = request.args.get('sort', 'soonest').strip()

    query = Event.query.filter(
        Event.published == True,
        Event.start_datetime > now,
        Event.is_trip == False,
    )

    if city:
        query = query.filter(Event.city == city)
    if search:
        like_term = f'%{search}%'
        query = query.filter(
            db.or_(
                Event.title.ilike(like_term),
                Event.short_description.ilike(like_term),
                Event.location_name.ilike(like_term),
                Event.city.ilike(like_term),
            )
        )
    if category:
        query = query.filter(Event.category == category)
    if budget:
        budget_ranges = {
            'under_300': (0, 299),
            '300_600': (300, 600),
            '600_1000': (601, 1000),
            'above_1000': (1001, 999999),
        }
        if budget in budget_ranges:
            lo, hi = budget_ranges[budget]
            query = query.filter(Event.price >= lo, Event.price <= hi)
    if availability:
        day_map = {
            'weekday': [1, 2, 3, 4, 5],
            'saturday': [6],
            'sunday': [0],
        }
        if availability in day_map:
            query = query.filter(
                extract('dow', Event.start_datetime).in_(day_map[availability])
            )

    if sort == 'price_low':
        query = query.order_by(Event.price.asc(), Event.start_datetime.asc())
    elif sort == 'price_high':
        query = query.order_by(Event.price.desc(), Event.start_datetime.asc())
    else:
        query = query.order_by(Event.start_datetime.asc())

    events = query.all()
    cities = sorted({
        c[0] for c in db.session.query(Event.city).filter(Event.published == True).distinct().all() if c[0]
    })
    categories = [c for c in get_categories(include_disabled=False) if c['slug'] != 'trip']

    return render_template(
        'explore.html',
        events=events,
        cities=cities,
        categories=categories,
        search=search,
        selected_category=category,
        selected_city=city,
        selected_budget=budget,
        selected_availability=availability,
        selected_sort=sort,
    )


@public.route('/experiences/<slug>')
def experience_detail(slug):
    event = Event.query.filter_by(slug=slug, published=True).first_or_404()
    approved_reviews = Review.query.filter_by(
        event_id=event.id, approved=True
    ).order_by(Review.created_at.desc()).limit(5).all()
    is_past = event.start_datetime <= datetime.now(timezone.utc).replace(tzinfo=None)
    return render_template(
        'experience_detail.html',
        event=event,
        reviews=approved_reviews,
        is_past=is_past,
    )


@public.route('/experiences/<slug>/book', methods=['POST'])
def book_experience(slug):
    event = Event.query.filter_by(slug=slug, published=True).first_or_404()
    approved_reviews = Review.query.filter_by(
        event_id=event.id, approved=True
    ).order_by(Review.created_at.desc()).limit(5).all()
    is_past = event.start_datetime <= datetime.now(timezone.utc).replace(tzinfo=None)

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    notes = request.form.get('notes', '').strip()
    places_raw = request.form.get('places', '1').strip()

    errors = []
    try:
        places = int(places_raw)
    except (ValueError, TypeError):
        places = 1
        errors.append("Please select a valid number of places.")

    if not name or len(name) < 2:
        errors.append("Please enter your name (at least 2 characters).")
    elif len(name) > 150:
        errors.append("Name must be 150 characters or fewer.")

    if not _is_valid_email(email):
        errors.append("Please enter a valid email address.")

    if phone and len(phone) > 20:
        errors.append("Phone number is too long.")

    if places < 1 or places > 5:
        errors.append("You can book between 1 and 5 places.")

    if is_past:
        errors.append("Registration for this experience has closed.")
    elif event.is_sold_out:
        errors.append("This experience is sold out.")

    if errors:
        return render_template(
            'experience_detail.html',
            event=event,
            errors=errors,
            form_data=request.form,
            reviews=approved_reviews,
            is_past=is_past,
        ), 400

    booking, error = create_booking(event.id, name, email, phone, places, notes)
    if error:
        return render_template(
            'experience_detail.html',
            event=event,
            errors=[error],
            form_data=request.form,
            reviews=approved_reviews,
            is_past=is_past,
        ), 400

    return render_template('booking_confirmation.html', booking=booking, event=event)


@public.route('/trips')
def trips():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    search = request.args.get('q', '').strip()
    city = request.args.get('city', '').strip()
    level = request.args.get('level', '').strip()
    budget = request.args.get('budget', '').strip()

    query = Event.query.filter(
        Event.published == True,
        Event.start_datetime > now,
        Event.is_trip == True,
    )

    if city:
        query = query.filter(Event.city == city)
    if search:
        like_term = f'%{search}%'
        query = query.filter(
            db.or_(
                Event.title.ilike(like_term),
                Event.short_description.ilike(like_term),
                Event.location_name.ilike(like_term),
                Event.city.ilike(like_term),
            )
        )
    if level in ('easy', 'moderate', 'active'):
        query = query.filter(Event.physical_level == level)
    if budget:
        budget_ranges = {
            'under_500': (0, 499),
            '500_1000': (500, 1000),
            'above_1000': (1001, 999999),
        }
        if budget in budget_ranges:
            lo, hi = budget_ranges[budget]
            query = query.filter(Event.price >= lo, Event.price <= hi)

    trip_events = query.order_by(Event.start_datetime.asc()).all()
    cities = sorted({
        c[0] for c in db.session.query(Event.city).filter(
            Event.published == True, Event.is_trip == True
        ).distinct().all() if c[0]
    })

    return render_template(
        'trips.html',
        trips=trip_events,
        cities=cities,
        search=search,
        selected_city=city,
        selected_level=level,
        selected_budget=budget,
    )


@public.route('/about')
def about():
    return render_template('about.html')


@public.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        category = request.form.get('category', 'general').strip()
        allowed_cats = {'general', 'booking', 'event', 'safety', 'organiser', 'other'}
        if category not in allowed_cats:
            category = 'general'

        errors = []
        if not name or len(name) < 2:
            errors.append("Name is required (at least 2 characters).")
        if not _is_valid_email(email):
            errors.append("Valid email address is required.")
        if not message or len(message) < 10:
            errors.append("Please write a message (at least 10 characters).")
        elif len(message) > 3000:
            errors.append("Message must be 3000 characters or fewer.")

        if errors:
            return render_template('contact.html', errors=errors, form_data=request.form), 400

        msg = ContactMessage(
            name=name[:150],
            email=email.lower()[:200],
            category=category,
            subject=subject[:200] if subject else None,
            message=message,
        )
        db.session.add(msg)
        db.session.commit()
        return render_template('contact.html', success=True)

    return render_template('contact.html')


@public.route('/my-plans', methods=['GET', 'POST'])
def my_plans():
    bookings = []
    searched = False
    error = None

    if request.method == 'POST':
        ref = request.form.get('reference', '').strip()
        email = request.form.get('email', '').strip()
        searched = True

        if not ref or not email:
            error = "Please enter both your booking reference and email."
        elif not _is_valid_email(email):
            error = "Please enter a valid email address."
        else:
            booking = get_booking_by_reference(ref, email)
            if booking:
                bookings = [booking]
            else:
                error = "No booking found with those details. Check your confirmation email."

    return render_template('my_plans.html', bookings=bookings, searched=searched, error=error)


@public.route('/reviews', methods=['GET', 'POST'])
def reviews():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        story = request.form.get('story', '').strip()
        rating_raw = request.form.get('rating', '').strip()
        experience_type = request.form.get('experience_type', '').strip()

        errors = []
        if not name or len(name) < 2:
            errors.append("Name is required (at least 2 characters).")
        elif len(name) > 150:
            errors.append("Name must be 150 characters or fewer.")

        if not story or len(story) < 20:
            errors.append("Please share more of your story (at least 20 characters).")
        elif len(story) > 1000:
            errors.append("Story must be 1000 characters or fewer.")

        rating = None
        if rating_raw:
            try:
                rating = int(rating_raw)
                if rating < 1 or rating > 5:
                    errors.append("Rating must be between 1 and 5 stars.")
            except ValueError:
                errors.append("Invalid rating value.")

        if not errors:
            review = Review(
                reviewer_name=name,
                reviewer_initial=name[0].upper(),
                story=story,
                rating=rating,
                experience_type=experience_type[:100] if experience_type else None,
                approved=False,
                is_sample=False,
            )
            db.session.add(review)
            db.session.commit()
            return render_template(
                'reviews.html',
                success=True,
                approved_reviews=_get_approved_reviews(),
            )

        return render_template(
            'reviews.html',
            errors=errors,
            form_data=request.form,
            approved_reviews=_get_approved_reviews(),
        ), 400

    return render_template('reviews.html', approved_reviews=_get_approved_reviews())


def _get_approved_reviews():
    return Review.query.filter_by(approved=True).order_by(Review.created_at.desc()).all()


# --- Legal & Community Policy pages ---

@public.route('/community-guidelines')
def community_guidelines():
    return render_template('policy.html', policy_type='guidelines')


@public.route('/privacy-policy')
def privacy_policy():
    return render_template('policy.html', policy_type='privacy')


@public.route('/cancellation-policy')
def cancellation_policy():
    return render_template('policy.html', policy_type='cancellation')


# --- API endpoints ---

@public.route('/api/surprise-me')
def api_surprise_me():
    settings = get_site_settings()
    city = request.args.get('city', settings.get('default_city', 'Vellore'))
    exclude_id = request.args.get('exclude')
    if exclude_id:
        try:
            exclude_id = int(exclude_id)
        except ValueError:
            exclude_id = None

    event = get_surprise_event(city=city, exclude_id=exclude_id)
    if not event:
        return jsonify({'error': 'No available experiences right now. Check back soon!'}), 404

    return jsonify({
        'id': event.id,
        'title': event.title,
        'slug': event.slug,
        'category': event.category,
        'short_description': event.short_description,
        'price': event.price,
        'start_datetime': event.start_datetime.isoformat(),
        'city': event.city,
        'location_name': event.location_name,
        'availability_label': event.availability_label,
        'duration_display': event.duration_display,
        'image_filename': event.image_filename,
        'url': url_for('public.experience_detail', slug=event.slug),
    })
