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

1. A custom `Dockerfile.postgres` builds on top of the standard `postgres:16-alpine` image to install Python 3, pip, and our door controller libraries:
   ```dockerfile
   FROM postgres:16-alpine
   RUN apk add --no-cache python3 py3-pip
   ...
   RUN pip install --no-cache-dir . --break-system-packages
   ```

2. The `postgres` service in `docker-compose.yaml` is configured to build this custom image and automatically mounts the `./init` folder to populate schemas and triggers on first-run:
   ```yaml
     postgres:
       build:
         context: .
         dockerfile: Dockerfile.postgres
       container_name: postgres
       volumes:
         - /mnt/sda1/postgresql:/var/lib/postgresql/data
         - ./init:/docker-entrypoint-initdb.d/
   ```

3. Build and launch the database service:
   ```bash
   docker compose up --build -d postgres
   ```

### 2. Automatic Database Initialization and Triggers

To support synchronization schedules and automatic database-to-controller updates, the database container self-initializes by executing SQL scripts mounted from the `./init` directory to `/docker-entrypoint-initdb.d/` in alphabetical order on first run:

*   **`01_init_db.sql`**: Configures the base database schemas (`key_fobs`, `door_controller`, `dataload`), tables, user accounts, and seed data.
*   **`02_f_get_runtimes.sql`**: Installs the `key_fobs.f_get_runtimes` permission schedule function which evaluates when access windows activate throughout the day.
*   **`03_fob_sync_trigger.sql`**: Enables the untrusted PL/Python 3 extension (`plpython3u`) and registers the trigger function `process_fob_changes_py()` on the `key_fobs.keyfobs` table.
    *   *Transaction Safety & Verification*: Before committing any database transaction (like an `INSERT` or `DELETE` on a fob), the trigger propagates the change to all controllers. If any controller fails, the trigger raises a `plpy.error` exception, rolling back the transaction.

### 3. Deploying / Updating Triggers via Deployment Tool

If you make modifications to the PL/Python trigger script and want to redeploy/update them on an existing database instance without rebuilding the database container, you can use the built-in trigger deployment command.

This deployment tool loads your database credentials from `config/config.yaml`, reads the trigger SQL script, and applies it safely inside a database transaction block:

*   **Run inside the Docker container**:
    ```bash
    docker compose exec doorcontroller deploy_triggers
    ```
*   **Run in the local host environment**:
    ```bash
    deploy_triggers
    ```

---

## Timezone Configuration

Since both the database functions (e.g., `f_get_runtimes` which queries `now()::time`) and the background scheduler tools evaluate permission schedules based on the current local time, it is critical that all containers are configured to use the correct local timezone.

To set the proper timezone in Docker Compose:

1. Add the `TZ` environment variable to all services in `docker-compose.yaml` (e.g., `America/New_York`). For the PostgreSQL service, also set the `PGTZ` environment variable to guarantee the database engine itself initializes with this default timezone:
   ```yaml
   services:
     keymanagement:
       # ...
       environment:
         TZ: America/New_York
         APP_CONFIG_DIR: /app/config

     doorcontroller:
       # ...
       environment:
         TZ: America/New_York
         APP_CONFIG_DIR: /app/config

     postgres:
       # ...
       environment:
         - POSTGRES_PASSWORD=ww_s3cret
         - POSTGRES_USER=wentworth_user
         - POSTGRES_DB=wntworth_db
         - TZ=America/New_York
         - PGTZ=America/New_York
   ```

2. Re-create the containers to apply the configuration:
   ```bash
   docker compose up -d --force-recreate
   ```

3. **Verify and Lock Timezone inside PostgreSQL**:
   To ensure the database and database users default to the local time zone regardless of connection layer defaults, run the following SQL commands on the database:
   ```sql
   -- Set the timezone for the specific database
   ALTER DATABASE wntworth_db SET timezone TO 'America/New_York';

   -- Set the timezone for the database user
   ALTER USER wentworth_user SET timezone TO 'America/New_York';
   ```
   You can apply these settings by executing:
   ```bash
   docker compose exec postgres psql -U wentworth_user -d wntworth_db -c "ALTER DATABASE wntworth_db SET timezone TO 'America/New_York';"
   docker compose exec postgres psql -U wentworth_user -d wntworth_db -c "ALTER USER wentworth_user SET timezone TO 'America/New_York';"
   ```

   To verify the current active timezone inside PostgreSQL, run:
   ```bash
   docker compose exec postgres psql -U wentworth_user -d wntworth_db -c "SHOW timezone;"
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
```services:
  keymanagement:
    image: key-management-app:latest
    container_name: keymanagement
    restart: unless-stopped
    environment:
      - TZ=America/New_York
    volumes:
      - /opt/data/door_controller/data:/app/data
      - /opt/data/door_controller/config:/app/config
      - /opt/data/door_controller/log:/app/log
      - /etc/localtime:/etc/localtime:ro

  doorcontroller:
    image: cli-synch-tools:latest
    container_name: cli-synch-tools
    restart: unless-stopped
    environment:
      - TZ=America/New_York
    volumes:
      - /opt/data/door_controller/data:/app/data
      - /opt/data/door_controller/config:/app/config
      - /opt/data/door_controller/log:/app/log
      - /etc/localtime:/etc/localtime:ro

  postgres:
    image: postgres:16-alpine
    build:
      context: .
      dockerfile: Dockerfile.postgres
    container_name: postgres
    restart: always
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_PASSWORD=ww_s3cret
      - POSTGRES_USER=wentworth_user
      - POSTGRES_DB=wntworth_db
      - TZ=America/New_York
      - PGTZ=America/New_York
    volumes:
      - /mnt/sda1/postgresql:/var/lib/postgresql/data
      - ./init:/docker-entrypoint-initdb.d/
      - /etc/localtime:/etc/localtime:ro

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

