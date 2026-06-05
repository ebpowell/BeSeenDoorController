import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from door_controller.key_management_application.db_manager import FobDatabaseManager
from door_controller.common_lib.utils import log_info

app = Flask(__name__)
# Secret key is required for session and flash messaging.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'beseen_secret_key_123!_change_me')

# Lazy initialize FobDatabaseManager
db_mgr = None

def get_db_mgr():
    global db_mgr
    if db_mgr is None:
        db_mgr = FobDatabaseManager()
    return db_mgr

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def secretary_or_sysadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        if session.get('role') not in ['Secretary', 'SysAdmin']:
            flash("Unauthorized: Secretary or SysAdmin privilege required.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash("Username and password are required.", "warning")
            return render_template('login.html')
            
        try:
            user = get_db_mgr().authenticate_user(username, password)
            if user:
                session['username'] = user['username']
                session['role'] = user['role']
                flash(f"Welcome back, {username}!", "success")
                return redirect(url_for('index'))
            else:
                flash("Invalid username or password.", "danger")
        except Exception as e:
            log_info(f"Web UI Login Error: {e}")
            flash(f"Database error during login: {e}", "danger")
            
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('fobs'))

@app.route('/fobs')
@login_required
def fobs():
    try:
        role = session.get('role')
        group_id = None
        if role == 'ManagementCo':
            group_id = get_db_mgr().get_group_id_by_name('ManagementCo') or -1
            
        fobs = get_db_mgr().list_fobs(group_id=group_id)
        properties = get_db_mgr().list_properties(group_id=group_id)
        replacement_logs = get_db_mgr().list_replacement_logs()
        audit_logs = get_db_mgr().list_audit_logs()
        
        return render_template(
            'fobs.html',
            fobs=fobs,
            properties=properties,
            replacement_logs=replacement_logs,
            audit_logs=audit_logs
        )
    except Exception as e:
        log_info(f"Web UI Error: Failed to load fobs data. {e}")
        flash(f"Error loading data from database: {e}", "danger")
        return render_template('fobs.html', fobs=[], properties=[], replacement_logs=[], audit_logs=[])

@app.route('/ownership')
@secretary_or_sysadmin_required
def ownership():
    try:
        role = session.get('role')
        group_id = None
        if role == 'ManagementCo':
            group_id = get_db_mgr().get_group_id_by_name('ManagementCo') or -1
            
        properties = get_db_mgr().list_properties(group_id=group_id)
        audit_logs = get_db_mgr().list_audit_logs()
        
        return render_template(
            'ownership.html',
            properties=properties,
            audit_logs=audit_logs
        )
    except Exception as e:
        log_info(f"Web UI Error: Failed to load ownership data. {e}")
        flash(f"Error loading data from database: {e}", "danger")
        return render_template('ownership.html', properties=[], audit_logs=[])

@app.route('/groups')
@secretary_or_sysadmin_required
def groups():
    try:
        role_properties = get_db_mgr().list_group_properties()
        groups_list = get_db_mgr().list_groups()
        properties = get_db_mgr().list_properties()
        audit_logs = get_db_mgr().list_audit_logs()
        
        return render_template(
            'groups.html',
            role_properties=role_properties,
            groups=groups_list,
            properties=properties,
            audit_logs=audit_logs
        )
    except Exception as e:
        log_info(f"Web UI Error: Failed to load groups data. {e}")
        flash(f"Error loading data from database: {e}", "danger")
        return render_template('groups.html', role_properties=[], groups=[], properties=[], audit_logs=[])

