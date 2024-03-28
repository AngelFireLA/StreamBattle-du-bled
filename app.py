import hashlib
import json
import os
import random
import re
import shutil
import zipfile
from datetime import datetime

import instaloader
from bing_image_downloader import downloader
from flask import Flask, session, abort
from flask import jsonify
from flask import request, redirect, url_for, flash, render_template
from flask import send_file
from flask_login import LoginManager
from flask_login import UserMixin
from flask_login import current_user, login_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms import BooleanField, TextAreaField
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Optional

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tournamentsite.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = "login"  #


class Pack(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, nullable=False)
    folder = db.Column(db.Text, nullable=False)
    categories = db.Column(db.Text, nullable=False)
    preview = db.Column(db.Text, nullable=False)
    images = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    private = db.Column(db.Boolean, nullable=False)
    authorized_users = db.Column(db.String, nullable=False)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    packs = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)


@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()

if not os.path.exists(os.path.join(app.static_folder, 'images')):
    os.makedirs(os.path.join(app.static_folder, 'images'))

if not os.path.exists(os.path.join(app.static_folder, 'tournaments')):
    os.makedirs(os.path.join(app.static_folder, 'tournaments'))

# load images
images_dir = os.path.join(app.static_folder, 'images')
tournaments_dir = os.path.join(app.static_folder, 'tournaments')
app.secret_key = "srguzGW2kTdjhqpsUKnG5DyJvvCUk5b9"

# These variables store the current images being compared (ROUND) and the winners of these comparisons (WINNERS)
ROUND = []
WINNERS = []
TOTAL_IMAGES = None
round_number = None
match_number = 0


def create_tournament(tournament_id, participants):
    date_prefix = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    file_name = f"{date_prefix}_{tournament_id}.json"
    tournament_data = {
        "tournament_id": tournament_id,
        "date_created": date_prefix,
        "status": "on-going",
        "type": "single-knockout",
        "participants": participants,
        "matches": [],
        "rankings": []
    }
    with open(os.path.join(tournaments_dir, file_name), 'w') as file:
        json.dump(tournament_data, file)
    return file_name


@app.route('/start', methods=['GET'])
def start():
    global ROUND, WINNERS, TOTAL_IMAGES, round_number
    images = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))]
    print(images)
    random.shuffle(images)
    tournament_file = create_tournament(random.randint(999, 9999999), images)
    session['tournament_file'] = tournament_file
    ROUND = images
    if len(images) % 2 == 1:
        round_number = len(images) + 1
    else:
        round_number = len(images)

    return redirect(url_for('match'))


def randomize_list(input_list):
    # Create a copy of the original list
    randomized_list = input_list.copy()

    # Initialize a loop from the last element to the first
    for i in range(len(randomized_list) - 1, 0, -1):
        # Generate a random index within the range [0, i]
        j = random.randint(0, i)

        # Swap the elements at indices i and j
        randomized_list[i], randomized_list[j] = randomized_list[j], randomized_list[i]

    return randomized_list


def convert_to_rankings(image_list):
    rankings = []
    for item in image_list:
        # Find if the rank already exists in the rankings list
        existing_rank = next((rank for rank in rankings if rank['rank'] == item['rank']), None)

        if existing_rank is None:
            # If the rank doesn't exist, add a new entry
            rankings.append({'rank': item['rank'], 'images': [item['file']]})
        else:
            # If the rank exists, append the file to the images list
            existing_rank['images'].append(item['file'])

    # Sorting the list based on rank
    rankings.sort(key=lambda x: x['rank'])
    return rankings


