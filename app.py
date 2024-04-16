import json
import os
import random
import zipfile
from datetime import datetime

from flask import Flask, session
from flask import request, redirect, url_for, render_template
from flask import send_file
from flask_migrate import Migrate
from flask import session
import shared
from managing import managing
from packs_management import packs_management
from user_management import user_management
from tournament_management import tournament_management
from custom_image_recuperation import custom_image_recuperation


def create_app():
    shared.app = Flask(__name__)  # Initialize the Flask app
    shared.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tournamentsite.db'
    shared.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    from werkzeug.middleware.proxy_fix import ProxyFix
    shared.app.wsgi_app = ProxyFix(shared.app.wsgi_app)

    shared.db.init_app(shared.app)  # Bind the database instance to the Flask app
    migrate = Migrate(shared.app, shared.db)
    shared.login.init_app(shared.app)
    shared.login.login_view = "user_management.login"  #
    with shared.app.app_context():
        shared.db.create_all()  # Create database tables if they don't exist
        # register_routes()  # Register routes from other modules

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



if __name__ == "__main__":

    app.run(debug=True)
