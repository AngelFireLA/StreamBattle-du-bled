import json
import re
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session
import os, random, math

app = Flask(__name__)

# load images
images_dir = os.path.join(app.static_folder, 'images')
tournaments_dir = os.path.join(app.static_folder, 'tournaments')
app.secret_key = "srguzGW2kTdjhqpsUKnG5DyJvvCUk5b9"

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

@app.route('/start', methods=['GET'])
def start():
    global ROUND, WINNERS, TOTAL_IMAGES, round_number
    images = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))]
    random.shuffle(images)
    tournament_file = create_tournament(random.randint(999, 9999999), images)
    session['tournament_file'] = tournament_file
    ROUND = images
    if len(images) % 2 == 1:
        round_number = len(images) + 1
    else:
        round_number = len(images)

    return redirect(url_for('match'))


def randomize_list(input_list):
    # Create a copy of the original list
    randomized_list = input_list.copy()

    # Initialize a loop from the last element to the first
    for i in range(len(randomized_list) - 1, 0, -1):
        # Generate a random index within the range [0, i]
        j = random.randint(0, i)

        # Swap the elements at indices i and j
        randomized_list[i], randomized_list[j] = randomized_list[j], randomized_list[i]

    return randomized_list

@app.route('/match', methods=['GET', 'POST'])
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
                            (match['round'] for match in tournament_data['matches'] if
                             participant in match['participants'] and match['winner'] != participant),
                            default=0
                        )
                        rankings[participant] = max_round

                # Sort rankings by rank and update JSON file
                sorted_rankings = sorted(rankings.items(), key=lambda x: x[1])
                tournament_data['rankings'] = [{"file": file, "rank": rank} for file, rank in sorted_rankings]

                with open(os.path.join(tournaments_dir, tournament_file), 'w') as file:
                    json.dump(tournament_data, file, indent=4)

                return render_template('winner.html', image=WINNERS[0], rankings=tournament_data['rankings'])
            WINNERS = randomize_list(WINNERS)
            ROUND, WINNERS = WINNERS, []
            ROUND = randomize_list(ROUND)
            random.shuffle(ROUND)
            if len(ROUND) % 2 == 1:
                round_number = len(ROUND) + 1
            else:
                round_number = len(ROUND)

        return redirect(url_for('match'))

    match_number += 1
    pair = []
    if len(ROUND) > 1:
        pair = [ROUND.pop(), ROUND.pop()]
    elif ROUND:
        pair = [ROUND.pop()]

    return render_template('match.html', pair=pair, round_name="Round of " + str(round_number), round_progress=str(match_number) + "/" + str(int(round_number / 2)))

def calc_round(round_images, total_images):
    round_name = total_images
    if round_images < total_images:
        round_name = round_images * 2
    round_num = round_images // 2
    total_rounds = total_images // 2
    return round_name, round_num, total_rounds
import zipfile
from flask import send_file

@app.route('/download_rank/<int:rank>')
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


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

from flask import Flask, render_template, request, redirect, url_for, jsonify
import os, shutil, hashlib

# Assuming a 'deleted' folder exists within 'static/images'
deleted_folder = os.path.join(app.static_folder, 'deleted')

@app.route('/manage')
def manage():
    images = os.listdir(os.path.join(app.static_folder, 'images'))
    images = [img for img in images] # Exclude the 'deleted' folder
    return render_template('manage.html', images=images)

@app.route('/delete-image', methods=['POST'])
def delete_image():
    image_name = request.form['image']
    image_path = os.path.join(app.static_folder, 'images', image_name)
    deleted_image_path = os.path.join(deleted_folder, image_name)

    # Check if the image already exists in the 'deleted' folder
    if os.path.exists(deleted_image_path):
        # Compare content to avoid duplicate images with different names
        if file_content_hash(image_path) == file_content_hash(deleted_image_path):
            os.remove(image_path) # Remove the current image as it's a duplicate
            return jsonify({'status': 'deleted'})
        else:
            # Rename the image to avoid name conflict
            new_name = rename_file(deleted_folder, image_name)
            shutil.move(image_path, os.path.join(deleted_folder, new_name))
    else:
        shutil.move(image_path, deleted_image_path)

    return jsonify({'status': 'moved'})

@app.route('/upload-images', methods=['POST'])
def upload_images():
    uploaded_files = request.files.getlist("images[]")
    for file in uploaded_files:
        file.save(os.path.join(app.static_folder, 'images', file.filename))
    return jsonify({'status': 'uploaded'})

def file_content_hash(file_path):
    """Generate a hash of the file content."""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def rename_file(directory, file_name):
    """Rename a file to avoid name conflicts."""
    base, ext = os.path.splitext(file_name)
    counter = 1
    new_name = f"{base}_{counter}{ext}"
    while os.path.exists(os.path.join(directory, new_name)):
        counter += 1
        new_name = f"{base}_{counter}{ext}"
    return new_name

import instaloader

count_by_images = False

def download_images(username, max_images=None):
    loader = instaloader.Instaloader(download_comments=False,
                                      download_videos=False,
                                      download_video_thumbnails=False,
                                      download_geotags=False,
                                      save_metadata=False,
                                      post_metadata_txt_pattern='',
                                      filename_pattern='{date_utc}_UTC')
    profile = instaloader.Profile.from_username(loader.context, username)

    image_count = 0

    for post in profile.get_posts():
        if not post.is_video:
            # If the post is an image
            if max_images is None or image_count < max_images:
                # Download the image
                loader.download_post(post, target=profile.username)
                image_count += 1
                if max_images is not None and image_count >= max_images:
                    break
    if count_by_images:
        # Clean-up: Remove images that don't end with UTC or UTC_1
        for image_file in os.listdir(username):
            if not re.search(r'UTC(_1)?\.(jpg|jpeg|png)$', image_file):
                os.remove(os.path.join(username, image_file))

@app.route('/delete-all-images', methods=['POST'])
def delete_all_images():
    image_dir = os.path.join(app.static_folder, 'images')
    for image in os.listdir(image_dir):
        if image != 'deleted':  # Avoid deleting the 'deleted' folder
            image_path = os.path.join(image_dir, image)
            shutil.move(image_path, os.path.join(deleted_folder, image))
    return jsonify({'status': 'all_deleted'})

@app.route('/download-instagram', methods=['POST'])
def download_instagram_images():
    username = request.form['username']
    max_images = int(request.form['count'])
    if max_images == 69:
        print("downloading every image")
        max_images = None
    # Use the download_images function to download images
    download_images(username, max_images)

    # The path where downloaded images are stored
    instagram_folder_path = os.path.join(os.getcwd(), username)

    # Target path to move images to
    target_folder_path = os.path.join(app.static_folder, 'images')

    # Moving the images to the 'images' folder
    for image_file in os.listdir(instagram_folder_path):
        source_path = os.path.join(instagram_folder_path, image_file)
        target_path = os.path.join(target_folder_path, image_file)
        shutil.move(source_path, target_path)

    # Remove the now-empty Instagram folder
    shutil.rmtree(instagram_folder_path)

    return jsonify({'status': 'downloaded'})



if __name__ == "__main__":
    app.run(debug=True)