from flask import Flask, Response, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
import MySQLdb.cursors
import re
import uuid
import requests
import pandas as pd
import matplotlib.pyplot as plt

app = Flask(__name__)

app.config['MYSQL_HOST'] = "localhost"
app.config['MYSQL_USER'] = "root"
app.config['MYSQL_PASSWORD'] = "02022004"
app.config['MYSQL_DB'] = "mt"

mysql = MySQL(app)
bcrypt = Bcrypt(app)

def human_format(num, t=0):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

@app.route('/')
def index():
  cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
  cursor.execute(
    "SELECT * FROM packages WHERE ratings = 5 ORDER BY RAND() LIMIT 10")
  top_packages = cursor.fetchall()
  cursor.execute("SELECT * FROM packages ORDER BY RAND() LIMIT 10")
  popular_packages = cursor.fetchall()
  cursor.execute("SELECT * FROM packages ORDER BY RAND() LIMIT 10")
  trending_packages = cursor.fetchall()
  user = {}
  if 'id' in session and 'email' in session:
    cursor.execute(
      "SELECT username FROM users WHERE id='{}'".format(session['id']))
    username = cursor.fetchall()[0]['username']
    user = {
      "id": session['id'],
      "email": session['email'],
      "username": username.split()[0]
    }
  return render_template('index.html', user=user, top_packages=top_packages, popular_packages=popular_packages, trending_packages=trending_packages)


@app.route('/destinations')
def packages():
  page = 0
  if request.args.get('page'):
    page = int(request.args.get('page')) - 1
  cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
  cursor.execute("SELECT COUNT(*) as c FROM packages")
  page_length = cursor.fetchall()[0]['c'] // 20 + 1
  cursor.execute("SELECT * FROM packages LIMIT {}, 20".format(20 * page))
  packages = cursor.fetchall()
  user = {}
  if 'id' in session and 'email' in session:
    user = {
      "id": session['id'],
      "email": session['email'],
    }
  return render_template('packages.html', user=user, packages=packages, page_length=page_length, page=page+1)


@app.route('/destination/<string:slug>')
def package(slug):
  cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
  cursor.execute("SELECT * FROM packages WHERE slug='{}'".format(slug))
  city = cursor.fetchall()[0]
  cursor.execute("SELECT * FROM places WHERE city='{}'".format(slug))
  places = cursor.fetchall()
  user = {}
  if 'id' in session and 'email' in session:
    user = {
        "id": session['id'],
        "email": session['email'],
    }
  return render_template('package.html', user=user, city=city, places=places)

@app.route('/covid-19')
def covid():
  world = requests.get("https://disease.sh/v3/covid-19/historical/all?lastdays=30")
  country_wise = requests.get("https://disease.sh/v3/covid-19/countries?sort=cases").json()[:20]
  cases = recovered = deaths = 0
  if world.status_code == 200:
    data = pd.DataFrame(world.json())
    plt.style.use('bmh')
    plt.rcParams.update({'font.size': 24})
    ax = data.plot(kind="bar", figsize=(25,15,), grid=True, y=['cases', 'recovered'], width=0.8, color=['#4788a3', '#4ee768'])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(human_format))
    plt.savefig('./static/graph/graph.png')

    cases = human_format(data['cases'].iloc[-1])
    recovered = human_format(data['recovered'].iloc[-1])
    deaths = human_format(data['deaths'].iloc[-1])
    
  user = {}
  if 'id' in session and 'email' in session:
    user = {
        "id": session['id'],
        "email": session['email'],
    }
  return render_template('covid.html', user=user, tally=(cases, recovered,deaths,), country_wise=country_wise, format=human_format)

@app.route('/newsletter', methods=['GET', 'POST'])
def newsletter():
  return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
  if 'id' in session and session['id']:
    return redirect(url_for('index'))
  msg = ''
  if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
    email = request.form['email']
    password = request.form['password']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
      'SELECT id,username, email, password FROM users WHERE email = %s', (email,))
    account = cursor.fetchone()
    if account and bcrypt.check_password_hash(account['password'], password):
      session['id'] = account['id']
      session['email'] = account['email']
      flash(f'Successfully logged in as {account["username"]}', 'success')
      return redirect(url_for('index'))
    else:
      flash('Incorrect email/password!', 'error')
  return render_template('login.html', msg=msg)


@app.route('/logout')
def logout():
  session.pop('id', None)
  session.pop('email', None)

  return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
  if 'id' in session and session['id']:
    return redirect(url_for('index'))
  msg = category = ''
  if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'confirm-password' in request.form and 'email' in request.form:
    username = request.form['username']
    password = request.form['password']
    confirm_password = request.form['confirm-password']
    email = request.form['email']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
    user = cursor.fetchone()
    if user:
      msg = 'Account already exists! Please try logging in.'
      category = 'warning'
    elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
      msg = 'Invalid email address!'
      category = 'warning'
    elif not re.match(r'[A-Za-z0-9]+', username):
      msg = 'Username must contain only characters and numbers!'
      category = 'warning'
    elif not password == confirm_password:
      msg = 'Passwords must match'
      category = 'warning'
    elif not username or not password or not email:
      msg = 'Please fill out the form!'
      category = 'warning'
    else:
      Id = str(uuid.uuid4())
      cursor.execute('INSERT INTO users VALUES (%s, %s, %s, %s)',
                      (Id, username, bcrypt.generate_password_hash(password), email,))
      mysql.connection.commit()
      msg = 'You have successfully registered!'
      category = 'success'
    flash(msg, category)
  elif request.method == 'POST':
    msg = 'Please fill out the form!'
    flash(msg, 'warning')
  return render_template('login.html')


@app.errorhandler(404)
def page_not_found(e):
  return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(e):
  return render_template('errors/500.html'), 500


if __name__ == "__main__":
  app.secret_key = 'kahfjkhswklefuihuanu4awnwina'
  app.run(debug=True, host="127.0.0.1", port=3000)
