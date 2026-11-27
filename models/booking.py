import uuid
from datetime import datetime
from . import db

def generate_reference():
    return 'NXT-' + uuid.uuid4().hex[:8].upper()

class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False, default=generate_reference, index=True)

    # Participant info
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(200), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)

    # Booking details
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)
    places = db.Column(db.Integer, nullable=False, default=1)
    notes = db.Column(db.Text, nullable=True)

    # Status: pending | confirmed | waitlisted | cancelled | attended | no_show
    status = db.Column(db.String(20), nullable=False, default='pending')
    # Payment: not_applicable | pending | paid | refunded
    payment_status = db.Column(db.String(20), nullable=False, default='not_applicable')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def status_label(self):
        labels = {
            'pending': 'Awaiting Confirmation',
            'confirmed': 'Confirmed',
            'waitlisted': 'On Waitlist',
            'cancelled': 'Cancelled',
            'attended': 'Attended',
            'no_show': 'No Show',
        }
        return labels.get(self.status, self.status.title())

    @property
    def status_class(self):
        classes = {
            'pending': 'status-pending',
            'confirmed': 'status-confirmed',
            'waitlisted': 'status-waitlisted',
            'cancelled': 'status-cancelled',
            'attended': 'status-attended',
            'no_show': 'status-noshow',
        }
        return classes.get(self.status, '')

    def __repr__(self):
        return f'<Booking {self.reference}>'
