import os
import shutil

from flask import Blueprint
from flask import jsonify
from flask import request, redirect, url_for, flash, render_template
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import BooleanField, TextAreaField
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import shared
import ast

from class_utils import Pack
from class_utils import User

packs_management = Blueprint("packs_management", __name__, static_folder="static", template_folder="templates")
images_dir = os.path.join(packs_management.static_folder, 'all_images')


def get_user_packs(user_id):
    packs_query = Pack.query.filter_by(user_id=user_id).all()
    packs = []
    for pack in packs_query:
        pack_dict = {
            "id": str(pack.id),
            "name": pack.name,
            "category": pack.categories,
            "preview": pack.preview,
            "all_images": ast.literal_eval(pack.images),
            "private": pack.private,
        }
        packs.append(pack_dict)
    return packs


def get_all_packs():
    packs_query = Pack.query.all()  # Retrieve all pack entries from the database
    image_packs = []
    for pack in packs_query:
        # For each pack, construct a dictionary with the required structure
        pack_dict = {
            "id": str(pack.id),
            "name": pack.name,
            "category": pack.categories,
            "preview": pack.preview,
            "all_images": ast.literal_eval(pack.images),
            "private": pack.private,
        }
        image_packs.append(pack_dict)

    return image_packs


@packs_management.route('/store')
@login_required
def store():
    if current_user.is_authenticated:
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
        # get user that owns pack
        user = User.query.get(pack.user_id)
        pack_dict = {
            "id": str(pack.id),
            "name": pack.name,
            "category": pack.categories,
            "preview": pack.preview,
            "all_images": ast.literal_eval(pack.images),
            "private": pack.private,
            "user_id": str(user.id),
            "username": user.username,
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
@login_required
def add_pack():
    pack_id = request.form.get('packId')
    try:
        pack_id = int(pack_id)  # Ensures that pack_id is an integer
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid pack ID'}), 400

    pack = convert_pack_to_dict(Pack.query.get(pack_id))
    if pack:
        user = User.query.get(current_user.id)
        image_paths = ','.join([image for image in pack["all_images"]])
        if user.current_images:
            user.current_images += ',' + image_paths
        else:
            user.current_images = image_paths
        print("added pack")
        shared.db.session.commit()
        return jsonify({'status': 'success'})
    else:
        print("invalid pack")
        return jsonify({'status': 'error', 'message': 'Invalid pack ID'}), 400


def convert_pack_to_dict(pack: Pack):
    pack_dict = {
        "id": str(pack.id),
        "name": pack.name,
        "category": pack.categories,
        "preview": pack.preview,
        "all_images": ast.literal_eval(pack.images),
        "private": pack.private,
    }
    return pack_dict


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
        print(pack_name)
        pack_category = form.pack_category.data
        pack_preview = form.pack_preview.data
        print(pack_preview)
        pack_images = request.files.getlist('pack_images')  # Ensure the field name matches your HTML form
        authorized_users = form.authorized_users.data

        # Processing for privacy and authorized_users
        is_private = form.private.data
        authorized_users_ids = [int(user_id.strip()) for user_id in authorized_users.split(',') if
                                user_id.strip().isdigit()]

        is_private = bool(is_private)

        # Create the Pack object without the all_images first
        new_pack = Pack(
            name=pack_name,
            categories=pack_category,
            preview='',  # Temporarily empty
            images='',  # Temporarily empty
            user_id=current_user.id,
            private=is_private,
            authorized_users=str(authorized_users_ids)
        )
        if not pack_preview:
            flash('No preview image provided', 'error')
            return render_template('packs_management/create_pack.html', form=form)
        shared.db.session.add(new_pack)
        shared.db.session.commit()

        # After committing, new_pack.id is available
        pack_id = new_pack.id

        # Function to save an image and return its filename
        def save_image(image_file):
            filename = f"{pack_id}_{pack_name}_{image_file.filename}"
            image_file.save(os.path.join(images_dir, filename))
            return filename

        # Save the preview image and update the Pack object
        preview_filename = save_image(pack_preview)
        new_pack.preview = preview_filename

        # Save the pack all_images
        image_filenames = []
        if pack_images:
            for image in pack_images:
                image_filename = save_image(image)
                image_filenames.append(image_filename)
            new_pack.images = str(image_filenames)
        else:
            flash('No all_images provided for the pack', 'error')
            return render_template('packs_management/create_pack.html', form=form)
        shared.db.session.add(new_pack)
        # Commit the updates to the Pack object
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

    for image in os.listdir(images_dir):
        if image.startswith(f"{pack_id}_"):
            os.remove(os.path.join(images_dir, image))
    shared.db.session.delete(pack)
    shared.db.session.commit()

    return jsonify({'status': 'success', 'message': 'Pack deleted successfully'})


# command to delete pack of specific id
@packs_management.cli.command("delete_pack")
def delete_pack_command():
    """CLI command to delete a pack."""
    pack_id = input("Enter the ID of the pack to delete: ")
    try:
        pack_id = int(pack_id)
    except ValueError:
        print("Invalid pack ID. Please enter a valid integer.")
        return

    pack = Pack.query.get(pack_id)
    if not pack:
        print("Pack not found.")
        return

    shared.db.session.delete(pack)
    # find if a user owns this pack and emove it from his list
    users = User.query.all()
    for user in users:
        if pack_id in ast.literal_eval(user.current_images):
            user.current_images = ast.literal_eval(user.current_images).remove(pack_id)

    shared.db.session.commit()
