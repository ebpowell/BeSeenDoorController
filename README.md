# BeSeen Door Controller - Hardware API & Client

Open-source API client layer, REST API module, and CLI toolset for interfacing with BeSeen Door Controller physical access hardware.

## Overview

`BeSeenDoorController` provides a Python API library, REST API endpoints, and command-line synchronization tools to manage physical key fobs, retrieve card swipe logs, query controller permissions, and maintain synchronization between hardware door controllers and a PostgreSQL backend database.

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

### Docker Setup

Run the CLI tools or synchronization daemons via Docker Compose:
```bash
docker compose up -d doorcontroller
```

---

## Configuration

Configuration is loaded from `config/config.yaml` or specified via environment variables (e.g., `APP_CONFIG_DIR`).

Example `config/config.yaml`:
```yaml
app_name: "BeSeenDoorController"
settings:
  urls:
    - "http://192.168.1.100"
  username: "admin"
  password: "your_password"
  recovery_delay: 5
  log_level: "INFO"
  postgres_connect_string: "postgresql://wentworth_user:password@localhost:5432/wntworth_db"
```

---

## REST API Client (`door_controller.api`)

The project provides a Flask Blueprint (`api_bp`) exposed under `/api` for RESTful operations on door controllers.

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

## Python API Library (`door_controller.common_lib`)

### Hardware Data Manager (`DataManager`)

Use `DataManager` for direct programmatic interaction with the hardware controller:

```python
from door_controller.common_lib.data_manager import DataManager

# Initialize client
dm = DataManager(controller_url="http://192.168.1.100", username="admin", password="password")

# Get hardware record ID for a fob ID
record_id = dm.get_record_id(fob_id=12345)

# Add a key fob
dm.add_fob(fob_id=12345, user_name="Jane Doe")

# Retrieve key fobs list from controller
fobs = dm.get_keyfobs()
```

---

## CLI & Synchronization Tools

Command-line utilities installed via `setup.py` entry points:

| Tool Command | Description |
| :--- | :--- |
| `BeSeen_driver` | CLI tool to add, remove, or set permissions for a key fob. |
| `get_swipes` | Pull door swipe logs from hardware controllers into the database. |
| `get_acl_from_controller` | Extract Access Control List (ACL) data from controllers. |
| `get_foblist_from_controller` | Retrieve key fob list stored on hardware controllers. |
| `list_fobs_simple` / `list_fobs` | Print simple key fob listing. |
| `sync_controller` | Synchronization daemon process. |
| `trim_fobs` | Trim orphaned key fobs from hardware memory. |
| `update_access` | Sync database access permissions to hardware controllers. |
| `collect_metrics` | Record system and controller performance metrics. |

### CLI Examples

```bash
# Add a key fob
BeSeen_driver add 12345 "John Doe"

# Remove a key fob
BeSeen_driver remove 12345

# Fetch swipes from hardware
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

