import os
import psycopg2
import psycopg2.extras
from datetime import datetime
from flask import (
    Flask,
    render_template,
    g,
    redirect,
    request,
    url_for,
    flash,
    abort,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = psycopg2.connect(os.environ.get("DATABASE_URL"))
        db.cursor_factory = psycopg2.extras.DictCursor
    return db


def get_unread_count(user_id: int) -> int:
    """Return count of unread messages for a user."""
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) AS c FROM messages WHERE receiver_id = %s AND is_read = 0",
        (user_id,),
    )
    row = cur.fetchone()
    return int(row["c"]) if row is not None else 0


def init_db():
    """Initialize database schema and seed demo data."""
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    c = conn.cursor()

    # Users table for authentication and profiles
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            education_level TEXT,
            role TEXT,
            skills TEXT,
            location TEXT,
            num_hackathons INTEGER,
            hackathon_role TEXT,
            project_links TEXT,
            profile_picture TEXT,
            headline TEXT
        )
        """
    )

    # Existing demo tables
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            year TEXT NOT NULL,
            major TEXT,
            skills TEXT
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            focus_area TEXT
        )
        """
    )

    # Messages table for real-time chat
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
             is_read INTEGER NOT NULL DEFAULT 0,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
        """
    )

    # Seed students table (legacy demo data) if empty
    c.execute("SELECT COUNT(*) FROM students")
    student_count = c.fetchone()[0]

    if student_count == 0:
        students = [
            (
                "Alex Chen",
                "1st year",
                "Data Science",
                "Python, pandas, Jupyter, Data Visualization",
            ),
            (
                "Maya Rodriguez",
                "1st year",
                "Biology",
                "Python, Molecular Biology, Lab Techniques",
            ),
            (
                "Samir Patel",
                "1st year",
                "Environmental Engineering",
                "Python, GIS, Data Cleaning, pandas",
            ),
            (
                "Jordan Lee",
                "1st year",
                "Computer Science",
                "Python, SQL, APIs, Basic Machine Learning",
            ),
        ]

        c.executemany(
            "INSERT INTO students (name, year, major, skills) VALUES (%s, %s, %s, %s)",
            students,
        )

    # Seed projects table if empty
    c.execute("SELECT COUNT(*) FROM projects")
    project_count = c.fetchone()[0]

    if project_count == 0:
        projects = [
            (
                "Campus Tree Carbon Storage Calculator",
                "Estimate how much carbon is stored in campus trees using simple field measurements and open data.",
                "Sustainability / Environmental Data",
            ),
            (
                "Real Estate Data Analyzer",
                "Build a small tool to explore housing prices, rent trends, and neighborhood features using public datasets.",
                "Urban Analytics / Real Estate",
            ),
            (
                "Park Watering Optimization Model",
                "Use historical weather and soil moisture data to recommend efficient watering schedules for local parks.",
                "Operations Research / Sustainability",
            ),
        ]

        c.executemany(
            "INSERT INTO projects (title, description, focus_area) VALUES (%s, %s, %s)",
            projects,
        )

    # Search history table for recommendation engine
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS search_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            search_term TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )

    # Seed users with realistic demo profiles if empty
    c.execute("SELECT COUNT(*) FROM users")
    user_count = c.fetchone()[0]

    if user_count == 0:
        demo_users = [
            (
                "Rasheed Khan",
                "rasheed@example.edu",
                generate_password_hash("password123"),
                "2nd year undergraduate",
                "Data",
                "Python, pandas, Data Analysis, SQL",
                "Bangalore",
                4,
                "Data Analysis",
                "https://github.com/rasheed-data/analytics-notebooks",
            ),
            (
                "Kaif Sharma",
                "kaif@example.edu",
                generate_password_hash("password123"),
                "1st year undergraduate",
                "Backend",
                "Python, FastAPI, PostgreSQL",
                "Hyderabad",
                2,
                "Backend",
                "https://github.com/kaif-backend/hackathon-apis",
            ),
            (
                "Maya Rodriguez",
                "maya@example.edu",
                generate_password_hash("password123"),
                "1st year undergraduate",
                "Research",
                "Molecular Biology, lab techniques, R basics",
                "Boston",
                1,
                "Wet lab / analysis",
                "https://example.com/maya-portfolio",
            ),
            (
                "Alex Chen",
                "alex@example.edu",
                generate_password_hash("password123"),
                "2nd year undergraduate",
                "Data",
                "Python, pandas, Data Visualization, machine learning",
                "Singapore",
                3,
                "Data / ML",
                "https://github.com/alex-chen/data-projects",
            ),
        ]

        c.executemany(
            """
            INSERT INTO users (
                name,
                email,
                password_hash,
                education_level,
                role,
                skills,
                location,
                num_hackathons,
                hackathon_role,
                project_links
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            demo_users,
        )

    conn.commit()
    conn.close()