@app.route('/fob/add', methods=['POST'])
@login_required
def add_fob():
    fob_id_str = request.form.get('fob_id', '').strip()
    property_id_str = request.form.get('property_id', '').strip()
    replaced_fob_id_str = request.form.get('replaced_fob_id', '').strip()
    
    if not fob_id_str or not property_id_str:
        flash("Fob ID and Address selection are required.", "warning")
        return redirect(url_for('fobs'))
    
    try:
        fob_id = int(fob_id_str)
        property_id = int(property_id_str)
    except ValueError:
        flash("Fob ID and Property ID must be valid integers.", "warning")
        return redirect(url_for('fobs'))
        
    replaced_fob_id = None
    if replaced_fob_id_str:
        try:
            replaced_fob_id = int(replaced_fob_id_str)
        except ValueError:
            flash("Replaced Fob ID must be a valid integer.", "warning")
            return redirect(url_for('fobs'))

    try:
        username = session.get('username', 'system')
        get_db_mgr().add_fob(fob_id, property_id, replaced_fob_id, username=username)
        if replaced_fob_id:
            flash(f"Fob {fob_id} assigned successfully, replacing old Fob {replaced_fob_id}.", "success")
        else:
            flash(f"Fob {fob_id} registered and assigned successfully.", "success")
    except ValueError as ve:
        flash(str(ve), "danger")
    except Exception as e:
        log_info(f"Web UI Error: Failed to add fob {fob_id}. {e}")
        flash(f"Database error: {e}", "danger")
        
    return redirect(url_for('fobs'))

@app.route('/property/update_owner', methods=['POST'])
@secretary_or_sysadmin_required
def update_property_owner():
    property_id_str = request.form.get('property_id', '').strip()
    owner_name = request.form.get('owner_name', '').strip()
    
    if not property_id_str or not owner_name:
        flash("Address and Owner Name are required.", "warning")
        return redirect(url_for('ownership'))
        
    try:
        property_id = int(property_id_str)
    except ValueError:
        flash("Property ID must be a valid integer.", "warning")
        return redirect(url_for('ownership'))
        
    try:
        username = session.get('username', 'system')
        updated = get_db_mgr().update_property_owner(property_id, owner_name, username=username)
        if updated:
            flash(f"Property owner updated to '{owner_name}' successfully.", "success")
        else:
            flash(f"Property ID {property_id} not found.", "warning")
    except Exception as e:
        log_info(f"Web UI Error: Failed to update property {property_id} owner. {e}")
        flash(f"Database error: {e}", "danger")
        
    return redirect(url_for('ownership'))

@app.route('/fob/remove/<int:fob_id>', methods=['POST'])
@login_required
def remove_fob(fob_id):
    try:
        username = session.get('username', 'system')
        removed = get_db_mgr().remove_fob(fob_id, username=username)
        if removed:
            flash(f"Fob {fob_id} removed successfully.", "success")
        else:
            flash(f"Fob {fob_id} not found.", "warning")
    except Exception as e:
        log_info(f"Web UI Error: Failed to remove fob {fob_id}. {e}")
        flash(f"Database error: {e}", "danger")
        
    return redirect(url_for('fobs'))

@app.route('/group/assign', methods=['POST'])
@secretary_or_sysadmin_required
def assign_group_access():
    group_id_str = request.form.get('group_id', '').strip()
    property_id_str = request.form.get('property_id', '').strip()

    if not group_id_str or not property_id_str:
        flash("Group and Address are required.", "warning")
        return redirect(url_for('groups'))

    try:
        group_id = int(group_id_str)
        property_id = int(property_id_str)
        get_db_mgr().assign_property_to_group(group_id, property_id, username=session.get('username'))
        flash("Granted access to group for selected address.", "success")
    except ValueError:
        flash("Group ID and Property ID must be integers.", "warning")
    except Exception as e:
        log_info(f"Web UI Error: Failed to assign group access. {e}")
        flash(f"Database error: {e}", "danger")

    return redirect(url_for('groups'))

@app.route('/group/unassign', methods=['POST'])
@secretary_or_sysadmin_required
def unassign_group_access():
    group_id_str = request.form.get('group_id', '').strip()
    property_id_str = request.form.get('property_id', '').strip()

    if not group_id_str or not property_id_str:
        flash("Group and Address are required.", "warning")
        return redirect(url_for('groups'))

    try:
        group_id = int(group_id_str)
        property_id = int(property_id_str)
        get_db_mgr().unassign_property_from_group(group_id, property_id, username=session.get('username'))
        flash("Revoked access to group for selected address.", "success")
    except ValueError:
        flash("Group ID and Property ID must be integers.", "warning")
    except Exception as e:
        log_info(f"Web UI Error: Failed to unassign group access. {e}")
        flash(f"Database error: {e}", "danger")

    return redirect(url_for('groups'))

def main():
    log_info("Starting BeSeen Door Controller Web Interface...")
    app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == '__main__':
    main()
