import tempfile
from flask import Blueprint, abort, render_template, request, send_file, flash, redirect, url_for, jsonify
from sftp_personal_drive.utils.sftp_utils import get_sftp_connection, list_files
import os
import io
import json
from datetime import datetime

main_bp = Blueprint("main", __name__, template_folder="../templates")

LOCAL_UPLOAD_FOLDER = "uploads"
os.makedirs(LOCAL_UPLOAD_FOLDER, exist_ok=True)

TEMP_PREVIEW_DIR = os.path.join(tempfile.gettempdir(), "sftp_previews")
os.makedirs(TEMP_PREVIEW_DIR, exist_ok=True)

# Activity log file
ACTIVITY_LOG_FILE = "activity_log.json"

def log_activity(action, filename, username, host):
    """Log user activity to a JSON file"""
    try:
        activity = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "filename": filename,
            "username": username,
            "host": host
        }
        
        # Load existing activities
        if os.path.exists(ACTIVITY_LOG_FILE):
            with open(ACTIVITY_LOG_FILE, 'r') as f:
                activities = json.load(f)
        else:
            activities = []
        
        # Add new activity and keep only last 100
        activities.append(activity)
        if len(activities) > 100:
            activities = activities[-100:]
        
        # Save back to file
        with open(ACTIVITY_LOG_FILE, 'w') as f:
            json.dump(activities, f, indent=2)
            
    except Exception as e:
        print(f"Error logging activity: {e}")

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
            print()
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
        return redirect(url_for("main.sftp_page"))

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

        # Log activity
        log_activity("upload", uploaded_file.filename, username, host)
        
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

@main_bp.route("/download_preview")
def download_preview():
    # Strip all parameters to remove extra spaces
    filename = request.args.get("filename", "").strip()
    host = request.args.get("host", "").strip()
    username = request.args.get("username", "").strip()
    password = request.args.get("password", "").strip()

    if not all([filename, host, username, password]):
        return abort(400, description="Missing parameters")

    try:
        sftp, transport = get_sftp_connection(host, username, password)
        remote_path = f"/home/{username}/uploads/{filename}"

        # Use temporary file to preview
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        sftp.get(remote_path, temp_file.name)
        sftp.close()
        transport.close()

        # Determine mime type
        ext = filename.split('.')[-1].lower()
        if ext in ["jpg", "jpeg", "png", "gif", "bmp"]:
            mimetype = f"image/{ext}"
        elif ext == "pdf":
            mimetype = "application/pdf"
        elif ext in ["txt", "csv", "log", "py", "json", "html", "js"]:
            mimetype = "text/plain"
        else:
            mimetype = "application/octet-stream"

        return send_file(temp_file.name, mimetype=mimetype, download_name=filename)

    except FileNotFoundError:
        return abort(404, description="File not found on SFTP server")
    except Exception as e:
        return abort(500, description=f"Error: {str(e)}")    

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
        # FIXED: Changed from "sftp" to "main.sftp_page"
        return redirect(url_for("main.sftp_page"))

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
        
        # Log activity
        log_activity("download", filename, username, host)
        
        return send_file(file_obj, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f"Download failed: {e}", "error")
        return redirect(url_for("main.sftp_page"))

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
        
        # Log activity
        log_activity("delete", filename, username, host)
        
        flash(f"File deleted: {filename}", "success")
        sftp.close()
        transport.close()
    except Exception as e:
        flash(f"Delete failed: {e}", "error")
        files = None

    return render_template("sftp_transfer.html", files=files, host=host, username=username, password=password)

# New routes for enhanced functionality

@main_bp.route("/file_info", methods=["POST"])
def file_info():
    """Get file metadata"""
    host = request.form.get("host")
    username = request.form.get("username")
    password = request.form.get("password")
    filename = request.form.get("filename")

    try:
        sftp, transport = get_sftp_connection(host, username, password)
        remote_path = f"/home/{username}/uploads/{filename}"
        
        # Get file attributes
        file_attr = sftp.stat(remote_path)
        
        file_info = {
            "filename": filename,
            "size": file_attr.st_size,
            "modified": datetime.fromtimestamp(file_attr.st_mtime).isoformat(),
            "permissions": oct(file_attr.st_mode)[-3:],
            "owner": file_attr.st_uid,
            "type": "file"
        }
        
        sftp.close()
        transport.close()
        
        return jsonify(file_info)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main_bp.route("/create_folder", methods=["POST"])