---

## Observability & Database Metrics (Grafana)

To monitor the integrity of the door controller permissions and detect discrepancies (such as missing fobs on controllers or unassigned fobs running on controllers), a dedicated metrics collection and statistical auditing utility is provided.

### 1. Database Observability Views
During initialization, the database container sets up helper views under the `door_controller` schema:
*   **`vint_system_assigned_fob_compare`**: Core comparison query that performs a full outer join of active assigned fobs against active fobs on the controllers.
*   **`vext_system_missing_assigned_fobs`**: Identifies which assigned fobs in the system are currently missing on specific door controllers.
*   **`vext_system_unassigned_fobs`**: Identifies which fobs are currently active on the controllers but not registered/assigned in the system.

### 2. Metrics Collection Tool (`collect_metrics`)
The `collect_metrics` command queries the discrepancy views and runs a statistical audit on a random sample of active fobs to verify that permissions match what is defined in the database (via `f_get_permissions`).

Results are saved to the `door_controller.controller_metrics` time-series table.

*   **Run Once**:
    ```bash
    docker compose exec doorcontroller collect_metrics
    ```
*   **Configure Auditing Sample Size**:
    ```bash
    # Audit a random sample of 50 fobs (or 10% of total active fobs, whichever is larger)
    docker compose exec doorcontroller collect_metrics --sample-size 50 --sample-percent 10
    ```
*   **Cron Schedule Setup**:
    Add a cron job to collect metrics every hour on the host:
    ```cron
    0 * * * * cd /opt/scripts/BeSeenDoorController && docker compose exec -T doorcontroller collect_metrics > /dev/null 2>&1
    ```

### 3. Dedicated Grafana Container & Automatic Provisioning
A dedicated Grafana service is integrated in `docker-compose.yaml`. It automatically provisions a PostgreSQL datasource pointing to the database container.

1. **Access Grafana**:
   Open your browser and navigate to `http://localhost:3000`.
2. **Log In**:
   Use default credentials:
   *   **Username**: `admin`
   *   **Password**: `admin` (or whatever was configured in `docker-compose.yaml` under `GF_SECURITY_ADMIN_PASSWORD`).
3. **Provisioned Datasource**:
   The `PostgreSQL` datasource is pre-configured and immediately available for queries.

To visualize metrics in your dashboard panels, use the following SQL queries:

#### Panel A: Permissions Integrity Score (Line Graph)
Shows the percentage of fobs with correct controller permissions (1.0 = 100% integrity).
```sql
SELECT 
  metric_time AS time, 
  metric_value AS "Integrity Score", 
  controller_ip::text AS metric
FROM door_controller.controller_metrics
WHERE metric_name = 'integrity_score' AND $__timeFilter(metric_time)
ORDER BY metric_time;
```

#### Panel B: Discrepant Fobs Count (Bar or Line Graph)
Tracks missing assigned fobs vs. unassigned fobs count over time.
```sql
SELECT 
  metric_time AS time, 
  metric_value, 
  controller_ip::text || ' - ' || metric_name AS metric
FROM door_controller.controller_metrics
WHERE metric_name IN ('missing_assigned_fobs_count', 'unassigned_fobs_count') AND $__timeFilter(metric_time)
ORDER BY metric_time;
```

#### Panel C: Audit Errors Detail (Table Panel)
Displays a detailed list of mismatched and missing fob IDs for manual reconciliation.
```sql
SELECT 
  metric_time, 
  controller_ip::text, 
  metric_value AS "Mismatch Rate", 
  metadata->'mismatched_fob_ids' AS mismatched_fobs, 
  metadata->'missing_fob_ids' AS missing_fobs
FROM door_controller.controller_metrics
WHERE metric_name = 'mismatch_rate' AND metric_value > 0 AND $__timeFilter(metric_time)
ORDER BY metric_time DESC;
```