class RegistrationForm(FlaskForm):
    name = StringField('Prénom', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField("S'inscrire")


class UpdateProfileForm(FlaskForm):
    name = StringField('Prénom', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Entrer le mot de passe actuel pour confirmer les changements.',
                             validators=[DataRequired()])
    new_password = PasswordField('Nouveau mot de passe (optionnel)', validators=[Optional(), EqualTo('confirm',
                                                                                                     message='Les mots de passe doivent correspondre.')])
    confirm = PasswordField('Confirmer le nouveau mot de passe', validators=[Optional()])
    submit = SubmitField('Sauvegarder les changements.')


# noinspection PyArgumentList
@app.route('/register', methods=['GET', 'POST'])
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
            return redirect(url_for('register'))
        db.session.add(user)
        db.session.commit()
        session.pop('_flashes', None)
        flash('Vous avez bien été enregistré!')
        user = User.query.filter_by(email=str(form.email.data).lower()).first()
        if user is None or not user.check_password(form.password.data):
            session.pop('_flashes', None)
            flash("Erreur, tu n'existe pas dans la base de donnée, comment c'est possible ?")
            return redirect(url_for('register'))
        login_user(user)
        return redirect(url_for('profile'))
    return render_template('register.html', form=form)


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField('Se connecter')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=str(form.email.data).lower()).first()
        if user is None or not user.check_password(form.password.data):
            session.pop('_flashes', None)
            flash('Email ou mot de passe invalide.')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('profile'))
    return render_template('login.html', form=form)


@app.route('/profile', methods=['GET', 'POST'])
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
                db.session.commit()
                flash('Your profile was updated successfully.')
                return redirect(url_for('profile'))
        else:
            flash('Incorrect password.')
    return render_template('profile.html', form=form, current_user=current_user, user_packs=user_packs)

@app.route('/user/<int:user_id>')
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
        pack_folder_path = os.path.join(app.static_folder, f'packs/{pack.folder}')
        images_list = [image for image in os.listdir(pack_folder_path)] if os.path.exists(pack_folder_path) else []

        pack_dict = {
            "id": pack.id,
            "name": pack.name,
            "category": pack.categories,
            "folder": pack.folder,
            "preview": pack.preview,
            "images": images_list,
            "private": pack.private,
        }
        packs.append(pack_dict)
    return render_template('user.html', user=user, user_packs=packs)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('_flashes', None)
    flash('Vous avez été déconnecté.')
    return redirect(url_for('login'))


@app.route('/match', methods=['GET', 'POST'])
def match():
    global ROUND, WINNERS, TOTAL_IMAGES, round_number, match_number
    tournament_file = session.get('tournament_file')

    if tournament_file:
        with open(os.path.join(tournaments_dir, tournament_file), 'r') as file:
            tournament_data = json.load(file)

    if request.method == 'POST':
        winner = request.form['winner']
        non_winner = request.form['non_winner']
        WINNERS.append(winner)

        tournament_data['matches'].append({
            'round': round_number,
            'participants': [winner, non_winner],  # Update with actual participants
            'winner': winner,
            'status': 'completed'
        })

        with open(os.path.join(tournaments_dir, tournament_file), 'w') as file:
            json.dump(tournament_data, file, indent=4)

        if not ROUND:
            match_number = 0
            if len(WINNERS) == 1:
                # Update the status to 'completed' in the JSON file
                tournament_data['status'] = 'completed'

                # Initialize rankings dictionary
                rankings = {winner: 1 for winner in WINNERS}

                # Iterate over participants to determine their ranks
                for participant in tournament_data['participants']:
                    if participant not in rankings:
                        # Find the highest round this participant reached
                        max_round = max(
                            (m['round'] for m in tournament_data['matches'] if
                             participant in m['participants'] and m['winner'] != participant),
                            default=0
                        )
                        rankings[participant] = max_round

                # Sort rankings by rank and update JSON file
                sorted_rankings = sorted(rankings.items(), key=lambda x: x[1])
                tournament_data['rankings'] = [{"file": file, "rank": rank} for file, rank in sorted_rankings]

                with open(os.path.join(tournaments_dir, tournament_file), 'w') as file:
                    json.dump(tournament_data, file, indent=4)

                return render_template('winner.html', winner_image=WINNERS[0],
                                       rankings=convert_to_rankings(tournament_data['rankings']))
            WINNERS = randomize_list(WINNERS)
            ROUND, WINNERS = WINNERS, []
            ROUND = randomize_list(ROUND)
            random.shuffle(ROUND)
            if len(ROUND) % 2 == 1:
                round_number = len(ROUND) + 1
            else:
                round_number = len(ROUND)

        return redirect(url_for('match'))

    match_number += 1
    pair = []
    if len(ROUND) > 1:
        pair = [ROUND.pop(), ROUND.pop()]
    elif ROUND:
        pair = [ROUND.pop()]
    print(pair
          )
    return render_template('match.html', pair=pair, round_name="Round of " + str(round_number),
                           round_progress=str(match_number) + "/" + str(int(round_number / 2)))


