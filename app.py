import ast
import os
from flask import Flask
from flask import render_template
from flask_migrate import Migrate
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy

import shared
from managing import managing
from packs_management import packs_management
from user_management import user_management
from tournament_management import tournament_management
from custom_image_recuperation import custom_image_recuperation
from class_utils import Pack, User

def create_app():
    shared.app = Flask(__name__)  # Initialize the Flask app
    shared.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tournamentsite.db'
    shared.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    shared.app.config['SESSION_TYPE'] = 'sqlalchemy'
    shared.app.config['SESSION_PERMANENT'] = True  # Sessions are permanent by default, modify as needed
    shared.app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 4  # Customize session lifetime as needed, here set to 7 days
    shared.app.config['SESSION_COOKIE_SECURE'] = True  # if you are using HTTPS
    shared.app.config['SESSION_COOKIE_HTTPONLY'] = True
    shared.app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Can be 'Strict' or 'Lax'

    shared.db.init_app(shared.app)  # Bind the database instance to the Flask app
    migrate = Migrate(shared.app, shared.db)
    shared.login.init_app(shared.app)
    shared.login.login_view = "user_management.login"  #
    with shared.app.app_context():
        shared.db.create_all()  # Create database tables if they don't exist
    shared.app.config['SESSION_SQLALCHEMY'] = shared.db  # Use the same SQLAlchemy instance
    Session(shared.app)


    return shared.app


app = create_app()
app.secret_key = "srguzGW2kTdjhqpsUKnG5DyJvvCUk5b9"
app.register_blueprint(user_management, url_prefix="")
app.register_blueprint(packs_management, url_prefix="")
app.register_blueprint(managing, url_prefix="")
app.register_blueprint(tournament_management, url_prefix="")
app.register_blueprint(custom_image_recuperation, url_prefix="")


with app.app_context():
    shared.db.create_all()

if not os.path.exists(os.path.join(tournament_management.static_folder, 'images')):
    os.makedirs(os.path.join(tournament_management.static_folder, 'images'))


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

import os
import json
from tournament_management import user_images_to_list
def cleanup_unused_images():
    referenced_images = set()

    # Collect all images referenced in the Pack.images
    packs = Pack.query.all()
    for pack in packs:
        if pack.images:
            pack_images = ast.literal_eval(pack.images)
            referenced_images.update(pack_images)

    # Collect all images referenced in User.current_images
    users = User.query.all()
    for user in users:
        if user.current_images:
            user_images = user_images_to_list(user.current_images)
            referenced_images.update(user_images)

    # Directory containing all images
    images_dir = os.path.join(app.static_folder, 'images')
    for filename in os.listdir(images_dir):
        file_path = os.path.join(images_dir, filename)
        if filename not in referenced_images:
            os.remove(file_path)  # Delete files not referenced
            print(f"Deleted unused image: {filename}")

# You might want to call this function from a route or a command
@app.cli.command("cleanup_images")
def cleanup_images_command():
    """CLI command to clean up unused images."""
    cleanup_unused_images()
    print("Cleanup complete.")


if __name__ == "__main__":
    app.run(debug=True)
