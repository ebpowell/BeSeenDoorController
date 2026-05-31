import os
from flask import Flask, render_template, request, redirect, url_for, flash
from door_controller.key_management_application.db_manager import FobDatabaseManager
from door_controller.common_lib.utils import log_info

app = Flask(__name__)
# Secret key is required for flash messaging.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'beseen_secret_key_123!_change_me')

# Lazy initialize FobDatabaseManager
db_mgr = None

def get_db_mgr():
    global db_mgr
    if db_mgr is None:
        db_mgr = FobDatabaseManager()
    return db_mgr

@app.route('/')
def index():
    try:
        fobs = get_db_mgr().list_fobs()
        properties = get_db_mgr().list_properties()
        replacement_logs = get_db_mgr().list_replacement_logs()
        return render_template('index.html', fobs=fobs, properties=properties, replacement_logs=replacement_logs)
    except Exception as e:
        log_info(f"Web UI Error: Failed to load index data. {e}")
        flash(f"Error loading data from database: {e}", "danger")
        return render_template('index.html', fobs=[], properties=[], replacement_logs=[])

@app.route('/fob/add', methods=['POST'])
def add_fob():
    fob_id_str = request.form.get('fob_id', '').strip()
    property_id_str = request.form.get('property_id', '').strip()
    replaced_fob_id_str = request.form.get('replaced_fob_id', '').strip()
    
    if not fob_id_str or not property_id_str:
        flash("Fob ID and Address selection are required.", "warning")
        return redirect(url_for('index'))
    
    try:
        fob_id = int(fob_id_str)
        property_id = int(property_id_str)
    except ValueError:
        flash("Fob ID and Property ID must be valid integers.", "warning")
        return redirect(url_for('index'))
        
    replaced_fob_id = None
    if replaced_fob_id_str:
        try:
            replaced_fob_id = int(replaced_fob_id_str)
        except ValueError:
            flash("Replaced Fob ID must be a valid integer.", "warning")
            return redirect(url_for('index'))

    try:
        get_db_mgr().add_fob(fob_id, property_id, replaced_fob_id)
        if replaced_fob_id:
            flash(f"Fob {fob_id} assigned successfully, replacing old Fob {replaced_fob_id}.", "success")
        else:
            flash(f"Fob {fob_id} registered and assigned successfully.", "success")
    except ValueError as ve:
        flash(str(ve), "danger")
    except Exception as e:
        log_info(f"Web UI Error: Failed to add fob {fob_id}. {e}")
        flash(f"Database error: {e}", "danger")
        
    return redirect(url_for('index'))

@app.route('/property/update_owner', methods=['POST'])
def update_property_owner():
    property_id_str = request.form.get('property_id', '').strip()
    owner_name = request.form.get('owner_name', '').strip()
    
    if not property_id_str or not owner_name:
        flash("Address and Owner Name are required.", "warning")
        return redirect(url_for('index'))
        
    try:
        property_id = int(property_id_str)
    except ValueError:
        flash("Property ID must be a valid integer.", "warning")
        return redirect(url_for('index'))
        
    try:
        updated = get_db_mgr().update_property_owner(property_id, owner_name)
        if updated:
            flash(f"Property owner updated to '{owner_name}' successfully.", "success")
        else:
            flash(f"Property ID {property_id} not found.", "warning")
    except Exception as e:
        log_info(f"Web UI Error: Failed to update property {property_id} owner. {e}")
        flash(f"Database error: {e}", "danger")
        
    return redirect(url_for('index'))

@app.route('/fob/remove/<int:fob_id>', methods=['POST'])
def remove_fob(fob_id):
    try:
        removed = get_db_mgr().remove_fob(fob_id)
        if removed:
            flash(f"Fob {fob_id} removed successfully.", "success")
        else:
            flash(f"Fob {fob_id} not found.", "warning")
    except Exception as e:
        log_info(f"Web UI Error: Failed to remove fob {fob_id}. {e}")
        flash(f"Database error: {e}", "danger")
        
    return redirect(url_for('index'))

def main():
    log_info("Starting BeSeen Door Controller Web Interface...")
    app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == '__main__':
    main()
