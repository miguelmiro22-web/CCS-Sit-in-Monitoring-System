from flask import Flask, render_template, request, redirect, session, url_for, jsonify, Response, flash
import sqlite3
import hashlib
import webbrowser
import threading
import os
import base64
import csv
import io
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'ccs_secret_key'
DB = 'ccs.db'

# ─── INIT DATABASE ─────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL UNIQUE,
            lastname TEXT NOT NULL,
            firstname TEXT NOT NULL,
            middlename TEXT,
            course TEXT NOT NULL,
            course_level INTEGER NOT NULL,
            email TEXT NOT NULL UNIQUE,
            address TEXT NOT NULL,
            password TEXT NOT NULL,
            remaining_session INTEGER DEFAULT 30,
            photo TEXT,
            points INTEGER DEFAULT 0,
            converted_sessions INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS sitin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            purpose TEXT NOT NULL,
            lab TEXT NOT NULL,
            session INTEGER NOT NULL,
            status TEXT DEFAULT 'Active',
            time_in TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            time_out TIMESTAMP,
            pc_number TEXT,
            pc_status TEXT DEFAULT 'Good',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            message TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS reservation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            lab TEXT NOT NULL,
            purpose TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            pc_number TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            rating INTEGER NOT NULL,
            message TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS software (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS lab_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab TEXT NOT NULL UNIQUE,
            reservation_enabled INTEGER DEFAULT 1
        )
    ''')
    try:
        c.execute('ALTER TABLE reservation ADD COLUMN start_time TEXT')
    except:
        pass
    try:
        c.execute('ALTER TABLE reservation ADD COLUMN end_time TEXT')
    except:
        pass
    try:
        c.execute('ALTER TABLE reservation ADD COLUMN pc_number TEXT')
    except:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS lab_pcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab TEXT NOT NULL,
            pc_number TEXT NOT NULL,
            status TEXT DEFAULT 'available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # UPDATED LAB LIST
    labs = ['Lab 517', 'Lab 524', 'Lab 526', 'Lab 528', 'Lab 530', 'Lab 540', 'Lab 542', 'Lab 544']
    for lab in labs:
        for i in range(1, 51):
            c.execute('INSERT OR IGNORE INTO lab_pcs (lab, pc_number) VALUES (?, ?)', (lab, f'PC{i}'))
        c.execute('INSERT OR IGNORE INTO lab_settings (lab, reservation_enabled) VALUES (?, 1)', (lab,))

    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT DEFAULT 'reservation',
            message TEXT NOT NULL,
            reservation_id INTEGER,
            student_name TEXT,
            lab TEXT,
            date TEXT,
            time_slot TEXT,
            pc_number TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS point_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            points INTEGER NOT NULL,
            action TEXT NOT NULL,
            remarks TEXT,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

# ─── HOME ──────────────────────────────────────────────────────────
@app.route('/')
def home():
    return render_template('index.html')

# ─── LOGIN ─────────────────────────────────────────────────────────
@app.route('/login', methods=['POST'])
def login():
    login_id = request.form.get('login_id', '').strip()
    password = request.form.get('password', '').strip()
    error    = None

    if login_id == 'admin@ccs.com' and password == 'admin123':
        session['role']      = 'admin'
        session['firstname'] = 'Admin'
        return redirect(url_for('admin_dashboard'))

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id_number = ?', (login_id,)).fetchone()
    conn.close()

    if user is None:
        error = 'No account found with that ID number.'
    elif user['password'] != hash_password(password):
        error = 'Incorrect password.'
    else:
        session['user_id']      = user['id']
        session['firstname']    = user['firstname']
        session['lastname']     = user['lastname']
        session['course']       = user['course']
        session['course_level'] = user['course_level']
        session['id_number']    = user['id_number']
        session['role']         = 'student'
        return redirect(url_for('student_dashboard'))

    return render_template('index.html', login_error=error, show_page='login')

# ─── REGISTER ──────────────────────────────────────────────────────
@app.route('/register', methods=['POST'])
def register():
    id_number    = request.form.get('id_number', '').strip()
    lastname     = request.form.get('lastname', '').strip()
    firstname    = request.form.get('firstname', '').strip()
    middlename   = request.form.get('middlename', '').strip()
    course       = request.form.get('course', '').strip()
    course_level = request.form.get('course_level', '').strip()
    email        = request.form.get('email', '').strip()
    address      = request.form.get('address', '').strip()
    password     = request.form.get('password', '').strip()
    confirm      = request.form.get('confirm', '').strip()
    error        = None

    if not all([id_number, lastname, firstname, course, course_level, email, address, password, confirm]):
        error = 'Please fill in all required fields.'
    elif password != confirm:
        error = 'Passwords do not match.'
    elif len(password) < 8:
        error = 'Password must be at least 8 characters.'
    else:
        try:
            conn = get_db()
            conn.execute('''
                INSERT INTO users (id_number, lastname, firstname, middlename, course, course_level, email, address, password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (id_number, lastname, firstname, middlename, course, int(course_level), email, address, hash_password(password)))
            conn.commit()
            conn.close()
            return render_template('index.html', register_success=True, show_page='login')
        except sqlite3.IntegrityError as e:
            if 'id_number' in str(e):
                error = 'ID Number already registered.'
            elif 'email' in str(e):
                error = 'Email already registered.'
            else:
                error = 'Registration failed. Please try again.'

    return render_template('index.html', register_error=error, show_page='register')

