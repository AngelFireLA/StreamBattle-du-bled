import ast
import json
import os
import random
import zipfile
from datetime import datetime
from io import BytesIO
from tierlist import create_tier_list, convert_rankings, load_images

from flask import Blueprint, request, send_file, jsonify
from flask import redirect, url_for, flash, render_template
from flask import session
from flask_login import current_user, login_required

import shared
from class_utils import User

tournament_management = Blueprint("tournament_management", __name__, static_folder="static",
                                  template_folder="templates")


class Tournament(shared.db.Model):
    id = shared.db.Column(shared.db.Integer, primary_key=True, autoincrement=True)
    name = shared.db.Column(shared.db.Text, nullable=False)
    categories = shared.db.Column(shared.db.Text, nullable=False)
    preview = shared.db.Column(shared.db.Text, nullable=False)
    images = shared.db.Column(shared.db.Text, nullable=False)
    user_id = shared.db.Column(shared.db.Integer, nullable=False)
    private = shared.db.Column(shared.db.Boolean, nullable=False)
    authorized_users = shared.db.Column(shared.db.String, nullable=False)
    type = shared.db.Column(shared.db.String(50), nullable=False, default='single-knockout')  # Add this field


class SwissRound(shared.db.Model):
    id = shared.db.Column(shared.db.Integer, primary_key=True)
    tournament_id = shared.db.Column(shared.db.Integer, shared.db.ForeignKey('tournament.id'), nullable=False)
    round_number = shared.db.Column(shared.db.Integer, nullable=False)
    matches = shared.db.relationship('SwissMatch', backref='round', lazy=True)


class SwissMatch(shared.db.Model):
    id = shared.db.Column(shared.db.Integer, primary_key=True)
    round_id = shared.db.Column(shared.db.Integer, shared.db.ForeignKey('swiss_round.id'), nullable=False)
    participant1 = shared.db.Column(shared.db.String(255), nullable=False)
    participant2 = shared.db.Column(shared.db.String(255), nullable=True)  # Nullable for bye rounds
    winner = shared.db.Column(shared.db.String(255), nullable=True)  # Null until match is played


class SwissStanding(shared.db.Model):
    id = shared.db.Column(shared.db.Integer, primary_key=True)
    tournament_id = shared.db.Column(shared.db.Integer, shared.db.ForeignKey('tournament.id'), nullable=False)
    participant = shared.db.Column(shared.db.String(255), nullable=False)
    wins = shared.db.Column(shared.db.Integer, default=0)
    losses = shared.db.Column(shared.db.Integer, default=0)
    ties = shared.db.Column(shared.db.Integer, default=0)  # If you want to include ties
    # Additional tie-breaker fields can be added here


# create and load folders

if not os.path.exists(os.path.join(tournament_management.static_folder, 'tournaments')):
    os.makedirs(os.path.join(tournament_management.static_folder, 'tournaments'))

images_dir = os.path.join(tournament_management.static_folder, 'all_images')
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
            flash("Pas d'all_images pour l'utilisateur.")
            return redirect(url_for('index'))
    else:
        flash("Pas d'all_images pour l'utilisateur.")
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
        with open(os.path.join(tournament_dir, tournament_id + ".json"), 'r') as file:
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

        with open(os.path.join(tournament_dir, tournament_id + ".json"), 'w') as file:
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

                with open(os.path.join(tournament_dir, tournament_id + ".json"), 'w') as file:
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
    return render_template('tournament_management/match.html', pair=pair,
                           round_name="Round of " + str(session['current_round_number']),
                           round_progress=str(session['current_match_number']) + "/" + str(
                               int(session['current_round_number'] / 2)))


