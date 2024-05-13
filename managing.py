import ast
import os

from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user, login_user, logout_user, login_required

import shared
from class_utils import User
from tournament_management import user_images_to_list

managing = Blueprint("managing", __name__, static_folder="static", template_folder="templates")

@managing.route('/manage')
@login_required
def manage():
    user = User.query.get(current_user.id)
    if user.current_images:
        images = user_images_to_list(user.current_images)
    else:
        images = []
    return render_template('tournament_management/manage.html', images=images)


@managing.route('/delete-image', methods=['POST'])
def delete_image():
    image_name = request.form['image']
    image_path = os.path.join(managing.static_folder, 'images', image_name)
    os.remove(image_path)
    user = User.query.get(current_user.id)
    print(user.current_images)
    user.current_images = user.current_images.replace(image_name + ',', '')

    print()
    print(user.current_images)
    shared.db.session.commit()
    return jsonify({'status': 'deleted'})
from custom_image_recuperation import safe_name
@managing.route('/upload-images', methods=['POST'])
def upload_images():
    user = User.query.get(current_user.id)
    uploaded_files = request.files.getlist("images[]")
    for file in uploaded_files:
        safe_image_name = safe_name("upload_"+file.filename, user.id)
        file.save(os.path.join(managing.static_folder, 'images', safe_image_name))
        print(file.filename)
        if  user.current_images == "":
            user.current_images = safe_image_name
        else:
            user.current_images += ','+safe_image_name
    print(user.current_images)
    return jsonify({'status': 'uploaded'})


@managing.route('/delete-all-images', methods=['POST'])
def delete_all_images():
    user = User.query.get(current_user.id)
    user.current_images = ""
    shared.db.session.commit()
    return jsonify({'status': 'all_deleted'})