# ─── STUDENT DASHBOARD (with points, recent sessions) ───────────────
@app.route('/student')
@login_required
def student_dashboard():
    conn = get_db()
    announcements = conn.execute('SELECT * FROM announcements ORDER BY date DESC').fetchall()
    user_data = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    sitins = conn.execute(
        'SELECT * FROM sitin WHERE id_number = ? ORDER BY date DESC LIMIT 5',
        (session.get('id_number'),)
    ).fetchall()
    mini_leaderboard = conn.execute('''
        SELECT id_number, firstname, lastname, points
        FROM users WHERE points > 0 ORDER BY points DESC LIMIT 5
    ''').fetchall()
    rank_row = conn.execute('''
        SELECT COUNT(*) + 1 as rank FROM users WHERE points > (SELECT points FROM users WHERE id_number = ?)
    ''', (session.get('id_number'),)).fetchone()
    rank = rank_row['rank'] if rank_row else 0
    conn.close()
    return render_template('student_dashboard.html', user=user_data, announcements=announcements,
                           sitins=sitins, mini_leaderboard=mini_leaderboard, rank=rank)

# ─── STUDENT EDIT PROFILE ──────────────────────────────────────────
@app.route('/student/edit_profile', methods=['GET', 'POST'])
@login_required
def student_edit_profile():
    conn = get_db()
    if request.method == 'POST':
        firstname  = request.form.get('firstname', '').strip()
        lastname   = request.form.get('lastname', '').strip()
        middlename = request.form.get('middlename', '').strip()
        address    = request.form.get('address', '').strip()
        email      = request.form.get('email', '').strip()
        photo      = request.files.get('photo')
        if photo and photo.filename != '':
            photo_data = base64.b64encode(photo.read()).decode('utf-8')
            mime_type  = photo.content_type
            photo_str  = f"data:{mime_type};base64,{photo_data}"
            conn.execute('''
                UPDATE users SET firstname=?, lastname=?, middlename=?, address=?, email=?, photo=?
                WHERE id=?
            ''', (firstname, lastname, middlename, address, email, photo_str, session['user_id']))
        else:
            conn.execute('''
                UPDATE users SET firstname=?, lastname=?, middlename=?, address=?, email=?
                WHERE id=?
            ''', (firstname, lastname, middlename, address, email, session['user_id']))
        conn.commit()
        session['firstname'] = firstname
        session['lastname']  = lastname
        conn.close()
        return redirect(url_for('student_dashboard'))
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('student_edit_profile.html', user=user)

# ─── STUDENT HISTORY ───────────────────────────────────────────────
@app.route('/student/history')
@login_required
def student_history():
    conn   = get_db()
    sitins = conn.execute(
        'SELECT * FROM sitin WHERE id_number = ? ORDER BY date DESC',
        (session.get('id_number'),)
    ).fetchall()
    conn.close()
    return render_template('student_history.html', user=session, sitins=sitins)

# ─── STUDENT FEEDBACK ──────────────────────────────────────────────
@app.route('/student/feedback', methods=['GET', 'POST'])
@login_required
def student_feedback():
    if request.method == 'POST':
        message   = request.form.get('message', '').strip()
        id_number = session.get('id_number')
        if message:
            conn = get_db()
            conn.execute('INSERT INTO feedback (id_number, message) VALUES (?, ?)', (id_number, message))
            conn.commit()
            conn.close()
        return redirect(url_for('student_feedback'))
    conn      = get_db()
    feedbacks = conn.execute('SELECT * FROM feedback WHERE id_number = ?', (session.get('id_number'),)).fetchall()
    conn.close()
    return render_template('student_feedback.html', user=session, feedbacks=feedbacks)

# ─── AVAILABLE PCS API ─────────────────────────────────────────────
@app.route('/student/available_pcs')
@login_required
def available_pcs():
    lab = request.args.get('lab')
    date = request.args.get('date')
    start_time = request.args.get('start_time')
    if not all([lab, date, start_time]):
        return jsonify({'error': 'Missing parameters'}), 400
    try:
        start_dt = datetime.strptime(start_time, '%H:%M')
        end_dt = start_dt + timedelta(hours=1)
        end_time = end_dt.strftime('%H:%M')
    except:
        return jsonify({'error': 'Invalid time'}), 400

    conn = get_db()
    all_pcs = conn.execute('SELECT pc_number FROM lab_pcs WHERE lab = ?', (lab,)).fetchall()
    reserved = conn.execute('''
        SELECT pc_number FROM reservation
        WHERE lab = ? AND date = ?
          AND status IN ('Pending', 'Approved')
          AND ((start_time <= ? AND end_time > ?) OR
               (start_time < ? AND end_time >= ?) OR
               (start_time >= ? AND start_time < ?))
    ''', (lab, date, start_time, start_time, end_time, end_time, start_time, end_time)).fetchall()
    reserved_pcs = {r['pc_number'] for r in reserved}
    available = [pc['pc_number'] for pc in all_pcs if pc['pc_number'] not in reserved_pcs]
    conn.close()
    return jsonify({'available_pcs': available})