@tournament_management.route('/get_tierlist', methods=['GET'])
def get_tierlist():
    tournament_id = session.get('tournament_id')
    if tournament_id:
        with open(os.path.join(tournament_dir, tournament_id + ".json"), 'r') as file:
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
            rankings.append({'rank': item['rank'], 'all_images': [item['file']]})
        else:
            # If the rank exists, append the file to the all_images list
            existing_rank['all_images'].append(item['file'])

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
@login_required
def download_rank(rank):
    tournament_id = session.get('tournament_id')
    standings = SwissStanding.query.filter_by(tournament_id=tournament_id).order_by(
        SwissStanding.wins.desc(),
        SwissStanding.losses.asc()
    ).all()
    rankings = organize_standings_into_ranks(standings)

    # Find the all_images corresponding to the requested rank
    for r in rankings:
        if r['rank'] == rank:
            images = r['all_images']
            break
    else:
        flash('Invalid rank.')
        return redirect(url_for('tournament_management.swiss_results'))

    # Create a zip file with the all_images
    zip_dir = os.path.join('static', 'zips')
    os.makedirs(zip_dir, exist_ok=True)
    zip_filename = f'top_{rank}_images.zip'
    zip_path = os.path.join(zip_dir, zip_filename)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for image_filename in images:
            image_path = os.path.join(images_dir, image_filename)
            zipf.write(image_path, arcname=image_filename)

    return send_file(zip_path, as_attachment=True)


def initialize_swiss_tournament(tournament_id, participants):
    # Create initial standings
    for participant in participants:
        standing = SwissStanding(
            tournament_id=tournament_id,
            participant=participant,
            wins=0,
            losses=0,
            ties=0
        )
        shared.db.session.add(standing)
    shared.db.session.commit()


def generate_swiss_pairings(tournament_id, round_id):
    standings = SwissStanding.query.filter_by(tournament_id=tournament_id).order_by(
        SwissStanding.wins.desc(),
        SwissStanding.losses.asc()
    ).all()

    participants = [s.participant for s in standings]
    matches = []
    used_participants = set()

    # Déterminer si un bye est nécessaire
    need_bye = len(participants) % 2 != 0
    bye_player = None

    if need_bye:
        # Sélectionner le joueur avec le plus bas score pour le bye
        for s in reversed(standings):
            if s.participant not in used_participants and not has_received_bye(tournament_id, s.participant):
                bye_player = s.participant
                used_participants.add(bye_player)
                # Créer le match avec bye
                match = SwissMatch(
                    round_id=round_id,
                    participant1=bye_player,
                    participant2=None,
                    winner=bye_player
                )
                matches.append(match)
                # Mettre à jour le classement
                s.wins += 1
                shared.db.session.add(s)
                break

    # Apparier les participants restants
    remaining_participants = [p for p in participants if p not in used_participants]

    while remaining_participants:
        p1 = remaining_participants.pop(0)
        if p1 in used_participants:
            continue

        opponent_found = False
        for idx, p2 in enumerate(remaining_participants):
            if p2 in used_participants:
                continue
            if not has_played_before(tournament_id, p1, p2):
                remaining_participants.pop(idx)
                match = SwissMatch(
                    round_id=round_id,
                    participant1=p1,
                    participant2=p2
                )
                matches.append(match)
                used_participants.update([p1, p2])
                opponent_found = True
                break

        if not opponent_found:
            # S'il n'y a pas d'adversaire avec lequel p1 n'a pas encore joué, apparier avec le prochain disponible
            for idx, p2 in enumerate(remaining_participants):
                if p2 in used_participants:
                    continue
                remaining_participants.pop(idx)
                match = SwissMatch(
                    round_id=round_id,
                    participant1=p1,
                    participant2=p2
                )
                matches.append(match)
                used_participants.update([p1, p2])
                opponent_found = True
                break

        if not opponent_found:
            # Si aucun adversaire n'est disponible, c'est une situation exceptionnelle
            # Vous pouvez décider de forcer un appariement ou de gérer différemment
            print(f"Aucun adversaire trouvé pour {p1} dans la ronde {round_id}")

    shared.db.session.add_all(matches)
    shared.db.session.commit()
    return matches