class User(UserMixin):
    """Simple User model backed by the SQLite users table."""

    def __init__(self, id, name, email, password_hash):
        self.id = id
        self.name = name
        self.email = email
        self.password_hash = password_hash

    @staticmethod
    def get_by_id(user_id):
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT id, name, email, password_hash FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return User(row["id"], row["name"], row["email"], row["password_hash"])

    @staticmethod
    def get_by_email(email):
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return User(row["id"], row["name"], row["email"], row["password_hash"])

    @staticmethod
    def create(name, email, password):
        db = get_db()
        password_hash = generate_password_hash(password)
        cur = db.cursor()
        cur.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (name, email, password_hash),
        )
        new_id = cur.fetchone()["id"]
        db.commit()
        return User(new_id, name, email, password_hash)


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

socketio = SocketIO(app, cors_allowed_origins="*")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)


with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Database initialization failed: {e}")


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


@app.route("/")
def home():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM projects")
    projects = cur.fetchall()
    unread_count = get_unread_count(current_user.id) if current_user.is_authenticated else 0

    conversations = []
    if current_user.is_authenticated:
        conv_query = """
            SELECT
                u.id as other_user_id,
                u.name as other_user_name,
                u.location as other_user_location,
                u.role as other_user_role,
                MAX(m.timestamp) as last_msg_time,
                (SELECT COUNT(*) FROM messages m2 WHERE m2.sender_id = u.id AND m2.receiver_id = %s AND m2.is_read = 0) as unread
            FROM users u
            JOIN messages m ON (m.sender_id = u.id AND m.receiver_id = %s) OR (m.sender_id = %s AND m.receiver_id = u.id)
            GROUP BY u.id
            ORDER BY last_msg_time DESC
        """
        cur.execute(conv_query, (current_user.id, current_user.id, current_user.id))
        conversations = cur.fetchall()

    # Search parameters
    query_raw = request.args.get("query", "").strip()
    query = query_raw.lower()
    role_filter = request.args.get("role", "").strip()
    education_filter = request.args.get("education_level", "").strip()
    location_filter = request.args.get("location", "").strip()

    sql = """
        SELECT
            id,
            name,
            education_level,
            role,
            skills,
            location,
            num_hackathons
        FROM users
        WHERE 1=1
    """
    params = []

    if query:
        sql += " AND (LOWER(name) LIKE %s OR LOWER(skills) LIKE %s)"
        like_term = f"%{query}%"
        params.extend([like_term, like_term])

    if role_filter:
        sql += " AND role = %s"
        params.append(role_filter)

    if education_filter:
        sql += " AND education_level = %s"
        params.append(education_filter)

    if location_filter:
        sql += " AND location = %s"
        params.append(location_filter)

    # Basic recommendation tweak: hide the current user from their own feed.
    if current_user.is_authenticated:
        sql += " AND id != %s"
        params.append(current_user.id)

        # Persist search term into search_history to power future recommendations.
        if query_raw:
            ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            cur.execute(
                """
                INSERT INTO search_history (user_id, search_term, timestamp)
                VALUES (%s, %s, %s)
                """,
                (current_user.id, query_raw, ts),
            )
            db.commit()

    cur.execute(sql, params)
    users = cur.fetchall()

    return render_template(
        "index.html",
        projects=projects,
        users=users,
        query=query_raw,
        role_filter=role_filter,
        education_filter=education_filter,
        location_filter=location_filter,
        unread_count=unread_count,
        conversations=conversations,
    )



