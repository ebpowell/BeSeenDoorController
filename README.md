# BeSeen Door Controller - Hardware API & Client

Open-source API client layer, REST API module, and CLI toolset for interfacing with BeSeen Door Controller physical access hardware.

## Architecture & System Overview

`BeSeenDoorController` separates hardware interaction, API service delivery, database synchronization, and configuration management into decoupled services:

```
+-------------------------------------------------------------+
|                      Hardware Door Controllers               |
+-------------------------------------------------------------+
                               ^
                               | (HTTP / REST API)
                               v
+-------------------------------------------------------------+
|                  beseen-api (REST API Container)            |
| - Controls hardware interactions via DataManager            |
| - Independent of PostgreSQL database                        |
| - Exposes RESTful endpoints on port 5000                    |
+-------------------------------------------------------------+
           ^                                     ^
           | (API Client)                        | (API Client)
+--------------------------+          +--------------------------+
|  cli-synch-tools         |          |  config-gui              |
|  (CLI & DB Sync Container)|          |  (Web GUI Config Tool)   |
|  - Uses ApiClient        |          |  - Edits config.yaml     |
|  - Associated w/ Postgres|          |  - Runs on port 5001     |
+--------------------------+          +--------------------------+
           |
           v
+--------------------------+
|  postgres                |
|  (PostgreSQL Database)   |
+--------------------------+
```

---

## Quick Start & Installation

### Prerequisites
- Python 3.8+
- PostgreSQL (optional, required for database synchronization tools)
- Dependencies listed in `requirements.txt`

### Local Installation

Install dependencies and the Python package:
```bash
pip install -r requirements.txt
pip install .
```

### Docker Compose Topology

Start all decoupled services:
```bash
docker compose up -d
```

#### Services Defined in `docker-compose.yaml`:
- **`beseen-api`**: Standalone REST API server for controlling door controller hardware (`port 5000`).
- **`cli-synch-tools`**: CLI tools and background synchronization daemon connected to `postgres` and using `beseen-api`.
- **`config-gui`**: Remote configuration Web GUI application (`port 5001`).
- **`postgres`**: PostgreSQL database backend for access control logs and key fob records.

---

## Configuration

Configuration is loaded from `config/config.yaml` or specified via environment variables (e.g., `APP_CONFIG_DIR`, `API_URL`).

Example `config/config.yaml`:
```yaml
app_name: "BeSeenDoorController"
settings:
  log_level: "INFO"
  urls:
    - "http://192.168.1.100"
  username: "admin"
  password: "your_password"
  recovery_delay: 5
  postgres_connect_string: "postgresql://wentworth_user:password@localhost:5432/wntworth_db"

ssl:
  enabled: false
  cert_file: config/certs/server.crt
  key_file: config/certs/server.key
```

---

## Configuration Web GUI Tool (`BeSeen_config_gui`)

The project includes a Flask-based Web GUI for remote management of `config.yaml`.

### Launching the Configuration Web GUI

Run the console script:
```bash
BeSeen_config_gui --port 5001
```
Or directly with Python:
```bash
python3 -m door_controller.config_gui --port 5001
```
Access the interface in your browser at `http://localhost:5001`.

### Web GUI Features
- **Remote Configuration Editing**: Update controller URLs, credentials, recovery delays, log levels, and database connection strings.
- **SSL Security Management**: Toggle SSL encryption and configure server certificate/key paths.
- **Live Connection Testing**: Test real-time reachability of hardware door controller URLs and PostgreSQL connection strings.
- **Hot Reloading & Saving**: Write updated settings back to `config.yaml` with safety validation.

---

## REST API Client Service (`door_controller.api` / `BeSeen_api`)

The REST API container (`beseen-api`) runs as an independent service controlling calls to hardware door controllers:

```bash
BeSeen_api --host 0.0.0.0 --port 5000
```

### API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/fob/<fob_id>/record_id` | Get hardware record ID for a key fob ID. |
| `POST` | `/api/fob` | Add a key fob. Payload: `{"fob_id": 12345, "owner_name": "John Doe"}` |
| `DELETE` | `/api/fob/<fob_id>` | Remove a key fob from the door controller. |
| `PUT` | `/api/fob/permissions` | Update fob door permissions. Payload: `{"record_id": 10, "permissions": [[1, true], [2, false]]}` |
| `GET` | `/api/swipes` | Query card swipe activity. Query param: `?period=24h` (supports `h`, `d`, `w`, `m`). |
| `GET` | `/api/controller/fobs` | List all key fobs stored directly on the hardware controller. |
| `GET` | `/api/controller/fob/<fob_id>/permissions` | Compare live hardware permissions against expected database permissions. |

---

## Unified Python API Client (`ApiClient`)

The `ApiClient` class (`door_controller.common_lib.api_client`) routes hardware requests through the `beseen-api` service, falling back to direct `DataManager` execution if the HTTP REST API is unreachable:

```python
from door_controller.common_lib.api_client import ApiClient

# Initialize client (uses API_URL env var or defaults to http://beseen-api:5000)
client = ApiClient()

# Get hardware record ID
record_id = client.get_fob_record_id(12345)

# Add key fob via API module
client.add_fob(fob_id=12345, owner_name="Jane Doe")

# Update permissions
client.update_fob_permissions(record_id=10, permissions=[[1, True], [2, True]])

# Retrieve controller key fobs
fobs = client.get_controller_fobs()
```

---

## CLI & Synchronization Tools

Command-line utilities installed via `setup.py` entry points:

| Tool Command | Description |
| :--- | :--- |
| `BeSeen_api` | Standalone REST API server for hardware control. |
| `BeSeen_driver` | CLI tool to add, remove, or set permissions for a key fob via API Client. |
| `BeSeen_config_gui` | Web GUI tool for remote management of `config.yaml`. |
| `get_swipes` | Pull door swipe logs from hardware controllers into the database via API Client. |
| `get_acl_from_controller` | Extract Access Control List (ACL) data from controllers via API Client. |
| `get_foblist_from_controller` | Retrieve key fob list stored on hardware controllers via API Client. |
| `list_fobs_simple` / `list_fobs` | Print simple key fob listing. |
| `sync_controller` | Synchronization daemon process. |
| `trim_fobs` | Trim orphaned key fobs from hardware memory. |
| `update_access` | Sync database access permissions to hardware controllers. |
| `collect_metrics` | Record system and controller performance metrics. |

### CLI Examples

```bash
# Add a key fob via driver
BeSeen_driver add 12345 "John Doe"

# Remove a key fob
BeSeen_driver remove 12345

# Fetch swipes from hardware into database
get_swipes

# Fetch fob list from controller
get_foblist_from_controller
```

---

## Testing

Run the automated unit test suite:
```bash
./run_tests.sh
```
Or directly with `pytest`:
```bash
pytest
```


