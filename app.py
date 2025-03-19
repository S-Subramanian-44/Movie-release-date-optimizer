from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import random
import datetime
import numpy as np
import MySQLdb.cursors

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'mani@2133044'
app.config['MYSQL_DB'] = 'movie_optimizer_db'

mysql = MySQL(app)

# Database Schema Creation
with app.app_context():
    cursor = mysql.connection.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS studios (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        studio_name VARCHAR(255) UNIQUE NOT NULL,
                        password VARCHAR(255) NOT NULL,
                        year_established INT,
                        movies_produced INT,
                        win_rate FLOAT DEFAULT 0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS movie_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        studio_name VARCHAR(255) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        genre VARCHAR(255) NOT NULL,
                        release_date DATE NOT NULL,
                        profit FLOAT,
                        won INT DEFAULT 0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS new_releases (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        studio_name VARCHAR(255) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        genre VARCHAR(255) NOT NULL,
                        release_date DATE NOT NULL,
                        budget FLOAT,
                        expected_revenue FLOAT)''')
    
    mysql.connection.commit()

def calculate_win_rate(studio_name):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT COUNT(*) as total, SUM(won) as won FROM movie_history WHERE studio_name=%s", (studio_name,))
    result = cursor.fetchone()
    if result:
        total_movies = result['total']
        won_movies = result['won'] if result['won'] else 0
        win_rate = (won_movies / total_movies) * 100 if total_movies > 0 else 0
        cursor.execute("UPDATE studios SET win_rate=%s WHERE studio_name=%s", (win_rate, studio_name))
        mysql.connection.commit()
        return win_rate
    return 0

def game_theory_optimization(studio, alternative_dates):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT DISTINCT release_date, studio_name FROM movie_history WHERE studio_name != %s", (studio,))
    competitors = cursor.fetchall()
    competitor_power = {comp['studio_name']: calculate_win_rate(comp['studio_name']) for comp in competitors if comp['studio_name']}
    payoffs = {date: random.uniform(0.5, 1.5) / (1 + float(sum(competitor_power.values()))) for date in alternative_dates}
    best_date = max(payoffs, key=payoffs.get)
    return best_date, [comp['release_date'] for comp in competitors]

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        studio_name = request.form.get('studio_name')
        password = request.form.get('password')
        year_established = request.form.get('year_established', type=int)
        movies_produced = request.form.get('movies_produced', type=int)

        if not (studio_name and password and year_established and movies_produced is not None):
            return "Missing fields", 400

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Check if studio already exists
        cursor.execute("SELECT * FROM studios WHERE studio_name = %s", (studio_name,))
        existing_studio = cursor.fetchone()

        if existing_studio:
            return render_template('signup.html', error="Studio already exists! Try another name.")

        if movies_produced == 0:
            # Directly insert into `studios` if no movies are produced
            cursor.execute(
                "INSERT INTO studios (studio_name, password, year_established, movies_produced) VALUES (%s, %s, %s, %s)",
                (studio_name, password, year_established, movies_produced)
            )
            mysql.connection.commit()
            return redirect(url_for('login'))  # No movies, proceed to login

        # Store session data to pass studio details to /add_movies
        session['studio_name'] = studio_name
        session['password'] = password
        session['year_established'] = year_established
        session['movies_produced'] = movies_produced

        return redirect(url_for('add_movies'))  # Redirect to add movies

    return render_template('signup.html', error=None)

@app.route('/add_movies', methods=['GET', 'POST'])
def add_movies():
    if request.method == 'POST':
        studio_name = session.get('studio_name')
        password = session.get('password')
        year_established = session.get('year_established')
        movies_produced = session.get('movies_produced')

        if not (studio_name and password and year_established and movies_produced):
            return redirect(url_for('signup'))  # Redirect if session data is lost

        cursor = mysql.connection.cursor()
        movie_data = []

        for i in range(movies_produced):
            title = request.form.get(f'title_{i}')
            genre = request.form.get(f'genre_{i}')
            release_date = request.form.get(f'release_date_{i}')
            profit = request.form.get(f'profit_{i}', type=float)
            won = request.form.get(f'won_{i}', type=int)

            if not (title and genre and release_date and profit is not None and won is not None):
                return "Missing movie details", 400

            movie_data.append((studio_name, title, genre, release_date, profit, won))

        # Insert all movies into `movie_history` table
        cursor.executemany(
            "INSERT INTO movie_history (studio_name, title, genre, release_date, profit, won) VALUES (%s, %s, %s, %s, %s, %s)",
            movie_data
        )
        mysql.connection.commit()

        # **Now insert the studio into the `studios` table after movie submission**
        cursor.execute(
            "INSERT INTO studios (studio_name, password, year_established, movies_produced) VALUES (%s, %s, %s, %s)",
            (studio_name, password, year_established, movies_produced)
        )
        mysql.connection.commit()

        # Update the win rate for the studio
        calculate_win_rate(studio_name)

        # Clear session data after successful insertion
        session.pop('studio_name', None)
        session.pop('password', None)
        session.pop('year_established', None)
        session.pop('movies_produced', None)

        return redirect(url_for('login'))  # After adding movies, go to login

    return render_template('movie_history.html', movies_produced=session.get('movies_produced', 0))

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        studio_name = request.form.get('studio_name')
        password = request.form.get('password')

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM studios WHERE studio_name = %s AND password = %s", (studio_name, password))
        studio = cursor.fetchone()

        if studio:
            session['studio_name'] = studio_name  
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials!")

    return render_template('login.html')

# Fix: Ensure the correct endpoint name is used
@app.route('/competitor_releases')
def competitor_releases():
    if 'studio_name' not in session:
        return redirect(url_for('login'))  

    today = datetime.date.today()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch all upcoming releases (from all studios)
    cursor.execute("""
        SELECT title, genre, release_date, studio_name 
        FROM movie_history 
        WHERE release_date >= %s
        UNION 
        SELECT title, genre, release_date, studio_name
        FROM new_releases 
        WHERE release_date >= %s
        ORDER BY release_date ASC
    """, (today, today))  

    upcoming_movies = cursor.fetchall()
    cursor.close()

    return render_template('competitor_releases.html', upcoming_movies=upcoming_movies)


# Fix: Update references to 'upcoming_releases' to 'competitor_releases'
@app.route('/dashboard')
def dashboard():
    if 'studio_name' not in session:
        return redirect(url_for('login'))  

    studio_name = session['studio_name']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch movie history for the logged-in studio
    cursor.execute("SELECT * FROM movie_history WHERE studio_name = %s", (studio_name,))
    movies = cursor.fetchall()

    # Fetch win rate
    cursor.execute("SELECT win_rate FROM studios WHERE studio_name = %s", (studio_name,))
    studio_data = cursor.fetchone()
    win_rate = studio_data['win_rate'] if studio_data else 0  

    # Fetch upcoming releases for logged-in studio only
    today = datetime.date.today()
    cursor.execute("""
        SELECT title, genre, release_date 
        FROM movie_history 
        WHERE release_date >= %s AND studio_name = %s
        UNION 
        SELECT title, genre, release_date
        FROM new_releases 
        WHERE release_date >= %s AND studio_name = %s
        ORDER BY release_date ASC
    """, (today, studio_name, today, studio_name))  

    upcoming_movies = cursor.fetchall()
    cursor.close()

    return render_template('dashboard.html', studio_name=studio_name, movies=movies, win_rate=win_rate, upcoming_movies=upcoming_movies)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/apply_release', methods=['POST'])
def apply_release():
    if 'studio_name' in session:
        data = request.json
        studio_name = session['studio_name']
        title = data.get('title')
        genre = data.get('genre')
        budget = float(data.get('budget', 0)) if data.get('budget') is not None else 0
        expected_revenue = float(data.get('expected_revenue', 0)) if data.get('expected_revenue') is not None else 0
        alternative_dates = data.get('alternative_dates')
        
        if not (title and genre and budget is not None and expected_revenue is not None and alternative_dates and len(alternative_dates) >= 3):
            return jsonify({'error': 'Invalid input data'}), 400
        
        best_date, competitors = game_theory_optimization(studio_name, alternative_dates)
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO new_releases (studio_name, title, genre, release_date, budget, expected_revenue) VALUES (%s, %s, %s, %s, %s, %s)", 
                       (studio_name, title, genre, best_date, budget, expected_revenue))
        mysql.connection.commit()
        
        return jsonify({'best_date': best_date, 'competitors': competitors})
    return jsonify({'error': 'Unauthorized'}), 401

if __name__ == '__main__':
    app.run(debug=True)
