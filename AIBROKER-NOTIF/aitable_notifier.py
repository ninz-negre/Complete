import requests
import schedule
import time
import json
import os
import sys
import logging
from datetime import datetime

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('notifier.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Set UTF-8 encoding for standard output and error
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Try to import winotify with better error handling
try:
    from winotify import Notification, audio
    logger.info("Successfully initialized winotify for Windows 11 notifications")
    WINOTIFY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"winotify not available ({str(e)}), falling back to PowerShell notifications")
    WINOTIFY_AVAILABLE = False
    import subprocess

# AITable API Details
API_URL = "https://ai-broker.korunaassist.com/fusion/v1/datasheets/dst1vag1MekDBbrzoS/records"
HEADERS = {"Authorization": "Bearer usk5YzjFkoAuRfYFNcPCM0j"}

# File paths setup with better organization
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAST_RECORD_FILE = os.path.join(BASE_DIR, "last_record.json")
ICON_LOCATIONS = [
    os.path.join(BASE_DIR, "ka.png"),
    os.path.join(BASE_DIR, "logo", "ka.png"),
    os.path.join(BASE_DIR, "assets", "ka.png"),
    os.path.join(BASE_DIR, "icons", "ka.png")
]

# Find icon path
ICON_PATH = next((path for path in ICON_LOCATIONS if os.path.exists(path)), None)
if ICON_PATH:
    logger.info(f"Found icon at: {ICON_PATH}")
else:
    logger.warning("No icon found in any of the specified locations")

class NotificationManager:
    @staticmethod
    def show_winotify_notification(title, message):
        """Show a Windows 11 notification using winotify"""
        try:
            toast = Notification(
                app_id="AI Broker",
                title=title,
                msg=message,
                duration="long",  # Changed to long duration
                icon=ICON_PATH
            )
            # Set to alarm sound for more attention
            toast.set_audio(audio.LoopingAlarm, loop=True)
            
            # Make notification persistent
            toast.add_actions(label="View Details", launch="")
            
            toast.show()
            logger.info(f"Successfully sent winotify notification: {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send winotify notification: {str(e)}")
            return False

    @staticmethod
    def show_powershell_notification(title, message):
        """Show a Windows notification using PowerShell as fallback"""
        try:
            safe_title = title.replace("'", "''")
            safe_message = message.replace("'", "''")
            
            ps_command = f'''
            powershell -Command "& {{
                $null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
                $null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
                
                $template = @'
                <toast scenario='alarm'>
                    <visual>
                        <binding template='ToastGeneric'>
                            <text id='1'>{safe_title}</text>
                            <text id='2'>{safe_message}</text>
                        </binding>
                    </visual>
                    <audio src='ms-winsoundevent:Notification.Looping.Alarm' loop='true'/>
                    <actions>
                        <action content='View Details' arguments=''/>
                    </actions>
                </toast>
                '@
                
                $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
                $xml.LoadXml($template)
                $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('AI Broker').Show($toast)
            }}"
            '''
            
            subprocess.run(ps_command, shell=True, check=True, capture_output=True)
            logger.info(f"Successfully sent PowerShell notification: {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send PowerShell notification: {str(e)}")
            return False

    @staticmethod
    def show_fallback_notification():
        """Show a basic notification using alternative methods"""
        try:
            # Try using Windows-specific command
            os.system('msg * "New AI Broker notification!"')
            return True
        except:
            return False

class AITableMonitor:
    def __init__(self):
        self.notification_manager = NotificationManager()
        self.last_error_time = None
        self.error_count = 0
        self.notification_attempts = 0
        self.max_notification_attempts = 3

    def get_current_record_count(self):
        try:
            response = requests.get(API_URL, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            count = data.get("data", {}).get("total", 0)
            logger.info(f"Successfully fetched record count: {count}")
            self.reset_error_state()
            return count
        except requests.exceptions.RequestException as e:
            self.handle_error(f"Failed to fetch data: {str(e)}")
            return None

    def save_last_record_count(self, count):
        try:
            data = {
                "last_count": count,
                "timestamp": datetime.now().isoformat()
            }
            with open(LAST_RECORD_FILE, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Successfully saved record count: {count}")
        except Exception as e:
            self.handle_error(f"Failed to save record count: {str(e)}")

    def load_last_record_count(self):
        try:
            if not os.path.exists(LAST_RECORD_FILE):
                logger.info("No previous record file found, starting fresh")
                return 0

            with open(LAST_RECORD_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                count = data.get("last_count", 0)
                logger.info(f"Successfully loaded last record count: {count}")
                return count
        except Exception as e:
            self.handle_error(f"Failed to load record count: {str(e)}")
            return 0

    def show_notification(self, new_records):
        title = "🔔 AI Broker Alert!"  # More attention-grabbing title
        message = f"📢 New Data Entry!\n{new_records} new record{'s' if new_records > 1 else ''} added."
        
        notification_sent = False
        self.notification_attempts = 0
        
        while not notification_sent and self.notification_attempts < self.max_notification_attempts:
            self.notification_attempts += 1
            
            if WINOTIFY_AVAILABLE:
                notification_sent = self.notification_manager.show_winotify_notification(title, message)
                if not notification_sent:
                    notification_sent = self.notification_manager.show_powershell_notification(title, message)
            else:
                notification_sent = self.notification_manager.show_powershell_notification(title, message)
            
            if not notification_sent:
                notification_sent = self.notification_manager.show_fallback_notification()
                time.sleep(2)  # Wait before retry
        
        if not notification_sent:
            logger.error("Failed to show notification after multiple attempts")

    def check_new_records(self):
        logger.info("Checking for new records...")
        last_count = self.load_last_record_count()
        current_count = self.get_current_record_count()

        if current_count is None:
            return

        if current_count > last_count:
            new_records = current_count - last_count
            logger.info(f"Found {new_records} new records!")
            self.show_notification(new_records)
            self.save_last_record_count(current_count)

    def handle_error(self, error_message):
        current_time = time.time()
        
        if self.last_error_time is None or (current_time - self.last_error_time) > 300:  # 5 minutes
            self.error_count = 1
        else:
            self.error_count += 1

        self.last_error_time = current_time
        logger.error(f"Error ({self.error_count}): {error_message}")

    def reset_error_state(self):
        if self.error_count > 0:
            self.error_count = 0
            self.last_error_time = None
            logger.info("Error state reset after successful operation")

    def run(self):
        logger.info("Starting AITable Monitor...")
        
        # Show startup notification
        self.notification_manager.show_winotify_notification(
            "AI Broker Started",
            "Monitoring system is now active and watching for updates."
        )
        
        # Initialize with current count
        initial_count = self.get_current_record_count()
        if initial_count is not None:
            self.save_last_record_count(initial_count)

        # Schedule regular checks
        schedule.every(10).seconds.do(self.check_new_records)
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.handle_error(f"Error in main loop: {str(e)}")
                time.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    monitor = AITableMonitor()
    monitor.run()