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
from packs_management import Pack
from packs_management import get_user_packs

user_management = Blueprint("user_management", __name__, static_folder="static", template_folder="templates")


class User(shared.db.Model, UserMixin):
    id = shared.db.Column(shared.db.Integer, primary_key=True, autoincrement=True)
    username = shared.db.Column(shared.db.String(80), nullable=False)
    email = shared.db.Column(shared.db.String(120), unique=True, nullable=False)
    password_hash = shared.db.Column(shared.db.String(128), nullable=False)
    packs = shared.db.Column(shared.db.Text)
    is_active = shared.db.Column(shared.db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)


@shared.login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class RegistrationForm(FlaskForm):
    name = StringField('Prénom', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField("S'inscrire")


# noinspection PyArgumentList
@user_management.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.name.data, email=str(form.email.data).lower())
        user.set_password(form.password.data)
        existing_user = User.query.filter_by(email=str(form.email.data).lower()).first()
        if existing_user:
            flash('Un utilisateur avec la même adresse mail existe déja.', 'error')
            return redirect(url_for('user_management.register'))
        shared.db.session.add(user)
        shared.db.session.commit()
        session.pop('_flashes', None)
        flash('Vous avez bien été enregistré!')
        user = User.query.filter_by(email=str(form.email.data).lower()).first()
        if user is None or not user.check_password(form.password.data):
            session.pop('_flashes', None)
            flash("Erreur, tu n'existe pas dans la base de donnée, comment c'est possible ?")
            return redirect(url_for('user_management.register'))
        login_user(user)
        return redirect(url_for('user_management.profile'))
    return render_template('user_management/register.html', form=form)


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField('Se connecter')


@user_management.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=str(form.email.data).lower()).first()
        if user is None or not user.check_password(form.password.data):
            session.pop('_flashes', None)
            flash('Email ou mot de passe invalide.')
            return redirect(url_for('user_management.login'))
        login_user(user)
        return redirect(url_for('user_management.profile'))
    return render_template('user_management/login.html', form=form)


class UpdateProfileForm(FlaskForm):
    name = StringField('Prénom', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Entrer le mot de passe actuel pour confirmer les changements.',
                             validators=[DataRequired()])
    new_password = PasswordField('Nouveau mot de passe (optionnel)', validators=[Optional(), EqualTo('confirm',
                                                                                                     message='Les mots de passe doivent correspondre.')])
    confirm = PasswordField('Confirmer le nouveau mot de passe', validators=[Optional()])
    submit = SubmitField('Sauvegarder les changements.')


@user_management.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateProfileForm()  # Assuming this form now includes a 'new_password' field
    user_packs = get_user_packs(current_user.id)  # Fetch user-specific packs
    if form.validate_on_submit():
        user = User.query.filter_by(id=current_user.id).first()
        if user and user.check_password(form.password.data):
            if form.email.data != current_user.email and User.query.filter_by(email=form.email.data).first():
                flash('This email is already used.')
            else:
                user.username = form.name.data
                user.email = form.email.data
                if form.new_password.data:  # If a new password is provided
                    user.set_password(form.new_password.data)
                shared.db.session.commit()
                flash('Your profile was updated successfully.')
                return redirect(url_for('user_management.profile'))
        else:
            flash('Incorrect password.')
    return render_template('user_management/profile.html', form=form, current_user=current_user, user_packs=user_packs)


@user_management.route('/user/<int:user_id>')
def show_user_profile(user_id):
    # Query the database for the user
    user = User.query.get(user_id)
    if not user:
        abort(404)  # If no user is found, return a 404 error
    if current_user.is_authenticated:
        # Fetch all packs that are either public, the user is authorized to view, or the user has created
        all_packs = Pack.query.filter(
            (Pack.private == False) |
            (Pack.user_id == current_user.id) |
            (Pack.authorized_users.contains(current_user.id))
        ).all()
    else:
        # Fetch only public packs for not authenticated users
        all_packs = Pack.query.filter_by(private=False).all()

    packs = []
    for pack in all_packs:

        pack_dict = {
            "id": pack.id,
            "name": pack.name,
            "category": pack.categories,
            "preview": pack.preview,
            "images": pack.images,
            "private": pack.private,
        }
        packs.append(pack_dict)
    return render_template('user_management/user.html', user=user, user_packs=packs)


@user_management.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('_flashes', None)
    flash('Vous avez été déconnecté.')
    return redirect(url_for('user_management.login'))