def calc_round(round_images, total_images):
    round_name = total_images
    if round_images < total_images:
        round_name = round_images * 2
    round_num = round_images // 2
    total_rounds = total_images // 2
    return round_name, round_num, total_rounds


@app.route('/download_rank/<int:rank>')
def download_rank(rank):
    tournament_file = session.get('tournament_file')

    if tournament_file:
        with open(os.path.join(tournaments_dir, tournament_file), 'r') as file:
            tournament_data = json.load(file)

        # Filter images by the specified rank
        images_to_download = [entry['file'] for entry in tournament_data['rankings'] if entry['rank'] == rank]

        # Create a ZIP file
        zip_filename = f'rank_{rank}_images.zip'
        zip_filepath = os.path.join(tournaments_dir, zip_filename)
        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            for img in images_to_download:
                img_path = os.path.join(images_dir, img)
                if os.path.exists(img_path):
                    zipf.write(img_path, img)

        return send_file(zip_filepath, as_attachment=True)

    return 'Tournament file not found', 404


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/manage')
def manage():
    images = os.listdir(os.path.join(app.static_folder, 'images'))
    images = [img for img in images]
    return render_template('manage.html', images=images)


@app.route('/delete-image', methods=['POST'])
def delete_image():
    image_name = request.form['image']
    image_path = os.path.join(app.static_folder, 'images', image_name)
    os.remove(image_path)

    return jsonify({'status': 'moved'})


@app.route('/upload-images', methods=['POST'])
def upload_images():
    uploaded_files = request.files.getlist("images[]")
    for file in uploaded_files:
        file.save(os.path.join(app.static_folder, 'images', file.filename))
    return jsonify({'status': 'uploaded'})


def file_content_hash(file_path):
    """Generate a hash of the file content."""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()


def rename_file(directory, file_name):
    """Rename a file to avoid name conflicts."""
    base, ext = os.path.splitext(file_name)
    counter = 1
    new_name = f"{base}_{counter}{ext}"
    while os.path.exists(os.path.join(directory, new_name)):
        counter += 1
        new_name = f"{base}_{counter}{ext}"
    return new_name


count_by_images = False


def download_insta_images(username, max_images=None):
    loader = instaloader.Instaloader(download_comments=False,
                                     download_videos=False,
                                     download_video_thumbnails=False,
                                     download_geotags=False,
                                     save_metadata=False,
                                     post_metadata_txt_pattern='',
                                     filename_pattern='{date_utc}_UTC')
    p = instaloader.Profile.from_username(loader.context, username)

    image_count = 0

    for post in profile.get_posts():
        if not post.is_video:
            # If the post is an image
            if max_images is None or image_count < max_images:
                # Download the image
                loader.download_post(post, target=p.username)
                image_count += 1
                if max_images is not None and image_count >= max_images:
                    break
    if count_by_images:
        # Clean-up: Remove images that don't end with UTC or UTC_1
        for image_file in os.listdir(username):
            if not re.search(r'UTC(_1)?\.(jpg|jpeg|png)$', image_file):
                os.remove(os.path.join(username, image_file))