# ─── STUDENT RESERVATION ───────────────────────────────────────────
@app.route('/student/reservation', methods=['GET', 'POST'])
@login_required
def student_reservation():
    conn = get_db()
    if request.method == 'POST':
        lab = request.form.get('lab', '').strip()
        purpose = request.form.get('purpose', '').strip()
        date = request.form.get('date', '').strip()
        start_time = request.form.get('start_time', '').strip()
        pc_number = request.form.get('pc_number', '').strip()
        id_number = session.get('id_number')
        error = None

        if not start_time:
            error = 'Please select a start time.'
        else:
            try:
                start_dt = datetime.strptime(start_time, '%H:%M')
                end_dt = start_dt + timedelta(hours=1)
                end_time = end_dt.strftime('%H:%M')
            except:
                error = 'Invalid time format.'

            if not error:
                lab_setting = conn.execute('SELECT * FROM lab_settings WHERE lab = ?', (lab,)).fetchone()
                if lab_setting and lab_setting['reservation_enabled'] == 0:
                    error = 'Reservations for this lab are currently disabled.'
                else:
                    reserved = conn.execute('''
                        SELECT pc_number FROM reservation
                        WHERE lab = ? AND date = ? AND pc_number = ?
                          AND status IN ('Pending', 'Approved')
                          AND ((start_time <= ? AND end_time > ?) OR
                               (start_time < ? AND end_time >= ?) OR
                               (start_time >= ? AND start_time < ?))
                    ''', (lab, date, pc_number, start_time, start_time, end_time, end_time, start_time, end_time)).fetchone()
                    if reserved:
                        error = 'This PC is already reserved for the selected time slot.'
                    else:
                        cursor = conn.execute('''
                            INSERT INTO reservation (id_number, lab, purpose, date, start_time, end_time, pc_number)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (id_number, lab, purpose, date, start_time, end_time, pc_number))
                        reservation_id = cursor.lastrowid
                        student = conn.execute('SELECT firstname, lastname FROM users WHERE id_number = ?', (id_number,)).fetchone()
                        student_name = f"{student['firstname']} {student['lastname']}"
                        conn.execute('''
                            INSERT INTO admin_notifications (type, message, reservation_id, student_name, lab, date, time_slot, pc_number)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', ('reservation', f'New reservation from {student_name}', reservation_id, student_name, lab, date, f'{start_time} - {end_time}', pc_number))
                        conn.commit()
                        conn.close()
                        return redirect(url_for('student_reservation'))

        reservations = conn.execute('SELECT * FROM reservation WHERE id_number = ?', (id_number,)).fetchall()
        lab_settings = conn.execute('SELECT * FROM lab_settings').fetchall()
        conn.close()
        return render_template('student_reservation.html', user=session,
                               reservations=reservations, lab_settings=lab_settings,
                               error=error)

    reservations = conn.execute('SELECT * FROM reservation WHERE id_number = ?', (session.get('id_number'),)).fetchall()
    lab_settings = conn.execute('SELECT * FROM lab_settings').fetchall()
    conn.close()
    return render_template('student_reservation.html', user=session,
                           reservations=reservations, lab_settings=lab_settings)

# ─── STUDENT TESTIMONIALS ──────────────────────────────────────────
@app.route('/student/testimonials', methods=['GET', 'POST'])
@login_required
def student_testimonials():
    conn = get_db()
    if request.method == 'POST':
        rating    = request.form.get('rating', '5')
        message   = request.form.get('message', '').strip()
        id_number = session.get('id_number')
        if message:
            conn.execute('INSERT INTO testimonials (id_number, rating, message) VALUES (?, ?, ?)',
                         (id_number, int(rating), message))
            conn.commit()
        conn.close()
        return redirect(url_for('student_testimonials'))
    testimonials = conn.execute('''
        SELECT t.*, u.firstname, u.lastname FROM testimonials t
        JOIN users u ON t.id_number = u.id_number
        ORDER BY t.date DESC
    ''').fetchall()
    my_testimonial = conn.execute(
        'SELECT * FROM testimonials WHERE id_number = ? ORDER BY date DESC LIMIT 1',
        (session.get('id_number'),)
    ).fetchone()
    conn.close()
    return render_template('student_testimonials.html', user=session,
        testimonials=testimonials, my_testimonial=my_testimonial)

# ─── STUDENT SUMMARY ───────────────────────────────────────────────
@app.route('/student/summary')
@login_required
def student_summary():
    conn      = get_db()
    id_number = session.get('id_number')
    sitins    = conn.execute(
        'SELECT * FROM sitin WHERE id_number = ? ORDER BY date DESC',
        (id_number,)
    ).fetchall()
    software  = conn.execute('SELECT * FROM software ORDER BY lab').fetchall()
    lab_settings = conn.execute('SELECT * FROM lab_settings').fetchall()
    user_data = conn.execute('SELECT * FROM users WHERE id_number = ?', (id_number,)).fetchone()
    conn.close()

    total_sessions = len(sitins)
    purpose_counts = {}
    for s in sitins:
        purpose = s['purpose']
        purpose_counts[purpose] = purpose_counts.get(purpose, 0) + 1
    if purpose_counts:
        most_used_purpose = max(purpose_counts, key=purpose_counts.get)
    else:
        most_used_purpose = '—'
    
    return render_template('student_summary.html', user=user_data,
        sitins=sitins, total_sessions=total_sessions,
        most_used_purpose=most_used_purpose,
        software=software, lab_settings=lab_settings)

# ─── STUDENT SESSIONS ──────────────────────────────────────────────
@app.route('/student/sessions')
@login_required
def student_sessions():
    conn = get_db()
    id_number = session.get('id_number')
    sitins = conn.execute('SELECT * FROM sitin WHERE id_number = ? ORDER BY date DESC', (id_number,)).fetchall()
    sessions_with_duration = []
    for s in sitins:
        s = dict(s)
        if s['time_in'] and s['time_out']:
            try:
                time_in = datetime.strptime(s['time_in'], '%Y-%m-%d %H:%M:%S')
                time_out = datetime.strptime(s['time_out'], '%Y-%m-%d %H:%M:%S')
                diff_seconds = (time_out - time_in).total_seconds()
                if diff_seconds > 0:
                    hours = int(diff_seconds // 3600)
                    minutes = int((diff_seconds % 3600) // 60)
                    duration = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                else:
                    duration = "0m"
            except:
                duration = "—"
        else:
            duration = "—"
        s['duration'] = duration
        sessions_with_duration.append(s)
    conn.close()
    return render_template('student_sessions.html', user=session, sitins=sessions_with_duration)

# ─── STUDENT LABS ──────────────────────────────────────────────────
@app.route('/student/labs')
@login_required
def student_labs():
    conn = get_db()
    lab_settings = conn.execute('SELECT * FROM lab_settings ORDER BY lab').fetchall()
    conn.close()
    return render_template('student_labs.html', user=session, lab_settings=lab_settings)

# ─── STUDENT NOTIFICATIONS ─────────────────────────────────────────
@app.route('/student/notifications')
@login_required
def get_notifications():
    conn          = get_db()
    announcements = conn.execute('SELECT * FROM announcements ORDER BY date DESC LIMIT 5').fetchall()
    conn.close()
    return jsonify([{'id': a['id'], 'content': a['content'], 'date': a['date'][:10]} for a in announcements])

# ─── ADMIN DASHBOARD (with new stats) ──────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    total_students = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    currently_sitin = conn.execute("SELECT COUNT(*) FROM sitin WHERE status='Active'").fetchone()[0]
    total_sitin = conn.execute('SELECT COUNT(*) FROM sitin').fetchone()[0]
    announcements = conn.execute('SELECT * FROM announcements ORDER BY date DESC').fetchall()
    purposes = conn.execute("SELECT purpose, COUNT(*) as count FROM sitin GROUP BY purpose").fetchall()
    total_points_given = conn.execute('SELECT COALESCE(SUM(points), 0) FROM point_logs WHERE action = "add"').fetchone()[0]
    total_converted = conn.execute('SELECT COALESCE(SUM(points), 0) FROM point_logs WHERE action = "convert"').fetchone()[0]
    top_student = conn.execute('SELECT firstname, lastname, points FROM users ORDER BY points DESC LIMIT 1').fetchone()
    total_sessions_completed = conn.execute('SELECT COUNT(*) FROM sitin WHERE status = "Done"').fetchone()[0]
    conn.close()
    return render_template('admin_dashboard.html',
        total_students=total_students, currently_sitin=currently_sitin,
        total_sitin=total_sitin, announcements=announcements, purposes=purposes,
        total_points_given=total_points_given, total_converted=total_converted,
        top_student=top_student, total_sessions_completed=total_sessions_completed)

# ─── ADMIN STATS API ───────────────────────────────────────────────
@app.route('/admin/stats')
@admin_required
def admin_stats():
    conn = get_db()
    total_students  = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    currently_sitin = conn.execute("SELECT COUNT(*) FROM sitin WHERE status='Active'").fetchone()[0]
    total_sitin     = conn.execute('SELECT COUNT(*) FROM sitin').fetchone()[0]
    purposes        = conn.execute("SELECT purpose, COUNT(*) as count FROM sitin GROUP BY purpose").fetchall()
    conn.close()
    return jsonify({
        'total_students': total_students,
        'currently_sitin': currently_sitin,
        'total_sitin': total_sitin,
        'labels': [p['purpose'] for p in purposes],
        'chart_data': [p['count'] for p in purposes]
    })

# ─── ADMIN STUDENTS ────────────────────────────────────────────────
@app.route('/admin/students')
@admin_required
def admin_students():
    conn = get_db()
    students = conn.execute('SELECT * FROM users ORDER BY lastname').fetchall()
    conn.close()
    return render_template('admin_students.html', students=students)

@app.route('/admin/students/add', methods=['POST'])
@admin_required
def add_student():
    id_number    = request.form.get('id_number', '').strip()
    lastname     = request.form.get('lastname', '').strip()
    firstname    = request.form.get('firstname', '').strip()
    middlename   = request.form.get('middlename', '').strip()
    course       = request.form.get('course', '').strip()
    course_level = request.form.get('course_level', '').strip()
    email        = request.form.get('email', '').strip()
    address      = request.form.get('address', '').strip()
    password     = request.form.get('password', '').strip()
    try:
        conn = get_db()
        conn.execute('''
            INSERT INTO users (id_number, lastname, firstname, middlename, course, course_level, email, address, password)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (id_number, lastname, firstname, middlename, course, int(course_level), email, address, hash_password(password)))
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        pass
    return redirect(url_for('admin_students'))

@app.route('/admin/students/delete/<id_number>')
@admin_required
def delete_student(id_number):
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id_number = ?', (id_number,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_students'))

@app.route('/admin/students/edit/<id_number>', methods=['GET', 'POST'])
@admin_required
def edit_student(id_number):
    conn = get_db()
    if request.method == 'POST':
        lastname     = request.form.get('lastname')
        firstname    = request.form.get('firstname')
        middlename   = request.form.get('middlename')
        course       = request.form.get('course')
        course_level = request.form.get('course_level')
        email        = request.form.get('email')
        address      = request.form.get('address')
        conn.execute('''
            UPDATE users SET lastname=?, firstname=?, middlename=?, course=?, course_level=?, email=?, address=?
            WHERE id_number=?
        ''', (lastname, firstname, middlename, course, course_level, email, address, id_number))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_students'))
    student = conn.execute('SELECT * FROM users WHERE id_number = ?', (id_number,)).fetchone()
    conn.close()
    return render_template('edit_student.html', student=student)

@app.route('/admin/students/reset_sessions')
@admin_required
def reset_sessions():
    conn = get_db()
    conn.execute('UPDATE users SET remaining_session = 30')
    conn.commit()
    conn.close()
    return redirect(url_for('admin_students'))

# ─── ADMIN SEARCH ──────────────────────────────────────────────────
@app.route('/admin/search', methods=['POST'])
@admin_required
def admin_search():
    query    = request.form.get('query', '').strip()
    conn     = get_db()
    students = conn.execute('''
        SELECT * FROM users WHERE id_number LIKE ? OR firstname LIKE ? OR lastname LIKE ?
    ''', (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
    conn.close()
    return render_template('admin_students.html', students=students, search=True, query=query)

# ─── ADMIN SIT-IN ──────────────────────────────────────────────────
@app.route('/admin/sitin')
@admin_required
def admin_sitin():
    conn   = get_db()
    sitins = conn.execute('''
        SELECT s.*, u.firstname, u.lastname FROM sitin s
        JOIN users u ON s.id_number = u.id_number
        WHERE s.status = "Active" ORDER BY s.date DESC
    ''').fetchall()
    conn.close()
    return render_template('admin_sitin.html', sitins=sitins)

@app.route('/admin/sitin/add', methods=['POST'])
@admin_required
def add_sitin():
    id_number  = request.form.get('id_number', '').strip()
    purpose    = request.form.get('purpose', '').strip()
    lab        = request.form.get('lab', '').strip()
    pc_number  = request.form.get('pc_number', '').strip()
    pc_status  = request.form.get('pc_status', 'Good').strip()
    conn       = get_db()
    user       = conn.execute('SELECT * FROM users WHERE id_number = ?', (id_number,)).fetchone()
    if user:
        remaining = user['remaining_session'] if user['remaining_session'] is not None else 30
        if remaining > 0:
            conn.execute('''
                INSERT INTO sitin (id_number, purpose, lab, session, pc_number, pc_status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (id_number, purpose, lab, remaining, pc_number, pc_status))
            conn.execute('UPDATE users SET remaining_session = remaining_session - 1 WHERE id_number = ?', (id_number,))
            conn.commit()
    conn.close()
    return redirect(url_for('admin_sitin'))

# ─── AWARD POINTS ON LOGOUT (modified) ────────────────────────────
@app.route('/admin/sitin/logout/<int:sitin_id>')
@admin_required
def sitin_logout(sitin_id):
    conn = get_db()
    sitin = conn.execute('SELECT * FROM sitin WHERE id = ?', (sitin_id,)).fetchone()
    if sitin:
        conn.execute("UPDATE sitin SET status='Done', time_out=? WHERE id=?",
                     (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sitin_id))
        # Award points (10 per completed session)
        points_awarded = 10
        student = conn.execute('SELECT points FROM users WHERE id_number = ?', (sitin['id_number'],)).fetchone()
        if student:
            new_points = student['points'] + points_awarded
            conn.execute('UPDATE users SET points = ? WHERE id_number = ?', (new_points, sitin['id_number']))
            conn.execute('INSERT INTO point_logs (student_id, points, action, remarks) VALUES (?, ?, ?, ?)',
                         (sitin['id_number'], points_awarded, 'add', 'Auto reward for completing sit-in session'))
        conn.commit()
    conn.close()
    return redirect(url_for('admin_sitin'))

# ─── ADMIN RECORDS ─────────────────────────────────────────────────
@app.route('/admin/records')
@admin_required
def admin_records():
    conn   = get_db()
    sitins = conn.execute('''
        SELECT s.*, u.firstname, u.lastname FROM sitin s
        JOIN users u ON s.id_number = u.id_number ORDER BY s.date DESC
    ''').fetchall()
    conn.close()
    return render_template('admin_records.html', sitins=sitins)

@app.route('/admin/records/delete/<int:sitin_id>')
@admin_required
def delete_record(sitin_id):
    conn = get_db()
    conn.execute('DELETE FROM sitin WHERE id = ?', (sitin_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_records'))

# ─── ADMIN REPORTS ─────────────────────────────────────────────────
@app.route('/admin/reports')
@admin_required
def admin_reports():
    conn   = get_db()
    sitins = conn.execute('''
        SELECT s.*, u.firstname, u.lastname FROM sitin s
        JOIN users u ON s.id_number = u.id_number ORDER BY s.date DESC
    ''').fetchall()
    conn.close()
    return render_template('admin_reports.html', sitins=sitins)

@app.route('/admin/reports/delete/<int:sitin_id>')
@admin_required
def delete_report(sitin_id):
    conn = get_db()
    conn.execute('DELETE FROM sitin WHERE id = ?', (sitin_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_reports'))

@app.route('/admin/reports/export/csv')
@admin_required
def export_csv():
    conn   = get_db()
    sitins = conn.execute('''
        SELECT s.id, s.id_number, u.firstname, u.lastname, s.purpose, s.lab,
               s.session, s.status, s.time_in, s.time_out, s.pc_number, s.pc_status
        FROM sitin s JOIN users u ON s.id_number = u.id_number ORDER BY s.date DESC
    ''').fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'ID Number', 'First Name', 'Last Name', 'Purpose', 'Lab',
                     'Session', 'Status', 'Time In', 'Time Out', 'PC Number', 'PC Status'])
    for s in sitins:
        writer.writerow([s['id'], s['id_number'], s['firstname'], s['lastname'],
                         s['purpose'], s['lab'], s['session'], s['status'],
                         s['time_in'], s['time_out'], s['pc_number'], s['pc_status']])
    output.seek(0)
    return Response(output, mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=sitin_report.csv'})

# ─── ADMIN GENERATE REPORTS (filtered) ─────────────────────────────
@app.route('/admin/generate_reports')
@admin_required
def admin_generate_reports():
    conn = get_db()
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')
    lab = request.args.get('lab', '')
    status = request.args.get('status', '')
    query = '''
        SELECT s.*, u.firstname, u.lastname FROM sitin s
        JOIN users u ON s.id_number = u.id_number
        WHERE 1=1
    '''
    params = []
    if from_date:
        query += ' AND DATE(s.date) >= ?'
        params.append(from_date)
    if to_date:
        query += ' AND DATE(s.date) <= ?'
        params.append(to_date)
    if lab:
        query += ' AND s.lab = ?'
        params.append(lab)
    if status:
        query += ' AND s.status = ?'
        params.append(status)
    query += ' ORDER BY s.date DESC'
    records = conn.execute(query, params).fetchall()
    labs = conn.execute('SELECT DISTINCT lab FROM sitin').fetchall()
    labs = [l['lab'] for l in labs]
    conn.close()
    return render_template('admin_generate_reports.html',
                           records=records, labs=labs,
                           from_date=from_date, to_date=to_date,
                           selected_lab=lab, status=status)

@app.route('/admin/reports/export/csv_filtered')
@admin_required
def export_csv_filtered():
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')
    lab = request.args.get('lab', '')
    status = request.args.get('status', '')
    conn = get_db()
    query = '''
        SELECT s.id, s.id_number, u.firstname, u.lastname, s.purpose, s.lab,
               s.session, s.status, s.time_in, s.time_out, s.pc_number, s.pc_status
        FROM sitin s JOIN users u ON s.id_number = u.id_number
        WHERE 1=1
    '''
    params = []
    if from_date:
        query += ' AND DATE(s.date) >= ?'
        params.append(from_date)
    if to_date:
        query += ' AND DATE(s.date) <= ?'
        params.append(to_date)
    if lab:
        query += ' AND s.lab = ?'
        params.append(lab)
    if status:
        query += ' AND s.status = ?'
        params.append(status)
    query += ' ORDER BY s.date DESC'
    sitins = conn.execute(query, params).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'ID Number', 'First Name', 'Last Name', 'Purpose', 'Lab',
                     'Session', 'Status', 'Time In', 'Time Out', 'PC Number', 'PC Status'])
    for s in sitins:
        writer.writerow([s['id'], s['id_number'], s['firstname'], s['lastname'],
                         s['purpose'], s['lab'], s['session'], s['status'],
                         s['time_in'], s['time_out'], s['pc_number'], s['pc_status']])
    output.seek(0)
    return Response(output, mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=filtered_sitin_report.csv'})

# ─── ADMIN ANALYTICS ───────────────────────────────────────────────
@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    conn = get_db()
    top_purpose  = conn.execute("SELECT purpose, COUNT(*) as count FROM sitin GROUP BY purpose ORDER BY count DESC LIMIT 5").fetchall()
    top_lab      = conn.execute("SELECT lab, COUNT(*) as count FROM sitin GROUP BY lab ORDER BY count DESC LIMIT 5").fetchall()
    daily        = conn.execute("SELECT DATE(date) as day, COUNT(*) as count FROM sitin GROUP BY DATE(date) ORDER BY day DESC LIMIT 7").fetchall()
    top_students = conn.execute('''
        SELECT s.id_number, u.firstname, u.lastname, COUNT(*) as count
        FROM sitin s JOIN users u ON s.id_number = u.id_number
        GROUP BY s.id_number ORDER BY count DESC LIMIT 5
    ''').fetchall()
    conn.close()
    return render_template('admin_analytics.html',
        top_purpose=top_purpose, top_lab=top_lab,
        daily=daily, top_students=top_students)

# ─── ADMIN FEEDBACK ────────────────────────────────────────────────
@app.route('/admin/feedback')
@admin_required
def admin_feedback():
    conn      = get_db()
    feedbacks = conn.execute('''
        SELECT f.*, u.firstname, u.lastname FROM feedback f
        JOIN users u ON f.id_number = u.id_number ORDER BY f.date DESC
    ''').fetchall()
    conn.close()
    return render_template('admin_feedback.html', feedbacks=feedbacks)

@app.route('/admin/feedback/delete/<int:feedback_id>')
@admin_required
def delete_feedback(feedback_id):
    conn = get_db()
    conn.execute('DELETE FROM feedback WHERE id = ?', (feedback_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_feedback'))

# ─── ADMIN TESTIMONIALS ────────────────────────────────────────────
@app.route('/admin/testimonials')
@admin_required
def admin_testimonials():
    conn         = get_db()
    testimonials = conn.execute('''
        SELECT t.*, u.firstname, u.lastname FROM testimonials t
        JOIN users u ON t.id_number = u.id_number ORDER BY t.date DESC
    ''').fetchall()
    avg_rating = conn.execute('SELECT AVG(rating) FROM testimonials').fetchone()[0]
    conn.close()
    return render_template('admin_testimonials.html',
        testimonials=testimonials,
        avg_rating=round(avg_rating, 1) if avg_rating else 0)

@app.route('/admin/testimonials/delete/<int:t_id>')
@admin_required
def delete_testimonial(t_id):
    conn = get_db()
    conn.execute('DELETE FROM testimonials WHERE id = ?', (t_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_testimonials'))

# ─── ADMIN RESERVATION ─────────────────────────────────────────────
@app.route('/admin/reservation')
@admin_required
def admin_reservation():
    conn         = get_db()
    reservations = conn.execute('''
        SELECT r.*, u.firstname, u.lastname FROM reservation r
        JOIN users u ON r.id_number = u.id_number ORDER BY r.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin_reservation.html', reservations=reservations)

@app.route('/admin/reservation/approve/<int:res_id>')
@admin_required
def approve_reservation(res_id):
    conn = get_db()
    res  = conn.execute('SELECT * FROM reservation WHERE id = ?', (res_id,)).fetchone()
    if res:
        conn.execute("UPDATE reservation SET status='Approved' WHERE id=?", (res_id,))
        conn.execute("UPDATE admin_notifications SET is_read=1 WHERE reservation_id=?", (res_id,))
        user = conn.execute('SELECT * FROM users WHERE id_number=?', (res['id_number'],)).fetchone()
        if user:
            remaining = user['remaining_session'] if user['remaining_session'] is not None else 30
            conn.execute('''
                INSERT INTO sitin (id_number, purpose, lab, session, time_in, pc_number)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (res['id_number'], res['purpose'], res['lab'], remaining,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), res['pc_number']))
            conn.execute('UPDATE users SET remaining_session=remaining_session-1 WHERE id_number=?',
                         (res['id_number'],))
        conn.commit()
    conn.close()
    return redirect(url_for('admin_reservation'))

@app.route('/admin/reservation/reject/<int:res_id>')
@admin_required
def reject_reservation(res_id):
    conn = get_db()
    conn.execute("UPDATE reservation SET status='Rejected' WHERE id=?", (res_id,))
    conn.execute("UPDATE admin_notifications SET is_read=1 WHERE reservation_id=?", (res_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_reservation'))

@app.route('/admin/reservation/delete/<int:res_id>')
@admin_required
def delete_reservation(res_id):
    conn = get_db()
    conn.execute('DELETE FROM reservation WHERE id=?', (res_id,))
    conn.execute('DELETE FROM admin_notifications WHERE reservation_id=?', (res_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_reservation'))

# ─── ADMIN LAB SETTINGS ────────────────────────────────────────────
@app.route('/admin/lab_settings')
@admin_required
def admin_lab_settings():
    conn     = get_db()
    settings = conn.execute('SELECT * FROM lab_settings ORDER BY lab').fetchall()
    software = conn.execute('SELECT * FROM software ORDER BY lab, name').fetchall()
    conn.close()
    return render_template('admin_lab_settings.html', settings=settings, software=software)

@app.route('/admin/lab_settings/toggle/<lab>')
@admin_required
def toggle_lab(lab):
    conn    = get_db()
    current = conn.execute('SELECT reservation_enabled FROM lab_settings WHERE lab=?', (lab,)).fetchone()
    if current:
        new_val = 0 if current['reservation_enabled'] == 1 else 1
        conn.execute('UPDATE lab_settings SET reservation_enabled=? WHERE lab=?', (new_val, lab))
        conn.commit()
    conn.close()
    return redirect(url_for('admin_lab_settings'))

@app.route('/admin/software/add', methods=['POST'])
@admin_required
def add_software():
    lab         = request.form.get('lab', '').strip()
    name        = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    if lab and name:
        conn = get_db()
        conn.execute('INSERT INTO software (lab, name, description) VALUES (?, ?, ?)',
                     (lab, name, description))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_lab_settings'))

@app.route('/admin/software/delete/<int:sw_id>')
@admin_required
def delete_software(sw_id):
    conn = get_db()
    conn.execute('DELETE FROM software WHERE id=?', (sw_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_lab_settings'))

# ─── ADMIN ANNOUNCEMENTS ───────────────────────────────────────────
@app.route('/admin/announce', methods=['POST'])
@admin_required
def add_announcement():
    content = request.form.get('content', '').strip()
    if content:
        conn = get_db()
        conn.execute('INSERT INTO announcements (content) VALUES (?)', (content,))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_dashboard'))

# ─── ADMIN NOTIFICATIONS (API) ─────────────────────────────────────
@app.route('/admin/notifications/count')
@admin_required
def admin_notifications_count():
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) FROM admin_notifications WHERE is_read = 0').fetchone()[0]
    conn.close()
    return jsonify({'count': count})

@app.route('/admin/notifications/list')
@admin_required
def admin_notifications_list():
    conn = get_db()
    notifs = conn.execute('SELECT * FROM admin_notifications ORDER BY created_at DESC LIMIT 20').fetchall()
    conn.close()
    return jsonify([dict(n) for n in notifs])

@app.route('/admin/notifications/mark_read/<int:notif_id>', methods=['POST'])
@admin_required
def mark_notification_read(notif_id):
    conn = get_db()
    conn.execute('UPDATE admin_notifications SET is_read = 1 WHERE id = ?', (notif_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/notifications/mark_all_read', methods=['POST'])
@admin_required
def mark_all_notifications_read():
    conn = get_db()
    conn.execute('UPDATE admin_notifications SET is_read = 1')
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ─── GET STUDENT INFO (AJAX) ───────────────────────────────────────
@app.route('/admin/get_student/<id_number>')
@admin_required
def get_student(id_number):
    conn    = get_db()
    student = conn.execute('SELECT * FROM users WHERE id_number=?', (id_number,)).fetchone()
    conn.close()
    if student:
        remaining = student['remaining_session'] if student['remaining_session'] is not None else 30
        return jsonify({
            'found': True,
            'name': f"{student['firstname']} {student['middlename'] or ''} {student['lastname']}".strip(),
            'remaining_session': remaining
        })
    return jsonify({'found': False})

# ─── LEADERBOARD API ───────────────────────────────────────────────
@app.route('/api/leaderboard')
def api_leaderboard():
    conn = get_db()
    leaderboard = conn.execute('''
        SELECT id_number, firstname, lastname, course,
               (SELECT COUNT(*) FROM sitin WHERE sitin.id_number = users.id_number AND status = 'Done') as total_sessions,
               points,
               RANK() OVER (ORDER BY points DESC) as rank
        FROM users
        WHERE points > 0 OR (SELECT COUNT(*) FROM sitin WHERE sitin.id_number = users.id_number) > 0
        ORDER BY points DESC
        LIMIT 100
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in leaderboard])

# ─── ADMIN REWARDS MANAGEMENT ──────────────────────────────────────
@app.route('/admin/rewards')
@admin_required
def admin_rewards():
    conn = get_db()
    students = conn.execute('SELECT id_number, firstname, lastname, course, points, converted_sessions FROM users ORDER BY points DESC').fetchall()
    point_logs = conn.execute('''
        SELECT l.*, u.firstname, u.lastname
        FROM point_logs l JOIN users u ON l.student_id = u.id_number
        ORDER BY l.date_created DESC LIMIT 50
    ''').fetchall()
    conn.close()
    return render_template('admin_rewards.html', students=students, point_logs=point_logs)

@app.route('/admin/adjust_points', methods=['POST'])
@admin_required
def adjust_points():
    student_id = request.form.get('student_id')
    points = request.form.get('points', type=int)
    action = request.form.get('action')
    remarks = request.form.get('remarks', '')
    if not student_id or not points or points <= 0:
        return jsonify({'error': 'Invalid input'}), 400
    conn = get_db()
    student = conn.execute('SELECT points FROM users WHERE id_number = ?', (student_id,)).fetchone()
    if not student:
        conn.close()
        return jsonify({'error': 'Student not found'}), 404
    new_points = student['points'] + points if action == 'add' else student['points'] - points
    if new_points < 0:
        conn.close()
        return jsonify({'error': 'Points cannot be negative'}), 400
    conn.execute('UPDATE users SET points = ? WHERE id_number = ?', (new_points, student_id))
    conn.execute('INSERT INTO point_logs (student_id, points, action, remarks) VALUES (?, ?, ?, ?)',
                 (student_id, points if action == 'add' else -points, action, remarks))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'new_points': new_points})

# ─── STUDENT CONVERT POINTS ────────────────────────────────────────
@app.route('/student/convert_points', methods=['POST'])
@login_required
def convert_points():
    points_to_convert = request.form.get('points', type=int)
    CONVERSION_RATE = 100
    if not points_to_convert or points_to_convert < CONVERSION_RATE:
        return jsonify({'error': f'Minimum {CONVERSION_RATE} points required.'}), 400
    conn = get_db()
    id_number = session.get('id_number')
    user = conn.execute('SELECT points, remaining_session FROM users WHERE id_number = ?', (id_number,)).fetchone()
    if not user or user['points'] < points_to_convert:
        conn.close()
        return jsonify({'error': 'Insufficient points.'}), 400
    sessions_gained = points_to_convert // CONVERSION_RATE
    new_points = user['points'] - points_to_convert
    new_sessions = user['remaining_session'] + sessions_gained
    conn.execute('UPDATE users SET points = ?, remaining_session = ?, converted_sessions = converted_sessions + ? WHERE id_number = ?',
                 (new_points, new_sessions, sessions_gained, id_number))
    conn.execute('INSERT INTO point_logs (student_id, points, action, remarks) VALUES (?, ?, ?, ?)',
                 (id_number, -points_to_convert, 'convert', f'Converted {points_to_convert} points to {sessions_gained} session(s)'))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'new_points': new_points, 'new_sessions': new_sessions, 'sessions_gained': sessions_gained})

# ─── LOGOUT ────────────────────────────────────────────────────────
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ─── RUN ───────────────────────────────────────────────────────────
def open_browser():
    import time
    time.sleep(1.5)
    webbrowser.open_new('http://127.0.0.1:5000')

if __name__ == '__main__':
    init_db()
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        threading.Thread(target=open_browser).start()
    app.run(debug=True)