from flask import Flask, render_template, request, redirect, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret123"  # change this in production

DB = "database/db.sqlite3"

# Ensure database folder exists
def get_db():
    os.makedirs("database", exist_ok=True)
    return sqlite3.connect(DB)

# Initialize database
def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # Transactions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL,
        category TEXT,
        type TEXT,
        date TEXT,
        user_id INTEGER
    )
    """)

    # Budget table (per user would be better later)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS budget (
        id INTEGER PRIMARY KEY,
        total REAL
    )
    """)

    conn.commit()
    conn.close()

# 🔐 LOGIN + SIGNUP PAGE
@app.route("/", methods=["GET", "POST"])
def login():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        action = request.form["action"]
        username = request.form["username"]
        password = request.form["password"]

        if action == "signup":
            try:
                cur.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, password)
                )
                conn.commit()
            except:
                return "User already exists"

        elif action == "login":
            cur.execute(
                "SELECT * FROM users WHERE username=? AND password=?",
                (username, password)
            )
            user = cur.fetchone()

            if user:
                session["user_id"] = user[0]
                session["username"] = user[1]
                return redirect("/home")
            else:
                return "Invalid login"

    conn.close()
    return render_template("login.html")

# 🏠 HOME PAGE
@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC",
        (session["user_id"],)
    )
    transactions = cur.fetchall()

    income = sum(t[1] for t in transactions if t[3] == "income")
    expenses = sum(t[1] for t in transactions if t[3] == "expense")
    remaining = income - expenses

    conn.close()

    return render_template(
        "index.html",
        username=session["username"],
        transactions=transactions,
        income=income,
        expenses=expenses,
        remaining=remaining
    )

# ➕ ADD TRANSACTION
@app.route("/add", methods=["POST"])
def add_transaction():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO transactions (amount, category, type, date, user_id) VALUES (?, ?, ?, ?, ?)",
        (
            float(request.form["amount"]),
            request.form["category"],
            request.form["type"],
            request.form["date"],
            session["user_id"]
        )
    )

    conn.commit()
    conn.close()

    return redirect("/home")

# 💰 BUDGET PAGE
@app.route("/budget", methods=["GET", "POST"])
def budget():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    # Handle new budget
    if request.method == "POST":
        amount = float(request.form["budget"])

        cur.execute("DELETE FROM budget")
        cur.execute("INSERT INTO budget (id, total) VALUES (1, ?)", (amount,))
        conn.commit()

        return redirect("/budget")

    # Get transactions
    cur.execute(
        "SELECT * FROM transactions WHERE user_id=?",
        (session["user_id"],)
    )
    transactions = cur.fetchall()

    income = sum(t[1] for t in transactions if t[3] == "income")
    expenses = sum(t[1] for t in transactions if t[3] == "expense")
    remaining = income - expenses

    # Get budget
    cur.execute("SELECT total FROM budget WHERE id=1")
    row = cur.fetchone()
    budget = row[0] if row else 0

    over_budget = expenses > budget

    conn.close()

    return render_template(
        "budget.html",
        username=session["username"],
        budget=budget,
        expenses=expenses,
        remaining=remaining,
        over_budget=over_budget
    )

# 📊 STATISTICS PAGE
@app.route("/statistics")
def statistics():
    if "user_id" not in session:
        return redirect("/")

    return render_template("statistics.html", username=session["username"])

# ⚙ SETTINGS PAGE
@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect("/")

    return render_template("settings.html", username=session["username"])

# 🔄 RESET USER DATA
@app.route("/reset", methods=["POST"])
def reset():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM transactions WHERE user_id=?", (session["user_id"],))
    cur.execute("DELETE FROM budget")

    conn.commit()
    conn.close()

    return redirect("/home")

# 🚪 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)