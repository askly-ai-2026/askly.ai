import os
import random
import string
import re
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from werkzeug.utils import secure_filename
from groq import Groq
from models import db, User, OTP, ChatSession, Message, UserSettings
from dotenv import load_dotenv
from PIL import Image
from flask_mail import Mail, Message as MailMessage
import bcrypt




load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Database configuration - PostgreSQL on production, SQLite locally
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

CORS(app)
db.init_app(app)
mail = Mail(app)

# Create database tables on startup (important for production)
with app.app_context():
    db.create_all()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ------------------- Helper Functions -------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    return User.query.get(int(session['user_id']))

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_email(to, subject, body):
    msg = MailMessage(subject, sender=app.config['MAIL_USERNAME'], recipients=[to])
    msg.body = body
    mail.send(msg)

def send_otp_email(email, otp, purpose='registration'):
    subject = f"Your OTP for {purpose} - Askly AI"
    body = f"Your OTP is: {otp}\nThis OTP is valid for 1 minute.\n\nThank you for using Askly AI."
    send_email(email, subject, body)

def store_otp(email, otp, purpose='registration'):
    # Delete old OTPs for this email and purpose
    OTP.query.filter_by(email=email, purpose=purpose).delete()
    new_otp = OTP(email=email, otp=otp, expires_at=datetime.utcnow() + timedelta(minutes=1), purpose=purpose)
    db.session.add(new_otp)
    db.session.commit()

def verify_otp(email, otp, purpose='registration'):
    record = OTP.query.filter_by(email=email, otp=otp, purpose=purpose).filter(OTP.expires_at > datetime.utcnow()).first()
    if record:
        db.session.delete(record)
        db.session.commit()
        return True
    return False

def get_or_create_settings(user_id):
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.session.add(settings)
        db.session.commit()
    return settings

def generate_chat_title(first_message):
    return first_message[:30] + "..." if len(first_message) > 30 else first_message

def clean_ai_response(text):
    """Remove markdown symbols (*, #, _, `, etc.) and format nicely."""
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*[-*]\s+', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# ------------------- PUBLIC ROUTES -------------------
@app.route('/')
def landing():
    return render_template('landing.html', theme='light')

@app.route('/about')
def about():
    return render_template('about.html', theme='light')

@app.route('/contact')
def contact():
    return render_template('contact.html', theme='light')

@app.route('/help')
def help_page():
    return render_template('help.html', theme='light')

# ------------------- AUTH ROUTES -------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form['login_id']
        password = request.form['password']
        user = User.query.filter((User.username == login_id) | (User.email == login_id)).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            session['user_id'] = str(user.id)
            session['username'] = user.username
            return redirect(url_for('chat'))
        else:
            flash('Invalid username/email or password', 'error')
    return render_template('login.html', theme='light')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or email already exists', 'error')
            return redirect(url_for('signup'))
        otp = generate_otp()
        store_otp(email, otp, 'registration')
        send_otp_email(email, otp, 'registration')
        session['temp_signup'] = {'username': username, 'email': email, 'password': password}
        return redirect(url_for('verify_signup'))
    return render_template('signup.html', theme='light')

@app.route('/verify-signup', methods=['GET', 'POST'])
def verify_signup():
    if 'temp_signup' not in session:
        return redirect(url_for('signup'))
    if request.method == 'POST':
        otp = request.form['otp']
        email = session['temp_signup']['email']
        if verify_otp(email, otp, 'registration'):
            data = session.pop('temp_signup')
            hashed = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            new_user = User(
                    username=data['username'],
                    email=data['email'],
                    password_hash=hashed,   # ← now a string
                    profile_photo='default.jpg',
                    created_at=datetime.utcnow()
)
            db.session.add(new_user)
            db.session.commit()
            send_email(data['email'], "Welcome to Askly AI", "Thank you for registering! Enjoy your AI assistant.")
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid or expired OTP', 'error')
    return render_template('verify_otp.html', purpose='signup', theme='light')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Email not found', 'error')
            return redirect(url_for('forgot_password'))
        otp = generate_otp()
        store_otp(email, otp, 'password_reset')
        send_otp_email(email, otp, 'password reset')
        session['reset_email'] = email
        return redirect(url_for('reset_password'))
    return render_template('forgot.html', theme='light')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session:
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        otp = request.form['otp']
        new_pass = request.form['new_password']
        confirm = request.form['confirm_password']
        if new_pass != confirm:
            flash('Passwords do not match', 'error')
            return redirect(url_for('reset_password'))
        email = session['reset_email']
        if verify_otp(email, otp, 'password_reset'):
            # Hash and decode to UTF-8 string for storage
            hashed = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user = User.query.filter_by(email=email).first()
            user.password_hash = hashed
            db.session.commit()
            session.pop('reset_email')
            flash('Password updated successfully. Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid or expired OTP', 'error')
    return render_template('reset_password.html', theme='light')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('landing'))

