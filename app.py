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
    return (1 - (abs(1 / (1 + 10 ** ((B - A) / 400)) - 0.5))) * 100


def expected_waiting(A):
    return (1 - 1.2 ** (-7.6 / 60 * A)) * 100


def expected_game(A, B):
    return (1 - (abs(1 / (1 + 10 ** ((B - A) / 50)) - 0.5))) * 100


def play_game(game_id, player1_id, player2_id):
    r.delete('games:' + game_id)
    r.lpush('played_games:' + player1_id, player2_id)
    #store last 5 played games
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


def create_new_game(player_id):
    date_created = str(int(time.time()))

    print('New game created')

    r.set('games:' + date_created, json.dumps({
        'player_id': player_id,
        'date_created': date_created
    }))


def new_game(id):
    games = json.loads(r.get('games:*'))
    waiting_games = []
    if games:
        for key in games:
            game = json.loads(r.get(key))
            opponent_id = int(game['player_id'])

            if opponent_id == id:
                continue

            if calculate_number_of_games(id, opponent_id) >= 4:
                print('Skipped by number of games')
                continue

            waiting_games.append(game)

    if len(waiting_games) == 0:
        create_new_game(id)
    else:
        print(waiting_games)





@app.route('/user/<id>')
def page(id):
    user = json.loads(r.get('users:' + str(id)))
    opponents = []
    for opp in get_all_users():
        new_opp = opp
        new_opp['elo_diff'] = expected_elo(user['rating'], opp['rating'])
        new_opp['game_diff'] = user['played_games'] - opp['played_games']
        new_opp['game_diff_coef'] = expected_game(user['played_games'], opp['played_games'])
        opponents.append(new_opp)

    return render_template('user.html', user=user, opponents=opponents)

def get_all_users():
    users = []
    keys = r.keys('users:*')

    for key in keys:
        users.append(json.loads(r.get(key)))

    return users


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
