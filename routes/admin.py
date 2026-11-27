import os
import io
import csv
import re
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, Response, current_app
)
from flask_login import login_user, logout_user, login_required, current_user
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename
from models import db, Event, Booking, AdminUser, Review, ContactMessage, SiteSetting
from sqlalchemy.orm import joinedload
from services.settings_service import (
    DEFAULT_CATEGORIES, DEFAULT_SETTINGS,
    get_site_settings, get_categories, get_featured_event_ids,
    is_valid_hex_color, is_safe_url, save_settings,
)

admin = Blueprint('admin', __name__, url_prefix='/admin')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _validate_and_save_image(file_storage, prefix):
    """
    Validate an uploaded image using Pillow and save with a collision-free filename.
    Returns (relative_filename, error_message).
    """
    if not file_storage or not file_storage.filename:
        return None, None
    if not allowed_file(file_storage.filename):
        return None, "Unsupported image format. Use PNG, JPG, JPEG, WEBP, or GIF."

    # Verify image integrity via Pillow
    try:
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)
        img.verify()
        file_storage.stream.seek(0)
    except (UnidentifiedImageError, Exception):
        return None, "Uploaded file is not a valid image."

    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    safe_prefix = secure_filename(prefix) or 'img'
    filename = f"{safe_prefix}_{uuid.uuid4().hex[:8]}.{ext}"
    upload_dir = current_app.config.get(
        'UPLOAD_FOLDER',
        os.path.join(current_app.root_path, 'static', 'images', 'uploads'),
    )
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, filename))
    return f'uploads/{filename}', None


def _parse_int(value, default, min_val=None, max_val=None):
    if value is None or str(value).strip() == '':
        return default, True
    try:
        num = int(str(value).strip())
    except ValueError:
        return default, False
    if min_val is not None and num < min_val:
        return default, False
    if max_val is not None and num > max_val:
        return default, False
    return num, True


def _is_safe_next(target):
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.netloc and not parsed.scheme and target.startswith('/admin')


def _csv_safe(value):
    """Prevent CSV formula injection in spreadsheet exports."""
    s = str(value) if value is not None else ''
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s


# ── Auth routes ──────────────────────────────────────────────────────────────

@admin.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = AdminUser.query.filter_by(email=email, is_active=True).first()
        if user and user.check_password(password):
            session.clear()
            login_user(user)
            session.permanent = True
            user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.commit()
            next_url = request.args.get('next', '')
            if _is_safe_next(next_url):
                return redirect(next_url)
            return redirect(url_for('admin.dashboard'))
        else:
            error = "Invalid email or password."

    return render_template('admin/login.html', error=error), (401 if error else 200)


@admin.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin.login'))


# ── Dashboard ────────────────────────────────────────────────────────────────

@admin.route('/')
@admin.route('/dashboard')
@login_required
def dashboard():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    total_events = Event.query.filter_by(published=True).count()
    upcoming_events = Event.query.filter(Event.start_datetime > now, Event.published == True).count()
    total_bookings = Booking.query.count()
    confirmed = Booking.query.filter_by(status='confirmed').count()
    pending = Booking.query.filter_by(status='pending').count()
    cancelled = Booking.query.filter_by(status='cancelled').count()
    waitlisted = Booking.query.filter_by(status='waitlisted').count()
    pending_reviews = Review.query.filter_by(approved=False, is_sample=False).count()
    new_messages = ContactMessage.query.filter_by(status='new').count()

    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(8).all()
    upcoming = Event.query.filter(
        Event.published == True, Event.start_datetime > now
    ).order_by(Event.start_datetime).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        total_events=total_events,
        upcoming_events=upcoming_events,
        total_bookings=total_bookings,
        confirmed=confirmed,
        pending=pending,
        cancelled=cancelled,
        waitlisted=waitlisted,
        pending_reviews=pending_reviews,
        new_messages=new_messages,
        recent_bookings=recent_bookings,
        upcoming=upcoming,
        admin_name=current_user.name,
    )


# ── Event management ─────────────────────────────────────────────────────────

@admin.route('/events')
@login_required
def events():
    all_events = Event.query.order_by(Event.start_datetime.desc()).all()
    return render_template('admin/events.html', events=all_events)


