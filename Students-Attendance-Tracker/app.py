from flask import (
    Flask, render_template, request, jsonify, g,
    session, redirect, url_for, flash, Response
)
import sqlite3
import os
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import io
import csv

APP_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(APP_DIR, "attendance.db")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-super-secret-key-change-this'

# ---------- DB helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    db = get_db()
    db.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, roll_no TEXT UNIQUE NOT NULL, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY, date TEXT NOT NULL, subject_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
            status TEXT CHECK(status IN ('Present','Absent Informed','Absent Uninformed')) NOT NULL,
            UNIQUE(date, subject_id, student_id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()

# ---------- Auth Decorator ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Auth Routes ----------
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('home'))
        flash('Invalid username or password.')
    return render_template('login.html', page='login')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        db = get_db()
        if db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
            flash(f'User {username} is already registered.', 'error')
        else:
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, generate_password_hash(password)))
            db.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', page='register')

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------- Pages ----------
@app.route("/")
@login_required
def home():
    return render_template("home.html", page="home")

@app.route("/store")
@login_required
def store():
    return render_template("store.html", page="store")

@app.route("/view")
@login_required
def view():
    return render_template("view.html", page="view")

@app.route("/individual")
@login_required
def individual():
    return render_template("individual.html", page="individual")

@app.route("/class_report")
@login_required
def class_report():
    return render_template("class_report.html", page="class_report")

@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html", page="admin")

# ---------- CRUD Routes ----------
@app.route("/manage_students")
@login_required
def manage_students():
    students = get_db().execute('SELECT * FROM students ORDER BY name').fetchall()
    return render_template("manage_students.html", students=students, page="manage_students")

@app.route("/add_student", methods=['POST'])
@login_required
def add_student():
    roll_no, name = request.form['roll_no'], request.form['name']
    db = get_db()
    try:
        db.execute('INSERT INTO students (roll_no, name) VALUES (?, ?)', (roll_no, name))
        db.commit()
        flash('Student added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Error: Roll number "{roll_no}" already exists.', 'error')
    return redirect(url_for('manage_students'))

@app.route("/edit_student/<int:student_id>", methods=['POST'])
@login_required
def edit_student(student_id):
    roll_no, name = request.form['roll_no'], request.form['name']
    db = get_db()
    try:
        db.execute('UPDATE students SET roll_no = ?, name = ? WHERE id = ?', (roll_no, name, student_id))
        db.commit()
        flash('Student updated successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Error: Roll number "{roll_no}" already exists.', 'error')
    return redirect(url_for('manage_students'))

@app.route("/delete_student/<int:student_id>", methods=['POST'])
@login_required
def delete_student(student_id):
    db = get_db()
    db.execute('DELETE FROM students WHERE id = ?', (student_id,))
    db.commit()
    flash('Student and all associated records deleted.', 'success')
    return redirect(url_for('manage_students'))

@app.route("/manage_subjects")
@login_required
def manage_subjects():
    subjects = get_db().execute('SELECT * FROM subjects ORDER BY name').fetchall()
    return render_template("manage_subjects.html", subjects=subjects, page="manage_subjects")

@app.route("/add_subject", methods=['POST'])
@login_required
def add_subject():
    name = request.form['name']
    db = get_db()
    try:
        db.execute('INSERT INTO subjects (name) VALUES (?)', (name,))
        db.commit()
        flash('Subject added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Error: Subject "{name}" already exists.', 'error')
    return redirect(url_for('manage_subjects'))

@app.route("/edit_subject/<int:subject_id>", methods=['POST'])
@login_required
def edit_subject(subject_id):
    name = request.form['name']
    db = get_db()
    try:
        db.execute('UPDATE subjects SET name = ? WHERE id = ?', (name, subject_id))
        db.commit()
        flash('Subject updated successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Error: Subject "{name}" already exists.', 'error')
    return redirect(url_for('manage_subjects'))

@app.route("/delete_subject/<int:subject_id>", methods=['POST'])
@login_required
def delete_subject(subject_id):
    db = get_db()
    db.execute('DELETE FROM subjects WHERE id = ?', (subject_id,))
    db.commit()
    flash('Subject and all associated records deleted.', 'success')
    return redirect(url_for('manage_subjects'))