# ------------------- MAIN CHAT (protected) -------------------
@app.route('/chat')
@login_required
def chat():
    user = get_current_user()
    user_id = int(session['user_id'])
    sessions = ChatSession.query.filter_by(user_id=user_id).order_by(ChatSession.created_at.desc()).all()
    settings = get_or_create_settings(user_id)
    return render_template('index.html',
                           sessions=[s.to_dict() for s in sessions],
                           settings=settings,
                           theme='light',
                           username=user.username,
                           profile_photo=user.profile_photo)

@app.route('/settings')
@login_required
def settings_page():
    user = get_current_user()
    user_id = int(session['user_id'])
    settings = get_or_create_settings(user_id)
    return render_template('settings.html',
                           settings=settings,
                           theme='light',
                           email=user.email,
                           username=user.username,
                           profile_photo=user.profile_photo)

@app.route('/api/send-delete-otp', methods=['POST'])
@login_required
def send_delete_otp():
    user = get_current_user()
    email = user.email
    otp = generate_otp()
    store_otp(email, otp, 'account_deletion')
    send_otp_email(email, otp, 'account deletion')
    return jsonify({'success': True})

@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    data = request.get_json()
    user_message = data.get('message', '')
    session_id = data.get('session_id')
    model = data.get('model', 'llama-3.3-70b-versatile')
    user_id = int(session['user_id'])

    if not session_id:
        title = generate_chat_title(user_message)
        new_session = ChatSession(title=title, user_id=user_id)
        db.session.add(new_session)
        db.session.commit()
        session_id = new_session.id

    user_msg = Message(session_id=session_id, role='user', content=user_message)
    db.session.add(user_msg)

    history = Message.query.filter_by(session_id=session_id).order_by(Message.timestamp).all()
    messages_for_api = [{"role": msg.role, "content": msg.content} for msg in history]

    system_prompt = {
        "role": "system",
        "content": (
            "You are Askly AI, a professional and friendly assistant. "
            "Provide well-structured, summarized, and easy-to-understand answers. "
            "Use plain text only. Do NOT use any markdown symbols like *, #, _, `, or backticks. "
            "For lists, use a dash - or bullet • at the start of each line. "
            "For sections, use line breaks and capital letters. "
            "Keep responses concise yet comprehensive."
        )
    }
    messages_for_api.insert(0, system_prompt)

    try:
        completion = groq_client.chat.completions.create(
            messages=messages_for_api,
            model=model,
            temperature=0.7,
            max_tokens=1024,
        )
        ai_response = completion.choices[0].message.content
        ai_response = clean_ai_response(ai_response)

        assistant_msg = Message(session_id=session_id, role='assistant', content=ai_response)
        db.session.add(assistant_msg)
        db.session.commit()

        return jsonify({'success': True, 'session_id': session_id, 'response': ai_response})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sessions', methods=['GET', 'POST', 'DELETE'])
@login_required
def manage_sessions():
    user_id = int(session['user_id'])
    if request.method == 'GET':
        sessions = ChatSession.query.filter_by(user_id=user_id).order_by(ChatSession.created_at.desc()).all()
        return jsonify([s.to_dict() for s in sessions])
    elif request.method == 'POST':
        new_session = ChatSession(user_id=user_id)
        db.session.add(new_session)
        db.session.commit()
        return jsonify(new_session.to_dict()), 201
    elif request.method == 'DELETE':
        session_id = request.args.get('session_id')
        if session_id:
            session_obj = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
            if session_obj:
                db.session.delete(session_obj)
                db.session.commit()
                return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Session not found'}), 404

@app.route('/api/sessions/<int:session_id>', methods=['PUT'])
@login_required
def rename_session(session_id):
    user_id = int(session['user_id'])
    data = request.get_json()
    new_title = data.get('title', '').strip()
    if not new_title:
        return jsonify({'success': False, 'error': 'Title cannot be empty'}), 400
    session_obj = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session_obj:
        return jsonify({'success': False, 'error': 'Session not found'}), 404
    session_obj.title = new_title[:100]
    db.session.commit()
    return jsonify({'success': True, 'session': session_obj.to_dict()})

@app.route('/api/sessions/<int:session_id>/messages', methods=['GET'])
@login_required
def get_session_messages(session_id):
    user_id = int(session['user_id'])
    session_obj = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session_obj:
        return jsonify({'error': 'Session not found'}), 404
    messages = Message.query.filter_by(session_id=session_id).order_by(Message.timestamp).all()
    return jsonify([msg.to_dict() for msg in messages])

