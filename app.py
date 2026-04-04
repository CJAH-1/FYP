from flask import Flask, render_template, request, redirect, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret123"  # change this later

DB = "database/db.sqlite3"

def get_db():
    os.makedirs("database", exist_ok=True)
    return sqlite3.connect(DB)

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

    # Transactions
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

    conn.commit()
    conn.close()

# 🔐 LOGIN / SIGNUP PAGE
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

# 🚪 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)