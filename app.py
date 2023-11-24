from flask import Flask, render_template, request, redirect, url_for
import os, random, math

app = Flask(__name__)

# load images
images_dir = os.path.join(app.static_folder, 'images')

# These variables store the current images being compared (ROUND) and the winners of these comparisons (WINNERS)
ROUND = []
WINNERS = []
TOTAL_IMAGES = None
round_number = None
match_number = 0

@app.route('/', methods=['GET'])
@app.route('/start', methods=['GET'])
def start():
    global ROUND, WINNERS, TOTAL_IMAGES, round_number
    images = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))]
    random.shuffle(images)
    ROUND = images
    if len(images) % 2 == 1:
        round_number = len(images)+1
    else:
        round_number = len(images)
    return redirect(url_for('match'))

@app.route('/match', methods=['GET', 'POST'])
def match():
    global ROUND, WINNERS, TOTAL_IMAGES, round_number, match_number

    if request.method == 'POST':
        winner = request.form['image']
        WINNERS.append(winner)
        if not ROUND:
            match_number = 0
            if len(WINNERS) == 1:
                return render_template('winner.html', image=WINNERS[0])
            ROUND, WINNERS = WINNERS, []
            if len(ROUND) % 2 == 1:
                round_number = len(ROUND) + 1
            else:
                round_number = len(ROUND)
        return redirect(url_for('match'))
    match_number+=1
    pair = []
    if len(ROUND) > 1:
        pair = [ROUND.pop(), ROUND.pop()]
    elif ROUND:
        pair = [ROUND.pop()]


    return render_template('match.html', pair=pair, round_name="Round of "+str(round_number), round_progress=str(match_number)+"/"+str(int(round_number/2)))

def calc_round(round_images, total_images):
    round_name = total_images
    if round_images < total_images:
        round_name = round_images * 2
    round_num = round_images // 2
    total_rounds = total_images // 2
    return round_name, round_num, total_rounds

if __name__ == "__main__":
    app.run(debug=True)