@app.route('/api/history/clear', methods=['POST'])
@login_required
def clear_all_history():
    user_id = int(session['user_id'])
    try:
        sessions = ChatSession.query.filter_by(user_id=user_id).all()
        for s in sessions:
            Message.query.filter_by(session_id=s.id).delete()
            db.session.delete(s)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def update_settings():
    user_id = int(session['user_id'])
    user = get_current_user()
    settings = get_or_create_settings(user_id)
    if request.method == 'GET':
        return jsonify({
            'profile_photo': settings.profile_photo,
            'theme': settings.theme,
            'email': user.email,
            'username': user.username
        })
    elif request.method == 'POST':
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                img = Image.open(filepath)
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                img.save(filepath, quality=95)
                settings.profile_photo = filename
                user.profile_photo = filename
                db.session.commit()
        if 'theme' in request.form:
            settings.theme = request.form['theme']
            db.session.commit()
        return jsonify({'success': True, 'settings': {
            'profile_photo': settings.profile_photo,
            'theme': settings.theme,
            'email': user.email
        }})

@app.route('/api/settings/remove-photo', methods=['POST'])
@login_required
def remove_profile_photo():
    user_id = int(session['user_id'])
    user = get_current_user()
    settings = get_or_create_settings(user_id)
    if settings.profile_photo != 'default.jpg':
        old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.profile_photo)
        if os.path.exists(old_path):
            os.remove(old_path)
        settings.profile_photo = 'default.jpg'
        user.profile_photo = 'default.jpg'
        db.session.commit()
    return jsonify({'success': True, 'photo': 'default.jpg'})

@app.route('/api/settings/reset-photo', methods=['POST'])
@login_required
def reset_profile_photo():
    user_id = int(session['user_id'])
    user = get_current_user()
    settings = get_or_create_settings(user_id)
    if settings.profile_photo != 'default.jpg':
        old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.profile_photo)
        if os.path.exists(old_path):
            os.remove(old_path)
    settings.profile_photo = 'default.jpg'
    user.profile_photo = 'default.jpg'
    db.session.commit()
    return jsonify({'success': True, 'photo': 'default.jpg'})

@app.route('/api/theme', methods=['POST'])
@login_required
def toggle_theme():
    data = request.get_json()
    theme = data.get('theme')
    if theme in ('dark', 'light'):
        user_id = int(session['user_id'])
        settings = get_or_create_settings(user_id)
        settings.theme = theme
        db.session.commit()
        return jsonify({'success': True, 'theme': theme})
    return jsonify({'success': False, 'error': 'Invalid theme'}), 400

# ------------------- ACCOUNT & EMAIL UPDATE -------------------
@app.route('/api/send-otp', methods=['POST'])
@login_required
def send_otp_for_email():
    data = request.get_json()
    new_email = data.get('email')
    if not new_email:
        return jsonify({'success': False, 'error': 'Email required'}), 400
    existing = User.query.filter(User.email == new_email, User.id != int(session['user_id'])).first()
    if existing:
        return jsonify({'success': False, 'error': 'Email already in use'}), 400
    otp = generate_otp()
    store_otp(new_email, otp, 'email_update')
    send_otp_email(new_email, otp, 'email update')
    session['pending_email'] = new_email
    return jsonify({'success': True})

@app.route('/api/verify-update-email', methods=['POST'])
@login_required
def verify_update_email():
    data = request.get_json()
    otp = data.get('otp')
    new_email = session.get('pending_email')
    if not new_email:
        return jsonify({'success': False, 'error': 'No pending email update'}), 400
    if verify_otp(new_email, otp, 'email_update'):
        user = get_current_user()
        user.email = new_email
        db.session.commit()
        session.pop('pending_email')
        return jsonify({'success': True, 'email': new_email})
    else:
        return jsonify({'success': False, 'error': 'Invalid or expired OTP'}), 400

@app.route('/api/delete-account', methods=['POST'])
@login_required
def delete_account():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')
    user = get_current_user()
    if user.email != email:
        return jsonify({'success': False, 'error': 'Email does not match'}), 400
    if verify_otp(email, otp, 'account_deletion'):
        # Delete messages first, then sessions, then settings, then user
        sessions = ChatSession.query.filter_by(user_id=user.id).all()
        for sess in sessions:
            Message.query.filter_by(session_id=sess.id).delete()
            db.session.delete(sess)
        UserSettings.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        # Clear Flask session and log out
        session.clear()  # This is the Flask session, not a chat session
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Invalid or expired OTP'}), 400

# ------------------- ADMIN PANEL -------------------
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # Total users
    total_users = User.query.count()
    
    # All users sorted by creation date (newest first)
    users = User.query.order_by(User.created_at.desc()).all()
    users_list = []
    for user in users:
        users_list.append({
            'username': user.username,
            'email': user.email,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else 'N/A'
        })
    
    # Data for chart: users created per day (last 7 days)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    labels = []
    counts = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        next_day = day + timedelta(days=1)
        labels.append(day.strftime('%b %d'))
        count = User.query.filter(User.created_at >= day, User.created_at < next_day).count()
        counts.append(count)
    
    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           users=users_list,
                           chart_labels=labels,
                           chart_data=counts)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)