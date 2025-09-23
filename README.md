# Vote For Me - Interactive Voting Platform

A modern, web-based voting application with real-time results, anonymous participation, and presentation modes.

## 🔗 Important Links

- **Main App**: <http://localhost:5000> (or <https://localhost:5000> with SSL)
- **Email Testing** (dev): <http://localhost:8025>

---

## ✨ Key Features

- **📊 Real-time Voting**: Interactive point allocation with live results
- **📧 Email Integration**: Automated invitations with encrypted voting links
- **🎨 Presentation Mode**: Full-screen results display perfect for meetings
- **🔒 Security**: AES-256 encryption and anonymous voting support
- **📱 Mobile Friendly**: Responsive design works on all devices
- **⚙️ Easy Setup**: One-command installation with automatic dependencies

## 🚀 Installation & Setup

### Prerequisites

- **Python 3.8+** - [Download here](https://www.python.org/downloads/)
- **Git** (optional) - For cloning the repository

### Quick Start

#### Windows (Recommended)

```batch
# Clone or download the repository
git clone https://github.com/niksavis/vote-for-me.git
cd vote-for-me

# For development (includes email testing server)
run-development.bat

# For production (requires email configuration)
run-production.bat
```

#### All Platforms (Manual)

```bash
# Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies and run
pip install -r requirements.txt
python app.py
```

### Access Your Application

After starting, you'll see URLs like:

```text
🗳️  VOTE FOR ME - VOTING PLATFORM
============================
📍 Local Access:     http://127.0.0.1:5000
🌐 Network Access:   http://192.168.1.100:5000
```

Open any URL in your browser to get started!

### HTTPS Setup (Optional)

The app automatically detects SSL certificates and switches between HTTP and HTTPS modes:

**🚀 First Time Setup (No SSL certificates)**:

- App runs on HTTP only: <http://localhost:5000>
- This is the default mode for new installations

**🔒 With SSL Certificates**:

- App automatically switches to HTTPS only: <https://localhost:5000>
- HTTP will not be available once certificates are present

To enable HTTPS, generate SSL certificates:

```bash
# Generate self-signed certificates for local development
python generate_ssl.py
```

After generating certificates:

- **Local HTTPS**: <https://localhost:5000> (replaces HTTP)
- **Network HTTPS**: <https://YOUR_IP:5000>

**Important**: The app runs on either HTTP OR HTTPS, never both simultaneously. SSL certificates determine which mode is used.

**Note**: Self-signed certificates will show a browser security warning that you can safely bypass for local development.

## 📋 How to Use

### Creating Your First Voting Session

1. **Open the app** in your browser
2. **Click "Create New Session"** on the home page
3. **Add your voting details**:
   - Title (e.g., "Team Lunch Choice", "Feature Priority")
   - Description (optional context)
   - Voting items (the options people vote on)
4. **Add participants** by email address
5. **Send invitations** - each person gets a unique voting link
6. **Monitor results** in real-time as votes come in

### Viewing Results

- **Live Results**: Watch votes update in real-time on the admin page
- **Presentation Mode**: Full-screen display perfect for meetings
- **Export Data**: Download results as CSV files

### Email Setup

**Development**: Email works automatically with built-in test server  
**Production**: Configure SMTP settings at `/config` page (Gmail, Outlook, etc.)

## 🛠️ Common Issues

### Port Already in Use

If you see an error like "port already in use" or "address already in use":

**Option 1: Change the port before running**

```batch
# Windows (Command Prompt)
set PORT=5001
run-development.bat

# Windows (PowerShell)
$env:PORT=5001
run-development.bat

# macOS/Linux
export PORT=5001
python app.py
```

**Option 2: Kill processes using port 5000**

```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <process_id> /F

# macOS/Linux
lsof -ti:5000 | xargs kill -9
```

### Missing Dependencies

```bash
# Reinstall requirements
pip install -r requirements.txt
```

### Permission Errors

- **Windows**: Run as Administrator
- **macOS/Linux**: Use `sudo` or check folder permissions

### Python Not Found

- Install Python 3.8+ from [python.org](https://www.python.org/downloads/)
- Make sure it's added to your PATH

---

**Status**: Production Ready (v0.2.0) | **License**: MIT License (see [LICENSE](LICENSE))
