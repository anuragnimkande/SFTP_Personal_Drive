from flask import Flask
from sftp_personal_drive.routes.main_routes import main_bp
import os

app = Flask(__name__)

# ------------------ SECRET KEY ------------------
# Required for session (flash messages) to work
app.secret_key = "this_is_a_temp_secret_key_for_dev"  # <-- just something random for now

# Ensure upload folder exists
LOCAL_UPLOAD_FOLDER = "uploads"
os.makedirs(LOCAL_UPLOAD_FOLDER, exist_ok=True)

# Register Blueprint
app.register_blueprint(main_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
