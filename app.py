from flask import Flask, render_template, request, redirect, session
import sqlite3, os
from datetime import timedelta
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

# 🔐 LOGIN
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

# 🏠 DASHBOARD
@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    # Filters
    start = request.args.get("start")
    end = request.args.get("end")
    category_filter = request.args.get("category")

    query = "SELECT * FROM transactions WHERE user_id=?"
    params = [session["user_id"]]

    if start and end:
        query += " AND date BETWEEN ? AND ?"
        params += [start, end]

    if category_filter:
        query += " AND category=?"
        params.append(category_filter)

    query += " ORDER BY date DESC"

    cur.execute(query, params)
    data = cur.fetchall()

    income = sum(t[1] for t in data if t[3] == "income")
    expenses = sum(t[1] for t in data if t[3] == "expense")

    # Budget
    cur.execute("SELECT total FROM budget WHERE user_id=?", (session["user_id"],))
    row = cur.fetchone()
    budget = row[0] if row else 0

    percent = (expenses / budget * 100) if budget > 0 else 0
    remaining = income - expenses

    # CATEGORY TOTALS
    categories = {}
    for t in data:
        if t[3] == "expense":
            categories[t[2]] = categories.get(t[2], 0) + t[1]

    # ================= AI INSIGHTS ENGINE =================
    insights = []

    # 1. Income vs expenses
    if expenses > income:
        insights.append("You are spending more than you earn. Immediate action is recommended.")
    else:
        insights.append("Your income currently covers your expenses.")

    # 2. Budget pressure
    if percent > 100:
        insights.append("You have exceeded your budget. Review spending urgently.")
    elif percent > 85:
        insights.append("You are very close to your budget limit.")
    elif percent > 70:
        insights.append("Spending is increasing—monitor closely.")

    # 3. Category dominance
    for category, total in categories.items():
        if total > expenses * 0.35:
            if category.lower() == "food":
                insights.append("High food spending detected. Try cheaper brands or meal prepping.")
            elif category.lower() == "housing":
                insights.append("Housing costs dominate your spending. Review bills or rent.")
            elif category.lower() == "clothing":
                insights.append("Clothing spending is high. Try limiting non-essential purchases.")
            else:
                insights.append(f"High spending in {category}. Consider reducing this category.")

    # 4. RECENT vs OLD TREND
    recent = data[:5]
    older = data[5:10]

    recent_spend = sum(t[1] for t in recent if t[3] == "expense")
    older_spend = sum(t[1] for t in older if t[3] == "expense")

    if older_spend > 0:
        change = ((recent_spend - older_spend) / older_spend) * 100

        if change > 25:
            insights.append(f"Spending increased by {round(change,1)}% recently.")
        elif change < -25:
            insights.append(f"Spending decreased by {round(abs(change),1)}%. Good progress!")

    # 5. SPIKE DETECTION
    if data:
        largest = max(data, key=lambda t: t[1])
        if largest[1] > (expenses * 0.3):
            insights.append(f"Large transaction detected (£{largest[1]}). Consider reviewing it.")

    # 6. SAVINGS
    if income > expenses:
        savings = income - expenses
        insights.append(f"You are saving around £{round(savings,2)} this period.")
    else:
        insights.append("You are not currently saving. Try reducing small daily costs.")

    # 7. SMART TIPS
    if categories.get("Food", 0) > 100:
        insights.append("Try supermarket own-brand products to reduce food costs.")

    if categories.get("Misc", 0) > expenses * 0.25:
        insights.append("High 'Misc' spending detected—consider categorising it better.")

    if not insights:
        insights.append("Your finances look healthy. Keep it up.")

    conn.close()

    return render_template(
        "index.html",
        username=session["username"],
        transactions=data,
        income=income,
        expenses=expenses,
        remaining=remaining,
        percent=percent,
        budget=budget,
        insights=insights
    )

# ➕ ADD
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

# 💰 BUDGET
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

# 📊 STATISTICS
@app.route("/statistics")
def stats():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT category, SUM(amount)
    FROM transactions
    WHERE type='expense' AND user_id=?
    GROUP BY category
    """, (session["user_id"],))
    categories = cur.fetchall()

    cur.execute("""
    SELECT date, SUM(amount)
    FROM transactions
    WHERE user_id=?
    GROUP BY date
    """, (session["user_id"],))
    timeline = cur.fetchall()

    cur.execute("""
    SELECT strftime('%Y-%m', date),
           SUM(CASE WHEN type='income' THEN amount ELSE 0 END),
           SUM(CASE WHEN type='expense' THEN amount ELSE 0 END)
    FROM transactions
    WHERE user_id=?
    GROUP BY strftime('%Y-%m', date)
    """, (session["user_id"],))
    monthly = cur.fetchall()

    return render_template("statistics.html",
        categories=categories,
        timeline=timeline,
        monthly=monthly
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)