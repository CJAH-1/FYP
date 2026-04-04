from flask import Flask, render_template, request, redirect
import sqlite3
import os

app = Flask(__name__)

DB = "database/db.sqlite3"

# Ensure database folder exists
def get_db():
    os.makedirs("database", exist_ok=True)
    return sqlite3.connect(DB)

# Initialize database
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL,
        category TEXT,
        type TEXT,
        date TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS budget (
        id INTEGER PRIMARY KEY,
        total REAL
    )
    """)

    conn.commit()
    conn.close()

# 🔹 Home page (ONLY GET)
@app.route("/")
def index():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM transactions ORDER BY date DESC")
    transactions = cur.fetchall()

    # Calculate totals
    income = sum(t[1] for t in transactions if t[3] == "income")
    expenses = sum(t[1] for t in transactions if t[3] == "expense")

    # 🔥 FIX: budget NOT included in remaining
    remaining = income - expenses

    # Get budget (display only)
    cur.execute("SELECT total FROM budget WHERE id=1")
    row = cur.fetchone()
    budget = row[0] if row else 0

    # Group by category (expenses only)
    categories = {}
    for t in transactions:
        if t[3] == "expense":
            categories[t[2]] = categories.get(t[2], 0) + t[1]

    conn.close()

    return render_template(
        "index.html",
        transactions=transactions,
        income=income,
        expenses=expenses,
        budget=budget,
        remaining=remaining,
        categories=categories
    )

# 🔹 Add transaction
@app.route("/add", methods=["POST"])
def add_transaction():
    conn = get_db()
    cur = conn.cursor()

    amount = float(request.form["amount"])
    category = request.form["category"]
    t_type = request.form["type"]
    date = request.form["date"]

    cur.execute(
        "INSERT INTO transactions (amount, category, type, date) VALUES (?, ?, ?, ?)",
        (amount, category, t_type, date)
    )

    conn.commit()
    conn.close()

    return redirect("/")

# 🔹 Reset everything
@app.route("/reset", methods=["POST"])
def reset():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM transactions")
    cur.execute("DELETE FROM budget")

    conn.commit()
    conn.close()

    return redirect("/")

# 🔹 Set budget (display only)
@app.route("/set_budget", methods=["POST"])
def set_budget():
    amount = float(request.form["budget"])

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM budget")
    cur.execute("INSERT INTO budget (id, total) VALUES (1, ?)", (amount,))

    conn.commit()
    conn.close()

    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)