def download_bing_images(search_term, number_of_images, download_path=''):
    """
    Downloads a specified number of images using Bing Image Downloader.

    :param search_term: The search term for the images you want to download.
    :param number_of_images: The number of images to download.
    :param download_path: The directory path where the images will be saved. Defaults to 'downloaded_images'.
    """
    print(download_path, number_of_images, search_term)
    downloader.download(search_term, limit=number_of_images, output_dir=download_path)


@app.route('/delete-all-images', methods=['POST'])
def delete_all_images():
    image_dir = os.path.join(app.static_folder, 'images')
    for image in os.listdir(image_dir):
        os.remove(os.path.join(app.static_folder, 'images', image))
    return jsonify({'status': 'all_deleted'})


@app.route('/download-instagram', methods=['POST'])
def download_instagram_images():
    username = request.form['username']
    max_images = int(request.form['count'])
    if max_images == 69:
        print("downloading every image")
        print("downloading every image")
        max_images = None
    # Use the download_images function to download images
    download_insta_images(username, max_images)

    # The path where downloaded images are stored
    instagram_folder_path = os.path.join(os.getcwd(), username)

    # Target path to move images to
    target_folder_path = os.path.join(app.static_folder, 'images')

    # Moving the images to the 'images' folder
    for image_file in os.listdir(instagram_folder_path):
        source_path = os.path.join(instagram_folder_path, image_file)
        target_path = os.path.join(target_folder_path, image_file)
        shutil.move(source_path, target_path)

    # Remove the now-empty Instagram folder
    shutil.rmtree(instagram_folder_path)

    return jsonify({'status': 'downloaded'})


@app.route('/download-bing', methods=['POST'])
def download_bing():
    keywords = request.form['keywords']
    max_images = int(request.form['count'])

    # Target path to move images to
    target_folder_path = os.path.join(app.static_folder, 'images')

    # Use the download_images function to download images
    download_bing_images(keywords, max_images, target_folder_path)
    instagram_folder_path = os.path.join(target_folder_path, keywords)
    for image_file in os.listdir(instagram_folder_path):
        source_path = os.path.join(instagram_folder_path, image_file)
        target_path = os.path.join(target_folder_path, image_file)
        shutil.move(source_path, target_path)

    # Remove the now-empty Instagram folder
    shutil.rmtree(instagram_folder_path)
    return jsonify({'status': 'downloaded'})


def get_all_packs():
    packs_query = Pack.query.all()  # Retrieve all pack entries from the database
    image_packs = []
    for pack in packs_query:
        # For each pack, construct a dictionary with the required structure
        pack_dict = {
            "id": pack.id,
            "name": pack.name,
            "category": pack.categories,  # Assuming the field is named 'categories' in your model
            "preview": pack.preview,
            "folder": pack.folder
        }
        image_packs.append(pack_dict)

    return image_packs


def get_user_packs(user_id):
    packs_query = Pack.query.filter_by(user_id=user_id).all()  # Filter packs by user ID
    packs = []
    for pack in packs_query:
        pack_folder_path = os.path.join(app.static_folder, f'packs/{pack.folder}')
        images_list = [image for image in os.listdir(pack_folder_path)] if os.path.exists(pack_folder_path) else []

        pack_dict = {
            "id": pack.id,
            "name": pack.name,
            "category": pack.categories,
            "folder": pack.folder,
            "preview": pack.preview,
            "images": images_list,
            "private": pack.private,
            # Include additional attributes as needed
        }
        packs.append(pack_dict)
    return packs



@app.route('/store')
def store():
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
        pack_folder_path = os.path.join(app.static_folder, f'packs/{pack.folder}')
        images_list = [image for image in os.listdir(pack_folder_path)] if os.path.exists(pack_folder_path) else []

        pack_dict = {
            "id": pack.id,
            "name": pack.name,
            "category": pack.categories,
            "folder": pack.folder,
            "preview": pack.preview,
            "images": images_list,
            "private": pack.private,
        }
        packs.append(pack_dict)

    return render_template('store.html', packs=packs)


