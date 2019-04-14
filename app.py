# en_US.utf-8
import random
import time
from math import exp

from flask import Flask, render_template, abort, request
import redis
import json

app = Flask(__name__)
r = redis.Redis(host='localhost', port=6379, db=0)


@app.route('/')
def hello_world():
    return str(r.get('foo'), 'utf-8')


@app.route('/upload_user')
def upload_user_data():
    users = []
    with open('data.json') as json_file:
        data = json.load(json_file)
        for p in data['data']['top_rating']:
            # print('Name: ' + p['username'])
            # print('ID: ' + str(p['id']))
            # print('Rating: ' + str(p['rating']))
            # print('\n')
            users.append(
                {
                    'username': p['username'],
                    'id': p['id'],
                    'rating': p['rating'],
                    'played_games': random.randint(0, 100)
                }
            )
    for user in users:
        r.set('users:' + str(user['id']), json.dumps(user))

    return 'Successful'


def expected_elo(A, B):
    return (0.5 - (abs(1 / (1 + 10 ** ((B - A) / 400)) - 0.5))) * 200


def expected_waiting(A):
    return (1 - 1.2 ** (-7.6 / 60 * A)) * 100


def expected_game(A, B):
    return (1 - (abs(1 / (1 + 10 ** ((B - A) / 50)) - 0.5))) * 100


def expected_score(player1_id, player2_id, waiting_time):
    player1 = json.loads(r.get('users:' + str(player1_id)))
    player2 = json.loads(r.get('users:' + str(player2_id)))

    return expected_elo(player1['rating'],
                        player2['rating']) * 0.4 + expected_waiting(
        float(waiting_time)) * 0.4 + expected_game(player1['played_games'],
                                                   player2[
                                                       'played_games']) * 0.2


def play_game(game_id, player1_id, player2_id):
    r.delete('games:' + game_id)
    r.lpush('played_games:' + player1_id, player2_id)
    # store last 5 played games
    r.ltrim('played_games:' + player1_id, 0, 4)

    r.lpush('played_games:' + player2_id, player1_id)
    # store last 5 played games
    r.ltrim('played_games:' + player2_id, 0, 4)

    print('Game between ' + player1_id + " and " + player2_id)


def calculate_number_of_games(player1_id, player2_id):
    number_of_games_by_first = 0
    for game in r.lrange('played_games:' + str(player1_id), 0, -1):
        if int(game) == int(player2_id):
            number_of_games_by_first = number_of_games_by_first + 1

    number_of_games_by_second = 0
    for game in r.lrange('played_games:' + str(player2_id), 0, -1):
        if int(game) == int(player1_id):
            number_of_games_by_second = number_of_games_by_second + 1

    return max(number_of_games_by_first, number_of_games_by_second)


@app.route('/create_new_game/<player_id>')
def create_new_game(player_id):
    date_created = str(int(time.time()))

    print('New game created')

    r.set('games:' + date_created, json.dumps({
        'id': date_created,
        'player_id': player_id,
        'date_created': date_created
    }))
    return 'Game created'


@app.route('/new_game/<id>')
def new_game(id):
    games = r.keys('games:*')
    waiting_games = []

    for key in games:
        game = json.loads(r.get(key))
        opponent_id = int(game['player_id'])

        if int(opponent_id) == int(id):
            continue

        if calculate_number_of_games(id, opponent_id) >= 4:
            print('Skipped by number of games')
            continue

        waiting_games.append(game)

    found = False

    stats = []

    if len(waiting_games) != 0:
        score_sum = 0
        for game in waiting_games:
            score = expected_score(id, game['player_id'], game['date_created'])
            score_sum += score

        # createing new game
        ng = 100 / min(10, len(waiting_games))
        score_sum += ng

        rnd_sum = random.random() * score_sum
        cur_sum = 0

        for game in waiting_games:
            score = expected_score(id, game['player_id'], game['date_created'])

            if cur_sum <= rnd_sum <= cur_sum + score:
                play_game(game['id'], id, game['player_id'])
                found = True
                break

            cur_sum += score

        cur_sum = 0
        for game in waiting_games:
            g = game
            g['probability'] = expected_score(id, game['player_id'],
                                              game['date_created']) / score_sum * 100

            g['chosen'] = False

            player1 = json.loads(r.get('users:' + str(id)))
            player2 = json.loads(r.get('users:' + str(game['player_id'])))
            g['elo'] = expected_elo(player1['rating'],player2['rating'])
            g['last_games'] = calculate_number_of_games(id, game['player_id'])


            if cur_sum <= rnd_sum <= cur_sum + score:
                g['chosen'] = True

            cur_sum += score

            stats.append(g)

        stats.append({'id': 'new game', 'player_id': 'new game', 'probability': ng / score_sum * 100, 'date_created': str(int(time.time())), 'chosen': found == False})
    else:
        stats.append({'id': 'new game', 'player_id': 'new game',
                      'probability': 100,
                      'date_created': str(int(time.time())),
                      'chosen': found == False})

    if found == False:
        create_new_game(id)

    return render_template('game_statistics.html', games=stats)


@app.route('/user/<id>')
def page(id):
    user = json.loads(r.get('users:' + str(id)))
    opponents = []
    for opp in get_all_users():
        new_opp = opp
        new_opp['elo_diff'] = expected_elo(user['rating'], opp['rating'])
        new_opp['game_diff'] = user['played_games'] - opp['played_games']
        new_opp['game_diff_coef'] = expected_game(user['played_games'],
                                                  opp['played_games'])
        opponents.append(new_opp)

    return render_template('user.html', user=user, opponents=opponents)


def get_all_users():
    users = []
    keys = r.keys('users:*')

    for key in keys:
        users.append(json.loads(r.get(key)))

    return users


@app.route('/clear_games')
def clear_games():

    for key in r.keys('games:*'):
        r.delete(key)

    for key in r.keys('played_games:*'):
        r.delete(key)
    return 'Success'


@app.route('/games')
def show_games():
    games = r.keys('games:*')
    game_list = []

    for key in games:
        game = json.loads(r.get(key))
        game['rating'] = json.loads(r.get('users:' + str(game['player_id'])))['rating']
        game_list.append(game)

    return render_template('games.html', games=game_list)


@app.route('/time')
def get_time():
    graphic = []
    for i in range(0, 200):
        graphic.append({
            'time': i,
            'expected': expected_waiting(i)
        })
    return render_template('waiting_time.html', waiting=graphic)


@app.route('/users')
def get_users():
    return render_template('users.html', users=get_all_users())


if __name__ == '__main__':
    app.run()
