"""
BeSeenDoorController - Configuration Web GUI Tool

Provides a web interface for remote management of config.yaml:
- View and edit controller URLs, credentials, log levels, recovery delays.
- View and edit PostgreSQL connection string.
- View and edit SSL settings (enabled status, cert and key file paths).
- Test controller hardware and database connectivity.
- Save updated configuration safely back to disk.
"""

import os
import sys
import argparse
import requests
import yaml
from flask import Flask, jsonify, request, render_template_string

from door_controller.common_lib.utils import load_config, log_info, log_error, get_ssl_config, get_ssl_context, configure_app_security

app = Flask(__name__)


def get_config_file_path(config_filename='config.yaml'):
    """Finds the absolute path of the configuration file on disk."""
    env_dir = os.getenv('APP_CONFIG_DIR')
    if env_dir:
        candidate_dirs = [env_dir]
    else:
        candidate_dirs = [
            './config',
            '/app/config',
            '/etc/door_controller',
            os.path.expanduser('~/.config/door_controller')
        ]

    for directory in candidate_dirs:
        possible_path = os.path.join(directory, config_filename)
        if os.path.exists(possible_path):
            return os.path.abspath(possible_path)

    # Return default path in current working directory / config
    default_dir = candidate_dirs[0]
    return os.path.abspath(os.path.join(default_dir, config_filename))


def save_config_to_disk(config_data, config_filename='config.yaml'):
    """Saves configuration dict back to disk as YAML."""
    path = get_config_file_path(config_filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        yaml.safe_dump(config_data, f, default_flow_style=False, sort_keys=False)
    log_info(f"Configuration successfully saved to {path}")
    return path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BeSeen Door Controller - Remote Configuration</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0f172a;
            --bg-surface: #1e293b;
            --bg-surface-elevated: #334155;
            --border-color: rgba(255, 255, 255, 0.1);
            --border-hover: rgba(255, 255, 255, 0.2);
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --primary-light: rgba(99, 102, 241, 0.15);
            --success: #10b981;
            --success-light: rgba(16, 185, 129, 0.15);
            --danger: #ef4444;
            --danger-light: rgba(239, 68, 68, 0.15);
            --warning: #f59e0b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --text-dim: #64748b;
            --glass-bg: rgba(30, 41, 59, 0.7);
            --glass-border: rgba(255, 255, 255, 0.08);
            --radius-lg: 16px;
            --radius-md: 10px;
            --radius-sm: 6px;
            --shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
            --transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-base);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            background-image: 
                radial-gradient(at 10% 10%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
                radial-gradient(at 90% 90%, rgba(16, 185, 129, 0.1) 0px, transparent 50%);
            background-attachment: fixed;
            padding-bottom: 60px;
        }

        header {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--glass-border);
            position: sticky;
            top: 0;
            z-index: 100;
            padding: 16px 32px;
        }

        .header-content {
            max-width: 1100px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-icon {
            width: 40px;
            height: 40px;
            border-radius: var(--radius-md);
            background: linear-gradient(135deg, var(--primary), #8b5cf6);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 20px;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        .brand-text h1 {
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .brand-text span {
            font-size: 12px;
            color: var(--text-muted);
        }

        .header-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            padding: 6px 12px;
            background: var(--bg-surface-elevated);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            color: var(--text-muted);
            max-width: 400px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        main {
            max-width: 1100px;
            width: 100%;
            margin: 32px auto;
            padding: 0 24px;
            flex: 1;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 24px;
        }

        .card {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-lg);
            padding: 28px;
            box-shadow: var(--shadow);
            transition: var(--transition);
        }

        .card:hover {
            border-color: var(--border-hover);
        }

        .card-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }

        .card-icon {
            width: 32px;
            height: 32px;
            border-radius: var(--radius-sm);
            background: var(--primary-light);
            color: var(--primary);
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .card-title {
            font-size: 16px;
            font-weight: 600;
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .form-group.full-width {
            grid-column: 1 / -1;
        }

        label {
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        input[type="text"],
        input[type="number"],
        input[type="password"],
        select {
            width: 100%;
            padding: 12px 16px;
            background: var(--bg-base);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-family: inherit;
            font-size: 14px;
            transition: var(--transition);
            outline: none;
        }

        input[type="text"]:focus,
        input[type="number"]:focus,
        input[type="password"]:focus,
        select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
        }

        .code-input {
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px !important;
        }

        .toggle-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 16px;
            background: var(--bg-base);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
        }

        .toggle-switch {
            position: relative;
            width: 44px;
            height: 24px;
            display: inline-block;
        }

        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: var(--bg-surface-elevated);
            transition: .3s;
            border-radius: 24px;
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .3s;
            border-radius: 50%;
        }

        input:checked + .slider {
            background-color: var(--primary);
        }

        input:checked + .slider:before {
            transform: translateX(20px);
        }

        .url-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .url-row {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .btn {
            padding: 10px 18px;
            border-radius: var(--radius-md);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            border: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: var(--transition);
            outline: none;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-hover));
            color: white;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35);
        }

        .btn-secondary {
            background: var(--bg-surface-elevated);
            color: var(--text-main);
            border: 1px solid var(--border-color);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--border-hover);
        }

        .btn-danger {
            background: var(--danger-light);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.2);
        }

        .btn-danger:hover {
            background: rgba(239, 68, 68, 0.25);
        }

        .btn-sm {
            padding: 8px 12px;
            font-size: 13px;
        }

        .action-bar {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border);
            padding: 12px 24px;
            border-radius: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6);
            display: flex;
            align-items: center;
            gap: 16px;
            z-index: 1000;
        }

        .toast {
            position: fixed;
            top: 80px;
            right: 24px;
            padding: 14px 20px;
            border-radius: var(--radius-md);
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow);
            color: var(--text-main);
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 10px;
            transform: translateY(-20px);
            opacity: 0;
            visibility: hidden;
            transition: var(--transition);
            z-index: 1100;
        }

        .toast.show {
            transform: translateY(0);
            opacity: 1;
            visibility: visible;
        }

        .toast.success {
            border-color: var(--success);
            background: var(--success-light);
            color: #6ee7b7;
        }

        .toast.error {
            border-color: var(--danger);
            background: var(--danger-light);
            color: #fca5a5;
        }

        .input-with-action {
            display: flex;
            gap: 10px;
        }

        .input-with-action input {
            flex: 1;
        }

        .status-pill {
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 12px;
            font-weight: 600;
        }
        
        .status-pill.online {
            background: var(--success-light);
            color: var(--success);
        }

        .status-pill.offline {
            background: var(--danger-light);
            color: var(--danger);
        }
    </style>
