import os

from flask import Blueprint, render_template, request, jsonify

managing = Blueprint("managing", __name__, static_folder="static", template_folder="templates")

@managing.route('/manage')
def manage():
    images = os.listdir(os.path.join(managing.static_folder, 'images'))
    images = [img for img in images]
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
    image_dir = os.path.join(managing.static_folder, 'images')
    for image in os.listdir(image_dir):
        os.remove(os.path.join(managing.static_folder, 'images', image))
    return jsonify({'status': 'all_deleted'})