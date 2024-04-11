import os

from flask import Blueprint
from flask import redirect, url_for, flash, render_template
from flask import session, abort
from flask_login import UserMixin
from flask_login import current_user, login_user, logout_user, login_required
from flask_wtf import FlaskForm
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Optional

import shared

class User(shared.db.Model, UserMixin):
    id = shared.db.Column(shared.db.Integer, primary_key=True, autoincrement=True)
    username = shared.db.Column(shared.db.String(80), nullable=False)
    email = shared.db.Column(shared.db.String(120), unique=True, nullable=False)
    password_hash = shared.db.Column(shared.db.String(128), nullable=False)
    packs = shared.db.Column(shared.db.Text)
    is_active = shared.db.Column(shared.db.Boolean, default=True)
    current_tournament = shared.db.Column(shared.db.Integer)
    tournaments = shared.db.Column(shared.db.Text)
    current_images = shared.db.Column(shared.db.Text)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)

class Pack(shared.db.Model):
    id = shared.db.Column(shared.db.Integer, primary_key=True, autoincrement=True)
    name = shared.db.Column(shared.db.Text, nullable=False)
    categories = shared.db.Column(shared.db.Text, nullable=False)
    preview = shared.db.Column(shared.db.Text, nullable=False)
    images = shared.db.Column(shared.db.Text, nullable=False)
    user_id = shared.db.Column(shared.db.Integer, nullable=False)
    private = shared.db.Column(shared.db.Boolean, nullable=False)
    authorized_users = shared.db.Column(shared.db.String, nullable=False)