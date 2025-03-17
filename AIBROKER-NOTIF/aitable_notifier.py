import requests
import schedule
import time
import json
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('notifier.log'),
        logging.StreamHandler()
    ]
)

# Set UTF-8 encoding for standard output and error
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Try to import winotify - best for Windows 11 notifications
try:
    from winotify import Notification, audio
    print("Using winotify for Windows 11 notifications")
    WINOTIFY_AVAILABLE = True
except ImportError:
    print("winotify not available, falling back to PowerShell notifications")
    WINOTIFY_AVAILABLE = False
    import subprocess

# AITable API Details
API_URL = "https://ai-broker.korunaassist.com/fusion/v1/datasheets/dst1vag1MekDBbrzoS/records"
HEADERS = {"Authorization": "Bearer usk5YzjFkoAuRfYFNcPCM0j"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
LAST_RECORD_FILE = os.path.join(BASE_DIR, "last_record.json")
ICON_PATH = os.path.join(BASE_DIR, "ka.png") 

# Check different locations for icon file
icon_locations = [
    os.path.join(BASE_DIR, "ka.png"),
    os.path.join(BASE_DIR, "logo", "ka.png"),
    os.path.join(BASE_DIR, "assets", "ka.png"),
    os.path.join(BASE_DIR, "icons", "ka.png")
]

for path in icon_locations:
    if os.path.exists(path):
        ICON_PATH = path
        print(f"Found icon at: {ICON_PATH}")
        break

def get_current_record_count():
    try:
        response = requests.get(API_URL, headers=HEADERS)
        data = response.json()
        return data.get("data", {}).get("total", 0)
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None

def save_last_record_count(count):
    try:
        with open(LAST_RECORD_FILE, "w") as f:
            json.dump({"last_count": count}, f)
    except Exception as e:
        print(f"❌ Error saving last record count: {e}")

def load_last_record_count():
    try:
        with open(LAST_RECORD_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_count", 0)
    except FileNotFoundError:
        return 0  # If no file exists, assume no previous records
    except Exception as e:
        print(f"❌ Error loading last record count: {e}")
        return 0

def show_winotify_notification(title, message):
    """Show a Windows 11 notification using winotify"""
    toast = Notification(
        app_id="AI Broker",  # This appears in the notification
        title=title,
        msg=message,
        duration="short",
        icon=ICON_PATH if os.path.exists(ICON_PATH) else None
    )
    
    # Add sound effect to make it more noticeable
    toast.set_audio(audio.Default, loop=False)
    
    # Show the notification
    toast.show()
    print(f"✅ Sent notification: {title}")

def show_powershell_notification(title, message):
    """Show a Windows notification using PowerShell as fallback"""
    # Escape single quotes in the message and title
    safe_title = title.replace("'", "''")
    safe_message = message.replace("'", "''")
    
    # PowerShell command to show notification - simpler version
    ps_command = f'''
    powershell -Command "& {{
        $null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
        $null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
        
        $template = @'
        <toast>
            <visual>
                <binding template='ToastText02'>
                    <text id='1'>{safe_title}</text>
                    <text id='2'>{safe_message}</text>
                </binding>
            </visual>
        </toast>
        '@
        
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('AI Broker').Show($toast)
    }}"
    '''
    
    try:
        subprocess.run(ps_command, shell=True, check=False)
        print(f"✅ Sent PowerShell notification: {title}")
    except Exception as e:
        print(f"❌ Error sending PowerShell notification: {e}")

def show_notification(new_records):
    """Show notification using the best available method"""
    title = "AI Broker Notification"
    message = f"📢 New Data Entry!\n{new_records} new record{'s' if new_records > 1 else ''} added."
    
    try:
        if WINOTIFY_AVAILABLE:
            show_winotify_notification(title, message)
        else:
            show_powershell_notification(title, message)
    except Exception as e:
        print(f"❌ Notification error: {e}")

def check_new_records():
    print("🔄 Checking for new records...")
    last_count = load_last_record_count()
    current_count = get_current_record_count()

    if current_count is None:
        return 

    if current_count > last_count:
        new_records = current_count - last_count
        print(f"🆕 {new_records} new records added!")
        show_notification(new_records)

    # Save the updated record count
    save_last_record_count(current_count)

# Run every 10 seconds
schedule.every(10).seconds.do(check_new_records)
initial_count = get_current_record_count()
if initial_count is not None:
    save_last_record_count(initial_count)

# Keep the script running
while True:
    try:
        schedule.run_pending()
        time.sleep(1)
    except KeyboardInterrupt:
        print("Monitoring stopped by user")
        break
    except Exception as e:
        print(f"❌ Error in main loop: {e}")
        time.sleep(5)  # Wait before retrying