import json
import os
import random
import zipfile
from datetime import datetime

from flask import Blueprint, request, send_file
from flask import redirect, url_for, flash, render_template
from flask import session, abort
import shared

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
if not os.path.exists(os.path.join(tournament_management.static_folder, 'images')):
    os.makedirs(os.path.join(tournament_management.static_folder, 'images'))
if not os.path.exists(os.path.join(tournament_management.static_folder, 'tournaments')):
    os.makedirs(os.path.join(tournament_management.static_folder, 'tournaments'))

images_dir = os.path.join(tournament_management.static_folder, 'images')
tournaments_dir = os.path.join(tournament_management.static_folder, 'tournaments')

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

@tournament_management.route('/start_quick_tournament', methods=['GET'])
def start_quick_tournament():
    global ROUND, WINNERS, TOTAL_IMAGES, round_number, match_number
    ROUND = []
    WINNERS = []
    TOTAL_IMAGES = None
    round_number = None
    match_number = 0
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

    return redirect(url_for('tournament_management.match'))

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


@tournament_management.route('/match', methods=['GET', 'POST'])
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

                return render_template('tournament_management/winner.html', winner_image=WINNERS[0],
                                       rankings=convert_to_rankings(tournament_data['rankings']))
            WINNERS = randomize_list(WINNERS)
            ROUND, WINNERS = WINNERS, []
            ROUND = randomize_list(ROUND)
            random.shuffle(ROUND)
            if len(ROUND) % 2 == 1:
                round_number = len(ROUND) + 1
            else:
                round_number = len(ROUND)

        return redirect(url_for('tournament_management.match'))

    match_number += 1
    pair = []
    if len(ROUND) > 1:
        pair = [ROUND.pop(), ROUND.pop()]
    elif ROUND:
        pair = [ROUND.pop()]
    print(pair)
    return render_template('tournament_management/match.html', pair=pair, round_name="Round of " + str(round_number),
                           round_progress=str(match_number) + "/" + str(int(round_number / 2)))


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