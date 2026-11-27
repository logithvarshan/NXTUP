import io
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, _seed_sample_data
from models import db, Event, Booking, AdminUser, Review, ContactMessage, SiteSetting


class NxtupTestCase(unittest.TestCase):
    def setUp(self):
        self.upload_dir = tempfile.mkdtemp(prefix='nxtup_test_uploads_')
        self.app = create_app('testing')
        self.app.config['UPLOAD_FOLDER'] = self.upload_dir
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            _seed_sample_data()
            admin = AdminUser(name='Test Admin', email='admin@nxtup.in', is_active=True)
            admin.set_password('TestPass123!')
            db.session.add(admin)

            inactive = AdminUser(name='Inactive Admin', email='inactive@nxtup.in', is_active=False)
            inactive.set_password('TestPass123!')
            db.session.add(inactive)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        for fname in os.listdir(self.upload_dir):
            os.remove(os.path.join(self.upload_dir, fname))
        os.rmdir(self.upload_dir)

    def _get_csrf(self, path):
        resp = self.client.get(path)
        html = resp.get_data(as_text=True)
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        self.assertIsNotNone(match, f'CSRF token not found on {path}')
        return match.group(1)

    def _login_admin(self, email='admin@nxtup.in', password='TestPass123!'):
        token = self._get_csrf('/admin/login')
        return self.client.post(
            '/admin/login',
            data={'csrf_token': token, 'email': email, 'password': password},
            follow_redirects=False,
        )

    # ── Public Routes ────────────────────────────────────────────────────────

    def test_public_pages_render_200(self):
        for path in [
            '/', '/explore', '/trips', '/about', '/contact',
            '/my-plans', '/reviews', '/community-guidelines',
            '/privacy-policy', '/cancellation-policy',
        ]:
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, f'Expected 200 for {path}')

    def test_404_custom_page(self):
        resp = self.client.get('/does-not-exist-xyz')
        self.assertEqual(resp.status_code, 404)
        self.assertIn(b'404', resp.data)

    def test_trips_page_filters(self):
        resp = self.client.get('/trips')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Day Trip', resp.data)
        self.assertNotIn(b'Sunset Strangers', resp.data)

        resp_level = self.client.get('/trips?level=moderate')
        self.assertIn(b'Yelagiri', resp_level.data)

        resp_empty = self.client.get('/trips?level=active')
        self.assertIn(b'No trips match your filters', resp_empty.data)

    def test_explore_filters_and_search(self):
        resp = self.client.get('/explore?q=Sunset')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Sunset Strangers', resp.data)

        resp_cat = self.client.get('/explore?category=mystery')
        self.assertIn(b'Mystery Meetup', resp_cat.data)

        resp_budget = self.client.get('/explore?budget=under_300')
        self.assertEqual(resp_budget.status_code, 200)

        resp_sort = self.client.get('/explore?sort=price_low')
        self.assertEqual(resp_sort.status_code, 200)

        resp_none = self.client.get('/explore?q=NoSuchEventXYZ')
        self.assertIn(b'No experiences match your filters', resp_none.data)

    def test_surprise_me_api(self):
        resp = self.client.get('/api/surprise-me')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('title', data)
        self.assertIn('url', data)

        resp2 = self.client.get(f"/api/surprise-me?exclude={data['id']}")
        self.assertEqual(resp2.status_code, 200)
        self.assertNotEqual(resp2.get_json()['id'], data['id'])

    # ── Bookings & My Plans ──────────────────────────────────────────────────

    def test_experience_detail_and_booking_flow(self):
        detail = self.client.get('/experiences/sunset-strangers-vellore')
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b'Reserve Your Place', detail.data)

        csrf_token = self._get_csrf('/experiences/sunset-strangers-vellore')

        # Invalid places string should return 400 cleanly (no 500)
        bad_places = self.client.post(
            '/experiences/sunset-strangers-vellore/book',
            data={'csrf_token': csrf_token, 'name': 'Test User', 'email': 't@example.com', 'places': 'abc'},
        )
        self.assertEqual(bad_places.status_code, 400)

        # Valid booking
        ok = self.client.post(
            '/experiences/sunset-strangers-vellore/book',
            data={
                'csrf_token': csrf_token,
                'name': 'Karthik R.',
                'email': 'karthik@example.com',
                'phone': '+91 9876543210',
                'places': '2',
                'notes': 'Excited!',
            },
        )
        self.assertEqual(ok.status_code, 200)
        html = ok.get_data(as_text=True)
        self.assertIn('Booking Received', html)

        match = re.search(r'(NXT-[A-F0-9]{8})', html)
        self.assertIsNotNone(match)
        ref = match.group(1)

        # Duplicate booking should be blocked
        dup = self.client.post(
            '/experiences/sunset-strangers-vellore/book',
            data={
                'csrf_token': csrf_token,
                'name': 'Karthik R.',
                'email': 'KARTHIK@example.com',
                'places': '1',
            },
        )
        self.assertEqual(dup.status_code, 400)
        self.assertIn(b'already have a booking', dup.data)

        # My Plans lookup (case-insensitive)
        mp_csrf = self._get_csrf('/my-plans')
        lookup = self.client.post(
            '/my-plans',
            data={'csrf_token': mp_csrf, 'reference': ref.lower(), 'email': 'KARTHIK@example.com'},
        )
        self.assertEqual(lookup.status_code, 200)
        self.assertIn(ref.encode(), lookup.data)

        # Wrong email lookup
        bad_lookup = self.client.post(
            '/my-plans',
            data={'csrf_token': mp_csrf, 'reference': ref, 'email': 'wrong@example.com'},
        )
        self.assertIn(b'No booking found', bad_lookup.data)

    def test_booking_csrf_and_past_event_protection(self):
        # Missing CSRF rejected
        no_csrf = self.client.post(
            '/experiences/sunset-strangers-vellore/book',
            data={'name': 'No CSRF', 'email': 'nocsrf@example.com', 'places': '1'},
        )
        self.assertEqual(no_csrf.status_code, 400)

        # Past event cannot be booked
        with self.app.app_context():
            past_ev = Event(
                title='Past Event',
                slug='past-event',
                short_description='Past',
                description='Past event description',
                category='meet',
                city='Vellore',
                start_datetime=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2),
                duration_minutes=60,
                price=0,
                capacity=10,
                published=True,
            )
            db.session.add(past_ev)
            db.session.commit()

        csrf_token = self._get_csrf('/contact')  # past event page hides booking form; get token from contact page
        resp = self.client.post(
            '/experiences/past-event/book',
            data={'csrf_token': csrf_token, 'name': 'Late User', 'email': 'late@example.com', 'places': '1'},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b'closed', resp.data)

    # ── Contact & Reviews ────────────────────────────────────────────────────

    def test_contact_persistence_and_validation(self):
        csrf_token = self._get_csrf('/contact')
        bad = self.client.post(
            '/contact',
            data={'csrf_token': csrf_token, 'name': 'A', 'email': 'bad-email', 'message': 'hi'},
        )
        self.assertEqual(bad.status_code, 400)

        ok = self.client.post(
            '/contact',
            data={
                'csrf_token': csrf_token,
                'category': 'safety',
                'name': 'Priya S.',
                'email': 'priya@example.com',
                'subject': 'Question',
                'message': 'This is a valid inquiry message with enough characters.',
            },
        )
        self.assertEqual(ok.status_code, 200)
        with self.app.app_context():
            self.assertEqual(ContactMessage.query.count(), 1)

    def test_reviews_submission_and_validation(self):
        csrf_token = self._get_csrf('/reviews')
        bad = self.client.post(
            '/reviews',
            data={'csrf_token': csrf_token, 'name': 'Me', 'story': 'Short', 'rating': '99'},
        )
        self.assertEqual(bad.status_code, 400)

        ok = self.client.post(
            '/reviews',
            data={
                'csrf_token': csrf_token,
                'name': 'Deepak K.',
                'experience_type': 'Sunset Strangers',
                'rating': '5',
                'story': 'Had an amazing evening meeting strangers at Vellore Fort!',
            },
        )
        self.assertEqual(ok.status_code, 200)
        with self.app.app_context():
            r = Review.query.filter_by(reviewer_name='Deepak K.').first()
            self.assertIsNotNone(r)
            self.assertFalse(r.approved)

    # ── Admin Auth, CRUD, CSV & Security ─────────────────────────────────────

    def test_admin_auth_guards_and_open_redirect(self):
        for route in [
            '/admin/dashboard', '/admin/events', '/admin/bookings',
            '/admin/reviews', '/admin/messages', '/admin/customize',
        ]:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/admin/login', res.headers['Location'])

        # Inactive user cannot login
        token = self._get_csrf('/admin/login')
        res_inactive = self.client.post(
            '/admin/login',
            data={'csrf_token': token, 'email': 'inactive@nxtup.in', 'password': 'TestPass123!'},
        )
        self.assertEqual(res_inactive.status_code, 401)

        # Open redirect protection
        res_redir = self.client.post(
            '/admin/login?next=https://evil.example.com',
            data={'csrf_token': token, 'email': 'admin@nxtup.in', 'password': 'TestPass123!'},
            follow_redirects=False,
        )
        self.assertEqual(res_redir.status_code, 302)
        self.assertNotIn('evil.example.com', res_redir.headers['Location'])

    def test_admin_event_crud_and_image_validation(self):
        self._login_admin()
        csrf_token = self._get_csrf('/admin/events/new')

        # Reject fake non-image upload
        fake_img = (io.BytesIO(b'not-an-image'), 'fake.png')
        res_bad_img = self.client.post(
            '/admin/events/new',
            data={
                'csrf_token': csrf_token,
                'title': 'New Meetup',
                'short_description': 'Short desc',
                'description': 'Full desc here',
                'category': 'meet',
                'city': 'Chennai',
                'start_datetime': '2027-01-15T18:00',
                'duration_minutes': '120',
                'price': '250',
                'capacity': '10',
                'published': 'on',
                'image': fake_img,
            },
            content_type='multipart/form-data',
        )
        self.assertEqual(res_bad_img.status_code, 400)

        # Valid Pillow image upload
        img_bytes = io.BytesIO()
        Image.new('RGB', (40, 40), color=(200, 255, 0)).save(img_bytes, format='PNG')
        img_bytes.seek(0)

        res_ok = self.client.post(
            '/admin/events/new',
            data={
                'csrf_token': csrf_token,
                'title': 'Chennai Marina Walk',
                'short_description': 'Sunrise walk with strangers',
                'description': 'Join us at Marina Beach.',
                'category': 'explore',
                'city': 'Chennai',
                'start_datetime': '2027-01-20T06:30',
                'duration_minutes': '90',
                'price': '150',
                'capacity': '12',
                'published': 'on',
                'image': (img_bytes, 'marina.png'),
            },
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertIn(b'Chennai Marina Walk', res_ok.data)

        with self.app.app_context():
            ev = Event.query.filter_by(slug='chennai-marina-walk').first()
            self.assertIsNotNone(ev)
            self.assertTrue(ev.image_filename.startswith('uploads/'))
            ev_id = ev.id

        # Delete event without bookings succeeds
        del_token = self._get_csrf('/admin/events')
        res_del = self.client.post(
            f'/admin/events/{ev_id}/delete',
            data={'csrf_token': del_token},
            follow_redirects=True,
        )
        self.assertEqual(res_del.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Event, ev_id))

    def test_admin_bookings_csv_formula_injection_protection(self):
        # Create a booking with dangerous formula prefix in name
        pub_token = self._get_csrf('/experiences/sunset-strangers-vellore')
        self.client.post(
            '/experiences/sunset-strangers-vellore/book',
            data={
                'csrf_token': pub_token,
                'name': '=CMD("calc")',
                'email': 'formula@example.com',
                'places': '1',
            },
        )
        self._login_admin()
        csv_resp = self.client.get('/admin/bookings/export')
        self.assertEqual(csv_resp.status_code, 200)
        csv_text = csv_resp.get_data(as_text=True)
        self.assertIn("'=CMD", csv_text)

    # ── Customization System ─────────────────────────────────────────────────

    def test_admin_customization_system(self):
        self._login_admin()
        csrf_token = self._get_csrf('/admin/customize')

        # Reject invalid hex color
        bad_color = self.client.post(
            '/admin/customize',
            data={
                'csrf_token': csrf_token,
                'section': 'branding_theme',
                'site_name': 'NXTUP',
                'primary_bg': 'not-a-color',
                'secondary_bg': '#171717',
                'accent_color': '#C8FF00',
                'text_color': '#F5F5F5',
            },
            follow_redirects=True,
        )
        self.assertIn(b'valid hex color', bad_color.data)

        # Valid branding + color update
        self.client.post(
            '/admin/customize',
            data={
                'csrf_token': csrf_token,
                'section': 'branding_theme',
                'site_name': 'NXTUP TN',
                'site_name_prefix': 'NXT',
                'site_name_accent': 'UP!',
                'tagline': 'Meet. Vibe. Explore.',
                'default_city': 'Vellore',
                'contact_email': 'care@nxtup.in',
                'primary_bg': '#0B0B0B',
                'secondary_bg': '#171717',
                'accent_color': '#FF5500',
                'text_color': '#FFFFFF',
            },
            follow_redirects=True,
        )

        # Enable announcement + custom nav label (and test XSS URL rejection)
        bad_ann = self.client.post(
            '/admin/customize',
            data={
                'csrf_token': csrf_token,
                'section': 'nav_announcements',
                'announcement_enabled': 'on',
                'announcement_text': 'Big Weekend Meetup!',
                'announcement_link': 'javascript:alert(1)',
                'nav_home': 'Home',
                'nav_explore': 'Discover',
                'nav_trips': 'Trips',
                'nav_stories': 'Stories',
                'nav_about': 'About',
                'nav_my_plans': 'My Plans',
                'nav_cta': 'Join Now',
            },
            follow_redirects=True,
        )
        self.assertIn(b'must start with /, http://, or https://', bad_ann.data)

        self.client.post(
            '/admin/customize',
            data={
                'csrf_token': csrf_token,
                'section': 'nav_announcements',
                'announcement_enabled': 'on',
                'announcement_text': 'Big Weekend Meetup!',
                'announcement_link': '/trips',
                'announcement_link_label': 'See Trips →',
                'nav_home': 'Home',
                'nav_explore': 'Discover',
                'nav_trips': 'Trips',
                'nav_stories': 'Stories',
                'nav_about': 'About',
                'nav_my_plans': 'My Plans',
                'nav_cta': 'Join Now',
            },
            follow_redirects=True,
        )

        # Verify dynamic changes appear on homepage
        home = self.client.get('/')
        home_text = home.get_data(as_text=True)
        self.assertIn('#FF5500', home_text)
        self.assertIn('Big Weekend Meetup!', home_text)
        self.assertIn('Discover', home_text)

        # Reset defaults
        self.client.post(
            '/admin/customize',
            data={'csrf_token': csrf_token, 'section': 'reset_defaults'},
            follow_redirects=True,
        )
        home_reset = self.client.get('/').get_data(as_text=True)
        self.assertIn('#C8FF00', home_reset)
        self.assertNotIn('Big Weekend Meetup!', home_reset)

    def test_theme_toggle_and_social_links(self):
        from services.settings_service import DEFAULT_SETTINGS

        whatsapp_url = DEFAULT_SETTINGS['social_whatsapp']
        instagram_url = DEFAULT_SETTINGS['social_instagram']
        self.assertIn('https://chat.whatsapp.com/', whatsapp_url)
        self.assertIn('https://www.instagram.com/nxtup.hub', instagram_url)

        for path in ('/', '/contact'):
            html = self.client.get(path).get_data(as_text=True)
            # Theme toggle & FOUC-prevention bootstrap
            self.assertIn('data-theme-toggle', html)
            self.assertIn("localStorage.getItem('nxtup-theme')", html)
            self.assertIn('theme-icon--moon', html)
            self.assertIn('theme-icon--sun', html)

            # Social links rendered cleanly from central settings
            self.assertIn('Join Our WhatsApp Community', html)
            self.assertIn('Follow Us on Instagram', html)
            self.assertIn(whatsapp_url, html)
            self.assertIn(instagram_url, html)
            self.assertIn('target="_blank"', html)
            self.assertIn('rel="noopener noreferrer"', html)

        # Contact page specifically renders social links both in community card and footer
        contact_html = self.client.get('/contact').get_data(as_text=True)
        self.assertEqual(contact_html.count('<span>Join Our WhatsApp Community</span>'), 2)
        self.assertEqual(contact_html.count('<span>Follow Us on Instagram</span>'), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