def has_received_bye(tournament_id, participant):
    bye_matches = SwissMatch.query.join(SwissRound).filter(
        SwissRound.tournament_id == tournament_id,
        SwissMatch.participant1 == participant,
        SwissMatch.participant2.is_(None)
    ).all()
    return len(bye_matches) > 0


def has_played_before(tournament_id, p1, p2):
    matches = SwissMatch.query.join(SwissRound).filter(
        SwissRound.tournament_id == tournament_id,
        (
                ((SwissMatch.participant1 == p1) & (SwissMatch.participant2 == p2)) |
                ((SwissMatch.participant1 == p2) & (SwissMatch.participant2 == p1))
        )
    ).all()
    return len(matches) > 0


def update_standings(tournament_id, winner, loser):
    winner_standing = SwissStanding.query.filter_by(tournament_id=tournament_id, participant=winner).first()
    loser_standing = SwissStanding.query.filter_by(tournament_id=tournament_id, participant=loser).first()

    winner_standing.wins += 1
    loser_standing.losses += 1

    shared.db.session.commit()


@tournament_management.route('/start_swiss_tournament', methods=['GET'])
@login_required
def start_swiss_tournament():
    user = User.query.get(current_user.id)
    if user.current_images:
        images = user_images_to_list(user.current_images)
        if not images:
            flash("Pas d'all_images pour l'utilisateur.")
            return redirect(url_for('index'))
    else:
        flash("Pas d'all_images pour l'utilisateur.")
        return redirect(url_for('index'))

    images = [f for f in images if os.path.isfile(os.path.join(images_dir, f))]
    random.shuffle(images)
    tournament_id = random.randint(999, 9999999)
    tournament = Tournament(
        id=tournament_id,
        name=f"Swiss Tournament {tournament_id}",
        categories="",  # Add categories if needed
        preview="",  # Add preview if needed
        images=",".join(images),
        user_id=current_user.id,
        private=True,
        authorized_users=str([current_user.id]),
        type='swiss'
    )
    shared.db.session.add(tournament)
    shared.db.session.commit()

    initialize_swiss_tournament(tournament_id, images)
    session['tournament_id'] = str(tournament_id)
    session['current_round'] = 1
    session['num_rounds'] = len(images) - 1  # Default number of rounds
    session['current_match_index'] = 0
    session['current_matches'] = []

    return redirect(url_for('tournament_management.swiss_round'))


@tournament_management.route('/swiss_round', methods=['GET', 'POST'])
@login_required
def swiss_round():
    tournament_id = session.get('tournament_id')
    current_round = session.get('current_round')
    num_rounds = session.get('num_rounds')
    current_match_index = session.get('current_match_index')

    if request.method == 'POST':
        winner = request.form.get('winner')
        match_id = session.get('current_match_id')
        match = SwissMatch.query.get(int(match_id))
        match.winner = winner
        shared.db.session.add(match)

        if match.participant2:  # Not a bye
            loser = match.participant1 if match.participant2 == winner else match.participant2
            update_standings(tournament_id, winner, loser)

        shared.db.session.commit()
        current_match_index += 1
        session['current_match_index'] = current_match_index

    # Check if we need to generate matches for the current round
    if current_match_index == 0:
        # Generate pairings for the round
        round = SwissRound(
            tournament_id=tournament_id,
            round_number=current_round
        )
        shared.db.session.add(round)
        shared.db.session.commit()

        matches = generate_swiss_pairings(tournament_id, round.id)
        session['current_matches'] = [match.id for match in matches]
        session['current_match_index'] = 0

    current_matches = session.get('current_matches')
    if current_match_index >= len(current_matches):
        # Round is over, reset match index and increment round
        session['current_match_index'] = 0
        session['current_round'] = current_round + 1

        # Check if tournament is over
        if current_round >= num_rounds:
            return redirect(url_for('tournament_management.swiss_results'))

        return redirect(url_for('tournament_management.show_standings'))

    match_id = current_matches[current_match_index]
    match = SwissMatch.query.get(int(match_id))
    session['current_match_id'] = match.id

    return render_template('tournament_management/swiss_match.html', match=match, round_number=current_round)


