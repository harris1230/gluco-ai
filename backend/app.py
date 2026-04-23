from flask import Flask, request, jsonify
from flask_cors import CORS
import os

from ppg_extraction import (
    extract_frames,
    extract_ppg_signal,
    remove_motion_artifacts,
    adaptive_bandpass_filter,
    smooth_signal,
    normalize_signal,
    detect_peaks,
    calculate_heart_rate,
    generate_plot_base64
)

from lstm_model import predict_glucose
from database import create_table, add_user, validate_user

# -------------------------------
# 🔥 INIT APP
# -------------------------------
app = Flask(__name__)
CORS(app)

# 🔥 FIX 413 ERROR (increase upload limit)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize DB
create_table()

# -------------------------------
# HOME
# -------------------------------
@app.route("/")
def home():
    return "🚀 Glucose Monitoring API Running"

# -------------------------------
# SIGNUP
# -------------------------------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing fields"}), 400

    if add_user(email, password):
        return jsonify({"message": "User created successfully"})
    else:
        return jsonify({"error": "User already exists"}), 400

# -------------------------------
# LOGIN
# -------------------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json

    email = data.get("email")
    password = data.get("password")

    if validate_user(email, password):
        return jsonify({"message": "Login successful"})
    else:
        return jsonify({"error": "Invalid credentials"}), 401

# -------------------------------
# 🔥 PREDICT API
# -------------------------------
@app.route("/predict", methods=["POST"])
def predict():

    if "video" not in request.files:
        return jsonify({"error": "No video uploaded"}), 400

    video = request.files["video"]

    if video.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    video_path = os.path.join(UPLOAD_FOLDER, video.filename)
    video.save(video_path)

    try:
        # -------------------------------
        # PROCESS VIDEO
        # -------------------------------
        frames = extract_frames(video_path)

        if len(frames) == 0:
            return jsonify({"error": "Invalid video"}), 400

        signal = extract_ppg_signal(frames)
        signal = remove_motion_artifacts(signal)
        signal = adaptive_bandpass_filter(signal)
        signal = smooth_signal(signal)
        signal = normalize_signal(signal)

        # -------------------------------
        # HEART RATE
        # -------------------------------
        peaks = detect_peaks(signal)
        heart_rate = calculate_heart_rate(peaks, len(frames))

        # -------------------------------
        # GLUCOSE PREDICTION
        # -------------------------------
        glucose = predict_glucose(signal)

        # -------------------------------
        # GRAPH
        # -------------------------------
        graph = generate_plot_base64(signal)

        # -------------------------------
        # FINAL RESPONSE
        # -------------------------------
        return jsonify({
            "heart_rate": round(heart_rate, 2),
            "glucose": round(glucose, 2),
            "status": "Experimental AI Prediction",
            "graph": graph
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # 🔥 DELETE VIDEO AFTER PROCESSING
        if os.path.exists(video_path):
            os.remove(video_path)

# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True)