@app.route('/add-pack', methods=['POST'])
def add_pack():
    pack_id = request.form.get('packId')
    pack = next((pack for pack in get_all_packs() if pack['id'] == int(pack_id)), None)

    if pack:
        for image in os.listdir(os.path.join(app.static_folder, f'packs/{pack["folder"]}')):
            image_path = os.path.join(app.static_folder, f'packs/{pack["folder"]}', image)
            if not os.path.exists(image_path):
                print(f"Image '{image}' does not exist in the 'images' folder.")
            else:
                shutil.copy(image_path, os.path.join(images_dir, image))

        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid pack ID'}), 400


@app.route('/delete-pack', methods=['POST'])
@login_required
def delete_pack():
    pack_id = request.form.get('packId')
    try:
        pack_id = int(pack_id)
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid pack ID'}), 400

    pack = Pack.query.get(pack_id)
    if not pack or pack.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Pack not found or unauthorized'}), 403

    pack_folder = os.path.join(app.static_folder, 'packs', pack.folder)
    if os.path.exists(pack_folder):
        shutil.rmtree(pack_folder)

    db.session.delete(pack)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Pack deleted successfully'})


class CreatePackForm(FlaskForm):
    pack_name = StringField('Nom du Pack', validators=[DataRequired()])
    pack_category = StringField('Catégories', validators=[DataRequired()])
    pack_preview = FileField('Icone', validators=[FileRequired(), FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    pack_images = FileField('Images', validators=[FileRequired(), FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')],
                            render_kw={"multiple": True})
    private = BooleanField('Privé')
    authorized_users = TextAreaField('Utilisateurs Autorisés (IDs séparés par une virgule)')
    submit = SubmitField('Créer Pack')


@app.route('/create-pack', methods=['GET', 'POST'])
@login_required
def create_pack():
    form = CreatePackForm()
    if form.validate_on_submit():
        pack_name = form.pack_name.data
        pack_category = form.pack_category.data
        pack_preview = form.pack_preview.data
        pack_images = request.files.getlist('pack_images')  # Ensure the field name matches your HTML form
        authorized_users = form.authorized_users.data

        # Processing for privacy and authorized_users
        is_private = form.private.data
        authorized_users_ids = [int(user_id.strip()) for user_id in authorized_users.split(',') if
                                user_id.strip().isdigit()]

        # Create a new folder for the pack
        pack_folder = os.path.join(app.static_folder, 'packs', secure_filename(pack_name.lower().replace(' ', '_')))
        os.makedirs(pack_folder, exist_ok=True)
        if is_private == 0:
            is_private = False
        else:
            is_private = True
        # Save the preview image
        if pack_preview:
            preview_filename = secure_filename(pack_preview.filename)
            pack_preview.save(os.path.join(pack_folder, preview_filename))
        else:
            flash('No preview image provided', 'error')
            return render_template('create_pack.html', form=form)

        # Save the pack images
        image_filenames = []
        if pack_images:
            for image in pack_images:
                image_filename = secure_filename(image.filename)
                image.save(os.path.join(pack_folder, image_filename))
                image_filenames.append(image_filename)
        else:
            flash('No images provided for the pack', 'error')
            return render_template('create_pack.html', form=form)

        new_pack = Pack(
            name=pack_name,
            categories=pack_category,
            folder=pack_name.lower(),
            preview=preview_filename,
            images=str(image_filenames),  # Assuming your Pack model can handle the list of filenames
            user_id=current_user.id,  # Ensure you have access to current_user
            private=bool(is_private),
            authorized_users=str(authorized_users_ids)
        )
        db.session.add(new_pack)
        db.session.commit()

        flash('Pack created successfully!', 'success')
        return redirect(url_for('store'))
    print("didn't validate")
    return render_template('create_pack.html', form=form)


if __name__ == "__main__":
    app.run(debug=True)