@admin.route('/events/new', methods=['GET', 'POST'])
@login_required
def event_new():
    if request.method == 'POST':
        return _save_event(None)
    return render_template('admin/event_form.html', event=None, action='Create')


@admin.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def event_edit(event_id):
    event = db.get_or_404(Event, event_id)
    if request.method == 'POST':
        return _save_event(event)
    return render_template('admin/event_form.html', event=event, action='Edit')


@admin.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
def event_delete(event_id):
    event = db.get_or_404(Event, event_id)
    if event.bookings.count() > 0:
        flash(
            f'Cannot delete "{event.title}" because it has existing bookings. Unpublish it instead.',
            'error',
        )
        return redirect(url_for('admin.events'))

    # Detach any linked reviews rather than breaking FK constraints
    Review.query.filter_by(event_id=event.id).update({'event_id': None})
    db.session.delete(event)
    db.session.commit()
    flash(f'Event "{event.title}" deleted.', 'success')
    return redirect(url_for('admin.events'))


@admin.route('/events/<int:event_id>/toggle-publish', methods=['POST'])
@login_required
def event_toggle_publish(event_id):
    event = db.get_or_404(Event, event_id)
    event.published = not event.published
    db.session.commit()
    status = 'published' if event.published else 'unpublished'
    flash(f'"{event.title}" {status}.', 'success')
    return redirect(url_for('admin.events'))


def _save_event(event):
    is_new = event is None
    action_label = 'Create' if is_new else 'Edit'

    title = request.form.get('title', '').strip()
    short_description = request.form.get('short_description', '').strip()
    description = request.form.get('description', '').strip()
    city = request.form.get('city', '').strip() or get_site_settings().get('default_city', 'Vellore')
    category = request.form.get('category', 'meet').strip().lower()
    start_str = request.form.get('start_datetime', '').strip()

    errors = []
    if not title:
        errors.append('Title is required.')
    if not short_description:
        errors.append('Short description is required.')
    if not description:
        errors.append('Full description is required.')

    valid_cats = {c['slug'] for c in get_categories(include_disabled=True)}
    if category not in valid_cats:
        errors.append('Please select a valid category.')

    duration_minutes, ok_dur = _parse_int(request.form.get('duration_minutes'), 120, min_val=15, max_val=20160)
    if not ok_dur:
        errors.append('Duration must be at least 15 minutes.')

    price, ok_price = _parse_int(request.form.get('price'), 0, min_val=0, max_val=500000)
    if not ok_price:
        errors.append('Price must be 0 or higher.')

    capacity, ok_cap = _parse_int(request.form.get('capacity'), 20, min_val=1, max_val=500)
    if not ok_cap:
        errors.append('Capacity must be between 1 and 500.')

    min_age_raw = request.form.get('min_age', '').strip()
    min_age = None
    if min_age_raw:
        min_age_val, ok_age = _parse_int(min_age_raw, None, min_val=18, max_val=99)
        if not ok_age:
            errors.append('Minimum age must be 18 or older.')
        else:
            min_age = min_age_val

    parsed_start = None
    if not start_str:
        errors.append('Start date & time is required.')
    else:
        try:
            parsed_start = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            errors.append('Invalid date/time format.')

    slug_base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-') or 'experience'
    uploaded_img = None
    if 'image' in request.files and request.files['image'].filename:
        uploaded_img, img_err = _validate_and_save_image(request.files['image'], slug_base)
        if img_err:
            errors.append(img_err)

    if errors:
        for err in errors:
            flash(err, 'error')
        return render_template(
            'admin/event_form.html',
            event=event,
            action=action_label,
            form_data=request.form,
        ), 400

    if is_new:
        event = Event()
        # NOTE: db.session.add(event) is deferred until after slug and all
        # required fields are set, to prevent premature autoflush with NULLs.

    event.title = title[:200]
    if is_new or not event.slug:
        slug = slug_base
        counter = 1
        # For a new (unsaved) event, event.id is None so we only need to check
        # for any existing slug match (no same-event exclusion needed).
        while Event.query.filter_by(slug=slug).first() if is_new else \
              Event.query.filter(Event.slug == slug, Event.id != event.id).first():
            slug = f'{slug_base}-{counter}'
            counter += 1
        event.slug = slug

    if is_new:
        db.session.add(event)

    event.short_description = short_description[:300]
    event.description = description
    event.category = category
    event.city = city[:100]
    event.location_name = request.form.get('location_name', '').strip()[:200] or None
    event.location_details = request.form.get('location_details', '').strip() or None
    event.start_datetime = parsed_start
    event.duration_minutes = duration_minutes
    event.price = price
    event.capacity = capacity
    event.min_age = min_age
    event.what_included = request.form.get('what_included', '').strip() or None
    event.what_not_included = request.form.get('what_not_included', '').strip() or None
    event.what_to_bring = request.form.get('what_to_bring', '').strip() or None
    event.activity_plan = request.form.get('activity_plan', '').strip() or None
    event.accessibility_info = request.form.get('accessibility_info', '').strip() or None
    event.safety_info = request.form.get('safety_info', '').strip() or None
    event.cancellation_terms = request.form.get('cancellation_terms', '').strip() or None
    event.faq = request.form.get('faq', '').strip() or None
    event.transport_info = request.form.get('transport_info', '').strip() or None
    event.meals_info = request.form.get('meals_info', '').strip() or None
    physical = request.form.get('physical_level', '').strip().lower()
    event.physical_level = physical if physical in ('easy', 'moderate', 'active') else None
    event.is_trip = 'is_trip' in request.form
    event.is_mystery = 'is_mystery' in request.form
    event.published = 'published' in request.form

    if uploaded_img:
        event.image_filename = uploaded_img
    elif request.form.get('preset_image', '').strip() and not event.image_filename:
        preset = os.path.basename(request.form.get('preset_image', '').strip())
        if preset in {'hero_group_sunset.jpg', 'cafe_meetup.jpg', 'group_exploration.jpg', 'vellore_group.jpg', 'first_timer.jpg'}:
            event.image_filename = preset

    db.session.commit()
    flash(f'Event "{event.title}" saved.', 'success')
    return redirect(url_for('admin.events'))


