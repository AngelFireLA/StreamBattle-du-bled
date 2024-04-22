import ast
import json
import os
import random
import zipfile
from datetime import datetime
from io import BytesIO

from flask import Blueprint, request, send_file, jsonify
from flask import redirect, url_for, flash, render_template
from flask import session
from flask_login import current_user, login_required

import shared
from class_utils import User

tournament_management = Blueprint("tournament_management", __name__, static_folder="static", template_folder="templates")

class Tournament(shared.db.Model):
    id = shared.db.Column(shared.db.Integer, primary_key=True, autoincrement=True)
    name = shared.db.Column(shared.db.Text, nullable=False)
    categories = shared.db.Column(shared.db.Text, nullable=False)
    preview = shared.db.Column(shared.db.Text, nullable=False)
    images = shared.db.Column(shared.db.Text, nullable=False)
    user_id = shared.db.Column(shared.db.Integer, nullable=False)
    private = shared.db.Column(shared.db.Boolean, nullable=False)
    authorized_users = shared.db.Column(shared.db.String, nullable=False)

# create and load folders

if not os.path.exists(os.path.join(tournament_management.static_folder, 'tournaments')):
    os.makedirs(os.path.join(tournament_management.static_folder, 'tournaments'))

images_dir = os.path.join(tournament_management.static_folder, 'images')
tournament_dir = os.path.join(tournament_management.static_folder, 'tournaments')


def create_tournament(tournament_id, participants):
    date_prefix = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    file_name = f"{tournament_id}.json"
    tournament_data = {
        "tournament_id": tournament_id,
        "date_created": date_prefix,
        "status": "on-going",
        "type": "single-knockout",
        "participants": participants,
        "matches": [],
        "rankings": []
    }
    with open(os.path.join(tournament_dir, file_name), 'w') as file:
        json.dump(tournament_data, file)
    return file_name

@tournament_management.route('/start_quick_tournament', methods=['GET'])
@login_required
def start_quick_tournament():
    user = User.query.get(current_user.id)
    if user.current_images:
        images = user_images_to_list(user.current_images)
        if not images:
            flash("Pas d'images pour l'utilisateur.")
            return redirect(url_for('index'))
    else:
        flash("Pas d'images pour l'utilisateur.")
        return redirect(url_for('index'))

    session.pop('tournament_id', None)
    session.pop('current_round_images', None)
    session.pop('current_round_number', None)
    session.pop('current_winners', None)
    session.pop('current_match_number', None)
    images = [f for f in images if os.path.isfile(os.path.join(images_dir, f))]
    random.shuffle(images)
    tournament_id = random.randint(999, 9999999)
    tournament_file = create_tournament(tournament_id, images)
    session['tournament_id'] = str(tournament_id)
    session['current_round_images'] = images
    session['current_round_number'] = len(images) + 1 if len(images) % 2 == 1 else len(images)
    session['current_winners'] = []
    session['current_match_number'] = 0
    session.modified = True

    return redirect(url_for('tournament_management.match'))