def create_folder():
    """Create a new folder"""
    host = request.form.get("host")
    username = request.form.get("username")
    password = request.form.get("password")
    folder_name = request.form.get("folder_name")

    try:
        sftp, transport = get_sftp_connection(host, username, password)
        remote_path = f"/home/{username}/uploads/{folder_name}"
        
        sftp.mkdir(remote_path)
        
        # Log activity
        log_activity("create_folder", folder_name, username, host)
        
        sftp.close()
        transport.close()
        
        return jsonify({"success": True, "message": f"Folder '{folder_name}' created"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main_bp.route("/list_dir", methods=["POST"])
def list_directory():
    """List directory contents"""
    host = request.form.get("host")
    username = request.form.get("username")
    password = request.form.get("password")
    path = request.form.get("path", f"/home/{username}/uploads")

    try:
        sftp, transport = get_sftp_connection(host, username, password)
        
        # List files and directories
        items = []
        for item in sftp.listdir_attr(path):
            item_info = {
                "name": item.filename,
                "size": item.st_size,
                "modified": datetime.fromtimestamp(item.st_mtime).isoformat(),
                "permissions": oct(item.st_mode)[-3:],
                "type": "directory" if item.st_mode & 0o40000 else "file"
            }
            items.append(item_info)
        
        sftp.close()
        transport.close()
        
        return jsonify(items)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main_bp.route("/delete_multiple", methods=["POST"])
def delete_multiple():
    """Delete multiple files"""
    host = request.form.get("host")
    username = request.form.get("username")
    password = request.form.get("password")
    filenames = request.form.getlist("filenames[]")

    try:
        sftp, transport = get_sftp_connection(host, username, password)
        
        for filename in filenames:
            remote_path = f"/home/{username}/uploads/{filename}"
            sftp.remove(remote_path)
            # Log activity for each file
            log_activity("delete", filename, username, host)
        
        files = list_files(sftp, username)
        sftp.close()
        transport.close()
        
        return jsonify({"success": True, "message": f"Deleted {len(filenames)} files"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main_bp.route("/activity_log", methods=["POST"])
def get_activity_log():
    """Get recent activity log"""
    try:
        if os.path.exists(ACTIVITY_LOG_FILE):
            with open(ACTIVITY_LOG_FILE, 'r') as f:
                activities = json.load(f)
            return jsonify(activities)
        else:
            return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main_bp.route("/storage_info", methods=["POST"])
def storage_info():
    """Get storage usage information"""
    host = request.form.get("host")
    username = request.form.get("username")
    password = request.form.get("password")

    try:
        sftp, transport = get_sftp_connection(host, username, password)
        
        # This is a simplified version - in production you'd use statvfs
        # For demo purposes, we'll return mock data
        storage_info = {
            "total": 10 * 1024 * 1024 * 1024,  # 10 GB
            "used": 1.2 * 1024 * 1024 * 1024,   # 1.2 GB
            "free": 8.8 * 1024 * 1024 * 1024,   # 8.8 GB
            "percent": 12
        }
        
        sftp.close()
        transport.close()
        
        return jsonify(storage_info)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Optional: blueprint registration helper
def register_blueprints(app):
    app.register_blueprint(main_bp)
    
@main_bp.route("/get_file_content")
def get_file_content():
    filename = request.args.get("filename")
    host = request.args.get("host")
    username = request.args.get("username")
    password = request.args.get("password")

    if not all([filename, host, username, password]):
        return jsonify({"error": "Missing connection parameters"}), 400

    try:
        # Connect to SFTP
        sftp, transport = get_sftp_connection(host, username, password)
        remote_path = f"/home/{username}/uploads/{filename}"

        # Read file content
        with sftp.open(remote_path, "r") as f:
            content = f.read().decode(errors="ignore")

        sftp.close()
        transport.close()

        # Detect file type
        ext = filename.split(".")[-1].lower()
        language_map = {
            "py": "python", "html": "html", "css": "css", "js": "javascript",
            "json": "json", "xml": "xml", "csv": "plaintext", "md": "markdown", "txt": "plaintext"
        }

        return jsonify({"content": content, "language": language_map.get(ext, "plaintext")})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/save_file", methods=["POST"])
def save_file():
    data = request.json
    filename = data.get("filename")
    content = data.get("content")
    host = data.get("host")
    username = data.get("username")
    password = data.get("password")

    if not all([filename, host, username, password]):
        return jsonify({"success": False, "message": "Missing connection parameters"}), 400

    try:
        sftp, transport = get_sftp_connection(host, username, password)
        remote_path = f"/home/{username}/uploads/{filename}"

        with sftp.open(remote_path, "w") as f:
            f.write(content.encode())

        sftp.close()
        transport.close()

        # Log the edit action
        log_activity("edit", filename, username, host)

        return jsonify({"success": True, "message": "File saved successfully!"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
