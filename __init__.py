"""
Avatars Plugin for CTFd
Simple file-based avatar upload for users and teams.
No database changes required — avatars stored as files in UPLOAD_FOLDER/avatars/.
Respects CTFd's UPLOAD_FOLDER config (important for Docker where it maps to /var/uploads).
"""
import hashlib
import logging
import os

from flask import Blueprint, abort, current_app, jsonify, request, send_file
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user, get_current_team

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

logger = logging.getLogger("avatars")

# Cache the resolved avatars directory path after first successful init
_avatars_dir = None
_avatars_dir_writable = False


def get_avatars_dir():
    """
    Return the avatars directory path.
    Uses CTFd's UPLOAD_FOLDER config (defaults to <root>/uploads).
    Does NOT call os.makedirs — that's done once in load().
    """
    global _avatars_dir
    if _avatars_dir is not None:
        return _avatars_dir

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        upload_folder = os.path.join(current_app.root_path, "uploads")

    _avatars_dir = os.path.join(upload_folder, "avatars")
    return _avatars_dir


def _ensure_avatars_dir():
    """Create the avatars directory if it doesn't exist. Called once at startup."""
    global _avatars_dir_writable
    avatars_dir = get_avatars_dir()
    try:
        os.makedirs(avatars_dir, exist_ok=True)
        _avatars_dir_writable = True
        logger.info(f"Avatars directory ready: {avatars_dir}")
    except OSError as e:
        _avatars_dir_writable = False
        logger.warning(
            f"Cannot create avatars directory '{avatars_dir}': {e}. "
            f"Avatar uploads will be disabled. Ensure UPLOAD_FOLDER is writable."
        )


def find_avatar(entity_type, entity_id):
    """Find avatar file for a user/team, returns path or None."""
    avatars_dir = get_avatars_dir()
    if not os.path.isdir(avatars_dir):
        return None
    for ext in ALLOWED_EXTENSIONS:
        path = os.path.join(avatars_dir, f"{entity_type}_{entity_id}.{ext}")
        if os.path.exists(path):
            return path
    return None


def delete_existing_avatar(entity_type, entity_id):
    """Remove all existing avatars for this entity."""
    avatars_dir = get_avatars_dir()
    if not os.path.isdir(avatars_dir):
        return
    for ext in ALLOWED_EXTENSIONS:
        path = os.path.join(avatars_dir, f"{entity_type}_{entity_id}.{ext}")
        if os.path.exists(path):
            os.remove(path)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load(app):
    avatar_bp = Blueprint("avatars", __name__)

    # Create avatars directory once at startup
    with app.app_context():
        _ensure_avatars_dir()

    # ── Serve avatar ──────────────────────────────────────────────
    @avatar_bp.route("/avatars/<entity_type>/<int:entity_id>")
    def get_avatar(entity_type, entity_id):
        if entity_type not in ("user", "team"):
            abort(400)

        path = find_avatar(entity_type, entity_id)
        if path is None:
            abort(404)

        return send_file(path, mimetype="image/png", max_age=300)

    # ── Upload user avatar ────────────────────────────────────────
    @avatar_bp.route("/avatars/user/upload", methods=["POST"])
    @authed_only
    def upload_user_avatar():
        if not _avatars_dir_writable:
            return jsonify(success=False, errors=["Avatar uploads are not available (storage not writable)"]), 503

        user = get_current_user()
        if user is None:
            return jsonify(success=False, errors=["Not authenticated"]), 403

        if "avatar" not in request.files:
            return jsonify(success=False, errors=["No file provided"]), 400

        f = request.files["avatar"]
        if f.filename == "":
            return jsonify(success=False, errors=["No file selected"]), 400

        if not allowed_file(f.filename):
            return jsonify(success=False, errors=["File type not allowed. Use PNG, JPG, GIF, or WebP"]), 400

        # Check file size
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify(success=False, errors=["File too large. Max 2MB"]), 400

        ext = f.filename.rsplit(".", 1)[1].lower()
        delete_existing_avatar("user", user.id)

        save_path = os.path.join(get_avatars_dir(), f"user_{user.id}.{ext}")
        f.save(save_path)

        return jsonify(success=True, url=f"/avatars/user/{user.id}")

    # ── Upload team avatar ────────────────────────────────────────
    @avatar_bp.route("/avatars/team/upload", methods=["POST"])
    @authed_only
    def upload_team_avatar():
        if not _avatars_dir_writable:
            return jsonify(success=False, errors=["Avatar uploads are not available (storage not writable)"]), 503

        user = get_current_user()
        team = get_current_team()
        if team is None:
            return jsonify(success=False, errors=["You are not on a team"]), 400

        # Only captain can change team avatar
        if team.captain_id != user.id:
            return jsonify(success=False, errors=["Only the team captain can change the avatar"]), 403

        if "avatar" not in request.files:
            return jsonify(success=False, errors=["No file provided"]), 400

        f = request.files["avatar"]
        if f.filename == "":
            return jsonify(success=False, errors=["No file selected"]), 400

        if not allowed_file(f.filename):
            return jsonify(success=False, errors=["File type not allowed. Use PNG, JPG, GIF, or WebP"]), 400

        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify(success=False, errors=["File too large. Max 2MB"]), 400

        ext = f.filename.rsplit(".", 1)[1].lower()
        delete_existing_avatar("team", team.id)

        save_path = os.path.join(get_avatars_dir(), f"team_{team.id}.{ext}")
        f.save(save_path)

        return jsonify(success=True, url=f"/avatars/team/{team.id}")

    # ── Delete user avatar ────────────────────────────────────────
    @avatar_bp.route("/avatars/user/delete", methods=["POST"])
    @authed_only
    def delete_user_avatar():
        user = get_current_user()
        if user is None:
            return jsonify(success=False, errors=["Not authenticated"]), 403
        delete_existing_avatar("user", user.id)
        return jsonify(success=True)

    # ── Delete team avatar ────────────────────────────────────────
    @avatar_bp.route("/avatars/team/delete", methods=["POST"])
    @authed_only
    def delete_team_avatar():
        user = get_current_user()
        team = get_current_team()
        if team is None:
            return jsonify(success=False, errors=["You are not on a team"]), 400
        if team.captain_id != user.id:
            return jsonify(success=False, errors=["Only the team captain can change the avatar"]), 403
        delete_existing_avatar("team", team.id)
        return jsonify(success=True)

    app.register_blueprint(avatar_bp)

    # ── Jinja2 helper: avatar_url(type, id, email) ───────────────
    @app.template_global("avatar_url")
    def avatar_url(entity_type, entity_id, fallback_email=None):
        """
        Returns avatar URL. If uploaded avatar exists, use it.
        Otherwise fall back to Gravatar (users) or DiceBear (teams).
        """
        path = find_avatar(entity_type, entity_id)
        if path is not None:
            return f"/avatars/{entity_type}/{entity_id}"

        # Fallback
        if entity_type == "user" and fallback_email:
            md5 = hashlib.md5(str(fallback_email).strip().lower().encode()).hexdigest()
            return f"https://www.gravatar.com/avatar/{md5}?d=identicon&s=120"

        # For teams or users without email, use DiceBear
        return f"https://api.dicebear.com/7.x/identicon/svg?seed={entity_id}&backgroundColor=1a1a1a"

    # Keep the md5 filter for backward compat
    @app.template_filter("md5")
    def md5_filter(s):
        if not s:
            return ""
        return hashlib.md5(str(s).strip().lower().encode()).hexdigest()
