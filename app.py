from flask import Flask, render_template, request, redirect, session
import sqlite3, os
from datetime import timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"
app.permanent_session_lifetime = timedelta(minutes=15)

DB = "database/db.sqlite3"

def get_db():
    os.makedirs("database", exist_ok=True)
    return sqlite3.connect(DB)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        amount REAL,
        category TEXT,
        type TEXT,
        date TEXT,
        user_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS budget (
        id INTEGER PRIMARY KEY,
        total REAL,
        user_id INTEGER
    )
    """)

    conn.commit()
    conn.close()

# LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        action = request.form["action"]
        username = request.form["username"]
        password = request.form["password"]

        if action == "signup":
            email = request.form["email"]

            if len(password) < 6:
                return render_template("login.html", error="Password too short")

            try:
                cur.execute(
                    "INSERT INTO users VALUES (NULL, ?, ?, ?)",
                    (username, email, generate_password_hash(password))
                )
                conn.commit()
                return render_template("login.html", success="Account created")
            except:
                return render_template("login.html", error="User exists")

        if action == "login":
            cur.execute(
                "SELECT * FROM users WHERE username=? OR email=?",
                (username, username)
            )
            user = cur.fetchone()

            if user and check_password_hash(user[3], password):
                session.permanent = True
                session["user_id"] = user[0]
                session["username"] = user[1]
                return redirect("/home")

            return render_template("login.html", error="Invalid login")

    return render_template("login.html")

# HOME
@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC", (session["user_id"],))
    data = cur.fetchall()

    income = sum(t[1] for t in data if t[3] == "income")
    expenses = sum(t[1] for t in data if t[3] == "expense")

    cur.execute("SELECT total FROM budget WHERE user_id=?", (session["user_id"],))
    row = cur.fetchone()
    budget = row[0] if row else 0

    percent = (expenses / budget * 100) if budget > 0 else 0
    remaining = income - expenses

    conn.close()

    return render_template(
        "index.html",
        username=session["username"],
        transactions=data,
        income=income,
        expenses=expenses,
        remaining=remaining,
        percent=percent,
        budget=budget
    )

# ADD
@app.route("/add", methods=["POST"])
def add():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO transactions VALUES (NULL, ?, ?, ?, ?, ?)",
        (
            request.form["amount"],
            request.form["category"],
            request.form["type"],
            request.form["date"],
            session["user_id"]
        )
    )

    conn.commit()
    return redirect("/home")

# BUDGET
@app.route("/budget", methods=["GET", "POST"])
def budget():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("DELETE FROM budget WHERE user_id=?", (session["user_id"],))
        cur.execute(
            "INSERT INTO budget VALUES (NULL, ?, ?)",
            (request.form["budget"], session["user_id"])
        )
        conn.commit()

    cur.execute("SELECT * FROM transactions WHERE user_id=?", (session["user_id"],))
    data = cur.fetchall()

    expenses = sum(t[1] for t in data if t[3] == "expense")

    cur.execute("SELECT total FROM budget WHERE user_id=?", (session["user_id"],))
    row = cur.fetchone()
    budget = row[0] if row else 0

    percent = (expenses / budget * 100) if budget else 0
    over = expenses > budget

    return render_template("budget.html",
        budget=budget,
        expenses=expenses,
        percent=percent,
        over=over
    )

# ================= FINAL BOSS STATISTICS =================
@app.route("/statistics")
def stats():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()
    uid = session["user_id"]

    # CATEGORY
    cur.execute("""
    SELECT category, SUM(amount)
    FROM transactions
    WHERE type='expense' AND user_id=?
    GROUP BY category
    """, (uid,))
    categories = cur.fetchall()

    # TIMELINE
    cur.execute("""
    SELECT date, SUM(amount)
    FROM transactions
    WHERE user_id=?
    GROUP BY date
    ORDER BY date
    """, (uid,))
    timeline = cur.fetchall()

    # MONTHLY
    cur.execute("""
    SELECT strftime('%Y-%m', date),
           SUM(CASE WHEN type='income' THEN amount ELSE 0 END),
           SUM(CASE WHEN type='expense' THEN amount ELSE 0 END)
    FROM transactions
    WHERE user_id=?
    GROUP BY strftime('%Y-%m', date)
    ORDER BY strftime('%Y-%m', date)
    """, (uid,))
    monthly = cur.fetchall()

    # 🔮 PREDICTIONS
    predictions = []
    if len(monthly) >= 2:
        last = monthly[-1]
        prev = monthly[-2]

        pred_income = last[1] + (last[1] - prev[1])
        pred_expense = last[2] + (last[2] - prev[2])

        predictions.append(f"Next income estimate: £{round(pred_income,2)}")
        predictions.append(f"Next expenses estimate: £{round(pred_expense,2)}")

        if pred_expense > pred_income:
            predictions.append("⚠ You may overspend next month.")

    # 🤖 AI INSIGHTS
    insights = []
    total_expenses = sum(x[1] for x in categories)

    for cat, total in categories:
        if total > total_expenses * 0.4:
            insights.append(f"{cat} dominates your spending.")

        if cat.lower() == "food" and total > 100:
            insights.append("Try cheaper food brands or meal prep.")

    # FINAL BOSS: Spending Score
    score = 100
    if len(monthly) >= 2:
        if monthly[-1][2] > monthly[-2][2]:
            score -= 20

    if total_expenses > 0:
        score -= int((total_expenses / 1000) * 10)

    score = max(score, 0)

    # FINAL BOSS: Run-out prediction
    runout = None
    cur.execute("SELECT SUM(amount) FROM transactions WHERE type='income' AND user_id=?", (uid,))
    income_total = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM transactions WHERE type='expense' AND user_id=?", (uid,))
    expense_total = cur.fetchone()[0] or 0

    if expense_total > 0:
        daily = expense_total / max(len(timeline),1)
        if daily > 0:
            days_left = int((income_total - expense_total) / daily)
            runout = f"At current spending, funds may last ~{days_left} days."

    conn.close()

    return render_template("statistics.html",
        categories=categories,
        timeline=timeline,
        monthly=monthly,
        predictions=predictions,
        insights=insights,
        score=score,
        runout=runout
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)