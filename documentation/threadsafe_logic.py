import threading
import logging
from typing import List

# =============================================================================
# FIXED IMPLEMENTATION: ISOLATED STATE PATTERN
# =============================================================================

class AccessSynchronizer(ControllerScheduler):
    def __init__(self, username, password, config):
        super().__init__(db_mgr, use_runtime_schedule=True)
        self.username = username
        self.password = password
        self.config = config

    def execute_action(self, controller_url: str, limit_changes=None):
        logging.info(f"Executing synchronization for: {controller_url}")
        # The return value captures changes locally
        total_changes = self.synchronize_access(controller_url, limit_changes)
        logging.info(f"Sync complete for {controller_url}. Verified changes: {total_changes}")

    def synchronize_access(self, controller_url: str, limit_changes=None) -> int:
        """
        FIX 1: All sync state (changes_made, current_batch, etc.) is kept
        strictly as a local, call-stack isolated variable.
        """
        changes_made = 0  # Local variable; immune to thread overrides
        
        # Calculate dynamic batches locally
        batches = self.calculate_batches(controller_url)
        
        for batch_idx, batch in enumerate(batches, 1):
            batch_changes = 0
            for fob in batch:
                mismatch = self.check_acl_mismatch(fob, controller_url)
                if mismatch:
                    success = self.apply_acl_update(fob, controller_url)
                    if success:
                        batch_changes += 1
            
            changes_made += batch_changes
            logging.info(
                f"Batch {batch_idx}/{len(batches)} complete for {controller_url}. "
                f"Total permissions Changes Made {changes_made}"
            )
            
        return changes_made

# =============================================================================
# FIXED THREAD LAUNCHER: UNIQUE INSTANCE PER THREAD
# =============================================================================

def start_thread_safe_scheduler(
    urls: List[str], 
    db_config: dict, 
    username: str, 
    password: str
) -> List[threading.Thread]:
    """
    FIX 2: Creates a brand-new, isolated AccessSynchronizer object 
    for each thread. This guarantees zero state-sharing.
    """
    threads = []
    
    for url in urls:
        # We bind the 'url' variable to avoid late-binding closure issues in the loop
        def thread_target(target_url=url):
            # Dedicated instance created on this thread's private memory heap
            sync_instance = AccessSynchronizer(
                username=username,
                password=password,
                config=db_config
            )
            # Run the infinite check/sync loop isolated within this instance
            sync_instance.run_controller_sync_loop(target_url)

        t = threading.Thread(
            target=thread_target, 
            name=f"Sync-{url.replace('http://', '').replace('/', '')}"
        )
        t.daemon = True
        t.start()
        threads.append(t)
        
    return threads