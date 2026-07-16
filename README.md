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

## Database Setup (with PL/Python Trigger)

The database triggers for synchronizing fob updates to the controllers are written in PostgreSQL PL/Python (`plpython3u`). Official PostgreSQL Docker images do not include the Python runtime environment by default.

To run the database container with Python support:

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

### Cron Integration (e.g., Pulling swipes every 15 minutes)
Since the `doorcontroller` container runs continuously in the background as the permissions updates scheduler daemon, you can run other CLI tools on the host machine using `docker compose exec` inside a cron job:
```cron
*/15 * * * * cd /opt/scripts/BeSeenDoorController && docker compose exec -T doorcontroller get_swipes > /dev/null 2>&1
```
Note: The `-T` option is recommended for cron jobs as it disables pseudo-TTY allocation.