# ---------- APIs ----------
@app.route("/api/class_report")
@login_required
def api_class_report():
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    subject_id = request.args.get("subject_id")

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Invalid date format. Please use YYYY-MM-DD."}), 400

    db = get_db()
    
    # --- NEW LOGIC ---
    # 1. First, find the true total number of classes held in the date range.
    total_classes_query = "SELECT COUNT(DISTINCT date) as count FROM attendance WHERE date BETWEEN ? AND ?"
    params_total = [start_date, end_date]
    if subject_id:
        total_classes_query += " AND subject_id = ?"
        params_total.append(subject_id)
    
    total_classes_result = db.execute(total_classes_query, params_total).fetchone()
    total_classes = total_classes_result['count'] if total_classes_result else 0

    if total_classes == 0:
        return jsonify({"ok": True, "records": []})

    # 2. Then, get each student and count their 'Present' records in that range.
    student_report_query = """
    SELECT
        s.id,
        s.roll_no,
        s.name,
        SUM(CASE WHEN a.status = 'Present' AND a.date BETWEEN ? AND ? {} THEN 1 ELSE 0 END) as present_count
    FROM
        students s
    LEFT JOIN
        attendance a ON s.id = a.student_id
    GROUP BY
        s.id, s.roll_no, s.name
    ORDER BY
        s.name
    """.format("AND a.subject_id = ?" if subject_id else "")
    
    params_students = [start_date, end_date]
    if subject_id:
        params_students.append(subject_id)

    student_records = db.execute(student_report_query, params_students).fetchall()

    # 3. Combine the results.
    final_records = []
    for record in student_records:
        final_records.append({
            "roll_no": record["roll_no"],
            "name": record["name"],
            "present_count": record["present_count"] or 0,
            "total_classes": total_classes
        })

    return jsonify({"ok": True, "records": final_records})

@app.route("/api/subjects")
@login_required
def api_subjects():
    rows = get_db().execute("SELECT id, name FROM subjects ORDER BY name").fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/students")
@login_required
def api_students():
    rows = get_db().execute("SELECT id, roll_no, name FROM students ORDER BY name").fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/save_attendance", methods=["POST"])
@login_required
def api_save_attendance():
    data = request.get_json(force=True)
    date, subject_id, marks = data.get("date"), data.get("subject_id"), data.get("marks", [])
    db = get_db()
    for m in marks:
        sid, status = m.get("student_id"), m.get("status")
        db.execute("INSERT INTO attendance(date, subject_id, student_id, status) VALUES(?,?,?,?) ON CONFLICT(date, subject_id, student_id) DO UPDATE SET status=excluded.status", (date, subject_id, sid, status))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/get_attendance")
@login_required
def api_get_attendance():
    subject_id, date = request.args.get("subject_id", type=int), request.args.get("date", type=str)
    rows = get_db().execute("SELECT st.roll_no, st.name, COALESCE(a.status,'Absent Uninformed') AS status FROM students st LEFT JOIN attendance a ON a.student_id = st.id AND a.subject_id = ? AND a.date = ? ORDER BY st.name", (subject_id, date)).fetchall()
    return jsonify({"ok": True, "records": [dict(r) for r in rows]})

@app.route("/api/get_attendance_for_store")
@login_required
def api_get_attendance_for_store():
    subject_id, date = request.args.get("subject_id", type=int), request.args.get("date", type=str)
    rows = get_db().execute("SELECT st.id as student_id, COALESCE(a.status, 'none') AS status FROM students st LEFT JOIN attendance a ON a.student_id = st.id AND a.subject_id = ? AND a.date = ?", (subject_id, date)).fetchall()
    return jsonify({"ok": True, "records": [dict(r) for r in rows]})

