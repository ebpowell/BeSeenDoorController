import logging
import time
import requests
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DoorControllerSync")

class ExternalSystemError(Exception):
    """Raised when the door controller hardware returns an unauthenticated/error state."""
    pass


class DoorController:
    def __init__(self, base_url: str, username: str, password: str, session_timeout_secs: int = 180):
        self.base_url = base_url
        self.username = username
        self.password = password
        
        # Hard token lifetime limit enforced by the physical controller board (e.g., 3 minutes)
        self.session_timeout_secs = session_timeout_secs
        self.last_login_time = 0.0
        
        # 1. Instantiate the single, shared persistent session with a unified cookie jar
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BeSeenAccessDaemon/2.0",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        
        # 2. Instantiating the subclass, explicitly passing 'self' to share the session
        self.fobs_manager = FobsSubclass(parent_controller=self)

    def login(self) -> bool:
        """Executes a login handshake and stores cookies/tokens in self.session.cookies."""
        login_url = urljoin(self.base_url, "/login_handler")
        payload = {"username": self.username, "password": self.password}
        
        try:
            logger.info(f"Initiating login handshake with controller at {self.base_url}...")
            response = self.session.post(login_url, data=payload, timeout=10)
            
            # If redirected to the login console, auth failed
            if response.status_code == 200 and "ACT_ID_21" not in response.url:
                logger.info("Login handshake successful. Cookies saved in session jar.")
                self.last_login_time = time.time()
                return True
            else:
                raise ExternalSystemError("Authentication failed: redirected to fallback login.")
        except Exception as e:
            logger.error(f"Failed to log in to controller: {str(e)}")
            return False

    def is_session_viable(self) -> bool:
        """
        Dual-layer verification checking both local time-elapsed limits
        and executing a lightweight ping test to the hardware.
        """
        # Layer 1: Check elapsed local time
        elapsed = time.time() - self.last_login_time
        if elapsed >= self.session_timeout_secs:
            logger.warning(f"Session age ({elapsed:.1f}s) exceeds threshold ({self.session_timeout_secs}s).")
            return False
            
        # Layer 2: Test ping the controller with the current session cookies
        ping_url = urljoin(self.base_url, "/session_ping")
        try:
            response = self.session.get(ping_url, timeout=5, allow_redirects=False)
            # A 302 redirect back to login (/ACT_ID_21) means the hardware invalidated the token
            if response.status_code == 302 or "ACT_ID_21" in response.headers.get("Location", ""):
                logger.warning("Hardware invalidated session token early. Redirect detected.")
                return False
            return response.status_code == 200
        except Exception:
            return False

    def verify_or_reauth(self):
        """Pre-emptively guarantees an active session before high-risk execution loops."""
        if not self.is_session_viable():
            logger.info("Session expired or invalid. Running pre-emptive re-authentication...")
            if not self.login():
                raise ExternalSystemError("Failed to re-authenticate session prior to sync phase.")
        else:
            logger.info("Current session is verified as active and healthy.")


class FobsSubclass:
    """Manages adding, updating, and removing individual key fobs."""
    def __init__(self, parent_controller: DoorController):
        self.parent = parent_controller

    def add_fob(self, fob_id: int, record_id: int) -> bool:
        # Reuses the exact same persistent session and active cookies from the parent controller
        add_url = urljoin(self.parent.base_url, "/add_fob_endpoint")
        payload = {"fob_id": fob_id, "record_id": record_id}
        
        try:
            response = self.parent.session.post(add_url, data=payload, timeout=10)
            if "ACT_ID_21" in response.url:
                raise ExternalSystemError("Hardware rejected action: session redirected to login page.")
                
            logger.info(f"Successfully added Fob {fob_id} (Record {record_id}) to controller.")
            return True
        except Exception as e:
            logger.error(f"Failed to add fob {fob_id}: {str(e)}")
            return False

# =============================================================================
# EXECUTING THE WORKFLOW (WITH PRE-EMPTIVE CHECK)
# =============================================================================

def run_synchronization_cycle(controller: DoorController, missing_fobs_queue: list):
    # Phase 1: Login and process main dynamic batches
    controller.login()
    
    logger.info("Processing main batch updates...")
    time.sleep(5)  # Simulate 5 seconds (or minutes in production) of processing activity
    
    # Phase 2: Complete Main Batches, prepare for follow-on pass
    logger.info("Main synchronization pass complete. Preparing follow-on queue additions.")
    
    # 🌟 CRITICAL SAFEGUARD: Pre-emptively verify session health and refresh if timed out
    try:
        controller.verify_or_reauth()
    except ExternalSystemError as e:
        logger.critical(f"Aborting follow-on pass: {str(e)}")
        return

    # Phase 3: Execute follow-on pass safely
    for fob_id, record_id in missing_fobs_queue:
        success = controller.fobs_manager.add_fob(fob_id, record_id)
        if not success:
            logger.error(f"Follow-on addition failed for Fob {fob_id}.")