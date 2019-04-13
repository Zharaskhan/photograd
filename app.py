# en_US.utf-8
from operator import itemgetter

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
                    'rating': p['rating']
                }
            )
    for user in users:
        r.set('users:' + str(user['id']), json.dumps(user))

    return 'Successful'

def expected_elo(A, B):
    return (1 - (abs(1 / (1 + 10 ** ((B - A) / 400)) - 0.5))) * 100

@app.route('/user/<id>')
def page(id):
    user = json.loads(r.get('users:' + str(id)))
    opponents = []
    for opp in get_all_users():
        new_opp = opp
        new_opp['elo_diff'] = expected_elo(user['rating'], opp['rating'])
        opponents.append(new_opp)

    return render_template('user.html', user=user, opponents=opponents)

def get_all_users():
    users = []
    keys = r.keys('users:*')

    for key in keys:
        users.append(json.loads(r.get(key)))

    return users

@app.route('/users')
def get_users():
    return render_template('users.html', users=get_all_users())


if __name__ == '__main__':
    app.run()
