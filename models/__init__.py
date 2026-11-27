from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
csrf = CSRFProtect()

from .event import Event
from .booking import Booking
from .admin_user import AdminUser, Review
from .site_setting import SiteSetting, ContactMessage

__all__ = [
    'db', 'bcrypt', 'login_manager', 'csrf',
    'Event', 'Booking', 'AdminUser', 'Review',
    'SiteSetting', 'ContactMessage',
]
