"""
Voting Application - Main Flask Application
A web-based voting platform with real-time results and anonymous participation.
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import json
import uuid
import secrets
import ssl
import csv
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from io import StringIO
import base64
from cryptography.fernet import Fernet
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Removed unused decorators: timeout_handler and safe_json_response
# These were defined but never used in the codebase


# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "your-secret-key-change-this")

# Initialize SocketIO for real-time features with stability configurations
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",  # Use threading for better stability
    ping_timeout=60,  # Increase timeout to prevent premature disconnects
    ping_interval=25,  # Send ping every 25 seconds
    logger=False,  # Reduce log verbosity
)

# Data directory structure
DATA_DIR = Path("data")
ACTIVE_DIR = DATA_DIR / "active"
COMPLETED_DIR = DATA_DIR / "completed"
CONFIG_FILE = DATA_DIR / "config.json"
ACTIVE_INDEX_FILE = DATA_DIR / "active_sessions_index.json"
COMPLETED_INDEX_FILE = DATA_DIR / "completed_sessions_index.json"

# Default application configuration (optimized for demo/development)
DEFAULT_CONFIG = {
    "email": {
        "smtp_server": "127.0.0.1",
        "smtp_port": 1025,
        "username": "",
        "password": "",
        "sender_name": "Vote For Me",
        "sender_email": "noreply@vote-for-me.app",
        "use_tls": False,
    },
    "application": {
        "memory_limit_mb": 100,
        "max_sessions_cache": 20,
        "session_timeout_days": 7,
        "demo_mode": True,
    },
}

# Ensure directories exist
for directory in [DATA_DIR, ACTIVE_DIR, COMPLETED_DIR]:
    directory.mkdir(exist_ok=True)

# Ensure index files exist
for index_file in [ACTIVE_INDEX_FILE, COMPLETED_INDEX_FILE]:
    if not index_file.exists():
        with open(index_file, "w") as f:
            json.dump(
                {
                    "sessions": [],
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
            )


class ConfigManager:
    """Manages application configuration"""

    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        """Load configuration from file or create default"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved_config = json.load(f)
                # Merge with defaults to ensure all keys exist
                config = DEFAULT_CONFIG.copy()
                for section in saved_config:
                    if section in config:
                        config[section].update(saved_config[section])
                return config
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                return DEFAULT_CONFIG.copy()
        else:
            # Create default config file
            config = DEFAULT_CONFIG.copy()
            self.save_config(config)
            return config

    def save_config(self, config=None):
        """Save configuration to file"""
        if config is None:
            config = self.config

        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def get(self, section, key=None):
        """Get configuration value"""
        if key is None:
            return self.config.get(section, {})
        return self.config.get(section, {}).get(key)

    def set(self, section, key, value):
        """Set configuration value"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
        return self.save_config()

    def update_section(self, section, updates):
        """Update entire configuration section"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section].update(updates)
        return self.save_config()


# Initialize configuration manager
config_manager = ConfigManager()


# Authentication System
class AuthManager:
    """Simple authentication system for admin access"""

    def __init__(self):
        # In production, this should be stored securely and hashed
        # For demo purposes, using a simple default password
        self.admin_password_hash = self._hash_password("admin123")

    def _hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password):
        """Verify if provided password is correct"""
        return self._hash_password(password) == self.admin_password_hash

    def is_authenticated(self, flask_session):
        """Check if current session is authenticated"""
        return flask_session.get("authenticated", False)

    def authenticate(self, flask_session, password):
        """Authenticate user and set session"""
        if self.verify_password(password):
            flask_session["authenticated"] = True
            flask_session.permanent = True
            return True
        return False

    def logout(self, flask_session):
        """Logout user and clear session"""
        flask_session.pop("authenticated", None)


