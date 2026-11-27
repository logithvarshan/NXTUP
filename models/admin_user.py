from datetime import datetime
from flask_login import UserMixin
from . import db, bcrypt

class AdminUser(UserMixin, db.Model):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<AdminUser {self.email}>'


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    reviewer_name = db.Column(db.String(150), nullable=False)
    reviewer_initial = db.Column(db.String(5), nullable=True)
    city = db.Column(db.String(100), nullable=True, default='Vellore')
    story = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=True)  # 1-5, optional
    experience_type = db.Column(db.String(100), nullable=True)
    approved = db.Column(db.Boolean, default=False)
    is_sample = db.Column(db.Boolean, default=False)  # clearly mark demo data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Review by {self.reviewer_name}>'
