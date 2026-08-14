# BeSeen Door Controller - HOA Tools
Code to interact with BeSeenControl Door Controller via web interface and manage key fobs, clubhouse reservations, access permissions, and calendar synchronization.

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

## Web Application Features

### 1. Key Fob Management (`/fobs` or `/`)
- Assign key fobs to property addresses with property owner search.
- Remove fobs or execute single-click fob replacements.
- View real-time synchronization status across door controllers.

### 2. Clubhouse Reservations (`/reservations`)
- **Private Resident Event Reservations**:
  - Property address search with auto-populated owner names.
  - **Configurable Time Blocks**: Morning (`08:00–12:00`), Afternoon (`13:00–17:00`), and Evening (`18:00–23:00`).
  - **Dynamic Fee Engine**: $15.00 for single time block, $30.00 flat rate for multi-block reservations.
  - **Early Set-up Surcharge**: Optional $15.00 early setup fee (validated against 24-hour buffer checks).
  - Track payment status, security deposit on file, and signed rental agreement receipt.

### 3. HOA Board of Directors Events (`/reservations/hoa`)
- Restricted to administrative roles (`ManagementCo`, `SysAdmin`, `Secretary`).
- **Board Precedence**: Board of Directors events take immediate precedence over private events.
- **Automatic Event Displacement**: Scheduling an HOA event automatically displaces any conflicting private reservation on that date, revoking early setup and flagging `reschedule_required = TRUE` to initiate resident refund processing.

### 4. Interactive Monthly Calendar View (`/calendar`)
- **Sunday–Saturday 7-Column Month Grid**: Displays scheduled events with color-coded badges:
  - 🟣 **HOA Event**: Full-day Board of Directors event badge.
  - 🔵 **Community Organization**: Community organization event.
  - 🟢 **Private Event**: Property reservation badge.
  - 🔴 **Reschedule Due**: Warning indicator for displaced reservations requiring reschedule & refund.
- **Interactive Event Popovers**: Clicking any date cell opens a Glassmorphic details drawer with timeslot, owner, fee, and booking shortcut links.
- **☀️ Light / 🌙 Dark Mode Switcher**: Header toggle button with instant `localStorage` theme persistence.

### 5. Public View-Only Calendar Embed (`/calendar/embed`)
- **Public 3rd-Party Integration**: Unauthenticated view-only route designed for embedding inside an `<iframe>` on external homeowner portals, WordPress, Wix, or Squarespace sites.
- **1-Click Copy Embed Snippet**: The `/calendar` page includes an **`🔗 Embed Calendar`** button providing copy-pasteable HTML `<iframe>` code snippets for both Light and Dark themes.

---

## Google Calendar Integration Tool

The application includes a backend Google Calendar integration tool (`gcalendar_event.py` and `door_controller/common_lib/gcal_sync.py`) to push reservations from PostgreSQL directly into a Google Calendar using a **Google Service Account**.

### 1. Google Cloud Console & Service Account Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or select an existing project) and enable the **Google Calendar API** in the API Library.
3. Navigate to **IAM & Admin > Service Accounts** and click **Create Service Account**.
   - Assign a name (e.g., `beseen-calendar-sync`).
   - Copy the generated Service Account email address (e.g., `beseen-calendar-sync@your-project-id.iam.gserviceaccount.com`).
4. Select the newly created Service Account, open the **Keys** tab, and click **Add Key > Create new key (JSON)**.
5. Save the downloaded JSON key file to your application directory as `service_account.json` (or set the `GOOGLE_SERVICE_ACCOUNT_FILE` environment variable).
6. Install Google API client dependencies (if running outside Docker):
   ```bash
   pip install google-auth google-api-python-client
   ```

### 2. Google Calendar Permission & Sharing Configuration

To allow the integration tool to write events into your target Google Calendar, you **must explicitly share the calendar with your Service Account** and grant write permissions:

1. Open [Google Calendar](https://calendar.google.com) in your web browser.
2. Under **My calendars** in the left sidebar, hover over your target calendar, click the three dots `⋮` (Options), and select **Settings and sharing**.
3. Scroll down to the **Share with specific people or groups** section and click **+ Add people and groups**.
4. Paste your Service Account email address (e.g., `beseen-calendar-sync@your-project-id.iam.gserviceaccount.com`).
5. Set the Permissions dropdown to **`Make changes to events`** (or **`Make changes and manage sharing`**).
   > [!WARNING]
   > If permissions are left as "See all event details", API calls from the tool will be rejected by Google with an `HTTP 403 Insufficient Permission` error.
6. Click **Send** / **Save**.
7. Scroll down to the **Integrate calendar** section on the same settings page and copy the **Calendar ID** (e.g., `c_188abc...@group.calendar.google.com` or `your_email@gmail.com`). Use this ID with the `--calendar-id` parameter.

### 2. Command-Line Tool Usage (`gcalendar_event.py`)

Run the synchronization tool via CLI:

- **Preview Payload Format (Dry-Run)**:
  ```bash
  python gcalendar_event.py --dry-run
  ```
- **Execute Live Sync**:
  ```bash
  python gcalendar_event.py --calendar-id "your_calendar_id@gmail.com" --service-account-file "service_account.json"
  ```
- **Output JSON Results**:
  ```bash
  python gcalendar_event.py --dry-run --json
  ```

### 3. Automated Cron Integration
Add a cron job to push database reservations to Google Calendar on a recurring schedule (e.g., every 30 minutes):
```cron
*/30 * * * * cd /opt/scripts/BeSeenDoorController && python3 gcalendar_event.py --calendar-id "clubhouse@example.com" > /dev/null 2>&1
```

### 4. Embedding Google Calendar Widget in Webpages (`<iframe>`)

To embed the synchronized Google Calendar directly into any 3rd party website or homeowner portal, use Google Calendar's standard `<iframe>` call:

```html
<!-- Official Google Calendar Widget Embed -->
<iframe 
    src="https://calendar.google.com/calendar/embed?src=your_calendar_id%40gmail.com&ctz=America%2FNew_York" 
    style="border: 0; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" 
    width="100%" 
    height="700" 
    frameborder="0" 
    scrolling="no" 
    title="Google Calendar Schedule">
</iframe>
```

> [!TIP]
> **Custom Web App Embed**: Alternatively, you can embed the application's native Glassmorphic view-only calendar widget:
> ```html
> <iframe 
>     src="http://YOUR-SERVER-DOMAIN-OR-IP:5000/calendar/embed?theme=light" 
>     width="100%" 
>     height="750" 
>     frameborder="0" 
>     style="border: 0; border-radius: 12px; overflow: hidden;" 
>     title="Clubhouse Event Calendar">
> </iframe>
> ```

---

## Database Setup & Schema Reference

The database engine runs in a PostgreSQL container (`postgres:16-alpine`) initialized with custom SQL scripts mounted from `./init`.

### 1. Core Schema Tables

*   **`key_fobs.clubhouse_reservations`**:
    Tracks clubhouse bookings:
    ```sql
    CREATE TABLE key_fobs.clubhouse_reservations (
        reservation_id SERIAL PRIMARY KEY,
        property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
        reservation_date DATE NOT NULL,
        from_time TIME,
        to_time TIME,
        payment_made BOOLEAN NOT NULL DEFAULT FALSE,
        deposit_on_file BOOLEAN NOT NULL DEFAULT FALSE,
        agreement_received BOOLEAN NOT NULL DEFAULT FALSE,
        fee DECIMAL(10,2) DEFAULT 15.00,
        early_setup BOOLEAN NOT NULL DEFAULT FALSE,
        event_type VARCHAR(50) DEFAULT 'Private Event',
        event_name VARCHAR(255),
        event_description TEXT,
        reschedule_required BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    ```
*   **`key_fobs.reservation_blocks`**: Time block configuration master table (`block_key`, `block_name`, `start_time`, `end_time`, `display_order`).
*   **`key_fobs.reservation_fee_config`**: Fee settings table (`single_block_fee`, `multi_block_fee`, `early_setup_fee`).
*   **`key_fobs.keyfobs`**: Key fobs assigned to property IDs.
*   **`key_fobs.properties` & `key_fobs.property_owners`**: Property catalog and owner records.

### 2. Automatic Database Initialization

SQL scripts in `./init` execute on first database creation:
*   **`01_init_db.sql`**: Configures base schemas (`key_fobs`, `door_controller`, `dataload`), tables, user accounts, and seed data.
*   **`02_f_get_runtimes.sql`**: Installs access schedule evaluator function `key_fobs.f_get_runtimes`.
*   **`03_fob_sync_trigger.sql`**: Enables PL/Python 3 extension (`plpython3u`) and registers trigger `process_fob_changes_py()` on `key_fobs.keyfobs`.

### 3. Deploying / Updating Schemas & Triggers

To redeploy triggers or schemas without rebuilding the database container:
*   **Inside Docker**:
    ```bash
    docker compose exec doorcontroller deploy_triggers
    ```
*   **Local Host**:
    ```bash
    deploy_triggers
    ```

---

## Timezone Configuration

Both database permission functions (e.g. `f_get_runtimes`) and calendar sync tools evaluate schedules in local time. Ensure containers use the local timezone (e.g., `America/New_York`):

1. Set `TZ` and `PGTZ` in `docker-compose.yaml`:
   ```yaml
   services:
     keymanagement:
       environment:
         TZ: America/New_York

     postgres:
       environment:
         - TZ=America/New_York
         - PGTZ=America/New_York
   ```

2. Lock timezone inside PostgreSQL:
   ```bash
   docker compose exec postgres psql -U wentworth_user -d wntworth_db -c "ALTER DATABASE wntworth_db SET timezone TO 'America/New_York';"
   docker compose exec postgres psql -U wentworth_user -d wntworth_db -c "ALTER USER wentworth_user SET timezone TO 'America/New_York';"
   ```

---

## CLI & Background Tasks

### Pulling Swipes and Access Control Information
- **Get Swipes**: `docker compose exec doorcontroller get_swipes`
- **Get Controller ACLs**: `docker compose exec doorcontroller get_acl_from_controller`
- **Get Controller Fob List**: `docker compose exec doorcontroller get_foblist_from_controller`
- **Trim Orphaned Fobs**: `docker compose exec doorcontroller trim_fobs`
- **Update Controller Access**: `docker compose exec doorcontroller update_access`
- **Google Calendar Sync**: `docker compose exec keymanagement python gcalendar_event.py`

---

## Observability & Database Metrics (Grafana)

A dedicated Grafana container (`http://localhost:3000`) is pre-configured with a PostgreSQL datasource pointing to `door_controller.controller_metrics`.

### Observability Views
- `door_controller.vint_system_assigned_fob_compare`
- `door_controller.vext_system_missing_assigned_fobs`
- `door_controller.vext_system_unassigned_fobs`

### Metrics Collection Command
```bash
docker compose exec doorcontroller collect_metrics --sample-size 50 --sample-percent 10
```
