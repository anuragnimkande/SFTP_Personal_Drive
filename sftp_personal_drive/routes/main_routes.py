from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for
from utils.sftp_utils import get_sftp_connection, list_files
import os
import io

main_bp = Blueprint("main", __name__, template_folder="../templates")

LOCAL_UPLOAD_FOLDER = "uploads"
os.makedirs(LOCAL_UPLOAD_FOLDER, exist_ok=True)

# Home page
@main_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@main_bp.route('/sftp', methods=['GET', 'POST'])
def sftp_page():
    host = request.form.get("host") or ""
    username = request.form.get("username") or ""
    password = request.form.get("password") or ""
    files = []

    if host and username and password:
        try:
            sftp, transport = get_sftp_connection(host, username, password)
            files = list_files(sftp, username)
            sftp.close()
            transport.close()
        except Exception as e:
            flash(f"Failed to connect to SFTP: {e}", "error")

    return render_template('sftp_transfer.html', files=files, host=host, username=username, password=password)


# Upload route
@main_bp.route("/upload", methods=["POST"])
def upload():
    uploaded_file = request.files.get("file")
    host = request.form.get("host")
    username = request.form.get("username")
    password = request.form.get("password")

    if not uploaded_file:
        flash("No file selected.", "error")
        return redirect(url_for("main.index"))

    local_path = os.path.join(LOCAL_UPLOAD_FOLDER, uploaded_file.filename)
    uploaded_file.save(local_path)

    remote_path = f"/home/{username}/uploads/{uploaded_file.filename}"

    try:
        sftp, transport = get_sftp_connection(host, username, password)

        # Ensure the remote directory exists
        try:
            sftp.stat(f"/home/{username}/uploads")
        except FileNotFoundError:
            sftp.mkdir(f"/home/{username}/uploads")

        # Upload the file
        sftp.put(local_path, remote_path)

        # List files on the server
        files = list_files(sftp, username)

        flash(f"File uploaded successfully: {uploaded_file.filename}", "success")

        sftp.close()
        transport.close()

    except Exception as e:
        flash(f"Upload failed: {e}", "error")
        files = None

    return render_template(
        "sftp_transfer.html",
        files=files,
        host=host,
        username=username,
        password=password
    )
    
@main_bp.route("/sftp_access", methods=["POST"])
def sftp_access():
    host = request.form.get("host")
    username = request.form.get("username")
    password = request.form.get("password")

    # Try connecting to SFTP
    try:
        sftp, transport = get_sftp_connection(host, username, password)
        # List files (ensure remote folder exists)
        try:
            sftp.stat(f"/home/{username}/uploads")
        except FileNotFoundError:
            sftp.mkdir(f"/home/{username}/uploads")

        files = list_files(sftp, username)
        sftp.close()
        transport.close()

        return render_template(
            "sftp_transfer.html",
            host=host,
            username=username,
            password=password,
            files=files
        )

    except Exception as e:
        flash(f"Connection failed: {e}", "error")
        return redirect(url_for("sftp"))


# Download route
@main_bp.route("/download", methods=["POST"])
def download():
    host = request.form.get("host")
    username = request.form.get("username")
    password = request.form.get("password")
    filename = request.form.get("filename")

    try:
        sftp, transport = get_sftp_connection(host, username, password)
        remote_path = f"/home/{username}/uploads/{filename}"
        file_obj = io.BytesIO()
        sftp.getfo(remote_path, file_obj)
        file_obj.seek(0)
        sftp.close()
        transport.close()
        return send_file(file_obj, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f"Download failed: {e}", "error")
        return redirect(url_for("main.sftp"))

# Delete route
@main_bp.route("/delete", methods=["POST"])
def delete():
    host = request.form.get("host")
    username = request.form.get("username")
    password = request.form.get("password")
    filename = request.form.get("filename")

    try:
        sftp, transport = get_sftp_connection(host, username, password)
        remote_path = f"/home/{username}/uploads/{filename}"
        sftp.remove(remote_path)
        files = list_files(sftp, username)
        flash(f"File deleted: {filename}", "success")
        sftp.close()
        transport.close()
    except Exception as e:
        flash(f"Delete failed: {e}", "error")
        files = None

    return render_template("sftp_transfer.html", files=files, host=host, username=username, password=password)

# Optional: blueprint registration helper
def register_blueprints(app):
    app.register_blueprint(main_bp)
