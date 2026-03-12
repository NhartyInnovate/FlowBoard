import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "super-secret-key"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "tasks.db")

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ---------------- MODELS ----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    tasks = db.relationship("Task", backref="owner", lazy=True)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    due_date = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="To Do")
    archived = db.Column(db.Boolean, default=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------- PUBLIC ROUTES ----------------
@app.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name").strip()
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered. Please log in.")
            return redirect(url_for("login"))

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256", salt_length=8)

        new_user = User(
            name=name,
            email=email,
            password_hash=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash("Account created successfully.")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if not user:
            flash("No account found with that email.")
            return redirect(url_for("login"))

        if not check_password_hash(user.password_hash, password):
            flash("Incorrect password.")
            return redirect(url_for("login"))

        login_user(user)
        flash(f"Welcome back, {user.name}.")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.")
    return redirect(url_for("landing"))


# ---------------- TASK ROUTES ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    todo_tasks = Task.query.filter_by(user_id=current_user.id, status="To Do", archived=False).all()
    doing_tasks = Task.query.filter_by(user_id=current_user.id, status="Doing", archived=False).all()
    done_tasks = Task.query.filter_by(user_id=current_user.id, status="Done", archived=False).all()

    return render_template(
        "index.html",
        todo_tasks=todo_tasks,
        doing_tasks=doing_tasks,
        done_tasks=done_tasks
    )


@app.route("/history")
@login_required
def history():
    archived_tasks = Task.query.filter_by(user_id=current_user.id, archived=True).order_by(Task.id.desc()).all()
    return render_template("history.html", archived_tasks=archived_tasks)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_task():
    if request.method == "POST":
        new_task = Task(
            title=request.form.get("title"),
            description=request.form.get("description"),
            priority=request.form.get("priority"),
            due_date=request.form.get("due_date"),
            status=request.form.get("status"),
            archived=False,
            user_id=current_user.id
        )
        db.session.add(new_task)
        db.session.commit()
        flash("Task added successfully.")
        return redirect(url_for("dashboard"))

    return render_template("add_task.html")


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        task.title = request.form.get("title")
        task.description = request.form.get("description")
        task.priority = request.form.get("priority")
        task.due_date = request.form.get("due_date")
        task.status = request.form.get("status")

        db.session.commit()
        flash("Task updated successfully.")
        return redirect(url_for("dashboard"))

    return render_template("edit_task.html", task=task)


@app.route("/delete/<int:task_id>")
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted successfully.")
    return redirect(url_for("dashboard"))


@app.route("/move/<int:task_id>/<new_status>")
@login_required
def move_task(task_id, new_status):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if new_status in ["To Do", "Doing", "Done"]:
        task.status = new_status
        db.session.commit()
        flash("Task moved successfully.")

    return redirect(url_for("dashboard"))


@app.route("/archive/<int:task_id>")
@login_required
def archive_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if task.status == "Done":
        task.archived = True
        db.session.commit()
        flash("Task archived successfully.")
    else:
        flash("Only completed tasks can be archived.")

    return redirect(url_for("dashboard"))


@app.route("/restore/<int:task_id>")
@login_required
def restore_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id, archived=True).first_or_404()
    task.archived = False
    task.status = "Done"
    db.session.commit()
    flash("Task restored to Done column.")
    return redirect(url_for("history"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)