# Authentication decorator
def require_auth(f):
    """Decorator to require authentication for admin routes"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import session, redirect, request, url_for

        if not auth_manager.is_authenticated(session):
            # Store the original URL to redirect back after login, but only for non-API routes
            # API routes should not be used for user navigation after login
            if not request.path.startswith("/api/"):
                session["next_url"] = request.url
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


# Initialize authentication manager
auth_manager = AuthManager()


class VotingSession:
    """Manages voting session data and operations"""

    def __init__(self, session_data=None):
        if session_data:
            self.__dict__.update(session_data)
        else:
            self.id = str(uuid.uuid4())
            self.created = datetime.now(timezone.utc).isoformat()
            self.completed = None
            self.title = ""
            self.description = ""
            self.items = []
            self.participants = {}
            self.votes = {}
            self.settings = {
                "anonymous": True,
                "show_results_live": False,
                "votes_per_participant": 10,
                "results_access": "public",  # 'private' or 'public'
                "show_item_names": True,
                "presentation_mode": True,
            }
            self.status = "draft"  # 'draft', 'active', 'completed'

    def mark_completed(self):
        """Mark session as completed with timestamp"""
        self.completed = datetime.now(timezone.utc).isoformat()
        self.status = "completed"

    def to_dict(self):
        """Convert session to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "created": self.created,
            "completed": self.completed,
            "title": self.title,
            "description": self.description,
            "items": self.items,
            "participants": self.participants,
            "votes": self.votes,
            "settings": self.settings,
            "status": self.status,
        }

    def get_file_path(self):
        """Get the file path for this session"""
        date_str = datetime.fromisoformat(self.created.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d"
        )
        if self.status == "completed":
            return COMPLETED_DIR / date_str / f"{self.id}.json"
        else:
            return ACTIVE_DIR / date_str / f"{self.id}.json"

    def get_key_file_path(self):
        """Get the encryption key file path for this session"""
        return self.get_file_path().with_suffix(".key")

    def save(self):
        """Save session to file with proper directory structure and atomic operations"""
        try:
            file_path = self.get_file_path()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate encryption key if it doesn't exist
            key_path = self.get_key_file_path()
            if not key_path.exists():
                key = Fernet.generate_key()
                # Atomic key file creation
                temp_key_path = key_path.with_suffix(".key.tmp")
                with open(temp_key_path, "wb") as f:
                    f.write(key)
                temp_key_path.replace(key_path)  # Atomic rename

            # Atomic session data save
            temp_file_path = file_path.with_suffix(".json.tmp")
            with open(temp_file_path, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
            temp_file_path.replace(file_path)  # Atomic rename

            # Update index files
            self._update_index_files()

            logger.info(f"Session {self.id} saved to {file_path}")

        except Exception as e:
            logger.error(f"Failed to save session {self.id}: {e}")
            # Clean up temp files if they exist
            temp_file_path = file_path.with_suffix(".json.tmp")
            temp_key_path = self.get_key_file_path().with_suffix(".key.tmp")
            for temp_path in [temp_file_path, temp_key_path]:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass  # Ignore cleanup errors
            raise

    def _update_index_files(self):
        """Update session index files"""
        try:
            # Determine which index file to update
            index_file = (
                ACTIVE_INDEX_FILE
                if self.status != "completed"
                else COMPLETED_INDEX_FILE
            )

            # Load current index
            with open(index_file, "r") as f:
                index_data = json.load(f)

            # Create session summary for index
            session_summary = {
                "id": self.id,
                "title": self.title,
                "created": self.created,
                "completed": self.completed,
                "status": self.status,
                "participants_count": len(self.participants),
                "items_count": len(self.items),
            }

            # Update or add session to index
            existing_sessions = index_data.get("sessions", [])
            session_found = False

            for i, session in enumerate(existing_sessions):
                if session["id"] == self.id:
                    existing_sessions[i] = session_summary
                    session_found = True
                    break

            if not session_found:
                existing_sessions.append(session_summary)

            # Update index
            index_data["sessions"] = existing_sessions
            index_data["last_updated"] = datetime.now(timezone.utc).isoformat()

            # Save updated index
            with open(index_file, "w") as f:
                json.dump(index_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to update index files: {e}")

    def move_to_completed(self):
        """Move session from active to completed folder and update indexes"""
        if self.status == "completed":
            return  # Already completed

        old_path = self.get_file_path()
        old_key_path = self.get_key_file_path()

        # Mark as completed
        self.mark_completed()

        new_path = self.get_file_path()
        new_key_path = self.get_key_file_path()

        # Create destination directory
        new_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Move files
            if old_path.exists():
                old_path.rename(new_path)
            if old_key_path.exists():
                old_key_path.rename(new_key_path)

            # Remove from active index and add to completed index
            self._remove_from_active_index()
            self._update_index_files()

            logger.info(f"Session {self.id} moved to completed")

        except Exception as e:
            logger.error(f"Failed to move session to completed: {e}")
            # Rollback status change
            self.status = "active"
            self.completed = None
            raise

    def _remove_from_active_index(self):
        """Remove session from active index"""
        try:
            with open(ACTIVE_INDEX_FILE, "r") as f:
                index_data = json.load(f)

            # Remove session from active index
            index_data["sessions"] = [
                s for s in index_data.get("sessions", []) if s["id"] != self.id
            ]
            index_data["last_updated"] = datetime.now(timezone.utc).isoformat()

            with open(ACTIVE_INDEX_FILE, "w") as f:
                json.dump(index_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to remove from active index: {e}")

    @classmethod
    def load(cls, session_id, status="active"):
        """Load session from file"""
        # Try to find the session file
        search_dir = ACTIVE_DIR if status == "active" else COMPLETED_DIR

        for date_dir in search_dir.iterdir():
            if date_dir.is_dir():
                session_file = date_dir / f"{session_id}.json"
                if session_file.exists():
                    with open(session_file, "r") as f:
                        data = json.load(f)
                    return cls(data)

        return None

    def generate_participant_link(self, email):
        """Generate encrypted participant link"""
        key_path = self.get_key_file_path()
        if not key_path.exists():
            key = Fernet.generate_key()
            with open(key_path, "wb") as f:
                f.write(key)

        with open(key_path, "rb") as f:
            key = f.read()

        fernet = Fernet(key)

        # Create participant data
        participant_data = {
            "session_id": self.id,
            "email": email,
            "participant_id": str(uuid.uuid4()),
            "expires": (datetime.now(timezone.utc).timestamp() + 86400 * 30),  # 30 days
        }

        # Encrypt and encode
        encrypted = fernet.encrypt(json.dumps(participant_data).encode())
        encoded = base64.urlsafe_b64encode(encrypted).decode()

        return f"/vote/{encoded}"


class SessionManager:
    """Manages all voting sessions and provides caching"""

    def __init__(self):
        self.cache = {}
        self.max_cache_size_mb = 1000  # Default 1000MB limit
        self.load_config()

    def load_config(self):
        """Load application configuration"""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                self.max_cache_size_mb = config.get("memory_limit_mb", 1000)

    def save_config(self):
        """Save application configuration"""
        config = {
            "memory_limit_mb": self.max_cache_size_mb,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

    def create_session(
        self, title, description="", votes_per_participant=10, anonymous=True
    ):
        """Create new voting session"""
        session = VotingSession()
        session.title = title
        session.description = description
        session.settings["votes_per_participant"] = votes_per_participant
        session.settings["anonymous"] = anonymous
        session.save()

        # Add to cache
        self.cache[session.id] = session

        logger.info(
            f"Created new session: {session.id} - {title} (votes: {votes_per_participant}, anonymous: {anonymous})"
        )
        return session

    def get_session(self, session_id):
        """Get session by ID (from cache or disk)"""
        if session_id in self.cache:
            return self.cache[session_id]

        # Try to load from disk
        session = VotingSession.load(session_id, "active")
        if not session:
            session = VotingSession.load(session_id, "completed")

        if session:
            self.cache[session_id] = session

        return session

    def get_active_sessions(self, limit=100):
        """Get list of active sessions from index"""
        try:
            with open(ACTIVE_INDEX_FILE, "r") as f:
                index_data = json.load(f)

            sessions_data = index_data.get("sessions", [])

            # Sort by creation date (newest first) and limit
            sessions_data.sort(key=lambda s: s["created"], reverse=True)
            limited_sessions = sessions_data[:limit]

            # Convert to session objects
            sessions = []
            for session_data in limited_sessions:
                session = self.get_session(session_data["id"])
                if session:
                    sessions.append(session)

            return sessions

        except Exception as e:
            logger.error(f"Failed to load active sessions from index: {e}")
            # Fallback to file system scan
            return self._scan_active_sessions_filesystem(limit)

    def _scan_active_sessions_filesystem(self, limit=100):
        """Fallback method to scan filesystem for active sessions"""
        sessions = []

        for date_dir in ACTIVE_DIR.iterdir():
            if date_dir.is_dir():
                for session_file in date_dir.glob("*.json"):
                    session_id = session_file.stem
                    session = self.get_session(session_id)
                    if session:
                        sessions.append(session)

        # Sort by creation date (newest first) and limit
        sessions.sort(key=lambda s: s.created, reverse=True)
        return sessions[:limit]

    def get_completed_sessions(self, limit=100):
        """Get list of completed sessions from index"""
        try:
            with open(COMPLETED_INDEX_FILE, "r") as f:
                index_data = json.load(f)

            sessions_data = index_data.get("sessions", [])

            # Sort by completion date (newest first) and limit
            sessions_data.sort(
                key=lambda s: s.get("completed", s["created"]), reverse=True
            )
            limited_sessions = sessions_data[:limit]

            # Convert to session objects
            sessions = []
            for session_data in limited_sessions:
                session = self.get_session(session_data["id"])
                if session:
                    sessions.append(session)

            return sessions

        except Exception as e:
            logger.error(f"Failed to load completed sessions from index: {e}")
            return []

    def delete_session(self, session_id):
        """Delete a session and all its files"""
        session = self.get_session(session_id)
        if not session:
            return False, "Session not found"

        try:
            # Get file paths
            session_file = session.get_file_path()
            key_file = session.get_key_file_path()

            # Remove files
            if session_file.exists():
                session_file.unlink()
            if key_file.exists():
                key_file.unlink()

            # Remove from cache
            if session_id in self.cache:
                del self.cache[session_id]

            # Remove from appropriate index
            index_file = (
                ACTIVE_INDEX_FILE
                if session.status != "completed"
                else COMPLETED_INDEX_FILE
            )
            with open(index_file, "r") as f:
                index_data = json.load(f)

            index_data["sessions"] = [
                s for s in index_data.get("sessions", []) if s["id"] != session_id
            ]
            index_data["last_updated"] = datetime.now(timezone.utc).isoformat()

            with open(index_file, "w") as f:
                json.dump(index_data, f, indent=2)

            logger.info(f"Session {session_id} deleted successfully")
            return True, "Session deleted successfully"

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False, f"Failed to delete session: {str(e)}"


# Initialize session manager
session_manager = SessionManager()


# Email configuration and sending
app.config.update(
    {
        "MAIL_SERVER": "smtp.gmail.com",
        "MAIL_PORT": 587,
        "MAIL_USE_TLS": True,
        "MAIL_USERNAME": "",  # To be configured by user
        "MAIL_PASSWORD": "",  # To be configured by user
        "MAIL_DEFAULT_SENDER": "noreply@vote-for-me.app",
    }
)


class EmailService:
    """Handle email operations for participant invitations"""

    def __init__(self):
        pass

    def send_invitation_email(
        self, recipient_email, session_title, voting_link, session_description=""
    ):
        """Send voting invitation email to participant"""
        email_config = config_manager.get("email")

        # Defensive programming: ensure email_config is not None
        if not email_config:
            return (
                False,
                "Email configuration not found. Please configure SMTP settings in the admin panel.",
            )

        if not email_config.get("smtp_server"):
            return (
                False,
                "Email configuration not set up. Please configure SMTP settings in the admin panel.",
            )

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Voting Invitation: {session_title}"
            msg["From"] = (
                f"{email_config.get('sender_name', 'Vote For Me')} <{email_config.get('sender_email', 'noreply@vote-for-me.app')}>"
            )
            msg["To"] = recipient_email

            # Create HTML content
            html_content = self._create_email_template(
                session_title, voting_link, session_description
            )

            # Create text content
            text_content = f"""
🗳️ You're invited to vote

{session_title}

{session_description}

To vote, copy and paste this link into your browser:
{voting_link}

This is your personal voting link - don't share it with others.

Vote For Me Platform
            """.strip()

            # Attach parts
            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")
            msg.attach(text_part)
            msg.attach(html_part)

            # Send email
            context = ssl.create_default_context()
            server_address = email_config.get("smtp_server", "")
            server_port = email_config.get("smtp_port", 587)

            with smtplib.SMTP(server_address, server_port) as server:
                if email_config.get("use_tls", True):
                    server.starttls(context=context)
                server.login(
                    email_config.get("username", ""), email_config.get("password", "")
                )
                server.send_message(msg)

            logger.info(f"Invitation email sent to {recipient_email}")
            return True, "Email sent successfully"

        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
            return False, f"Failed to send email: {str(e)}"

    def test_email_configuration(self):
        """Test email configuration by sending a test email"""
        email_config = config_manager.get("email")

        # Defensive programming: ensure email_config is not None
        if not email_config:
            return False, "Email configuration not found"

        if not email_config.get("smtp_server"):
            return False, "Email configuration incomplete"

        try:
            # Test connection
            context = ssl.create_default_context()
            server_address = email_config.get("smtp_server", "")
            server_port = email_config.get("smtp_port", 587)

            with smtplib.SMTP(server_address, server_port) as server:
                if email_config.get("use_tls", True):
                    server.starttls(context=context)
                server.login(
                    email_config.get("username", ""), email_config.get("password", "")
                )

            return True, "Email configuration is working correctly"

        except Exception as e:
            logger.error(f"Email configuration test failed: {str(e)}")
            return False, f"Email configuration test failed: {str(e)}"

    def _create_email_template(self, session_title, voting_link, description):
        """Create HTML email template"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vote Now - {session_title}</title>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            line-height: 1.4; 
            color: #333; 
            margin: 0; 
            padding: 20px; 
            background-color: #f8fafc;
        }}
        .container {{ 
            max-width: 500px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 12px; 
            overflow: hidden; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{ 
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); 
            color: white; 
            padding: 24px; 
            text-align: center; 
        }}
        .header h1 {{ 
            margin: 0; 
            font-size: 22px; 
            font-weight: 600; 
        }}
        .content {{ 
            padding: 24px; 
            text-align: center; 
        }}
        .title {{ 
            font-size: 20px; 
            font-weight: 600; 
            color: #1f2937; 
            margin: 0 0 12px 0; 
        }}
        .description {{ 
            color: #6b7280; 
            margin: 0 0 24px 0; 
            font-size: 16px;
        }}
        .cta-button {{ 
            display: inline-block; 
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); 
            color: white !important; 
            padding: 14px 32px; 
            text-decoration: none; 
            border-radius: 8px; 
            font-weight: 600; 
            font-size: 16px; 
            margin: 8px 0 24px 0;
            box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
            transition: all 0.2s ease;
        }}
        .cta-button:hover {{ 
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.4);
            color: white !important;
        }}
        .footer-note {{ 
            font-size: 13px; 
            color: #9ca3af; 
            margin: 16px 0 0 0;
            padding-top: 16px;
            border-top: 1px solid #e5e7eb;
        }}
        @media only screen and (max-width: 480px) {{
            body {{ padding: 10px; }}
            .content {{ padding: 20px; }}
            .cta-button {{ 
                display: block; 
                width: 100%; 
                box-sizing: border-box; 
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗳️ You're invited to vote</h1>
        </div>
        <div class="content">
            <div class="title">{session_title}</div>
            {f'<div class="description">{description}</div>' if description else ""}
            
            <p style="margin: 0 0 20px 0; color: #374151; font-size: 15px;">
                Click the button below to cast your vote:
            </p>
            
            <a href="{voting_link}" class="cta-button">
                Vote Now →
            </a>
            
            <div class="footer-note">
                This is your personal voting link. Don't share it with others.
            </div>
        </div>
    </div>
</body>
</html>
        """.strip()


# Initialize email service
email_service = EmailService()


# Context processor for authentication status
@app.context_processor
def inject_auth():
    """Inject authentication status into all templates"""
    from flask import session

    return {
        "is_authenticated": auth_manager.is_authenticated(session),
        "is_participant_page": request.endpoint == "vote_page",
    }


# Routes
@app.route("/")
def index():
    """Main dashboard page"""
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Admin login page"""
    from flask import session, redirect, request

    if request.method == "POST":
        password = request.form.get("password")
        if auth_manager.authenticate(session, password):
            # Redirect to the originally requested page or admin dashboard
            next_url = session.pop("next_url", "/admin")
            return redirect(next_url)
        else:
            return render_template("login.html", error="Invalid password")

    # If already authenticated, redirect to admin
    if auth_manager.is_authenticated(session):
        return redirect("/admin")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Admin logout"""
    from flask import session, redirect

    auth_manager.logout(session)
    return redirect("/")


@app.route("/admin")
@require_auth
def admin_dashboard():
    """Admin dashboard for managing sessions"""
    active_sessions = session_manager.get_active_sessions()
    return render_template("admin.html", sessions=active_sessions)


@app.route("/admin/<session_id>")
@require_auth
def admin_session(session_id):
    """Admin page for individual session management"""
    session = session_manager.get_session(session_id)
    if not session:
        return "Session not found", 404

    return render_template("admin_session.html", session=session)


@app.route("/config")
@require_auth
def config_page():
    """Configuration page for email and application settings"""
    return render_template("config.html")


@app.route("/api/config", methods=["GET"])
@require_auth
def get_config():
    """Get current configuration (sensitive data masked)"""
    config = config_manager.config.copy()

    # Mask sensitive data
    if "email" in config:
        if config["email"].get("password"):
            config["email"]["password"] = "***hidden***"

    return jsonify({"success": True, "config": config})


@app.route("/api/config/email", methods=["PUT"])
@require_auth
def update_email_config():
    """Update email configuration"""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    # Validate required fields
    required_fields = [
        "smtp_server",
        "smtp_port",
        "username",
        "password",
        "sender_email",
    ]
    for field in required_fields:
        if not data.get(field):
            return jsonify(
                {"success": False, "error": f"Missing required field: {field}"}
            ), 400

    # Update email configuration
    email_config = {
        "smtp_server": data["smtp_server"],
        "smtp_port": int(data["smtp_port"]),
        "username": data["username"],
        "password": data["password"],
        "sender_name": data.get("sender_name", "Vote For Me"),
        "sender_email": data["sender_email"],
        "use_tls": data.get("use_tls", True),
    }

    if config_manager.update_section("email", email_config):
        return jsonify(
            {"success": True, "message": "Email configuration updated successfully"}
        )
    else:
        return jsonify({"success": False, "error": "Failed to save configuration"}), 500


@app.route("/api/config/email/test", methods=["POST"])
@require_auth
def test_email_config():
    """Test current email configuration"""
    success, message = email_service.test_email_configuration()
    return jsonify({"success": success, "message": message})


@app.route("/api/sessions", methods=["GET"])
@require_auth
def get_active_sessions():
    """Get list of active sessions"""
    limit = request.args.get("limit", 100, type=int)
    active_sessions = session_manager.get_active_sessions(limit)

    sessions_data = []
    for session in active_sessions:
        sessions_data.append(
            {
                "id": session.id,
                "title": session.title,
                "created": session.created,
                "status": session.status,
                "participants_count": len(session.participants),
                "items_count": len(session.items),
                "total_votes": len(session.votes),
            }
        )

    return jsonify({"sessions": sessions_data})


@app.route("/api/sessions", methods=["POST"])
@require_auth
def create_session():
    """API endpoint to create new voting session"""
    data = request.json

    if not data or "title" not in data:
        return jsonify({"error": "Title is required"}), 400

    # Validate email configuration if participants will be added
    if data.get("send_invitations", False) or data.get("participants"):
        email_config = config_manager.get("email")
        if not email_config or not email_config.get("smtp_server"):
            return jsonify(
                {
                    "error": "Email configuration is required before creating sessions with participants. Please configure SMTP settings in the admin panel first.",
                    "error_type": "email_config_required",
                    "redirect": "/config",
                }
            ), 400

        # Test email configuration
        email_service = EmailService()
        test_success, test_message = email_service.test_email_configuration()
        if not test_success:
            return jsonify(
                {
                    "error": f"Email configuration test failed: {test_message}. Please check your SMTP settings.",
                    "error_type": "email_config_invalid",
                    "redirect": "/config",
                }
            ), 400

    session = session_manager.create_session(
        title=data["title"],
        description=data.get("description", ""),
        votes_per_participant=data.get("votes_per_participant", 10),
        anonymous=data.get("anonymous", True),
    )

    return jsonify(
        {"success": True, "session_id": session.id, "session": session.to_dict()}
    )


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    """Get session data"""
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(session.to_dict())


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """Delete a session"""
    success, message = session_manager.delete_session(session_id)
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"error": message}), 404


@app.route("/api/sessions/completed", methods=["GET"])
def get_completed_sessions():
    """Get list of completed sessions"""
    limit = request.args.get("limit", 100, type=int)
    completed_sessions = session_manager.get_completed_sessions(limit)

    sessions_data = []
    for session in completed_sessions:
        sessions_data.append(
            {
                "id": session.id,
                "title": session.title,
                "created": session.created,
                "completed": session.completed,
                "participants_count": len(session.participants),
                "items_count": len(session.items),
                "total_votes": len(session.votes),
            }
        )

    return jsonify({"sessions": sessions_data})


@app.route("/api/sessions/<session_id>/move-to-completed", methods=["POST"])
def move_session_to_completed(session_id):
    """Move session from active to completed"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    try:
        session.move_to_completed()
        return jsonify({"success": True, "completed_at": session.completed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/<session_id>/start", methods=["POST"])
def start_session(session_id):
    """Start a session (draft -> active)"""
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    if session.status != "draft":
        return jsonify(
            {"error": f"Cannot start session in {session.status} state"}
        ), 400

    # Validate session has items
    if not session.items:
        return jsonify({"error": "Cannot start session without voting items"}), 400

    # Change status to active
    session.status = "active"
    session.save()

    # Emit real-time update
    socketio.emit("session_started", {"session_id": session_id})

    return jsonify({"success": True, "status": "active", "session": session.to_dict()})


@app.route("/api/sessions/<session_id>/complete", methods=["POST"])
def complete_session(session_id):
    """Complete a session (active -> completed)"""
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    if session.status != "active":
        return jsonify(
            {"error": f"Cannot complete session in {session.status} state"}
        ), 400

    # Mark as completed (this handles the status change and timestamp)
    session.mark_completed()
    session.save()

    # Emit real-time update
    socketio.emit(
        "session_completed",
        {"session_id": session_id, "completed_at": session.completed},
    )

    return jsonify(
        {
            "success": True,
            "status": "completed",
            "completed_at": session.completed,
            "session": session.to_dict(),
        }
    )


@app.route("/api/sessions/<session_id>/status", methods=["GET", "POST", "PUT"])
def session_status(session_id):
    """Get or update session status"""
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    if request.method == "GET":
        return jsonify(
            {
                "session_id": session_id,
                "status": session.status,
                "created": session.created,
                "completed": session.completed,
            }
        )

    # POST/PUT - Update status
    data = request.json
    if not data or "status" not in data:
        return jsonify({"error": "Status is required"}), 400

    new_status = data["status"]
    if new_status not in ["draft", "active", "completed"]:
        return jsonify(
            {"error": "Invalid status. Must be: draft, active, or completed"}
        ), 400

    old_status = session.status

    # Validate status transitions
    if old_status == "completed":
        return jsonify({"error": "Cannot change status of completed session"}), 400

    if old_status == "draft" and new_status == "completed":
        return jsonify(
            {"error": "Cannot complete draft session. Must be active first"}
        ), 400

    if new_status == "active" and not session.items:
        return jsonify({"error": "Cannot activate session without voting items"}), 400

    # Update status
    if new_status == "completed":
        session.mark_completed()
    else:
        session.status = new_status

    session.save()

    # Emit real-time update
    socketio.emit(
        "status_changed",
        {
            "session_id": session_id,
            "old_status": old_status,
            "new_status": new_status,
            "completed_at": session.completed if new_status == "completed" else None,
        },
    )

    return jsonify(
        {
            "success": True,
            "old_status": old_status,
            "new_status": new_status,
            "session": session.to_dict(),
        }
    )


@app.route("/api/sessions/<session_id>/items", methods=["POST"])
def add_session_item(session_id):
    """Add voting item to session"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = request.json
    if not data or "name" not in data:
        return jsonify({"error": "Item name is required"}), 400

    # Create new item
    new_item = {
        "id": len(session.items) + 1,
        "name": data["name"],
        "description": data.get("description", ""),
    }

    session.items.append(new_item)
    session.save()

    return jsonify({"success": True, "item": new_item})


@app.route("/api/sessions/<session_id>/items/<int:item_id>", methods=["DELETE"])
def remove_session_item(session_id, item_id):
    """Remove voting item from session"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Find and remove item
    session.items = [item for item in session.items if item["id"] != item_id]
    session.save()

    return jsonify({"success": True})


@app.route("/api/sessions/<session_id>/participants", methods=["POST"])
def add_participant(session_id):
    """Add a participant to a session"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404

    data = request.get_json()
    email = data.get("email")
    send_invitation = data.get("send_invitation", False)

    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    # Validate email format
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        return jsonify({"success": False, "error": "Invalid email format"}), 400

    # If invitation will be sent, validate email configuration
    if send_invitation:
        email_config = config_manager.get("email")
        if not email_config or not email_config.get("smtp_server"):
            return jsonify(
                {
                    "success": False,
                    "error": "Email configuration is required to send invitations. Please configure SMTP settings first.",
                    "error_type": "email_config_required",
                }
            ), 400

    # Generate participant ID and token
    participant_id = str(uuid.uuid4())
    participant_token = secrets.token_urlsafe(32)

    # Add participant
    session.participants[participant_id] = {
        "email": email,
        "token": participant_token,
        "voted": False,
        "votes": {},
        "added": datetime.now().isoformat(),
    }

    session.save()

    # Send invitation email if requested
    if send_invitation:
        try:
            # Get email service
            email_service = EmailService()

            # Generate voting link
            key_path = session.get_key_file_path()
            if not key_path.exists():
                key = Fernet.generate_key()
                with open(key_path, "wb") as f:
                    f.write(key)

            with open(key_path, "rb") as f:
                key = f.read()

            fernet = Fernet(key)

            # Create participant data for voting
            participant_data = {
                "session_id": session_id,
                "participant_id": participant_id,
                "email": email,
                "token": participant_token,
                "expires": (datetime.now(timezone.utc).timestamp() + 86400 * 30),
            }

            # Encrypt and encode
            encrypted = fernet.encrypt(json.dumps(participant_data).encode())
            encoded = base64.urlsafe_b64encode(encrypted).decode()
            voting_link = f"{request.host_url.rstrip('/')}/vote/{encoded}"

            # Send invitation email
            success, error_msg = email_service.send_invitation_email(
                recipient_email=email,
                session_title=session.title,
                session_description=session.description,
                voting_link=voting_link,
            )

            if success:
                logger.info(
                    f"Successfully sent invitation to {email} for session {session_id}"
                )
                return jsonify(
                    {
                        "success": True,
                        "participant_id": participant_id,
                        "participant_token": participant_token,
                        "invitation_sent": True,
                        "message": f"Participant added and invitation sent to {email}",
                    }
                )
            else:
                logger.error(f"Failed to send invitation to {email}: {error_msg}")
                return jsonify(
                    {
                        "success": True,
                        "participant_id": participant_id,
                        "participant_token": participant_token,
                        "invitation_sent": False,
                        "warning": f"Participant added but invitation failed to send: {error_msg}",
                    }
                )

        except Exception as e:
            logger.error(f"Error sending invitation to {email}: {str(e)}")
            return jsonify(
                {
                    "success": True,
                    "participant_id": participant_id,
                    "participant_token": participant_token,
                    "invitation_sent": False,
                    "warning": f"Participant added but invitation failed to send: {str(e)}",
                }
            )

    return jsonify(
        {
            "success": True,
            "participant_id": participant_id,
            "participant_token": participant_token,
        }
    )


@app.route(
    "/api/sessions/<session_id>/participants/<participant_id>", methods=["DELETE"]
)
def remove_participant(session_id, participant_id):
    """Remove a participant from a session"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404

    if participant_id not in session.participants:
        return jsonify({"success": False, "error": "Participant not found"}), 404

    # Remove participant
    del session.participants[participant_id]
    session.save()

    return jsonify({"success": True})


@app.route(
    "/api/sessions/<session_id>/participants/<participant_id>/link", methods=["GET"]
)
def get_participant_link(session_id, participant_id):
    """Get voting link for a specific participant"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404

    if participant_id not in session.participants:
        return jsonify({"success": False, "error": "Participant not found"}), 404

    participant = session.participants[participant_id]

    # Generate encrypted voting link
    key_path = session.get_key_file_path()
    if not key_path.exists():
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)

    with open(key_path, "rb") as f:
        key = f.read()

    fernet = Fernet(key)

    # Create participant data for voting
    participant_data = {
        "session_id": session_id,
        "participant_id": participant_id,
        "email": participant["email"],
        "token": participant["token"],
        "expires": (datetime.now(timezone.utc).timestamp() + 86400 * 30),  # 30 days
    }

    # Encrypt and encode
    encrypted = fernet.encrypt(json.dumps(participant_data).encode())
    encoded = base64.urlsafe_b64encode(encrypted).decode()

    voting_link = f"/vote/{encoded}"

    return jsonify(
        {
            "success": True,
            "voting_link": voting_link,
            "full_url": f"{request.host_url.rstrip('/')}{voting_link}",
        }
    )


@app.route("/api/sessions/<session_id>/send-invitations", methods=["POST"])
def send_all_invitations(session_id):
    """Send invitation emails to all participants in a session"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404

    if not session.participants:
        return jsonify({"success": False, "error": "No participants found"}), 400

    sent_count = 0
    failed_count = 0
    errors = []

    # Get email service
    email_service = EmailService()

    for participant_id, participant in session.participants.items():
        try:
            # Generate voting link
            key_path = session.get_key_file_path()
            if not key_path.exists():
                key = Fernet.generate_key()
                with open(key_path, "wb") as f:
                    f.write(key)

            with open(key_path, "rb") as f:
                key = f.read()

            fernet = Fernet(key)

            # Create participant data for voting
            participant_data = {
                "session_id": session_id,
                "participant_id": participant_id,
                "email": participant["email"],
                "token": participant["token"],
                "expires": (datetime.now(timezone.utc).timestamp() + 86400 * 30),
            }

            # Encrypt and encode
            encrypted = fernet.encrypt(json.dumps(participant_data).encode())
            encoded = base64.urlsafe_b64encode(encrypted).decode()
            voting_link = f"{request.host_url.rstrip('/')}/vote/{encoded}"

            # Send invitation email
            success, error_msg = email_service.send_invitation_email(
                recipient_email=participant["email"],
                session_title=session.title,
                session_description=session.description,
                voting_link=voting_link,
            )

            if success:
                sent_count += 1
            else:
                failed_count += 1
                errors.append(f"{participant['email']}: {error_msg}")

        except Exception as e:
            failed_count += 1
            errors.append(f"{participant['email']}: {str(e)}")

    return jsonify(
        {
            "success": True,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "errors": errors,
        }
    )


@app.route(
    "/api/sessions/<session_id>/participants/<participant_id>/invite", methods=["POST"]
)
def send_individual_invitation(session_id, participant_id):
    """Send invitation email to a specific participant"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({"success": False, "error": "Session not found"}), 404

        if participant_id not in session.participants:
            return jsonify({"success": False, "error": "Participant not found"}), 404

        participant = session.participants[participant_id]

        # Get email service
        email_service = EmailService()

        # Generate voting link
        key_path = session.get_key_file_path()
        if not key_path.exists():
            key = Fernet.generate_key()
            with open(key_path, "wb") as f:
                f.write(key)

        with open(key_path, "rb") as f:
            key = f.read()

        fernet = Fernet(key)

        # Create participant data for voting
        participant_data = {
            "session_id": session_id,
            "participant_id": participant_id,
            "email": participant["email"],
            "token": participant["token"],
            "expires": (datetime.now(timezone.utc).timestamp() + 86400 * 30),
        }

        # Encrypt and encode
        encrypted = fernet.encrypt(json.dumps(participant_data).encode())
        encoded = base64.urlsafe_b64encode(encrypted).decode()
        voting_link = f"{request.host_url.rstrip('/')}/vote/{encoded}"

        # Send invitation email
        success, error_msg = email_service.send_invitation_email(
            recipient_email=participant["email"],
            session_title=session.title,
            session_description=session.description,
            voting_link=voting_link,
        )

        if success:
            app.logger.info(
                f"Successfully sent individual invitation to {participant['email']} for session {session_id}"
            )
            return jsonify(
                {
                    "success": True,
                    "message": "Invitation sent successfully",
                    "participant_email": participant["email"],
                }
            )
        else:
            app.logger.error(
                f"Failed to send individual invitation to {participant['email']}: {error_msg}"
            )
            return jsonify({"success": False, "error": error_msg}), 500

    except Exception as e:
        app.logger.error(f"Error sending individual invitation: {str(e)}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/sessions/<session_id>/settings", methods=["PUT"])
def update_session_settings(session_id):
    """Update session settings"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404

    data = request.get_json()

    # Update settings
    if "anonymous" in data:
        session.settings["anonymous"] = bool(data["anonymous"])
    if "show_results_live" in data:
        session.settings["show_results_live"] = bool(data["show_results_live"])
    if "votes_per_participant" in data:
        session.settings["votes_per_participant"] = int(data["votes_per_participant"])

    session.save()

    return jsonify({"success": True})


@app.route("/api/sessions/<session_id>", methods=["PUT"])
def update_session(session_id):
    """Update session title and description"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404

    data = request.get_json()

    if "title" in data:
        session.title = data["title"]
    if "description" in data:
        session.description = data["description"]

    session.save()

    return jsonify({"success": True})


@app.route("/api/sessions/<session_id>/status", methods=["PUT"])
def update_session_status(session_id):
    """Update session status (draft/active/completed)"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = request.json or {}
    new_status = data.get("status")

    if new_status not in ["draft", "active", "completed"]:
        return jsonify({"error": "Invalid status"}), 400

    old_status = session.status
    session.status = new_status

    # Handle status transitions
    if new_status == "completed" and old_status != "completed":
        session.mark_completed()
        # Move to completed directory would happen here

    session.save()

    # Notify all participants of status change
    socketio.emit(
        "session_status_changed",
        {"session_id": session_id, "status": new_status},
        to=session_id,
    )

    return jsonify({"success": True, "status": new_status})


@app.route("/api/sessions/<session_id>/export/csv")
def export_session_csv(session_id):
    """Export session results as CSV"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Generate CSV content
    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(["Position", "Item Name", "Description", "Votes", "Percentage"])

    # Get results
    results = calculate_voting_results(session)

    # Write data
    for i, result in enumerate(results):
        writer.writerow(
            [
                i + 1,
                result["name"],
                result.get("description", ""),
                result["votes"],
                f"{result['percentage']:.1f}%",
            ]
        )

    # Create response
    csv_content = output.getvalue()
    response = app.response_class(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=session_{session_id}_results.csv"
        },
    )

    return response