</head>
<body>

    <header>
        <div class="header-content">
            <div class="brand">
                <div class="brand-icon">🔑</div>
                <div class="brand-text">
                    <h1>BeSeen Door Controller</h1>
                    <span>Remote Configuration Manager</span>
                </div>
            </div>
            <div class="header-badge" id="config-path-badge">Path: Loading...</div>
        </div>
    </header>

    <main>
        <form id="config-form" onsubmit="event.preventDefault(); saveConfig();">
            <div class="dashboard-grid">

                <!-- 1. General App Settings -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">⚙️</div>
                        <div class="card-title">General Application Settings</div>
                    </div>
                    <div class="form-grid">
                        <div class="form-group">
                            <label for="app_name">Application Name</label>
                            <input type="text" id="app_name" name="app_name" placeholder="Door Controller" required>
                        </div>
                        <div class="form-group">
                            <label for="log_level">Logging Level</label>
                            <select id="log_level" name="log_level">
                                <option value="DEBUG">DEBUG (Verbose logging)</option>
                                <option value="INFO" selected>INFO (Standard operational messages)</option>
                                <option value="WARNING">WARNING (Warnings & errors only)</option>
                                <option value="ERROR">ERROR (Errors only)</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- 2. Controller Settings -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">📡</div>
                        <div class="card-title">Door Controller Hardware Settings</div>
                    </div>
                    <div class="form-grid">
                        <div class="form-group full-width">
                            <label>Controller Hardware URLs <span class="text-muted" style="font-size:12px; font-weight:normal;">(HTTP/HTTPS URLs for hardware controllers)</span></label>
                            <div class="url-list" id="url-container">
                                <!-- URL rows populated dynamically -->
                            </div>
                            <button type="button" class="btn btn-secondary btn-sm" onclick="addUrlRow()" style="align-self: flex-start; margin-top: 8px;">
                                ➕ Add Controller URL
                            </button>
                        </div>

                        <div class="form-group">
                            <label for="username">Controller Username</label>
                            <input type="text" id="username" name="username" placeholder="admin" required>
                        </div>
                        <div class="form-group">
                            <label for="password">Controller Password</label>
                            <input type="password" id="password" name="password" placeholder="••••••••" required>
                        </div>
                        <div class="form-group">
                            <label for="recovery_delay">Recovery Delay (seconds)</label>
                            <input type="number" id="recovery_delay" name="recovery_delay" min="1" max="60" value="5" required>
                        </div>
                    </div>
                </div>

                <!-- 3. Database Settings -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">🗄️</div>
                        <div class="card-title">Database Backend Settings</div>
                    </div>
                    <div class="form-grid">
                        <div class="form-group full-width">
                            <label for="postgres_connect_string">PostgreSQL Connection String</label>
                            <div class="input-with-action">
                                <input type="text" id="postgres_connect_string" name="postgres_connect_string" class="code-input" placeholder="postgresql://user:pass@localhost:5432/dbname" required>
                                <button type="button" class="btn btn-secondary" onclick="testDatabase()">Test DB</button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 4. SSL Settings -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">🔒</div>
                        <div class="card-title">SSL / HTTPS Security Configuration</div>
                    </div>
                    <div class="form-grid">
                        <div class="form-group full-width">
                            <div class="toggle-container">
                                <div>
                                    <strong style="font-size:14px;">Enable SSL Encryption</strong>
                                    <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Enforces HTTPS and secure session parameters</div>
                                </div>
                                <label class="toggle-switch">
                                    <input type="checkbox" id="ssl_enabled" name="ssl_enabled">
                                    <span class="slider"></span>
                                </label>
                            </div>
                        </div>

                        <div class="form-group">
                            <label for="ssl_cert_file">SSL Certificate File Path</label>
                            <input type="text" id="ssl_cert_file" name="ssl_cert_file" class="code-input" placeholder="config/certs/server.crt">
                        </div>
                        <div class="form-group">
                            <label for="ssl_key_file">SSL Private Key File Path</label>
                            <input type="text" id="ssl_key_file" name="ssl_key_file" class="code-input" placeholder="config/certs/server.key">
                        </div>
                    </div>
                </div>

            </div>
        </form>
    </main>

    <div class="action-bar">
        <button type="button" class="btn btn-secondary" onclick="loadConfig()">🔄 Reset / Reload</button>
        <button type="button" class="btn btn-primary" onclick="saveConfig()">💾 Save Changes</button>
    </div>

    <div id="toast" class="toast">
        <span id="toast-message">Notification message</span>
    </div>

    <script>
        let currentConfig = {};

        async function loadConfig() {
            try {
                const res = await fetch('/api/config');
                const data = await res.json();
                if (data.status === 'success') {
                    currentConfig = data.config;
                    document.getElementById('config-path-badge').innerText = `Path: ${data.file_path}`;
                    populateForm(data.config);
                    showToast('Configuration loaded successfully', 'success');
                } else {
                    showToast('Failed to load configuration: ' + data.message, 'error');
                }
            } catch (err) {
                showToast('Network error loading configuration', 'error');
            }
        }

        function populateForm(cfg) {
            document.getElementById('app_name').value = cfg.app_name || 'Door Controller';
            const settings = cfg.settings || {};
            document.getElementById('log_level').value = settings.log_level || 'INFO';
            document.getElementById('username').value = settings.username || '';
            document.getElementById('password').value = settings.password || '';
            document.getElementById('recovery_delay').value = settings.recovery_delay || 5;
            document.getElementById('postgres_connect_string').value = settings.postgres_connect_string || '';

            // URLs
            const urlContainer = document.getElementById('url-container');
            urlContainer.innerHTML = '';
            const urls = settings.urls || ['http://192.168.1.100'];
            urls.forEach(url => addUrlRow(url));

            // SSL
            const ssl = cfg.ssl || {};
            document.getElementById('ssl_enabled').checked = !!ssl.enabled;
            document.getElementById('ssl_cert_file').value = ssl.cert_file || ssl.cert || '';
            document.getElementById('ssl_key_file').value = ssl.key_file || ssl.key || '';
        }

        function addUrlRow(value = '') {
            const urlContainer = document.getElementById('url-container');
            const row = document.createElement('div');
            row.className = 'url-row';
            row.innerHTML = `
                <input type="text" class="url-input code-input" value="${escapeHtml(value)}" placeholder="http://192.168.1.100" required>
                <button type="button" class="btn btn-secondary btn-sm" onclick="testSingleUrl(this)">Test</button>
                <button type="button" class="btn btn-danger btn-sm" onclick="removeUrlRow(this)">Remove</button>
            `;
            urlContainer.appendChild(row);
        }

        function removeUrlRow(btn) {
            const rows = document.querySelectorAll('.url-row');
            if (rows.length <= 1) {
                showToast('At least one controller URL is required', 'error');
                return;
            }
            btn.closest('.url-row').remove();
        }

        async function testSingleUrl(btn) {
            const input = btn.closest('.url-row').querySelector('input');
            const url = input.value.trim();
            if (!url) {
                showToast('Please enter a URL to test', 'error');
                return;
            }
            btn.innerText = 'Testing...';
            btn.disabled = true;
            try {
                const res = await fetch('/api/test-controller', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    showToast(`Controller REACHABLE (${data.status_code})`, 'success');
                } else {
                    showToast(`Controller UNREACHABLE: ${data.message}`, 'error');
                }
            } catch (e) {
                showToast('Test request failed', 'error');
            } finally {
                btn.innerText = 'Test';
                btn.disabled = false;
            }
        }

        async function testDatabase() {
            const connStr = document.getElementById('postgres_connect_string').value.trim();
            if (!connStr) {
                showToast('Please enter a PostgreSQL connection string', 'error');
                return;
            }
            try {
                const res = await fetch('/api/test-db', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ connect_string: connStr })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    showToast('Database Connection SUCCESSFUL!', 'success');
                } else {
                    showToast(`Database Connection FAILED: ${data.message}`, 'error');
                }
            } catch (e) {
                showToast('Database test request failed', 'error');
            }
        }

        async function saveConfig() {
            const urlInputs = document.querySelectorAll('.url-input');
            const urls = Array.from(urlInputs).map(i => i.value.trim()).filter(Boolean);
            if (urls.length === 0) {
                showToast('At least one controller URL is required', 'error');
                return;
            }

            const updatedConfig = {
                app_name: document.getElementById('app_name').value.trim(),
                settings: {
                    log_level: document.getElementById('log_level').value,
                    urls: urls,
                    username: document.getElementById('username').value.trim(),
                    password: document.getElementById('password').value,
                    recovery_delay: parseInt(document.getElementById('recovery_delay').value, 10) || 5,
                    postgres_connect_string: document.getElementById('postgres_connect_string').value.trim()
                },
                ssl: {
                    enabled: document.getElementById('ssl_enabled').checked,
                    cert_file: document.getElementById('ssl_cert_file').value.trim(),
                    key_file: document.getElementById('ssl_key_file').value.trim()
                }
            };

            try {
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updatedConfig)
                });
                const data = await res.json();
                if (data.status === 'success') {
                    showToast('Configuration saved successfully!', 'success');
                } else {
                    showToast('Failed to save: ' + data.message, 'error');
                }
            } catch (err) {
                showToast('Error saving configuration', 'error');
            }
        }

        function showToast(msg, type = 'info') {
            const toast = document.getElementById('toast');
            const toastMsg = document.getElementById('toast-message');
            toastMsg.innerText = msg;
            toast.className = `toast show ${type}`;
            setTimeout(() => {
                toast.className = 'toast';
            }, 4000);
        }

        function escapeHtml(str) {
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
        }

        window.addEventListener('DOMContentLoaded', loadConfig);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Serves the primary web management interface."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/config', methods=['GET'])
