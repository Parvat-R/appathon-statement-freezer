# server.py
import json
import os
from threading import Lock
from flask import Flask, render_template, request, session, redirect, url_for
import socketio

# Create Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Create Socket.IO server
sio = socketio.Server(async_mode='threading')
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

# Data lock for thread safety
data_lock = Lock()
teams_lock = Lock()

# Load problem statements data
def load_data():
    try:
        with open('data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Initialize with sample data if file doesn't exist
        data = {
            "PS01": {
                "id": "PS01",
                "name": "Problem Statement 1",
                "description": "This is the first problem statement",
                "limit": 3,
                "teams": [],
                "open": True
            }
        }
        with open('data.json', 'w') as f:
            json.dump(data, f, indent=4)
        return data

# Load teams data
def load_teams():
    try:
        with open('teams.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Initialize with empty data if file doesn't exist
        teams = {
            "team1": "team1@example.com",
            "team2": "team2@example.com"
        }
        with open('teams.json', 'w') as f:
            json.dump(teams, f, indent=4)
        return teams

# Save problem statements data
def save_data(data):
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

# Check if team has already selected a problem statement
def get_team_selected_ps(team_id):
    data = load_data()
    for ps_id, ps_info in data.items():
        if team_id in ps_info['teams']:
            return ps_id
    return None

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    team_id = request.form.get('team_id')
    email = request.form.get('email')
    
    # Admin login
    if team_id == "i am admin" and email == "let me to the dashboard":
        session['is_admin'] = True
        return redirect(url_for('admin_dashboard'))
    
    # Team login
    teams = load_teams()
    if team_id in teams and teams[team_id] == email:
        session['team_id'] = team_id
        return redirect(url_for('team_dashboard'))
    
    return render_template('index.html', error="Invalid team ID or email")

@app.route('/team_dashboard')
def team_dashboard():
    if 'team_id' not in session:
        return redirect(url_for('index'))
    
    team_id = session['team_id']
    data = load_data()
    selected_ps = get_team_selected_ps(team_id)
    
    return render_template('team_dashboard.html', 
                          problem_statements=data, 
                          team_id=team_id, 
                          selected_ps=selected_ps)

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('is_admin', False):
        return redirect(url_for('index'))
    
    data = load_data()
    return render_template('admin_dashboard.html', problem_statements=data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Socket.IO events
@sio.event
def connect(sid, environ):
    print('Client connected', sid)

@sio.event
def disconnect(sid):
    print('Client disconnected', sid)

@sio.event
def join_room(sid, data):
    if 'room' in data:
        sio.enter_room(sid, data['room'])
        print(f"Client {sid} joined room {data['room']}")

@sio.event
def select_problem_statement(sid, data):
    team_id = data['team_id']
    ps_id = data['ps_id']
    
    with data_lock:
        problem_statements = load_data()
        
        # Check if team has already selected a PS
        for existing_ps_id, ps_info in problem_statements.items():
            if team_id in ps_info['teams']:
                return {'success': False, 'message': 'Team has already selected a problem statement'}
        
        ps_info = problem_statements.get(ps_id)
        if not ps_info:
            return {'success': False, 'message': 'Problem statement not found'}
        
        # Check if problem statement is open
        if not ps_info['open']:
            return {'success': False, 'message': 'Problem statement is closed'}
        
        # Check if limit is reached
        if len(ps_info['teams']) >= ps_info['limit']:
            return {'success': False, 'message': 'Problem statement has reached its team limit'}
        
        # Add team to problem statement
        ps_info['teams'].append(team_id)
        save_data(problem_statements)
        
        # Broadcast update to all clients
        sio.emit('ps_update', problem_statements)
        
        # Return success with updated problem statements
        return {
            'success': True, 
            'message': 'Problem statement selected successfully',
            'selected_ps': ps_id,
            'problem_statements': problem_statements
        }

@sio.event
def get_updated_data(sid, data=None):
    # The data parameter accepts any data sent from the client, even if it's empty
    data = load_data()
    return data

# Start the server
if __name__ == '__main__':
    print("Starting server on http://localhost:5000")
    # Use the built-in Flask dev server as an alternative (not ideal for production)
    app.run(debug=True)