@tournament_management.route('/match', methods=['GET', 'POST'])
@login_required
def match():
    tournament_id = session.get('tournament_id')
    if tournament_id:
        with open(os.path.join(tournament_dir, tournament_id+".json"), 'r') as file:
            tournament_data = json.load(file)

    if request.method == 'POST':
        winner = request.form['winner']
        non_winner = request.form['non_winner']
        session['current_winners'].append(winner)

        tournament_data['matches'].append({
            'round': session['current_round_number'],
            'participants': [winner, non_winner],  # Update with actual participants
            'winner': winner,
            'status': 'completed'
        })

        with open(os.path.join(tournament_dir, tournament_id+".json"), 'w') as file:
            json.dump(tournament_data, file, indent=4)

        if not session['current_round_images']:
            session['current_match_number'] = 0
            if len(session['current_winners']) == 1:
                # Update the status to 'completed' in the JSON file
                tournament_data['status'] = 'completed'

                # Initialize rankings dictionary
                rankings = {winner: 1 for winner in session['current_winners']}

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

                with open(os.path.join(tournament_dir, tournament_id+".json"), 'w') as file:
                    json.dump(tournament_data, file, indent=4)
                session.modified = True
                return render_template('tournament_management/winner.html', winner_image=session['current_winners'][0],
                                       rankings=convert_to_rankings(tournament_data['rankings']))
            session['current_winners'] = randomize_list(session['current_winners'])
            session['current_round_images'], session['current_winners'] = session['current_winners'], []
            session['current_round_images'] = randomize_list(session['current_round_images'])
            random.shuffle(session['current_round_images'])
            if len(session['current_round_images']) % 2 == 1:
                session['current_round_number'] = len(session['current_round_images']) + 1
            else:
                session['current_round_number'] = len(session['current_round_images'])
        session.modified = True
        return redirect(url_for('tournament_management.match'))

    session['current_match_number'] += 1
    pair = []
    if len(session['current_round_images']) > 1:
        pair = [session['current_round_images'].pop(), session['current_round_images'].pop()]
    elif session['current_round_images']:
        pair = [session['current_round_images'].pop()]
    session.modified = True
    return render_template('tournament_management/match.html', pair=pair, round_name="Round of " + str(session['current_round_number']),
                           round_progress=str(session['current_match_number']) + "/" + str(int(session['current_round_number'] / 2)))

from tierlist import create_tier_list, convert_rankings, load_images


@tournament_management.route('/get_tierlist', methods=['GET'])
def get_tierlist():
    tournament_id = session.get('tournament_id')
    if tournament_id:
        with open(os.path.join(tournament_dir, tournament_id+".json"), 'r') as file:
            tournament_data = json.load(file)
    else:
        return jsonify({'error': 'Tournament not found'})

    rankings = {}

    for participant in tournament_data['participants']:
        max_round = max(
            (m['round'] for m in tournament_data['matches'] if
             participant in m['participants'] and m['winner'] != participant),
            default=0
        )
        rankings[participant] = max_round
    sorted_rankings = sorted(rankings.items(), key=lambda x: x[1])
    tournament_data['rankings'] = [{"file": file, "rank": rank} for file, rank in sorted_rankings]
    tiers = convert_to_rankings(tournament_data['rankings'])
    tier_images = load_images(convert_rankings(tiers))
    tier_list_img = create_tier_list(tier_images)

    # Save the image to a BytesIO object
    img_io = BytesIO()
    tier_list_img.save(img_io, 'PNG')
    img_io.seek(0)  # Go to the beginning of the BytesIO stream

    # Send the BytesIO stream as a file
    return send_file(img_io, mimetype='image/png', as_attachment=True, download_name='tierlist.png')

def user_images_to_list(user_current_images):
    formatted_string = '["' + '","'.join(user_current_images.split(',')) + '"]'
    if not formatted_string == '[""]':
        return ast.literal_eval(formatted_string)
    else:
        return []
def randomize_list(input_list):
    randomized_list = input_list.copy()
    for i in range(len(randomized_list) - 1, 0, -1):
        j = random.randint(0, i)
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





def calc_round(round_images, total_images):
    round_name = total_images
    if round_images < total_images:
        round_name = round_images * 2
    round_num = round_images // 2
    total_rounds = total_images // 2
    return round_name, round_num, total_rounds


@tournament_management.route('/download_rank/<int:rank>')
def download_rank(rank):
    tournament_file = session.get('tournament_file')

    if tournament_file:
        with open(os.path.join(tournament_dir, tournament_file), 'r') as file:
            tournament_data = json.load(file)

        # Filter images by the specified rank
        images_to_download = [entry['file'] for entry in tournament_data['rankings'] if entry['rank'] == rank]

        # Create a ZIP file
        zip_filename = f'rank_{rank}_images.zip'
        zip_filepath = os.path.join(tournament_dir, zip_filename)
        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            for img in images_to_download:
                img_path = os.path.join(images_dir, img)
                if os.path.exists(img_path):
                    zipf.write(img_path, img)

        return send_file(zip_filepath, as_attachment=True)

    return 'Tournament file not found', 404