@tournament_management.route('/swiss_results')
@login_required
def swiss_results():
    tournament_id = session.get('tournament_id')
    standings = SwissStanding.query.filter_by(tournament_id=tournament_id).order_by(
        SwissStanding.wins.desc(),
        SwissStanding.losses.asc()
    ).all()
    rankings = organize_standings_into_ranks(standings)
    return render_template('tournament_management/swiss_results.html', standings=standings, rankings=rankings,
                           tournament_id=tournament_id)


@tournament_management.route('/show_standings')
@login_required
def show_standings():
    tournament_id = session.get('tournament_id')
    standings = SwissStanding.query.filter_by(tournament_id=tournament_id).order_by(
        SwissStanding.wins.desc(),
        SwissStanding.losses.asc()
    ).all()
    rankings = organize_standings_into_ranks(standings)
    return render_template('tournament_management/standings.html', standings=standings, rankings=rankings, tournament_id=tournament_id)


@tournament_management.route('/get_swiss_tierlist/<int:tournament_id>')
@login_required
def get_swiss_tierlist(tournament_id):
    standings = SwissStanding.query.filter_by(tournament_id=tournament_id).order_by(
        SwissStanding.wins.desc(),
        SwissStanding.losses.asc()
    ).all()
    rankings = organize_standings_into_ranks(standings)

    # Convert rankings to the format expected by tierlist functions
    converted_rankings = {}
    for rank in rankings:
        converted_rankings[str(rank['rank'])] = rank['all_images']

    tier_images = load_images(converted_rankings)
    tier_list_img = create_tier_list(tier_images)

    # Save the tierlist image
    tierlist_dir = os.path.join('static', 'tierlists')
    os.makedirs(tierlist_dir, exist_ok=True)
    tierlist_image_path = os.path.join(tierlist_dir, f'tierlist_{tournament_id}.png')
    tier_list_img.save(tierlist_image_path)

    return send_file(tierlist_image_path, as_attachment=True)


def organize_standings_into_ranks(standings):
    rankings = []
    index = 0
    rank_sizes = [1, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4095, 8192, 16384, 32768]  # Extend as needed

    for i, rank_size in enumerate(rank_sizes):
        if index >= len(standings):
            break
        num_images_in_rank = min(rank_size, len(standings) - index)
        rank_images = standings[index:index + num_images_in_rank]
        rank_value = 2 ** i  # Ranks: 1, 2, 4, 8, 16, ...

        rankings.append({
            'rank': rank_value,
            'all_images': [s.participant for s in rank_images]
        })
        index += num_images_in_rank

    return rankings


def generate_tierlist_image(rankings, tournament_id):
    from PIL import Image, ImageDraw, ImageFont

    # Set up paths and directories
    tierlist_dir = os.path.join('static', 'tierlists')
    os.makedirs(tierlist_dir, exist_ok=True)
    tierlist_image_path = os.path.join(tierlist_dir, f'tierlist_{tournament_id}.png')

    # Define image dimensions
    width = 800
    rank_height = 100  # Adjust based on your needs
    total_height = rank_height * len(rankings)
    canvas = Image.new('RGB', (width, total_height), 'white')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('arial.ttf', size=24)

    y_offset = 0
    for rank in rankings:
        # Draw rank label
        draw.text((10, y_offset + 10), f"Top {rank['rank']}", fill='black', font=font)

        x_offset = 150
        for image_filename in rank['all_images']:
            image_path = os.path.join(images_dir, image_filename)
            img = Image.open(image_path)
            img.thumbnail((80, 80))
            canvas.paste(img, (x_offset, y_offset + 10))
            x_offset += 90  # Adjust spacing as needed

        y_offset += rank_height

    # Save the tierlist image
    canvas.save(tierlist_image_path)

    return tierlist_image_path
