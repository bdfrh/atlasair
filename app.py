import os
import logging
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "atlas-air-secret-key-dev")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///pilots.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

# Pilot model
class Pilot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    callsign = db.Column(db.String(20), nullable=False)
    rank = db.Column(db.String(50), default='First Officer')
    balance = db.Column(db.Integer, default=25000)
    hours = db.Column(db.Integer, default=0)
    completed_flights = db.Column(db.Integer, default=0)
    aircraft_owned = db.Column(db.Text, default='')  # Store as comma-separated string
    cargo_delivered = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_aircraft_list(self):
        if self.aircraft_owned:
            return [item.strip() for item in self.aircraft_owned.split(',') if item.strip()]
        return []
    
    def add_aircraft(self, aircraft_id):
        current_aircraft = self.get_aircraft_list()
        if aircraft_id not in current_aircraft:
            current_aircraft.append(aircraft_id)
            self.aircraft_owned = ', '.join(current_aircraft)

class FlightLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pilot_id = db.Column(db.Integer, db.ForeignKey('pilot.id'), nullable=False)
    flight_number = db.Column(db.String(20), nullable=False)  # GTI_1234 format
    aircraft_type = db.Column(db.String(50), nullable=False)
    departure_airport = db.Column(db.String(10), nullable=False)
    arrival_airport = db.Column(db.String(10), nullable=False)
    cargo_type = db.Column(db.String(100), nullable=False)
    departure_time = db.Column(db.DateTime, nullable=False)  # UTC time
    flight_duration = db.Column(db.Integer, default=0)  # minutes in seconds
    status = db.Column(db.String(20), default='In Progress')  # In Progress, Paused, Completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    pilot = db.relationship('Pilot', backref='flight_logs')

with app.app_context():
    db.create_all()
    # Create a sample pilot if none exist
    if not Pilot.query.first():
        sample_pilot = Pilot(
            username='pilot001',
            name='Captain John Smith',
            callsign='ATLAS001',
            rank='Captain',
            balance=45000,
            hours=0,
            completed_flights=0,
            cargo_delivered=0,
            aircraft_owned='boeing_767, boeing_777'
        )
        sample_pilot.set_password('password123')
        db.session.add(sample_pilot)
        db.session.commit()
        logging.info("Sample pilot created: pilot001 / password123")
        
        # No sample flight logs - pilot starts fresh
        logging.info("Fresh pilot account created - ready for first flight")

# Clear any invalid session data on startup
@app.before_request
def clear_invalid_sessions():
    if 'pilot_id' in session:
        # Check if the pilot_id is valid
        try:
            pilot_id = int(session['pilot_id'])
            pilot = Pilot.query.get(pilot_id)
            if not pilot:
                session.clear()
        except (ValueError, TypeError):
            # Invalid pilot_id format, clear session
            session.clear()

# Remove old session initialization function as we now use database authentication

