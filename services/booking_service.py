from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from models import db
from models.booking import Booking
from models.event import Event


def create_booking(event_id, name, email, phone, places, notes=''):
    """
    Atomic booking with capacity check inside a DB transaction.
    Returns (booking, error_message).
    """
    if not isinstance(places, int) or places < 1 or places > 5:
        return None, "You can book between 1 and 5 places."

    try:
        with db.session.begin_nested():
            event = db.session.get(Event, event_id)
            if event is None:
                return None, "Experience not found."

            if not event.published:
                return None, "This experience is no longer available."

            if event.start_datetime <= datetime.now(timezone.utc).replace(tzinfo=None):
                return None, "Registration for this experience has closed."

            if event.available_places < places:
                if event.available_places == 0:
                    return None, "Sorry, this experience is sold out."
                return None, f"Only {event.available_places} place(s) remaining."

            # Guard against duplicate active booking (same email + event)
            existing = Booking.query.filter_by(
                email=email.lower().strip(),
                event_id=event_id
            ).filter(
                Booking.status.in_(['pending', 'confirmed', 'waitlisted'])
            ).first()

            if existing:
                return None, f"You already have a booking for this experience (Ref: {existing.reference})."

            booking = Booking(
                name=name.strip(),
                email=email.lower().strip(),
                phone=phone.strip() if phone else None,
                event_id=event_id,
                places=places,
                notes=notes.strip() if notes else None,
                status='pending',
                payment_status='not_applicable',
            )
            db.session.add(booking)

        db.session.commit()
        return booking, None

    except IntegrityError:
        db.session.rollback()
        return None, "A booking conflict occurred. Please try again."
    except Exception:
        db.session.rollback()
        return None, "An unexpected error occurred. Please try again."


def get_booking_by_reference(reference, email):
    """Secure lookup — requires both reference and email."""
    return Booking.query.filter_by(
        reference=reference.upper().strip(),
        email=email.lower().strip()
    ).first()


def cancel_booking(booking_id):
    """Cancel a booking and return success/error."""
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return False, "Booking not found."
    if booking.status == 'cancelled':
        return False, "Booking is already cancelled."
    if booking.status == 'attended':
        return False, "Cannot cancel an attended booking."
    booking.status = 'cancelled'
    db.session.commit()
    return True, "Booking cancelled."
