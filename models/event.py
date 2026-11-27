from datetime import datetime
from . import db

class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    short_description = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # meet, vibe, explore, chill
    is_trip = db.Column(db.Boolean, default=False)
    image_filename = db.Column(db.String(255), nullable=True)

    # Location
    city = db.Column(db.String(100), nullable=False, default='Vellore')
    location_name = db.Column(db.String(200), nullable=True)
    location_details = db.Column(db.Text, nullable=True)

    # Timing
    start_datetime = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=120)

    # Pricing & capacity
    price = db.Column(db.Integer, nullable=False, default=0)  # in rupees
    capacity = db.Column(db.Integer, nullable=False, default=20)
    min_age = db.Column(db.Integer, nullable=True)

    # Content
    what_included = db.Column(db.Text, nullable=True)
    what_not_included = db.Column(db.Text, nullable=True)
    what_to_bring = db.Column(db.Text, nullable=True)
    activity_plan = db.Column(db.Text, nullable=True)
    accessibility_info = db.Column(db.Text, nullable=True)
    safety_info = db.Column(db.Text, nullable=True)
    cancellation_terms = db.Column(db.Text, nullable=True)
    faq = db.Column(db.Text, nullable=True)  # JSON string

    # Trip-specific
    transport_info = db.Column(db.Text, nullable=True)
    meals_info = db.Column(db.Text, nullable=True)
    physical_level = db.Column(db.String(50), nullable=True)  # easy, moderate, active

    # Status
    published = db.Column(db.Boolean, default=False)
    is_mystery = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bookings = db.relationship('Booking', backref='event', lazy='dynamic')
    reviews = db.relationship('Review', backref='event', lazy='dynamic')

    @property
    def confirmed_bookings_count(self):
        from .booking import Booking
        return Booking.query.filter_by(
            event_id=self.id
        ).filter(
            Booking.status.in_(['confirmed', 'pending'])
        ).with_entities(db.func.sum(Booking.places)).scalar() or 0

    @property
    def available_places(self):
        return max(0, self.capacity - self.confirmed_bookings_count)

    @property
    def is_sold_out(self):
        return self.available_places == 0

    @property
    def availability_label(self):
        places = self.available_places
        if places == 0:
            return 'Sold Out'
        elif places <= 3:
            return f'Only {places} left!'
        elif places <= 8:
            return f'{places} spots left'
        else:
            return 'Available'

    @property
    def duration_display(self):
        hours = self.duration_minutes // 60
        mins = self.duration_minutes % 60
        if hours and mins:
            return f'{hours}h {mins}m'
        elif hours:
            return f'{hours}h'
        else:
            return f'{mins}m'

    def __repr__(self):
        return f'<Event {self.slug}>'