# Shop items data
SHOP_ITEMS = {
    'aircraft': [
        {
            'id': 'boeing_767',
            'name': 'Boeing 767-300F',
            'price': 25000,
            'description': 'Reliable mid-range freighter perfect for regional cargo operations',
            'category': 'Aircraft Access',
            'range': '3,255 nm',
            'cruise': 'Mach 0.80',
            'mtow': '186,880 kg',
            'payload': '52.4 tons'
        },
        {
            'id': 'boeing_777',
            'name': 'Boeing 777F',
            'price': 35000,
            'description': 'Versatile wide-body freighter offering exceptional range and efficiency',
            'category': 'Aircraft Access',
            'range': '4,970 nm',
            'cruise': 'Mach 0.84',
            'mtow': '347,800 kg',
            'payload': '103.0 tons'
        },
        {
            'id': 'airbus_a330',
            'name': 'Airbus A330-200F',
            'price': 32000,
            'description': 'Modern twin-engine wide-body freighter with excellent fuel efficiency',
            'category': 'Aircraft Access',
            'range': '4,000 nm',
            'cruise': 'Mach 0.82',
            'mtow': '233,000 kg',
            'payload': '70.0 tons'
        },
        {
            'id': 'boeing_747',
            'name': 'Boeing 747-8F',
            'price': 45000,
            'description': 'The legendary Queen of the Skies - Atlas Air\'s flagship freighter',
            'category': 'Aircraft Access',
            'range': '4,120 nm',
            'cruise': 'Mach 0.85',
            'mtow': '447,700 kg',
            'payload': '137.7 tons'
        }
    ],
    'roles': [
        {
            'id': 'first_officer',
            'name': 'First Officer Certification',
            'price': 5000,
            'description': 'Upgrade to First Officer rank with additional privileges',
            'category': 'Role Upgrade'
        },
        {
            'id': 'captain',
            'name': 'Captain Certification',
            'price': 12000,
            'description': 'Achieve Captain status with command authority',
            'category': 'Role Upgrade'
        },
        {
            'id': 'check_airman',
            'name': 'Check Airman Certification',
            'price': 20000,
            'description': 'Elite certification for training and evaluating other pilots',
            'category': 'Role Upgrade'
        }
    ],
    'missions': [
        {
            'id': 'cargo_express',
            'name': 'Express Cargo Mission',
            'price': 2500,
            'description': 'High-priority cargo delivery with time bonus',
            'category': 'Mission'
        },
        {
            'id': 'international_freight',
            'name': 'International Freight Route',
            'price': 4000,
            'description': 'Long-haul international cargo mission',
            'category': 'Mission'
        },
        {
            'id': 'emergency_medical',
            'name': 'Emergency Medical Transport',
            'price': 6000,
            'description': 'Critical medical supply delivery mission',
            'category': 'Mission'
        }
    ]
}

# Available flights data (inspired by real Atlas Air website)
AVAILABLE_FLIGHTS = [
    {
        'flight_number': 'AAC2156',
        'origin': 'KJFK',
        'destination': 'EGLL',
        'aircraft': 'Boeing 747-8F',
        'distance': '3,451 nm',
        'status': 'Available',
        'reward': 8500,
        'cargo_type': 'Electronics'
    },
    {
        'flight_number': 'AAC3211',
        'origin': 'KSFO',
        'destination': 'RJAA',
        'aircraft': 'Boeing 777F',
        'distance': '4,517 nm',
        'status': 'Available',
        'reward': 11200,
        'cargo_type': 'Automotive Parts'
    },
    {
        'flight_number': 'AAC1824',
        'origin': 'OMDB',
        'destination': 'VHHH',
        'aircraft': 'Airbus A330-200F',
        'distance': '3,648 nm',
        'status': 'In Progress',
        'reward': 9800,
        'cargo_type': 'Medical Supplies'
    },
    {
        'flight_number': 'AAC9542',
        'origin': 'KATL',
        'destination': 'KMIA',
        'aircraft': 'Boeing 767-300F',
        'distance': '594 nm',
        'status': 'Available',
        'reward': 3400,
        'cargo_type': 'General Freight'
    },
    {
        'flight_number': 'AAC4875',
        'origin': 'EDDF',
        'destination': 'LIRF',
        'aircraft': 'Boeing 777F',
        'distance': '734 nm',
        'status': 'Available',
        'reward': 4200,
        'cargo_type': 'Machinery'
    }
]