@app.route("/api/sessions/<session_id>/analytics")
def get_session_analytics(session_id):
    """Get detailed analytics for a session"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Calculate analytics
    total_participants = len(session.participants)
    voted_participants = len(
        [p for p in session.participants.values() if p.get("voted", False)]
    )

    # Voting timeline
    vote_timeline = []
    for participant_id, participant in session.participants.items():
        if participant.get("voted") and participant.get("vote_timestamp"):
            vote_timeline.append(
                {
                    "timestamp": participant["vote_timestamp"],
                    "participant_id": participant_id
                    if not session.settings.get("anonymous", True)
                    else None,
                }
            )

    # Sort by timestamp
    vote_timeline.sort(key=lambda x: x["timestamp"])

    analytics = {
        "session_id": session_id,
        "title": session.title,
        "status": session.status,
        "created": session.created,
        "completed": session.completed,
        "total_participants": total_participants,
        "voted_participants": voted_participants,
        "participation_rate": round(voted_participants / total_participants * 100, 1)
        if total_participants > 0
        else 0,
        "total_items": len(session.items),
        "vote_timeline": vote_timeline,
        "settings": session.settings,
    }

    return jsonify(analytics)


@app.route("/api/sessions/<session_id>/duplicate", methods=["POST"])
def duplicate_session(session_id):
    """Create a duplicate of an existing session"""
    original_session = session_manager.get_session(session_id)
    if not original_session:
        return jsonify({"error": "Session not found"}), 404

    # Create new session with same structure
    new_session = VotingSession()
    new_session.title = f"{original_session.title} (Copy)"
    new_session.description = original_session.description
    new_session.items = original_session.items.copy()
    new_session.settings = original_session.settings.copy()
    new_session.status = "draft"  # Always start as draft

    # Save the new session
    new_session.save()
    session_manager.cache[new_session.id] = new_session

    return jsonify(
        {
            "success": True,
            "session_id": new_session.id,
            "session": new_session.to_dict(),
        }
    )


@app.route("/api/sessions/<session_id>/results")
def get_session_results(session_id):
    """Get voting results with calculations"""
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Calculate results
    results = calculate_voting_results(session)

    return jsonify(
        {
            "session_id": session_id,
            "session_title": session.title,
            "status": session.status,
            "total_participants": len(session.participants),
            "votes_cast": len(
                [p for p in session.participants.values() if p.get("voted")]
            ),
            "results": results,
        }
    )


def calculate_voting_results(session):
    """Calculate and sort voting results"""
    if not session.items or not session.votes:
        return []

    # Initialize vote counts
    results = []
    for item in session.items:
        results.append(
            {
                "id": item["id"],
                "name": item["name"],
                "description": item.get("description", ""),
                "votes": 0,
                "percentage": 0.0,
            }
        )

    # Count votes
    total_votes = 0
    for participant_votes in session.votes.values():
        if isinstance(participant_votes, dict):
            for item_id, vote_count in participant_votes.items():
                item_id = int(item_id)
                vote_count = int(vote_count)
                # Find the result item
                for result in results:
                    if result["id"] == item_id:
                        result["votes"] += vote_count
                        total_votes += vote_count
                        break

    # Calculate percentages
    if total_votes > 0:
        for result in results:
            result["percentage"] = round((result["votes"] / total_votes) * 100, 1)

    # Sort by votes (descending)
    results.sort(key=lambda x: x["votes"], reverse=True)

    return results


@app.route("/vote/<encrypted_data>", methods=["GET", "POST"])
def vote_page(encrypted_data):
    """Participant voting page"""
    # Decrypt participant data to validate the link
    participant_data = decrypt_participant_data(encrypted_data)

    if not participant_data:
        return "Invalid or expired voting link", 400

    # Get session data
    session = session_manager.get_session(participant_data["session_id"])
    if not session:
        return "Session not found", 404

    # Handle form submission (fallback method)
    if request.method == "POST":
        try:
            # Get vote data from form
            votes = {}
            for item in session.items:
                vote_count = request.form.get(f"vote_{item['id']}", "0")
                votes[item["id"]] = int(vote_count)

            participant_id = participant_data["participant_id"]

            # Store the vote in session.votes
            if not hasattr(session, "votes") or session.votes is None:
                session.votes = {}

            session.votes[participant_id] = votes

            # Mark participant as voted
            if participant_id in session.participants:
                session.participants[participant_id]["voted"] = True
                session.participants[participant_id]["vote_timestamp"] = (
                    datetime.now().isoformat()
                )

            # Save session
            session.save()

            logger.info(
                f"Vote submitted by participant {participant_id} in session {session.id} via form submission"
            )

            # Show success page
            return render_template(
                "vote.html",
                encrypted_data=encrypted_data,
                participant_data=participant_data,
                session=session,
                success=True,
            )

        except Exception as e:
            logger.error(f"Error processing form vote submission: {e}")
            return render_template(
                "vote.html",
                encrypted_data=encrypted_data,
                participant_data=participant_data,
                session=session,
                error="Failed to submit votes. Please try again.",
            )

    return render_template(
        "vote.html",
        encrypted_data=encrypted_data,
        participant_data=participant_data,
        session=session,
    )


@app.route("/present/<session_id>")
def presentation_mode(session_id):
    """Full-screen presentation mode for results"""
    session = session_manager.get_session(session_id)

    if not session:
        return "Session not found", 404

    # Convert session to JSON-serializable format
    session_dict = session.to_dict()
    return render_template("presentation.html", session=session_dict)


@app.route("/results/<session_id>")
def results_page(session_id):
    """Results page for viewing voting results"""
    session = session_manager.get_session(session_id)
    if not session:
        return "Session not found", 404

    # Convert session to JSON-serializable format
    session_dict = session.to_dict()
    return render_template("results.html", session=session_dict)


# WebSocket events for real-time features
@socketio.on("connect")
def on_connect():
    """Handle client connection"""
    logger.info("Client connected")


@socketio.on("disconnect")
def on_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")


@socketio.on("join_session")
def on_join_session(data):
    """Join a session room for real-time updates"""
    session_id = data.get("session_id")
    if session_id:
        join_room(session_id)
        logger.info(f"Client joined session {session_id}")
        # Send confirmation back to client
        emit("session_joined", {"session_id": session_id})


@socketio.on("leave_session")
def on_leave_session(data):
    """Leave a session room"""
    session_id = data.get("session_id")
    if session_id:
        leave_room(session_id)
        logger.info(f"Client left session {session_id}")
        emit("session_left", {"session_id": session_id})


@socketio.on("vote_submitted")
def on_vote_submitted(data):
    """Handle vote submission from participant"""
    session_id = data.get("session_id")
    votes = data.get("votes", {})
    participant_id = data.get("participant_id")

    if not session_id or not votes:
        emit("vote_error", {"error": "Invalid vote data"})
        return

    # Get session and update votes
    session = session_manager.get_session(session_id)
    if not session:
        emit("vote_error", {"error": "Session not found"})
        return

    # Store vote (simplified for now)
    if participant_id:
        session.votes[participant_id] = votes
        session.save()

        # Broadcast vote update to all participants in the session
        socketio.emit(
            "vote_update",
            {
                "session_id": session_id,
                "votes": votes,
                "participant_id": participant_id
                if not session.settings.get("anonymous", True)
                else None,
            },
            to=session_id,
        )

        # Send confirmation to voter
        emit("vote_confirmed", {"session_id": session_id})

        logger.info(f"Vote submitted for session {session_id}")


@socketio.on("request_results")
def on_request_results(data):
    """Send current results to client"""
    session_id = data.get("session_id")
    session = session_manager.get_session(session_id)

    if session:
        # Calculate current results
        results = calculate_session_results(session)
        emit("results_update", {"session_id": session_id, "results": results})


def calculate_session_results(session):
    """Calculate voting results for a session"""
    if not session.votes:
        return []

    # Initialize item vote counts
    item_totals = {}
    for item in session.items:
        item_totals[str(item["id"])] = 0

    # Sum up votes from all participants
    for participant_votes in session.votes.values():
        for item_id, vote_count in participant_votes.items():
            if item_id in item_totals:
                item_totals[item_id] += int(vote_count)

    # Create results list with percentages
    total_votes = sum(item_totals.values())
    results = []

    for item in session.items:
        item_id = str(item["id"])
        vote_count = item_totals.get(item_id, 0)
        percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0

        results.append(
            {
                "id": item["id"],
                "name": item["name"],
                "description": item.get("description", ""),
                "votes": vote_count,
                "percentage": round(percentage, 1),
            }
        )

    # Sort by vote count (descending)
    results.sort(key=lambda x: x["votes"], reverse=True)
    return results


@app.route("/api/vote", methods=["POST"])
def api_vote():
    """Handle participant voting API calls"""
    try:
        data = request.get_json()
        encrypted_data = data.get("encrypted_data")
        action = data.get("action")

        logger.info(
            f"Vote API called with action: {action}, encrypted_data length: {len(encrypted_data) if encrypted_data else 0}"
        )

        if not encrypted_data:
            return jsonify({"error": "Missing encrypted data"}), 400

        # Decrypt participant data
        participant_data = decrypt_participant_data(encrypted_data)
        logger.info(f"Decryption result: {participant_data is not None}")

        if not participant_data:
            logger.warning("Failed to decrypt participant data")
            return jsonify({"error": "Invalid or expired voting link"}), 400

        # Get session
        session = session_manager.get_session(participant_data["session_id"])
        if not session:
            return jsonify({"error": "Session not found"}), 404

        # Check session status for voting
        if action == "submit" and session.status == "completed":
            return jsonify(
                {
                    "error": "This voting session has ended. Votes can no longer be submitted."
                }
            ), 400

        if action == "submit" and session.status == "draft":
            return jsonify(
                {
                    "error": "This voting session has not started yet. Please wait for the session to begin."
                }
            ), 400

        if action == "validate":
            # Return session data for voting interface
            return jsonify(
                {
                    "success": True,
                    "session": {
                        "id": session.id,
                        "title": session.title,
                        "description": session.description,
                        "items": session.items,
                        "settings": session.settings,
                    },
                    "participant": {
                        "id": participant_data["participant_id"],
                        "email": participant_data["email"],
                    },
                }
            )

        elif action == "submit":
            # Handle vote submission
            votes = data.get("votes", {})
            participant_id = participant_data["participant_id"]

            # Validate votes
            if not votes:
                return jsonify({"error": "No votes provided"}), 400

            # Store the vote in session.votes
            if not hasattr(session, "votes") or session.votes is None:
                session.votes = {}

            session.votes[participant_id] = votes

            # Mark participant as voted
            if participant_id in session.participants:
                session.participants[participant_id]["voted"] = True
                session.participants[participant_id]["vote_timestamp"] = (
                    datetime.now().isoformat()
                )

            # Save session
            session.save()

            # Emit real-time update
            socketio.emit(
                "vote_submitted",
                {
                    "session_id": session.id,
                    "participant_id": participant_id,
                    "total_votes": len(session.votes),
                },
                to=f"session_{session.id}",
            )

            logger.info(
                f"Vote submitted by participant {participant_id} in session {session.id}"
            )
            return jsonify({"success": True, "message": "Vote submitted successfully"})

        else:
            return jsonify({"error": "Invalid action"}), 400

    except Exception as e:
        logger.error(f"Error in vote API: {e}")
        return jsonify({"error": "Internal server error"}), 500


def decrypt_participant_data(encrypted_data):
    """Decrypt participant data from voting link"""
    try:
        logger.debug(f"Attempting to decrypt data: {encrypted_data[:50]}...")

        # Decode base64 (add padding if needed)
        # URL-safe base64 may be missing padding
        encrypted_data += "=" * (-len(encrypted_data) % 4)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data)

        # We need to find the session to get the key
        # For now, we'll try all session keys (not efficient but works for demo)
        for date_dir in ACTIVE_DIR.iterdir():
            if date_dir.is_dir():
                for key_file in date_dir.glob("*.key"):
                    try:
                        with open(key_file, "rb") as f:
                            key = f.read()

                        fernet = Fernet(key)
                        decrypted = fernet.decrypt(encrypted_bytes)
                        participant_data = json.loads(decrypted.decode())

                        # Verify the session exists
                        if session_manager.get_session(participant_data["session_id"]):
                            return participant_data

                    except Exception:
                        continue  # Try next key

        return None

    except Exception as e:
        logger.error(f"Error decrypting participant data: {e}")
        return None


def get_network_ip():
    """Get the local network IP address"""
    try:
        # Connect to a remote server to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def create_ssl_context():
    """Create SSL context for HTTPS if certificates are available"""
    cert_file = Path("ssl/cert.pem")
    key_file = Path("ssl/key.pem")

    if cert_file.exists() and key_file.exists():
        # Use modern TLS protocol for better security
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        return context
    return None


if __name__ == "__main__":
    # Configuration
    HOST = "0.0.0.0"
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG = (
        os.environ.get("DEBUG", "False").lower() == "true"
    )  # Changed default to False

    # Check for SSL certificates
    ssl_context = create_ssl_context()
    protocol = "https" if ssl_context else "http"

    logger.info("Starting Voting Application...")

    # Get network information
    local_ip = get_network_ip()
    hostname = socket.gethostname()

    print("\n" + "=" * 60)
    print("🗳️  VOTE FOR ME - VOTING PLATFORM")
    print("=" * 60)
    print(f"📍 Local Access:     {protocol}://127.0.0.1:{PORT}")
    print(f"🌐 Network Access:   {protocol}://{local_ip}:{PORT}")
    print(f"🖥️  Host Name:       {protocol}://{hostname}.local:{PORT}")

    if ssl_context:
        print("🔒 HTTPS:            ✅ SSL certificates found and loaded")
    else:
        print(
            "🔒 HTTPS:            ⚠️  HTTP only (add ssl/cert.pem & ssl/key.pem for HTTPS)"
        )

    print("=" * 60)
    print("📋 Quick Start:")
    print("   1. Open any URL above in your browser")
    print("   2. Create a new voting session")
    print("   3. Add voting items")
    print("   4. Share participant links")
    print("   5. View results in real-time")
    print("=" * 60)
    print("⚠️  Network Access Notes:")
    print("   • Ensure firewall allows port", PORT)
    print("   • Mobile devices: Use network IP address")

    if not ssl_context:
        print("   • For HTTPS: Add SSL certificates to ssl/ directory")
        print("     - ssl/cert.pem (certificate file)")
        print("     - ssl/key.pem (private key file)")

    print("   • For production: Set SECRET_KEY environment variable")
    print("=" * 60)
    print("🛑 Press Ctrl+C to stop the server")
    print("=" * 60 + "\n")

    try:
        # Configure SocketIO for production stability
        if ssl_context:
            # For HTTPS with SSL - pass cert/key files as a tuple
            socketio.run(
                app,
                debug=DEBUG,
                host=HOST,
                port=PORT,
                ssl_context=("ssl/cert.pem", "ssl/key.pem"),
                use_reloader=False,  # Disable reloader to prevent double startup
            )
        else:
            # HTTP mode - optimized for stability
            socketio.run(
                app,
                debug=DEBUG,
                host=HOST,
                port=PORT,
                use_reloader=False,  # Critical: Disable reloader to prevent socket conflicts
            )
    except KeyboardInterrupt:
        print("\n\n👋 Voting Application stopped. Goodbye!")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        print(f"\n❌ Error starting server: {e}")
        print("💡 Try running as administrator or check if port is already in use.")
    finally:
        # Ensure cleanup
        logger.info("Server shutdown complete")
