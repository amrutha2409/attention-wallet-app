from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import date

app = Flask(__name__)
CORS(app)

# ---------------- DATABASE CONNECTION ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",   
    database="attention_wallet"
)
cursor = db.cursor(dictionary=True)

# ---------------- DAILY RESET ----------------
def daily_reset(user_id):
    today = date.today()
    cursor.execute(
        "SELECT last_reset FROM tokens WHERE user_id=%s",
        (user_id,)
    )
    row = cursor.fetchone()

    if row and row["last_reset"] != today:
        cursor.execute(
            "UPDATE tokens SET used_tokens=0, last_reset=%s WHERE user_id=%s",
            (today, user_id)
        )
        db.commit()

# ---------------- TEST ROUTE ----------------
@app.route("/test")
def test():
    return jsonify({"status": "backend working"})

# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    name = data.get("name")
    role = data.get("role")

    if not name or not role:
        return jsonify({"error": "Invalid data"}), 400

    cursor.execute(
        "SELECT * FROM users WHERE name=%s AND role=%s",
        (name, role)
    )
    user = cursor.fetchone()

    if user:
        user_id = user["id"]
    else:
        cursor.execute(
            "INSERT INTO users (name, role) VALUES (%s,%s)",
            (name, role)
        )
        db.commit()
        user_id = cursor.lastrowid

        if role == "kid":
            cursor.execute(
                """INSERT INTO tokens (user_id, total_tokens, used_tokens, last_reset)
                   VALUES (%s,100,0,%s)""",
                (user_id, date.today())
            )
            db.commit()

    return jsonify({"user_id": user_id, "role": role})

# ---------------- GET TOKENS ----------------
@app.route("/tokens/<int:user_id>")
def get_tokens(user_id):
    daily_reset(user_id)
    cursor.execute(
        "SELECT total_tokens, used_tokens FROM tokens WHERE user_id=%s",
        (user_id,)
    )
    data = cursor.fetchone()
    return jsonify(data)

# ---------------- SET LIMIT (PARENT) ----------------
@app.route("/set_limit", methods=["POST"])
def set_limit():
    data = request.json
    kid_id = data.get("kid_id")
    limit = data.get("limit")

    cursor.execute(
        """UPDATE tokens
           SET total_tokens=%s, used_tokens=0, last_reset=%s
           WHERE user_id=%s""",
        (limit, date.today(), kid_id)
    )
    db.commit()

    return jsonify({"message": "Token limit updated"})

# ---------------- APP USAGE ----------------
@app.route("/use_app", methods=["POST"])
def use_app():
    data = request.json
    user_id = data["user_id"]
    app_name = data["app"]
    minutes = int(data["minutes"])
    rate = int(data["rate"])

    daily_reset(user_id)

    tokens_used = minutes * rate

    cursor.execute(
        """UPDATE tokens
           SET used_tokens = LEAST(total_tokens, used_tokens + %s)
           WHERE user_id=%s""",
        (tokens_used, user_id)
    )

    cursor.execute(
        """INSERT INTO app_usage
           (user_id, app, minutes, tokens_used, usage_date)
           VALUES (%s,%s,%s,%s,%s)""",
        (user_id, app_name, minutes, tokens_used, date.today())
    )

    db.commit()
    return jsonify({"tokens_used": tokens_used})

# ---------------- GOOD HABITS ----------------
@app.route("/add_habit", methods=["POST"])
def add_habit():
    data = request.json
    user_id = data["user_id"]
    habit = data["habit"]
    minutes = int(data["minutes"])
    rate = int(data["rate"])

    daily_reset(user_id)

    tokens_earned = minutes * rate

    cursor.execute(
        """UPDATE tokens
           SET used_tokens = GREATEST(0, used_tokens - %s)
           WHERE user_id=%s""",
        (tokens_earned, user_id)
    )

    cursor.execute(
        """INSERT INTO habits
           (user_id, habit, minutes, tokens_earned, usage_date)
           VALUES (%s,%s,%s,%s,%s)""",
        (user_id, habit, minutes, tokens_earned, date.today())
    )

    db.commit()
    return jsonify({"tokens_earned": tokens_earned})

# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    app.run(debug=True)
