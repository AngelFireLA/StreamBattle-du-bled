import ast
import os

from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user, login_user, logout_user, login_required

import shared
from class_utils import User

managing = Blueprint("managing", __name__, static_folder="static", template_folder="templates")

@managing.route('/manage')
@login_required
def manage():
    user = User.query.get(current_user.id)
    if user.current_images:
        formatted_string = '["' + '","'.join(user.current_images.split(',')) + '"]'
        if not formatted_string == '[""]':
            images = ast.literal_eval(formatted_string)
        else:
            images = []
    else:
        images = []
    return render_template('tournament_management/manage.html', images=images)


@managing.route('/delete-image', methods=['POST'])
def delete_image():
    image_name = request.form['image']
    image_path = os.path.join(managing.static_folder, 'images', image_name)
    os.remove(image_path)

    return jsonify({'status': 'moved'})


@managing.route('/upload-images', methods=['POST'])
def upload_images():
    uploaded_files = request.files.getlist("images[]")
    for file in uploaded_files:
        file.save(os.path.join(managing.static_folder, 'images', file.filename))
    return jsonify({'status': 'uploaded'})


@managing.route('/delete-all-images', methods=['POST'])
def delete_all_images():
    user = User.query.get(current_user.id)
    user.current_images = ""
    shared.db.session.commit()
    return jsonify({'status': 'all_deleted'})