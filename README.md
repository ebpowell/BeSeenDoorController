# BeSeenDoorController
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

## CLI & Background Tasks

### Pulling Swipes and ACL Information
To manually execute background scripts via the Docker container:

- **Get Swipes**:
  ```bash
  docker compose run doorcontroller get_swipes
  ```
- **Get ACL list from controller**:
  ```bash
  docker compose run doorcontroller get_acl_from_controller
  ```
- **Get registered fob list from controller**:
  ```bash
  docker compose run doorcontroller get_foblist_from_controller
  ```

### Cron Integration (e.g., Pulling swipes every 15 minutes)
Add the following line to your crontab:
```cron
*/15 * * * * cd /opt/scripts/BeSeenDoorController && docker compose -f docker-compose.yaml run doorcontroller get_swipes > /dev/null 2>&1
```