def get_config_api():
    """Returns the current active configuration."""
    try:
        cfg = load_config()
        file_path = get_config_file_path()
        return jsonify({
            'status': 'success',
            'file_path': file_path,
            'config': cfg
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/config', methods=['POST'])
def update_config_api():
    """Updates and saves the configuration back to disk."""
    new_config = request.get_json()
    if not isinstance(new_config, dict):
        return jsonify({'status': 'error', 'message': 'Invalid JSON body format'}), 400

    try:
        saved_path = save_config_to_disk(new_config)
        return jsonify({
            'status': 'success',
            'message': 'Configuration updated successfully',
            'file_path': saved_path
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/test-controller', methods=['POST'])
def test_controller_api():
    """Tests reachability of a door controller URL."""
    data = request.get_json() or {}
    url = data.get('url')
    if not url:
        return jsonify({'status': 'error', 'message': 'URL is required'}), 400

    try:
        resp = requests.get(url, timeout=3)
        return jsonify({
            'status': 'success',
            'url': url,
            'status_code': resp.status_code
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'url': url,
            'message': str(e)
        }), 200


@app.route('/api/test-db', methods=['POST'])
def test_db_api():
    """Tests connection to PostgreSQL database string."""
    data = request.get_json() or {}
    conn_str = data.get('connect_string')
    if not conn_str:
        return jsonify({'status': 'error', 'message': 'Connection string is required'}), 400

    try:
        import psycopg2
        conn = psycopg2.connect(conn_str, connect_timeout=3)
        conn.close()
        return jsonify({'status': 'success', 'message': 'Connected to PostgreSQL database successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 200


def main():
    parser = argparse.ArgumentParser(description="BeSeen Door Controller Configuration Web GUI")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5001, help="Port to run configuration GUI (default: 5001)")
    parser.add_argument("--ssl", action="store_true", help="Enable SSL/HTTPS")
    parser.add_argument("--cert", type=str, help="Path to SSL certificate file")
    parser.add_argument("--key", type=str, help="Path to SSL private key file")
    args = parser.parse_args()

    ssl_cfg = get_ssl_config(args)
    configure_app_security(app, ssl_enabled=ssl_cfg.get('enabled', False))
    ssl_context = get_ssl_context(ssl_cfg)

    log_info(f"Starting BeSeen Configuration Web GUI on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, ssl_context=ssl_context, debug=False)


if __name__ == '__main__':
    main()
