import os
import shutil

from flask import Blueprint
from flask import jsonify
from flask import request, redirect, url_for, flash, render_template
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from werkzeug.utils import secure_filename
from wtforms import BooleanField, TextAreaField
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

import shared


class Pack(shared.db.Model):
    id = shared.db.Column(shared.db.Integer, primary_key=True, autoincrement=True)
    name = shared.db.Column(shared.db.Text, nullable=False)
    folder = shared.db.Column(shared.db.Text, nullable=False)
    categories = shared.db.Column(shared.db.Text, nullable=False)
    preview = shared.db.Column(shared.db.Text, nullable=False)
    images = shared.db.Column(shared.db.Text, nullable=False)
    user_id = shared.db.Column(shared.db.Integer, nullable=False)
    private = shared.db.Column(shared.db.Boolean, nullable=False)
    authorized_users = shared.db.Column(shared.db.String, nullable=False)


packs_management = Blueprint("packs_management", __name__, static_folder="static", template_folder="templates")
images_dir = os.path.join(packs_management.static_folder, 'images')


def get_user_packs(user_id):
    packs_query = Pack.query.filter_by(user_id=user_id).all()  # Filter packs by user ID
    packs = []
    for pack in packs_query:
        pack_folder_path = os.path.join(packs_management.static_folder, f'packs/{pack.folder}')
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


@packs_management.route('/store')
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
        pack_folder_path = os.path.join(packs_management.static_folder, f'packs/{pack.folder}')
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

    return render_template('packs_management/store.html', packs=packs)


def rename_file(directory, file_name):
    """Rename a file to avoid name conflicts."""
    base, ext = os.path.splitext(file_name)
    counter = 1
    new_name = f"{base}_{counter}{ext}"
    while os.path.exists(os.path.join(directory, new_name)):
        counter += 1
        new_name = f"{base}_{counter}{ext}"
    return new_name


@packs_management.route('/add-pack', methods=['POST'])
def add_pack():
    pack_id = request.form.get('packId')
    pack = next((pack for pack in get_all_packs() if pack['id'] == int(pack_id)), None)

    if pack:
        for image in os.listdir(os.path.join(packs_management.static_folder, f'packs/{pack["folder"]}')):
            image_path = os.path.join(packs_management.static_folder, f'packs/{pack["folder"]}', image)
            if not os.path.exists(image_path):
                print(f"Image '{image}' does not exist in the 'images' folder.")
            else:
                shutil.copy(image_path, os.path.join(images_dir, image))

        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid pack ID'}), 400


class CreatePackForm(FlaskForm):
    pack_name = StringField('Nom du Pack', validators=[DataRequired()])
    pack_category = StringField('Catégories', validators=[DataRequired()])
    pack_preview = FileField('Icone', validators=[FileRequired(), FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    pack_images = FileField('Images', validators=[FileRequired(), FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')],
                            render_kw={"multiple": True})
    private = BooleanField('Privé')
    authorized_users = TextAreaField('Utilisateurs Autorisés (IDs séparés par une virgule)')
    submit = SubmitField('Créer Pack')


@packs_management.route('/create-pack', methods=['GET', 'POST'])
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
        pack_folder = os.path.join(packs_management.static_folder, 'packs',
                                   secure_filename(pack_name.lower().replace(' ', '_')))
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
            return render_template('packs_management/create_pack.html', form=form)

        # Save the pack images
        image_filenames = []
        if pack_images:
            for image in pack_images:
                image_filename = secure_filename(image.filename)
                image.save(os.path.join(pack_folder, image_filename))
                image_filenames.append(image_filename)
        else:
            flash('No images provided for the pack', 'error')
            return render_template('packs_management/create_pack.html', form=form)

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
        shared.db.session.add(new_pack)
        shared.db.session.commit()

        flash('Pack created successfully!', 'success')
        return redirect(url_for('packs_management.store'))
    print("didn't validate")
    return render_template('packs_management/create_pack.html', form=form)


@packs_management.route('/delete-pack', methods=['POST'])
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

    pack_folder = os.path.join(packs_management.static_folder, 'packs', pack.folder)
    if os.path.exists(pack_folder):
        shutil.rmtree(pack_folder)

    shared.db.session.delete(pack)
    shared.db.session.commit()

    return jsonify({'status': 'success', 'message': 'Pack deleted successfully'})