@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not name or not email or not password:
            flash("Full name, email, and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.get_by_email(email) is not None:
            flash("An account with that email already exists.", "error")
        else:
            user = User.create(name, email, password)
            login_user(user)
            flash("Registration successful. You are now logged in.", "success")
            return redirect(url_for("home"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.get_by_email(email)
        if user is None or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "error")
        else:
            login_user(user)
            flash("Logged in successfully.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("home"))

    return render_template("login.html")


@app.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()

    if request.method == "POST":
        education_level = request.form.get("education_level", "").strip()
        role = request.form.get("role", "").strip()
        skills = request.form.get("skills", "").strip()
        location = request.form.get("location", "").strip()
        num_hackathons_raw = request.form.get("num_hackathons", "").strip()
        hackathon_role = request.form.get("hackathon_role", "").strip()
        project_links = request.form.get("project_links", "").strip()
        headline = request.form.get("headline", "").strip()

        cur = db.cursor()
        cur.execute("SELECT profile_picture FROM users WHERE id = %s", (current_user.id,))
        current_pic_row = cur.fetchone()
        filename = current_pic_row["profile_picture"] if current_pic_row else None

        profile_picture = request.files.get("profile_picture")
        if profile_picture and profile_picture.filename:
            from werkzeug.utils import secure_filename
            new_filename = secure_filename(profile_picture.filename)
            upload_folder = os.path.join(app.root_path, "static", "uploads", "profile_pics")
            os.makedirs(upload_folder, exist_ok=True)
            profile_picture.save(os.path.join(upload_folder, new_filename))
            filename = new_filename

        num_hackathons = None
        if num_hackathons_raw:
            try:
                num_hackathons = int(num_hackathons_raw)
            except ValueError:
                num_hackathons = None

        cur.execute(
            """
            UPDATE users
            SET education_level = %s,
                role = %s,
                skills = %s,
                location = %s,
                num_hackathons = %s,
                hackathon_role = %s,
                project_links = %s,
                headline = %s,
                profile_picture = %s
            WHERE id = %s
            """,
            (
                education_level,
                role,
                skills,
                location,
                num_hackathons,
                hackathon_role,
                project_links,
                headline,
                filename,
                current_user.id,
            ),
        )
        db.commit()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("profile"))

    cur = db.cursor()
    cur.execute(
        """
        SELECT name,
               email,
               education_level,
               role,
               skills,
               location,
               num_hackathons,
               hackathon_role,
               project_links,
               headline,
               profile_picture
        FROM users
        WHERE id = %s
        """,
        (current_user.id,),
    )
    user_row = cur.fetchone()

    unread_count = get_unread_count(current_user.id)
    return render_template("profile.html", user=user_row, unread_count=unread_count)


@app.route("/user/<int:user_id>")
def user_profile(user_id):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT id,
               name,
               email,
               education_level,
               role,
               skills,
               location,
               num_hackathons,
               hackathon_role,
               project_links,
               headline,
               profile_picture
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    )
    user_row = cur.fetchone()

    if user_row is None:
        abort(404)

    return render_template("user_profile.html", user=user_row)


def _get_chat_room_id(user_a_id: int, user_b_id: int) -> str:
    """Stable room id for a pair of users."""
    low = min(user_a_id, user_b_id)
    high = max(user_a_id, user_b_id)
    return f"chat_{low}_{high}"


@app.route("/chat/<int:receiver_id>")
@login_required
def chat(receiver_id: int):
    db = get_db()

    # Prevent chatting with yourself via this route
    if receiver_id == current_user.id:
        return redirect(url_for("profile"))

    cur = db.cursor()
    cur.execute(
        "SELECT id, name FROM users WHERE id = %s", (receiver_id,)
    )
    other_user = cur.fetchone()
    if other_user is None:
        abort(404)

    room_id = _get_chat_room_id(current_user.id, receiver_id)

    # Mark messages from this user as read when opening the thread.
    cur.execute(
        """
        UPDATE messages
        SET is_read = 1
        WHERE receiver_id = %s AND sender_id = %s AND is_read = 0
        """,
        (current_user.id, receiver_id),
    )
    db.commit()

    cur.execute(
        """
        SELECT sender_id, receiver_id, message_text, timestamp
        FROM messages
        WHERE (sender_id = %s AND receiver_id = %s)
           OR (sender_id = %s AND receiver_id = %s)
        ORDER BY timestamp ASC
        """,
        (current_user.id, receiver_id, receiver_id, current_user.id),
    )
    messages = cur.fetchall()

    unread_count = get_unread_count(current_user.id)

    return render_template(
        "chat.html",
        room_id=room_id,
        other_user=other_user,
        messages=messages,
        current_user_id=current_user.id,
        unread_count=unread_count,
    )


@app.route("/api/chat/<int:receiver_id>")
@login_required
def api_chat(receiver_id: int):
    db = get_db()
    # Mark messages as read
    cur = db.cursor()
    cur.execute(
        """
        UPDATE messages
        SET is_read = 1
        WHERE receiver_id = %s AND sender_id = %s AND is_read = 0
        """,
        (current_user.id, receiver_id),
    )
    db.commit()

    cur.execute(
        """
        SELECT sender_id, receiver_id, message_text, timestamp
        FROM messages
        WHERE (sender_id = %s AND receiver_id = %s)
           OR (sender_id = %s AND receiver_id = %s)
        ORDER BY timestamp ASC
        """,
        (current_user.id, receiver_id, receiver_id, current_user.id),
    )
    messages = cur.fetchall()
    
    cur.execute("SELECT id, name, role FROM users WHERE id = %s", (receiver_id,))
    other_user = cur.fetchone()
    
    return {
        "messages": [dict(m) for m in messages],
        "other_user": dict(other_user) if other_user else None,
        "room_id": _get_chat_room_id(current_user.id, receiver_id),
        "current_user_id": current_user.id
    }


@socketio.on("join")
@login_required
def handle_join(data):
    room = data.get("room")
    if not room:
        return
    join_room(room)


@socketio.on("send_message")
@login_required
def handle_send_message(data):
    db = get_db()
    room = data.get("room")
    receiver_id = data.get("receiver_id")
    message_text = (data.get("message") or "").strip()

    if not room or not receiver_id or not message_text:
        return

    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO messages (sender_id, receiver_id, message_text, timestamp)
        VALUES (%s, %s, %s, %s)
        """,
        (current_user.id, int(receiver_id), message_text, timestamp),
    )
    db.commit()

    payload = {
        "sender_id": current_user.id,
        "sender_name": current_user.name,
        "receiver_id": int(receiver_id),
        "message": message_text,
        "timestamp": timestamp,
    }

    emit("receive_message", payload, room=room, include_self=False)


if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)

