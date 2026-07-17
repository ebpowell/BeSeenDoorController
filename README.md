# BeSeen Door Controller - HOA Tools
Code to interact with BeSeenControl Door Controller via web interface.

Code runs in a Docker container and uses Docker Compose and an external configuration file to manage credentials, database connections, and operational settings.

---

## Launching the Web Interface

### Using Docker Compose (Recommended)
The web interface is configured as the default service command in Docker Compose and exposes port `5000`.

1. **Start the Web Interface**:
   ```bash
   docker compose up -d
   ```
2. **Access the Application**:
   Open your browser and navigate to `http://localhost:5000`.

### Running Locally (Alternative)
If you wish to run the Flask application directly in your host environment using python:
1. Ensure your PostgreSQL instance is running and accessible (defined in `config/config.yaml`).
2. Run the server script:
   ```bash
   python3 door_controller/key_management_application/web_app/app.py
   ```

---

## Database Setup (with PL/Python Trigger)

The database triggers for synchronizing fob updates to the controllers are written in PostgreSQL PL/Python (`plpython3u`). Official PostgreSQL Docker images do not include the Python runtime environment by default.

### 1. Run the Database Container with Python Support

1. Create a `Dockerfile.postgres` in the root directory:
   ```dockerfile
   FROM postgres:16-alpine
   RUN apk add --no-cache python3
   ```

2. Update the `postgres` service in `docker-compose.yaml` to build the custom image:
   ```yaml
     postgres:
       build:
         context: .
         dockerfile: Dockerfile.postgres
       container_name: postgres
       # ... other settings (ports, volumes, environment)
   ```

3. Build and launch the database service:
   ```bash
   docker compose up --build -d postgres
   ```

### 2. Apply the Database Functions and Trigger

To support synchronization schedules and automatic database-to-controller updates:

#### A. Install the Permission Changes Schedule Function (`f_get_runtimes`)
The `update_access` tool uses the [SQL/f_get_runtimes.sql](file:///home/ebpowell/GIT_REPO/BeSeenDoorController/SQL/f_get_runtimes.sql) script to determine when permission changes (ACL rules activation/deactivation) occur throughout the day:

```bash
# Copy the script to the postgres container
docker cp SQL/f_get_runtimes.sql postgres:/tmp/f_get_runtimes.sql

# Execute the script in the postgres database
docker compose exec postgres psql -U wentworth_user -d wntworth_db -f /tmp/f_get_runtimes.sql
```

#### B. Apply the PL/Python Trigger (`fob_sync_trigger`)
The fob synchronization trigger is defined in [SQL/fob_sync_trigger.sql](file:///home/ebpowell/GIT_REPO/BeSeenDoorController/SQL/fob_sync_trigger.sql). It automatically propagates `INSERT` and `DELETE` operations on the `key_fobs.keyfobs` table to all configured door controllers.

* **Transaction Safety & Verification**: Before committing the database transaction, the trigger verifies the results returned by the door controllers. If any controller fails, the trigger raises a `plpy.error` exception, rolling back the database transaction.

```bash
# Copy the trigger SQL script to the postgres container
docker cp SQL/fob_sync_trigger.sql postgres:/tmp/fob_sync_trigger.sql

# Execute the SQL script in the postgres database
docker compose exec postgres psql -U wentworth_user -d wntworth_db -f /tmp/fob_sync_trigger.sql
```

---

## CLI & Background Tasks

### Pulling Swipes and ACL Information
To manually execute background scripts via the running Docker container:

- **Get Swipes**:
  ```bash
  docker compose exec doorcontroller get_swipes
  ```
- **Get ACL list from controller**:
  ```bash
  docker compose exec doorcontroller get_acl_from_controller
  ```
- **Get registered fob list from controller**:
  ```bash
  docker compose exec doorcontroller get_foblist_from_controller
  ```

- **Trim Orphaned Fobs**:
  Removes fob IDs from the controllers that are not present in the database.
  * **Run Once**:
    ```bash
    docker compose exec doorcontroller trim_fobs
    ```
  * **Run in Daemon Mode** (uses the recurrence schedule):
    ```bash
    docker compose exec doorcontroller trim_fobs --daemon
    ```

#### Configuration for trim_fobs
The scheduler recurrence interval for `trim_fobs` is configured in `config/config.yaml` using the `recurrence` attribute inside the `settings` block (specified in seconds):
```yaml
settings:
  recurrence: 3600 # Sync interval in seconds (e.g. 1 hour)
```

- **Update Access Permissions (update_access)**:
  Synchronizes database fob list and ACL permissions to all configured door controllers. It executes multi-threaded runs where each controller is updated in parallel on its own schedule.
  * **Run Once**:
    ```bash
    docker compose exec doorcontroller update_access
    ```
  * **Run in Daemon Mode** (uses controller-specific schedules derived from the database):
    ```bash
    docker compose exec doorcontroller update_access --daemon
    ```

### Cron Integration (e.g., Pulling swipes every 15 minutes)
Since the `doorcontroller` container runs continuously in the background as the permissions updates scheduler daemon, you can run other CLI tools on the host machine using `docker compose exec` inside a cron job:
```cron
*/15 * * * * cd /opt/scripts/BeSeenDoorController && docker compose exec -T doorcontroller get_swipes > /dev/null 2>&1
```
Note: The `-T` option is recommended for cron jobs as it disables pseudo-TTY allocation.