# ── Booking management ───────────────────────────────────────────────────────

@admin.route('/bookings')
@login_required
def bookings():
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    event_filter = request.args.get('event_id', '').strip()

    query = Booking.query
    if search:
        query = query.filter(
            db.or_(
                Booking.name.ilike(f'%{search}%'),
                Booking.email.ilike(f'%{search}%'),
                Booking.reference.ilike(f'%{search}%'),
            )
        )
    if status_filter:
        query = query.filter(Booking.status == status_filter)
    if event_filter:
        try:
            query = query.filter(Booking.event_id == int(event_filter))
        except ValueError:
            event_filter = ''

    all_bookings = query.order_by(Booking.created_at.desc()).all()
    all_events = Event.query.order_by(Event.title).all()

    return render_template(
        'admin/bookings.html',
        bookings=all_bookings,
        events=all_events,
        search=search,
        status_filter=status_filter,
        event_filter=event_filter,
    )


@admin.route('/bookings/<int:booking_id>/status', methods=['POST'])
@login_required
def booking_update_status(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    new_status = request.form.get('status', '').strip()
    new_payment = request.form.get('payment_status', '').strip()
    allowed_status = {'pending', 'confirmed', 'waitlisted', 'cancelled', 'attended', 'no_show'}
    allowed_payment = {'not_applicable', 'pending', 'paid', 'refunded'}

    updated = False
    if new_status in allowed_status:
        booking.status = new_status
        updated = True
    if new_payment in allowed_payment:
        booking.payment_status = new_payment
        updated = True

    if updated:
        db.session.commit()
        flash(f'Booking {booking.reference} updated ({booking.status_label}).', 'success')
    else:
        flash('Invalid status value.', 'error')
    return redirect(url_for('admin.bookings'))


@admin.route('/bookings/export')
@login_required
def bookings_export():
    bookings_data = Booking.query.options(joinedload(Booking.event)).order_by(Booking.created_at.desc()).all()

    def generate():
        data = io.StringIO()
        writer = csv.writer(data)
        writer.writerow(['Reference', 'Name', 'Email', 'Phone', 'Event',
                         'Places', 'Status', 'Payment', 'Created'])
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

        for b in bookings_data:
            writer.writerow([
                _csv_safe(b.reference),
                _csv_safe(b.name),
                _csv_safe(b.email),
                _csv_safe(b.phone or ''),
                _csv_safe(b.event.title if b.event else ''),
                b.places,
                _csv_safe(b.status),
                _csv_safe(b.payment_status),
                b.created_at.strftime('%Y-%m-%d %H:%M'),
            ])
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    return Response(
        generate(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=nxtup-bookings.csv'},
    )


# ── Review moderation ────────────────────────────────────────────────────────

@admin.route('/reviews')
@login_required
def admin_reviews():
    all_reviews = Review.query.order_by(Review.approved, Review.created_at.desc()).all()
    return render_template('admin/reviews.html', reviews=all_reviews)


@admin.route('/reviews/<int:review_id>/approve', methods=['POST'])
@login_required
def approve_review(review_id):
    review = db.get_or_404(Review, review_id)
    review.approved = True
    db.session.commit()
    flash('Review approved.', 'success')
    return redirect(url_for('admin.admin_reviews'))


@admin.route('/reviews/<int:review_id>/unapprove', methods=['POST'])
@login_required
def unapprove_review(review_id):
    review = db.get_or_404(Review, review_id)
    review.approved = False
    db.session.commit()
    flash('Review hidden from public view.', 'info')
    return redirect(url_for('admin.admin_reviews'))


@admin.route('/reviews/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    review = db.get_or_404(Review, review_id)
    db.session.delete(review)
    db.session.commit()
    flash('Review deleted.', 'success')
    return redirect(url_for('admin.admin_reviews'))


# ── Contact Messages & Safety Reports ────────────────────────────────────────

@admin.route('/messages')
@login_required
def messages():
    status_filter = request.args.get('status', '').strip()
    query = ContactMessage.query
    if status_filter in ('new', 'reviewed', 'resolved'):
        query = query.filter_by(status=status_filter)
    all_msgs = query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/messages.html', messages=all_msgs, status_filter=status_filter)


@admin.route('/messages/<int:msg_id>/status', methods=['POST'])
@login_required
def message_update_status(msg_id):
    msg = db.get_or_404(ContactMessage, msg_id)
    status = request.form.get('status', '').strip()
    if status in ('new', 'reviewed', 'resolved'):
        msg.status = status
        db.session.commit()
        flash('Message status updated.', 'success')
    return redirect(url_for('admin.messages'))


@admin.route('/messages/<int:msg_id>/delete', methods=['POST'])
@login_required
def message_delete(msg_id):
    msg = db.get_or_404(ContactMessage, msg_id)
    db.session.delete(msg)
    db.session.commit()
    flash('Message deleted.', 'success')
    return redirect(url_for('admin.messages'))


# ── Site Customization System ────────────────────────────────────────────────

@admin.route('/customize', methods=['GET', 'POST'])
@login_required
def customize():
    all_events = Event.query.filter_by(published=True).order_by(Event.start_datetime.asc()).all()

    if request.method == 'POST':
        section = request.form.get('section', 'general')
        errors = []
        updates = {}

        if section == 'branding_theme':
            site_name = request.form.get('site_name', '').strip()
            if not site_name or len(site_name) > 60:
                errors.append('Website name is required (max 60 characters).')
            else:
                updates['site_name'] = site_name
                updates['site_name_prefix'] = request.form.get('site_name_prefix', '').strip()[:30] or site_name
                updates['site_name_accent'] = request.form.get('site_name_accent', '').strip()[:30]

            updates['tagline'] = request.form.get('tagline', '').strip()[:150] or DEFAULT_SETTINGS['tagline']
            updates['brand_tagline_secondary'] = request.form.get('brand_tagline_secondary', '').strip()[:150]
            updates['default_city'] = request.form.get('default_city', '').strip()[:80] or 'Vellore'

            contact_email = request.form.get('contact_email', '').strip()
            if contact_email and '@' not in contact_email:
                errors.append('Contact email must be valid.')
            else:
                updates['contact_email'] = contact_email or DEFAULT_SETTINGS['contact_email']

            for color_key, label in [
                ('primary_bg', 'Primary background color'),
                ('secondary_bg', 'Secondary background color'),
                ('accent_color', 'Accent color'),
                ('text_color', 'Text color'),
            ]:
                val = request.form.get(color_key, '').strip()
                if not is_valid_hex_color(val):
                    errors.append(f'{label} must be a valid hex color (e.g. #C8FF00).')
                else:
                    updates[color_key] = val.upper()

            if 'remove_logo' in request.form:
                updates['logo_filename'] = ''
            elif 'logo_file' in request.files and request.files['logo_file'].filename:
                logo_path, logo_err = _validate_and_save_image(request.files['logo_file'], 'site-logo')
                if logo_err:
                    errors.append(logo_err)
                else:
                    updates['logo_filename'] = logo_path

        elif section == 'hero_sections':
            updates['hero_eyebrow'] = request.form.get('hero_eyebrow', '').strip()[:120]
            updates['hero_heading_line1'] = request.form.get('hero_heading_line1', '').strip()[:40] or 'NAMMA'
            updates['hero_heading_line2'] = request.form.get('hero_heading_line2', '').strip()[:40]
            updates['hero_heading_accent'] = request.form.get('hero_heading_accent', '').strip()[:40]
            updates['hero_heading_line4'] = request.form.get('hero_heading_line4', '').strip()[:40]
            updates['hero_subtitle'] = request.form.get('hero_subtitle', '').strip()[:160]
            updates['hero_description'] = request.form.get('hero_description', '').strip()[:500]
            updates['hero_cta_primary'] = request.form.get('hero_cta_primary', '').strip()[:60] or 'FIND YOUR NEXT PLAN →'
            updates['hero_cta_secondary'] = request.form.get('hero_cta_secondary', '').strip()[:60] or 'HOW NXTUP WORKS'

            if 'hero_image_file' in request.files and request.files['hero_image_file'].filename:
                img_path, img_err = _validate_and_save_image(request.files['hero_image_file'], 'hero-bg')
                if img_err:
                    errors.append(img_err)
                else:
                    updates['hero_image'] = img_path

            for toggle in (
                'show_categories_section', 'show_upcoming_section', 'show_featured_section',
                'show_firsttimer_section', 'show_surprise_section', 'show_howitworks_section',
                'show_vibe_section', 'show_stories_section', 'show_safety_section',
            ):
                updates[toggle] = 'true' if toggle in request.form else 'false'

            updates['categories_eyebrow'] = request.form.get('categories_eyebrow', '').strip()[:80]
            updates['categories_title'] = request.form.get('categories_title', '').strip()[:100]
            updates['categories_subtitle'] = request.form.get('categories_subtitle', '').strip()[:200]
            updates['upcoming_eyebrow'] = request.form.get('upcoming_eyebrow', '').strip()[:80]
            updates['upcoming_title'] = request.form.get('upcoming_title', '').strip()[:100]
            updates['upcoming_subtitle'] = request.form.get('upcoming_subtitle', '').strip()[:200]
            updates['featured_eyebrow'] = request.form.get('featured_eyebrow', '').strip()[:80]
            updates['featured_title'] = request.form.get('featured_title', '').strip()[:100]

            selected_featured = request.form.getlist('featured_event_ids')
            featured_ids = [int(x) for x in selected_featured if x.isdigit()]
            updates['featured_event_ids'] = json.dumps(featured_ids)

        elif section == 'nav_announcements':
            updates['announcement_enabled'] = 'true' if 'announcement_enabled' in request.form else 'false'
            updates['announcement_text'] = request.form.get('announcement_text', '').strip()[:200]
            ann_link = request.form.get('announcement_link', '').strip()[:300]
            if not is_safe_url(ann_link):
                errors.append('Announcement link must start with /, http://, or https://.')
            else:
                updates['announcement_link'] = ann_link
            updates['announcement_link_label'] = request.form.get('announcement_link_label', '').strip()[:50] or 'Learn more →'

            for nav_key in ('nav_home', 'nav_explore', 'nav_trips', 'nav_stories', 'nav_about', 'nav_my_plans', 'nav_cta'):
                val = request.form.get(nav_key, '').strip()[:40]
                if not val:
                    errors.append(f'Navigation label "{nav_key}" cannot be empty.')
                else:
                    updates[nav_key] = val

        elif section == 'footer':
            updates['footer_tagline'] = request.form.get('footer_tagline', '').strip()[:300]
            updates['footer_copyright'] = request.form.get('footer_copyright', '').strip()[:160]
            updates['footer_made_in'] = request.form.get('footer_made_in', '').strip()[:120]
            for social_key in ('social_instagram', 'social_twitter', 'social_whatsapp'):
                sval = request.form.get(social_key, '').strip()[:300]
                if not is_safe_url(sval):
                    errors.append(f'{social_key.replace("_", " ").title()} URL must start with http://, https://, or /.')
                else:
                    updates[social_key] = sval

        elif section == 'categories':
            existing_cats = get_categories(include_disabled=True)
            updated_cats = []
            for cat in existing_cats:
                slug = cat['slug']
                label = request.form.get(f'cat_label_{slug}', '').strip()[:60]
                icon = request.form.get(f'cat_icon_{slug}', '').strip()[:10] or cat['icon']
                desc = request.form.get(f'cat_desc_{slug}', '').strip()[:240]
                color = request.form.get(f'cat_color_{slug}', '').strip()
                cta_label = request.form.get(f'cat_cta_{slug}', '').strip()[:40] or 'EXPLORE →'
                tags_raw = request.form.get(f'cat_tags_{slug}', '').strip()
                tags = [t.strip() for t in tags_raw.split(',') if t.strip()][:6]

                if not label:
                    errors.append(f'Category "{slug}" requires a label.')
                if not is_valid_hex_color(color):
                    errors.append(f'Category "{slug}" color must be a valid hex code.')

                updated_cats.append({
                    'slug': slug,
                    'label': label or cat['label'],
                    'icon': icon,
                    'description': desc,
                    'color': color.upper() if is_valid_hex_color(color) else cat['color'],
                    'tags': tags,
                    'cta_label': cta_label,
                    'show_on_home': f'cat_home_{slug}' in request.form,
                    'enabled': f'cat_enabled_{slug}' in request.form,
                })

            # Optional new category
            new_slug = re.sub(r'[^a-z0-9_-]+', '', request.form.get('new_cat_slug', '').strip().lower())
            new_label = request.form.get('new_cat_label', '').strip()[:60]
            if new_slug and new_label:
                if any(c['slug'] == new_slug for c in updated_cats):
                    errors.append(f'Category slug "{new_slug}" already exists.')
                else:
                    new_color = request.form.get('new_cat_color', '#C8FF00').strip()
                    if not is_valid_hex_color(new_color):
                        new_color = '#C8FF00'
                    new_tags = [t.strip() for t in request.form.get('new_cat_tags', '').split(',') if t.strip()][:6]
                    updated_cats.append({
                        'slug': new_slug,
                        'label': new_label,
                        'icon': request.form.get('new_cat_icon', '✨').strip()[:10] or '✨',
                        'description': request.form.get('new_cat_desc', '').strip()[:240],
                        'color': new_color.upper(),
                        'tags': new_tags,
                        'cta_label': request.form.get('new_cat_cta', 'EXPLORE →').strip()[:40] or 'EXPLORE →',
                        'show_on_home': 'new_cat_home' in request.form,
                        'enabled': True,
                    })

            if not errors:
                updates['categories_json'] = json.dumps(updated_cats)

        elif section == 'reset_defaults':
            SiteSetting.query.delete()
            db.session.commit()
            flash('All customizations have been reset to NXTUP defaults.', 'success')
            return redirect(url_for('admin.customize'))

        if errors:
            for err in errors:
                flash(err, 'error')
        elif updates:
            save_settings(updates)
            flash('Customization settings saved and applied live!', 'success')
            return redirect(url_for('admin.customize', tab=section))

    active_tab = request.args.get('tab', 'branding_theme')
    return render_template(
        'admin/customize.html',
        settings=get_site_settings(),
        categories=get_categories(include_disabled=True),
        all_events=all_events,
        featured_ids=get_featured_event_ids(),
        active_tab=active_tab,
    )