@app.route('/')
def home():
    if 'pilot_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        pilot = Pilot.query.filter_by(username=username).first()
        
        if pilot and pilot.check_password(password):
            session['pilot_id'] = pilot.id
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('pilot_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'pilot_id' not in session:
        return redirect(url_for('login'))
    
    pilot = Pilot.query.get(session['pilot_id'])
    if not pilot:
        session.pop('pilot_id', None)
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', pilot=pilot, flights=AVAILABLE_FLIGHTS, shop_items=SHOP_ITEMS)

@app.route('/shop')
def shop():
    if 'pilot_id' not in session:
        return redirect(url_for('login'))
    
    pilot = Pilot.query.get(session['pilot_id'])
    return render_template('shop.html', shop_items=SHOP_ITEMS, pilot=pilot)

@app.route('/flights')
def flights():
    if 'pilot_id' not in session:
        return redirect(url_for('login'))
    
    pilot = Pilot.query.get(session['pilot_id'])
    return render_template('flights.html', flights=AVAILABLE_FLIGHTS, pilot=pilot)

@app.route('/purchase/<item_id>')
def purchase(item_id):
    if 'pilot_id' not in session:
        return redirect(url_for('login'))
    
    pilot = Pilot.query.get(session['pilot_id'])
    
    # Find the item in shop
    item = None
    for category in SHOP_ITEMS.values():
        for shop_item in category:
            if shop_item['id'] == item_id:
                item = shop_item
                break
        if item:
            break
    
    if not item:
        flash('Item not found!', 'error')
        return redirect(url_for('shop'))
    
    # Check if already owned
    if item_id in pilot.get_aircraft_list():
        flash(f'You already own {item["name"]}!', 'warning')
        return redirect(url_for('shop'))
    
    # Check if pilot has enough balance
    if pilot.balance < item['price']:
        flash(f'Insufficient funds! You need ${item["price"]:,} but only have ${pilot.balance:,}', 'error')
        return redirect(url_for('shop'))
    
    # Process purchase
    pilot.balance -= item['price']
    pilot.add_aircraft(item_id)
    db.session.commit()
    
    flash(f'Successfully purchased {item["name"]} for ${item["price"]:,}!', 'success')
    return redirect(url_for('shop'))

@app.route('/inventory')
def inventory():
    if 'pilot_id' not in session:
        return redirect(url_for('login'))
    
    pilot = Pilot.query.get(session['pilot_id'])
    
    # Get owned items details
    owned_items = []
    for item_id in pilot.get_aircraft_list():
        for category in SHOP_ITEMS.values():
            for shop_item in category:
                if shop_item['id'] == item_id:
                    owned_items.append(shop_item)
                    break
    
    return render_template('inventory.html', owned_items=owned_items, pilot=pilot)

@app.route('/sync-discord/<discord_user_id>')
def sync_discord_stats(discord_user_id):
    """Sync pilot stats from Discord bot API"""
    if 'pilot_id' not in session:
        return redirect(url_for('login'))
    
    pilot = Pilot.query.get(session['pilot_id'])
    
    # Discord bot API endpoint - replace with your actual Discord bot API
    # Format should be: https://your-bot-domain.com/api/stats/{discord_user_id}
    discord_api_url = f"https://your-discord-bot-api.com/api/stats/{discord_user_id}"
    
    try:
        # Make API request to Discord bot
        response = requests.get(discord_api_url, timeout=10)
        
        if response.status_code == 200:
            discord_data = response.json()
            
            # Update pilot stats with Discord data
            pilot.balance = discord_data.get('balance', pilot.balance)
            pilot.hours = discord_data.get('flight_hours', pilot.hours)
            pilot.completed_flights = discord_data.get('completed_flights', pilot.completed_flights)
            pilot.cargo_delivered = discord_data.get('cargo_delivered', pilot.cargo_delivered)
            pilot.rank = discord_data.get('rank', pilot.rank)
            
            # Update username from Discord
            discord_username = discord_data.get('username')
            if discord_username:
                pilot.name = discord_username
            
            # Update aircraft fleet
            discord_aircraft = discord_data.get('aircraft_owned', [])
            if discord_aircraft:
                pilot.aircraft_owned = ', '.join(discord_aircraft)
            
            db.session.commit()
            flash('Successfully synced stats from Discord bot!', 'success')
            
        else:
            flash(f'Failed to sync from Discord bot. Status: {response.status_code}', 'error')
            
    except requests.exceptions.RequestException as e:
        flash(f'Error connecting to Discord bot API: {str(e)}', 'error')
        logging.error(f"Discord API error: {e}")
    
    return redirect(url_for('dashboard'))

@app.route('/flight-logs')
def flight_logs():
    """Flight logs page - shows all logged flights"""
    if 'pilot_id' not in session:
        return redirect(url_for('login'))
    
    pilot = Pilot.query.get(session['pilot_id'])
    logs = FlightLog.query.filter_by(pilot_id=pilot.id).order_by(FlightLog.departure_time.desc()).all()
    
    return render_template('flight_logs.html', pilot=pilot, flight_logs=logs)

@app.route('/add-flight-log', methods=['GET', 'POST'])
def add_flight_log():
    """Add a new flight log entry"""
    if 'pilot_id' not in session:
        return redirect(url_for('login'))
    
    pilot = Pilot.query.get(session['pilot_id'])
    
    if request.method == 'POST':
        try:
            # Parse form data
            flight_number = request.form.get('flight_number')
            aircraft_type = request.form.get('aircraft_type')
            departure_airport = request.form.get('departure_airport', '').upper()
            arrival_airport = request.form.get('arrival_airport', '').upper()
            cargo_type = request.form.get('cargo_type')
            departure_time_str = request.form.get('departure_time')
            
            # Validate flight number format (GTI_1234)
            if not flight_number.startswith('GTI_') or len(flight_number) < 5:
                flash('Flight number must be in GTI_XXXX format', 'error')
                return redirect(url_for('add_flight_log'))
            
            # Parse departure time
            departure_time = datetime.fromisoformat(departure_time_str)
            
            # Create new flight log
            new_log = FlightLog(
                pilot_id=pilot.id,
                flight_number=flight_number,
                aircraft_type=aircraft_type,
                departure_airport=departure_airport,
                arrival_airport=arrival_airport,
                cargo_type=cargo_type,
                departure_time=departure_time
            )
            
            db.session.add(new_log)
            
            # Note: Pilot stats will be updated when flight is completed via flight tracker
            # This just creates the initial flight log entry
            
            db.session.commit()
            flash('Flight log created! Starting flight tracking...', 'success')
            return redirect(url_for('flight_tracker', log_id=new_log.id))
            
        except Exception as e:
            flash(f'Error adding flight log: {str(e)}', 'error')
            logging.error(f"Flight log error: {e}")
    
    # Aircraft options for our fleet
    aircraft_options = [
        '747-400F',
        '767-300F', 
        '747-8F',
        '777-F'
    ]
    
    # Cargo type options
    cargo_options = [
        'General Freight – Consumer goods, electronics, textiles, pharmaceuticals',
        'E-Commerce & Express – Online retail shipments, high-volume parcels',
        'Perishables & Pharma – Fresh produce, seafood, flowers, vaccines, medical supplies',
        'Heavy & Oversized – Aerospace components, oil and gas equipment, large structures',
        'Industrial Machinery & Vehicles – Construction equipment, factory machinery, transportation vehicles',
        'Livestock & Animals – Racehorses, zoo animals, poultry transport',
        'Humanitarian Aid – Disaster relief supplies, emergency response equipment',
        'Military & Government – Vehicles, defense equipment, tactical gear'
    ]
    
    return render_template('add_flight_log.html', pilot=pilot, aircraft_options=aircraft_options, cargo_options=cargo_options)

@app.route('/flight-tracker/<int:log_id>')
def flight_tracker(log_id):
    """Flight tracking page with stopwatch"""
    if 'pilot_id' not in session:
        return redirect(url_for('login'))
    
    pilot = Pilot.query.get(session['pilot_id'])
    flight_log = FlightLog.query.get_or_404(log_id)
    
    # Ensure this flight belongs to the logged-in pilot
    if flight_log.pilot_id != pilot.id:
        flash('Unauthorized access to flight log', 'error')
        return redirect(url_for('flight_logs'))
    
    return render_template('flight_tracker.html', pilot=pilot, flight_log=flight_log)

@app.route('/api/flight/<int:log_id>/pause', methods=['POST'])
def pause_flight(log_id):
    """Pause a flight"""
    if 'pilot_id' not in session:
        return {'error': 'Unauthorized'}, 401
    
    flight_log = FlightLog.query.get_or_404(log_id)
    if flight_log.pilot_id != session['pilot_id']:
        return {'error': 'Unauthorized'}, 401
    
    flight_log.status = 'Paused'
    db.session.commit()
    
    return {'status': 'paused', 'message': 'Flight paused'}

@app.route('/api/flight/<int:log_id>/resume', methods=['POST'])
def resume_flight(log_id):
    """Resume a paused flight"""
    if 'pilot_id' not in session:
        return {'error': 'Unauthorized'}, 401
    
    flight_log = FlightLog.query.get_or_404(log_id)
    if flight_log.pilot_id != session['pilot_id']:
        return {'error': 'Unauthorized'}, 401
    
    flight_log.status = 'In Progress'
    db.session.commit()
    
    return {'status': 'resumed', 'message': 'Flight resumed'}

@app.route('/api/flight/<int:log_id>/end', methods=['POST'])
def end_flight(log_id):
    """End a flight and save duration"""
    if 'pilot_id' not in session:
        return {'error': 'Unauthorized'}, 401
    
    pilot = Pilot.query.get(session['pilot_id'])
    flight_log = FlightLog.query.get_or_404(log_id)
    
    if flight_log.pilot_id != pilot.id:
        return {'error': 'Unauthorized'}, 401
    
    data = request.get_json()
    flight_duration_seconds = data.get('duration', 0)
    
    # Update flight log
    flight_log.status = 'Completed'
    flight_log.flight_duration = flight_duration_seconds
    flight_log.completed_at = datetime.utcnow()
    
    # Update pilot stats
    flight_hours = flight_duration_seconds / 3600  # Convert seconds to hours
    pilot.hours += int(flight_hours)
    pilot.completed_flights += 1
    pilot.cargo_delivered += 50  # Default 50 tons per flight
    pilot.balance += 50  # $50 reward per flight
    
    db.session.commit()
    
    return {
        'status': 'completed', 
        'message': f'Flight completed! +{int(flight_hours)} hours, +50 tons cargo, +$50 reward',
        'duration_hours': round(flight_hours, 2),
        'hours_added': int(flight_hours),
        'cargo_added': 50,
        'money_earned': 50,
        'redirect_url': url_for('flight_logs')
    }

@app.route('/api/pilot/<int:pilot_id>')
def api_get_pilot(pilot_id):
    """API endpoint to get pilot data (for Discord bot integration)"""
    pilot = Pilot.query.get(pilot_id)
    if not pilot:
        return {'error': 'Pilot not found'}, 404
    
    return {
        'id': pilot.id,
        'username': pilot.username,
        'name': pilot.name,
        'callsign': pilot.callsign,
        'rank': pilot.rank,
        'balance': pilot.balance,
        'hours': pilot.hours,
        'completed_flights': pilot.completed_flights,
        'cargo_delivered': pilot.cargo_delivered,
        'aircraft_owned': pilot.get_aircraft_list(),
        'status': pilot.status,
        'created_at': pilot.created_at.isoformat() if pilot.created_at else None
    }

@app.route('/api/pilot/<int:pilot_id>/update', methods=['POST'])
def api_update_pilot(pilot_id):
    """API endpoint to update pilot data from Discord bot"""
    pilot = Pilot.query.get(pilot_id)
    if not pilot:
        return {'error': 'Pilot not found'}, 404
    
    data = request.get_json()
    
    # Update fields if provided
    if 'balance' in data:
        pilot.balance = data['balance']
    if 'hours' in data:
        pilot.hours = data['hours']
    if 'completed_flights' in data:
        pilot.completed_flights = data['completed_flights']
    if 'cargo_delivered' in data:
        pilot.cargo_delivered = data['cargo_delivered']
    if 'rank' in data:
        pilot.rank = data['rank']
    if 'aircraft_owned' in data:
        if isinstance(data['aircraft_owned'], list):
            pilot.aircraft_owned = ', '.join(data['aircraft_owned'])
        else:
            pilot.aircraft_owned = data['aircraft_owned']
    
    db.session.commit()
    
    return {'message': 'Pilot updated successfully', 'pilot': {
        'id': pilot.id,
        'balance': pilot.balance,
        'hours': pilot.hours,
        'completed_flights': pilot.completed_flights,
        'cargo_delivered': pilot.cargo_delivered,
        'rank': pilot.rank,
        'aircraft_owned': pilot.get_aircraft_list()
    }}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