@app.route("/api/student_report")
@login_required
def api_student_report():
    q = (request.args.get("query") or "").strip()
    subject_id, date_type, year, month, date = request.args.get("subject_id"), request.args.get("dateType"), request.args.get("year"), request.args.get("month"), request.args.get("date")
    db = get_db()
    stu = db.execute("SELECT * FROM students WHERE roll_no LIKE ? OR name LIKE ? ORDER BY name LIMIT 1", (f"%{q}%", f"%{q}%")).fetchone()
    if not stu:
        return jsonify({"ok": True, "student": None, "rows": []})
    conditions, params = ["a.student_id = ?"], [stu["id"]]
    if subject_id: conditions.append("a.subject_id = ?"); params.append(subject_id)
    if date_type == "year" and year: conditions.append("substr(a.date,7,4) = ?"); params.append(year)
    if date_type == "month" and month: conditions.append("substr(a.date,4,2) = ?"); params.append(month.zfill(2))
    if date_type == "date" and date:
        dmy = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
        conditions.append("a.date = ?"); params.append(dmy)
    query = f"SELECT a.date, s.name AS subject, a.status FROM attendance a JOIN subjects s ON s.id = a.subject_id WHERE {' AND '.join(conditions)} ORDER BY substr(a.date,7,4)||'-'||substr(a.date,4,2)||'-'||substr(a.date,1,2) ASC, s.name ASC"
    rows = db.execute(query, params).fetchall()
    days_present = sum(1 for row in rows if row['status'] == 'Present')
    return jsonify({"ok": True, "student": {"id": stu["id"], "roll_no": stu["roll_no"], "name": stu["name"]}, "rows": [dict(r) for r in rows], "days_present": days_present})

# ---------- EXPORT ROUTES ----------
@app.route('/export/class_report')
@login_required
def export_class_report():
    start_date_str, end_date_str, subject_id = request.args.get("start_date"), request.args.get("end_date"), request.args.get("subject_id")
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    db = get_db()
    
    # Re-using the corrected logic for export as well
    total_classes_query = "SELECT COUNT(DISTINCT date) as count FROM attendance WHERE date BETWEEN ? AND ?"
    params_total = [start_date, end_date]
    if subject_id:
        total_classes_query += " AND subject_id = ?"
        params_total.append(subject_id)
    total_classes_result = db.execute(total_classes_query, params_total).fetchone()
    total_classes = total_classes_result['count'] if total_classes_result else 0
    
    student_report_query = "SELECT s.roll_no, s.name, SUM(CASE WHEN a.status = 'Present' AND a.date BETWEEN ? AND ? {} THEN 1 ELSE 0 END) as present_count FROM students s LEFT JOIN attendance a ON s.id = a.student_id GROUP BY s.id ORDER BY s.name".format("AND a.subject_id = ?" if subject_id else "")
    params_students = [start_date, end_date]
    if subject_id:
        params_students.append(subject_id)
    records = db.execute(student_report_query, params_students).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Roll No', 'Name', 'Classes Attended', 'Total Classes', 'Percentage'])
    for row in records:
        present_count = row['present_count'] or 0
        percentage = (present_count / total_classes * 100) if total_classes > 0 else 0
        writer.writerow([row['roll_no'], row['name'], present_count, total_classes, f"{percentage:.2f}%"])
    
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=class_report.csv"})

@app.route('/export/individual_report')
@login_required
def export_individual_report():
    q = (request.args.get("query") or "").strip()
    db = get_db()
    stu = db.execute("SELECT * FROM students WHERE roll_no LIKE ? OR name LIKE ? ORDER BY name LIMIT 1", (f"%{q}%", f"%{q}%")).fetchone()
    if not stu: return "Student not found", 404
    subject_id, date_type, year, month, date = request.args.get("subject_id"), request.args.get("dateType"), request.args.get("year"), request.args.get("month"), request.args.get("date")
    conditions, params = ["a.student_id = ?"], [stu["id"]]
    if subject_id: conditions.append("a.subject_id = ?"); params.append(subject_id)
    if date_type == "year" and year: conditions.append("substr(a.date,7,4) = ?"); params.append(year)
    if date_type == "month" and month: conditions.append("substr(a.date,4,2) = ?"); params.append(month.zfill(2))
    if date_type == "date" and date:
        dmy = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
        conditions.append("a.date = ?"); params.append(dmy)
    query = f"SELECT a.date, s.name AS subject, a.status FROM attendance a JOIN subjects s ON s.id = a.subject_id WHERE {' AND '.join(conditions)} ORDER BY substr(a.date,7,4)||'-'||substr(a.date,4,2)||'-'||substr(a.date,1,2) ASC, s.name ASC"
    rows = db.execute(query, params).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Subject', 'Status'])
    for row in rows:
        writer.writerow([row['date'], row['subject'], row['status']])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":f"attachment;filename=report_{stu['roll_no']}.csv"})

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)