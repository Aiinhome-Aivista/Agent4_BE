import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from flask import request, jsonify
from database.db_connection import get_db_connection

SECRET = os.getenv("JWT_SECRET", "changeme")
EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 24))

def _generate_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(hours=EXPIRY_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def login():
    data = request.get_json()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return jsonify({"error": "Invalid credentials"}), 401

    token = _generate_token(user)
    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        }
    }), 200

def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except Exception:
        return None

def get_me():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401
    payload = verify_token(auth.split(" ")[1])
    if not payload:
        return jsonify({"error": "Invalid token"}), 401
    return jsonify({"user": payload}), 200
