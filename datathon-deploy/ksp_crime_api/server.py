import os
import subprocess
import sys
import site

# 1. Force install ONLY the lightweight API dependencies
print("Installing backend dependencies...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--no-cache-dir", "-r", "requirements.txt"])
print("Dependencies installed successfully!")

# 2. Add the user site-packages directory to Python's system path
user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.insert(0, user_site)

# 3. Import and boot
import uvicorn
from app.main import app

if __name__ == '__main__':
    port = int(os.environ.get('X_ZOHO_CATALYST_LISTEN_PORT', 8080))
    uvicorn.run(app, host='0.0.0.0', port=port)
