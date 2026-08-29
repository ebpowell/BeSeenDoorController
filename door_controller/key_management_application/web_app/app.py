import os
import calendar
import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from door_controller.key_management_application.db_manager import FobDatabaseManager
from door_controller.common_lib.utils import log_info, load_config

app = Flask(__name__)
# Secret key is required for session and flash messaging.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'beseen_secret_key_123!_change_me')

def get_ssl_config(cli_args=None):
    """
    Resolves SSL configuration options from CLI arguments, environment variables, or config.yaml.
    """
    cfg = {
        'enabled': False,
        'cert': None,
        'key': None
    }
    
    # Config file configuration
    try:
        config_data = load_config()
        ssl_section = config_data.get('ssl', {}) if isinstance(config_data, dict) else {}
        cfg['enabled'] = bool(ssl_section.get('enabled', False))
        cfg['cert'] = ssl_section.get('cert_file') or ssl_section.get('cert')
        cfg['key'] = ssl_section.get('key_file') or ssl_section.get('key')
    except Exception as e:
        log_info(f"Notice: Unable to parse ssl section from config file: {e}")

    # Environment variable overrides
    env_ssl = os.environ.get('SSL_ENABLED', '').strip().lower()
    if env_ssl in ('true', '1', 'yes', 'on'):
        cfg['enabled'] = True
    elif env_ssl in ('false', '0', 'no', 'off'):
        cfg['enabled'] = False

    env_cert = os.environ.get('SSL_CERT') or os.environ.get('SSL_CERT_PATH') or os.environ.get('SSL_CERT_FILE')
    if env_cert:
        cfg['cert'] = env_cert

    env_key = os.environ.get('SSL_KEY') or os.environ.get('SSL_KEY_PATH') or os.environ.get('SSL_KEY_FILE')
    if env_key:
        cfg['key'] = env_key

    # Command-line argument overrides
    if cli_args:
        if getattr(cli_args, 'ssl', False):
            cfg['enabled'] = True
        if getattr(cli_args, 'cert', None):
            cfg['cert'] = getattr(cli_args, 'cert')
        if getattr(cli_args, 'key', None):
            cfg['key'] = getattr(cli_args, 'key')

    return cfg

def get_ssl_context(ssl_cfg):
    """
    Returns Flask ssl_context based on resolved ssl_cfg.
    - If enabled and cert/key exist: returns (cert_path, key_path).
    - If enabled and no valid cert/key provided: returns 'adhoc'.
    - If disabled: returns None.
    """
    if not ssl_cfg or not ssl_cfg.get('enabled'):
        return None

    cert = ssl_cfg.get('cert')
    key = ssl_cfg.get('key')

    if cert and key:
        if os.path.exists(cert) and os.path.exists(key):
            return (cert, key)
        else:
            log_info(f"SSL Warning: Certificate path ({cert}) or Key path ({key}) not found on disk. Falling back to adhoc SSL context.")
            return 'adhoc'
    else:
        return 'adhoc'

def configure_app_security(app_instance, ssl_enabled=False):
    """
    Configures session cookie security flags and security headers on the Flask app.
    """
    app_instance.config['SESSION_COOKIE_HTTPONLY'] = True
    app_instance.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app_instance.config['SSL_ENABLED'] = ssl_enabled
    
    if ssl_enabled:
        app_instance.config['SESSION_COOKIE_SECURE'] = True
    else:
        app_instance.config['SESSION_COOKIE_SECURE'] = False

# Apply initial default security configuration
_initial_ssl_cfg = get_ssl_config()
_initial_ssl_context = get_ssl_context(_initial_ssl_cfg)
configure_app_security(app, ssl_enabled=(_initial_ssl_context is not None))

@app.before_request
def enforce_ssl_redirect():
    """Redirect unencrypted HTTP traffic to HTTPS if SSL is enabled and request is HTTP."""
    if app.config.get('SSL_ENABLED') and not request.is_secure:
        if request.headers.get('X-Forwarded-Proto', 'http') == 'http':
            # Preserve host and path when redirecting
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

# Lazy initialize FobDatabaseManager
db_mgr = None

def get_db_mgr():
    global db_mgr
    if db_mgr is None:
        db_mgr = FobDatabaseManager()
        db_mgr.ensure_db_functions()
    return db_mgr

def trigger_gcal_sync(reservation_id, action='sync'):
    """
    Triggers Google Calendar synchronization directly from Web UI application actions if application sync_mode is enabled.
    Supports action='sync' (insert/update) or action='delete'.
    """
    try:
        from door_controller.common_lib.gcal_sync import GoogleCalendarSync
        syncer = GoogleCalendarSync()
        if not syncer.is_application_sync_enabled():
            log_info(f"Web UI GCal Sync Notice: Application-level sync is disabled by configuration (sync_mode='{syncer.sync_mode}').")
            return
        if action == 'delete':
            res = syncer.delete_single_reservation(reservation_id)
            log_info(f"Web UI GCal Sync (Delete) for Reservation #{reservation_id}: {res.get('action')}")
        else:
            res_dict = get_db_mgr().get_reservation_by_id(reservation_id)
            if res_dict:
                res = syncer.sync_single_reservation(res_dict)
                log_info(f"Web UI GCal Sync Result for Reservation #{reservation_id}: {res.get('action')}")
    except Exception as e:
        log_info(f"Web UI GCal Sync Notice for Reservation #{reservation_id}: {e}")

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
        fobs = get_db_mgr().list_fobs(group_id=None)
        properties = get_db_mgr().list_properties(group_id=None)
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
        # if role == 'ManagementCo':
            # group_id = get_db_mgr().get_group_id_by_name('ManagementCo') or -1
            
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

@app.route('/reservations', methods=['GET', 'POST'])
@login_required
def reservations():
    if request.method == 'POST':
        property_id_str = request.form.get('property_id', '').strip()
        reservation_date = request.form.get('reservation_date', '').strip()
        blocks = request.form.getlist('blocks')
        from_time = request.form.get('from_time', '').strip()
        to_time = request.form.get('to_time', '').strip()
        event_type = request.form.get('event_type', 'Private Event').strip()
        early_setup = request.form.get('early_setup') == 'on'
        payment_made = request.form.get('payment_made') == 'on'
        deposit_on_file = request.form.get('deposit_on_file') == 'on'
        agreement_received = request.form.get('agreement_received') == 'on'

        if event_type == 'HOA Event':
            early_setup = False
            payment_made = False
            deposit_on_file = False
            agreement_received = False
            if not property_id_str:
                props = get_db_mgr().list_properties()
                property_id = props[0]['property_id'] if props else 10001
            else:
                property_id = int(property_id_str)
        else:
            if not property_id_str or not reservation_date:
                flash("Property and Reservation Date are required.", "warning")
                return redirect(url_for('reservations'))
            property_id = int(property_id_str)

        if event_type != 'HOA Event' and not blocks and not (from_time or to_time):
            flash("Please select at least one time block for the reservation.", "warning")
            return redirect(url_for('reservations'))

        try:
            username = session.get('username', 'system')
            user_role = session.get('role', 'ManagementCo')
            res_id, displaced = get_db_mgr().add_reservation(
                property_id=property_id,
                reservation_date=reservation_date,
                from_time=from_time if from_time else None,
                to_time=to_time if to_time else None,
                blocks=blocks if blocks else None,
                early_setup=early_setup,
                payment_made=payment_made,
                deposit_on_file=deposit_on_file,
                agreement_received=agreement_received,
                event_type=event_type,
                user_role=user_role,
                username=username
            )
            get_db_mgr().sync_clubhouse_reservation_permissions()
            trigger_gcal_sync(res_id, 'sync')

            if event_type == 'HOA Event':
                flash("Official Board of Directors (HOA) Event added successfully! Rate: $0.00", "success")
                if displaced:
                    for d in displaced:
                        addr = d.get('address', 'Unknown Property')
                        fee_val = float(d.get('fee', 15.00))
                        res_id_val = d.get('reservation_id', '')
                        flash(f"CONFLICT DETECTED: Reservation #{res_id_val} for '{addr}' was displaced by the HOA Event and marked for rescheduling. Early set-up revoked. Action Required: Issue fee refund of ${fee_val:.2f} to property owner.", "warning")
            else:
                if event_type == 'Community Organization':
                    calc_fee = 15.00 if len(blocks) >= 2 else 7.50
                else:
                    fee_config = get_db_mgr().get_reservation_fee_config()
                    raw_fee = fee_config.get('multi_block_fee', 30.00) if len(blocks) > 1 else fee_config.get('single_block_fee', 15.00)
                    setup_surcharge = fee_config.get('early_setup_fee', 15.00) if early_setup else 0.00
                    try:
                        calc_fee = float(raw_fee) + float(setup_surcharge)
                    except (ValueError, TypeError):
                        calc_fee = 15.00
                flash(f"Clubhouse reservation added successfully! Calculated Fee: ${calc_fee:.2f}", "success")
        except ValueError as ve:
            flash(str(ve), "danger")
        except Exception as e:
            log_info(f"Web UI Error: Failed to add reservation. {e}")
            flash(f"Database error: {e}", "danger")

        return redirect(url_for('reservations'))

    # GET request
    try:
        res_list = get_db_mgr().list_reservations()
        properties = get_db_mgr().list_properties()
        blocks_list = get_db_mgr().list_reservation_blocks()
        fee_config = get_db_mgr().get_reservation_fee_config()
        return render_template('reservations.html', reservations=res_list, properties=properties, blocks_list=blocks_list, fee_config=fee_config)
    except Exception as e:
        log_info(f"Web UI Error: Failed to load reservations page. {e}")
        flash(f"Error loading reservations: {e}", "danger")
        return render_template('reservations.html', reservations=[], properties=[], blocks_list=[], fee_config={'single_block_fee': 15.0, 'multi_block_fee': 30.0})

def generate_recurring_dates(recurrence_type, start_date_str, occurrences=6, ordinal=1, day_of_week=0, day_of_month=15):
    """
    Generates a list of datetime.date objects for a recurring schedule.
    """
    import calendar, datetime
    dates = []
    if isinstance(start_date_str, str):
        curr_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    else:
        curr_date = start_date_str

    if recurrence_type == 'nth_weekday':
        # E.g., 2nd Thursday (ordinal=2, day_of_week=3 [0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun])
        year = curr_date.year
        month = curr_date.month
        
        while len(dates) < occurrences:
            cal = calendar.monthcalendar(year, month)
            matching_days = [week[day_of_week] for week in cal if week[day_of_week] != 0]
            if matching_days:
                if ordinal == 5 or ordinal > len(matching_days):
                    target_day = matching_days[-1]
                else:
                    target_day = matching_days[ordinal - 1]
                
                target_date = datetime.date(year, month, target_day)
                if target_date >= curr_date:
                    dates.append(target_date)
            
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1

    elif recurrence_type == 'weekly':
        # Every week on day_of_week
        days_ahead = day_of_week - curr_date.weekday()
        if days_ahead < 0:
            days_ahead += 7
        target_date = curr_date + datetime.timedelta(days=days_ahead)
        
        while len(dates) < occurrences:
            dates.append(target_date)
            target_date += datetime.timedelta(weeks=1)

    elif recurrence_type == 'day_of_month':
        # E.g., 15th of every month
        year = curr_date.year
        month = curr_date.month
        
        while len(dates) < occurrences:
            _, max_days = calendar.monthrange(year, month)
            target_day = min(day_of_month, max_days)
            target_date = datetime.date(year, month, target_day)
            if target_date >= curr_date:
                dates.append(target_date)
            
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1

    return dates

@app.route('/reservations/hoa', methods=['GET', 'POST'])
@login_required
def hoa_reservations():
    user_role = session.get('role', 'ManagementCo')
    allowed_roles = ['managementco', 'sysadmin', 'secretary', 'management']
    if not user_role or str(user_role).lower() not in allowed_roles:
        flash("Unauthorized: HOA Board Events management requires administrative privileges.", "danger")
        return redirect(url_for('reservations'))

    if request.method == 'POST':
        schedule_type = request.form.get('schedule_type', 'single').strip()
        event_name = request.form.get('event_name', '').strip()
        event_description = request.form.get('event_description', '').strip()
        blocks = request.form.getlist('blocks')

        if not event_name:
            flash("Event Name is required for HOA Events.", "warning")
            return redirect(url_for('hoa_reservations'))

        try:
            username = session.get('username', 'system')
            props = get_db_mgr().list_properties()
            property_id = props[0]['property_id'] if props else 10001

            if schedule_type == 'recurring':
                recurrence_type = request.form.get('recurrence_type', 'nth_weekday')
                try:
                    ordinal = int(request.form.get('ordinal', 2))
                    day_of_week = int(request.form.get('day_of_week', 3))
                    day_of_month = int(request.form.get('day_of_month', 15))
                    occurrences = int(request.form.get('occurrences', 6))
                except ValueError:
                    ordinal, day_of_week, day_of_month, occurrences = 2, 3, 15, 6

                start_date_str = request.form.get('start_date', '').strip()
                if not start_date_str:
                    import datetime
                    start_date_str = datetime.date.today().strftime('%Y-%m-%d')

                target_dates = generate_recurring_dates(
                    recurrence_type=recurrence_type,
                    start_date_str=start_date_str,
                    occurrences=occurrences,
                    ordinal=ordinal,
                    day_of_week=day_of_week,
                    day_of_month=day_of_month
                )

                if not target_dates:
                    flash("No matching dates generated for the selected recurrence pattern.", "danger")
                    return redirect(url_for('hoa_reservations'))

                total_created = 0
                all_displaced = []
                created_dates_str = []

                for t_date in target_dates:
                    date_fmt = t_date.strftime('%Y-%m-%d')
                    res_id, displaced = get_db_mgr().add_reservation(
                        property_id=property_id,
                        reservation_date=date_fmt,
                        blocks=blocks if blocks else None,
                        event_type='HOA Event',
                        event_name=event_name,
                        event_description=event_description,
                        user_role=user_role,
                        username=username
                    )
                    total_created += 1
                    created_dates_str.append(date_fmt)
                    if displaced:
                        all_displaced.extend(displaced)
                    trigger_gcal_sync(res_id, 'sync')

                get_db_mgr().sync_clubhouse_reservation_permissions()

                ord_name = {1:'1st', 2:'2nd', 3:'3rd', 4:'4th', 5:'Last'}.get(ordinal, 'Nth')
                dow_name = {0:'Monday', 1:'Tuesday', 2:'Wednesday', 3:'Thursday', 4:'Friday', 5:'Saturday', 6:'Sunday'}.get(day_of_week, '')
                pattern_desc = f"{ord_name} {dow_name} of every month" if recurrence_type == 'nth_weekday' else f"Every {dow_name}" if recurrence_type == 'weekly' else f"Day {day_of_month} of every month"

                flash(f"Successfully scheduled {total_created} recurring HOA Events for '{pattern_desc}'! Dates: {', '.join(created_dates_str)}", "success")

                if all_displaced:
                    dis_details = ", ".join([f"Reservation #{d.get('reservation_id')} ({d.get('address')})" for d in all_displaced])
                    flash(f"CONFLICT WARNING: {len(all_displaced)} private reservation(s) were displaced by recurring HOA events ({dis_details}). Marked for rescheduling; fee refunds required.", "warning")

            else:
                reservation_date = request.form.get('reservation_date', '').strip()
                if not reservation_date:
                    flash("Reservation Date is required.", "warning")
                    return redirect(url_for('hoa_reservations'))

                res_id, displaced = get_db_mgr().add_reservation(
                    property_id=property_id,
                    reservation_date=reservation_date,
                    blocks=blocks if blocks else None,
                    event_type='HOA Event',
                    event_name=event_name,
                    event_description=event_description,
                    user_role=user_role,
                    username=username
                )
                get_db_mgr().sync_clubhouse_reservation_permissions()
                trigger_gcal_sync(res_id, 'sync')

                flash(f"Official HOA Event '{event_name}' scheduled successfully for {reservation_date}!", "success")
                if displaced:
                    for d in displaced:
                        addr = d.get('address', 'Unknown Property')
                        fee_val = float(d.get('fee', 15.00))
                        res_id_val = d.get('reservation_id', '')
                        flash(f"CONFLICT DETECTED: Reservation #{res_id_val} for '{addr}' was displaced by the HOA Event and marked for rescheduling. Early set-up revoked. Action Required: Issue fee refund of ${fee_val:.2f} to property owner.", "warning")
        except ValueError as ve:
            flash(str(ve), "danger")
        except Exception as e:
            log_info(f"Web UI Error: Failed to add HOA reservation. {e}")
            flash(f"Database error: {e}", "danger")

        return redirect(url_for('hoa_reservations'))

    # GET request
    try:
        res_list = get_db_mgr().list_reservations()
        blocks_list = get_db_mgr().list_reservation_blocks()
        return render_template('hoa_reservations.html', reservations=res_list, blocks_list=blocks_list)
    except Exception as e:
        log_info(f"Web UI Error: Failed to load HOA reservations page. {e}")
        flash(f"Error loading HOA reservations: {e}", "danger")
        return render_template('hoa_reservations.html', reservations=[], blocks_list=[])

@app.route('/reservations/delete/<int:reservation_id>', methods=['POST'])
@login_required
def delete_reservation(reservation_id):
    try:
        username = session.get('username', 'system')
        deleted = get_db_mgr().delete_reservation(reservation_id, username=username)
        if deleted:
            get_db_mgr().sync_clubhouse_reservation_permissions()
            trigger_gcal_sync(reservation_id, 'delete')
            flash("Clubhouse reservation deleted successfully.", "success")
        else:
            flash("Reservation not found.", "warning")
    except Exception as e:
        log_info(f"Web UI Error: Failed to delete reservation {reservation_id}. {e}")
        flash(f"Database error: {e}", "danger")

    return redirect(url_for('reservations'))

@app.route('/reservations/toggle_payment/<int:reservation_id>', methods=['POST'])
@login_required
def toggle_payment(reservation_id):
    try:
        current_value = request.form.get('current_value') == 'true'
        new_value = not current_value
        username = session.get('username', 'system')
        get_db_mgr().update_reservation_status(reservation_id, 'payment_made', new_value, username=username)
        get_db_mgr().sync_clubhouse_reservation_permissions()
        trigger_gcal_sync(reservation_id, 'sync')
        flash("Payment status updated.", "success")
    except Exception as e:
        log_info(f"Web UI Error: Failed to toggle payment for reservation {reservation_id}. {e}")
        flash(f"Database error: {e}", "danger")

    return redirect(url_for('reservations'))

@app.route('/reservations/create_payment_intent', methods=['POST'])
@login_required
def create_reservation_payment_intent_route():
    try:
        data = request.get_json() if request.is_json else request.form
        reservation_id_str = data.get('reservation_id', '')
        amount_str = data.get('amount')
        owner_name = data.get('owner_name', '')

        reservation_id = int(reservation_id_str) if reservation_id_str else None

        if reservation_id and not owner_name:
            res_list = get_db_mgr().list_reservations()
            res = next((r for r in res_list if r.get('reservation_id') == reservation_id), None)
            if res:
                owner_name = res.get('owner_name', 'Resident')
                if amount_str is None:
                    amount_str = res.get('fee', 15.00)

        amount = float(amount_str) if amount_str is not None else 15.00

        from PaymentProcessing import create_swipe_payment_intent
        result = create_swipe_payment_intent(
            amount_dollars=amount,
            owner_name=owner_name,
            reservation_id=reservation_id
        )

        return jsonify(result), (200 if result.get('success') else 400)
    except Exception as e:
        log_info(f"Web UI Payment Error: Failed to create payment intent. {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reservations/confirm_payment', methods=['POST'])
@login_required
def confirm_reservation_payment_route():
    try:
        data = request.get_json() if request.is_json else request.form
        reservation_id_str = data.get('reservation_id')
        payment_intent_id = data.get('payment_intent_id', '')

        if not reservation_id_str:
            return jsonify({'success': False, 'error': 'Reservation ID is required.'}), 400

        reservation_id = int(reservation_id_str)
        username = session.get('username', 'system')

        # Update clubhouse_reservations table setting payment_made = True
        get_db_mgr().update_reservation_status(reservation_id, 'payment_made', True, username=username)
        get_db_mgr().sync_clubhouse_reservation_permissions()
        trigger_gcal_sync(reservation_id, 'sync')

        flash(f"Payment transaction {payment_intent_id} processed successfully!", "success")
        return jsonify({
            'success': True,
            'reservation_id': reservation_id,
            'payment_made': True,
            'message': 'Payment successfully processed and recorded.'
        }), 200
    except Exception as e:
        log_info(f"Web UI Payment Error: Failed to confirm payment. {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reservations/toggle_deposit/<int:reservation_id>', methods=['POST'])
@login_required
def toggle_deposit(reservation_id):
    try:
        current_value = request.form.get('current_value') == 'true'
        new_value = not current_value
        username = session.get('username', 'system')
        get_db_mgr().update_reservation_status(reservation_id, 'deposit_on_file', new_value, username=username)
        get_db_mgr().sync_clubhouse_reservation_permissions()
        trigger_gcal_sync(reservation_id, 'sync')
        flash("Deposit status updated.", "success")
    except Exception as e:
        log_info(f"Web UI Error: Failed to toggle deposit for reservation {reservation_id}. {e}")
        flash(f"Database error: {e}", "danger")

    return redirect(url_for('reservations'))

@app.route('/reservations/toggle_agreement/<int:reservation_id>', methods=['POST'])
@login_required
def toggle_agreement(reservation_id):
    try:
        current_value = request.form.get('current_value') == 'true'
        new_value = not current_value
        username = session.get('username', 'system')
        get_db_mgr().update_reservation_status(reservation_id, 'agreement_received', new_value, username=username)
        get_db_mgr().sync_clubhouse_reservation_permissions()
        trigger_gcal_sync(reservation_id, 'sync')
        flash("Rental agreement status updated.", "success")
    except Exception as e:
        log_info(f"Web UI Error: Failed to toggle agreement for reservation {reservation_id}. {e}")
        flash(f"Database error: {e}", "danger")

    return redirect(url_for('reservations'))

@app.route('/deposits', methods=['GET', 'POST'])
@login_required
def deposits():
    if request.method == 'POST':
        property_id_str = request.form.get('property_id', '').strip()
        amount_str = request.form.get('amount', '150.00').strip()
        deposit_status = request.form.get('deposit_status', 'On File').strip()
        check_or_ref_no = request.form.get('check_or_ref_no', '').strip()
        deposit_date = request.form.get('deposit_date', '').strip()
        date_added = request.form.get('date_added', '').strip()
        reservation_id = request.form.get('reservation_id', '').strip()
        notes = request.form.get('notes', '').strip()

        if not property_id_str:
            flash("Property is required to record a deposit.", "warning")
            return redirect(url_for('deposits'))

        try:
            property_id = int(property_id_str)
            try:
                amount = float(amount_str)
            except ValueError:
                amount = 150.00

            username = session.get('username', 'system')
            dep_id = get_db_mgr().add_clubhouse_deposit(
                property_id=property_id,
                amount=amount,
                deposit_status=deposit_status,
                check_or_ref_no=check_or_ref_no if check_or_ref_no else None,
                deposit_date=deposit_date if deposit_date else None,
                date_added=date_added if date_added else None,
                reservation_id=reservation_id if reservation_id else None,
                notes=notes if notes else None,
                received_by=username
            )
            flash(f"Clubhouse security deposit of ${amount:.2f} recorded successfully (Deposit #{dep_id}).", "success")
        except Exception as e:
            log_info(f"Web UI Error: Failed to add deposit. {e}")
            flash(f"Database error recording deposit: {e}", "danger")

        return redirect(url_for('deposits'))

    # GET request
    try:
        deposit_list = get_db_mgr().list_clubhouse_deposits()
        properties = get_db_mgr().list_properties()
        reservations = get_db_mgr().list_reservations()

        total_on_file = sum(float(d.get('amount', 0)) for d in deposit_list if d.get('deposit_status') == 'On File')
        total_refunded = sum(float(d.get('amount', 0)) for d in deposit_list if d.get('deposit_status') == 'Refunded')
        total_forfeited = sum(float(d.get('amount', 0)) for d in deposit_list if d.get('deposit_status') == 'Forfeited')
        active_count = sum(1 for d in deposit_list if d.get('deposit_status') == 'On File')

        return render_template(
            'deposits.html',
            deposits=deposit_list,
            properties=properties,
            reservations=reservations,
            total_on_file=total_on_file,
            total_refunded=total_refunded,
            total_forfeited=total_forfeited,
            active_count=active_count
        )
    except Exception as e:
        log_info(f"Web UI Error: Failed to load deposits page. {e}")
        flash(f"Error loading deposits: {e}", "danger")
        return render_template(
            'deposits.html',
            deposits=[],
            properties=[],
            reservations=[],
            total_on_file=0.0,
            total_refunded=0.0,
            total_forfeited=0.0,
            active_count=0
        )

@app.route('/deposits/update/<int:deposit_id>', methods=['POST'])
@login_required
def update_deposit(deposit_id):
    try:
        deposit_status = request.form.get('deposit_status', 'On File').strip()
        refund_date = request.form.get('refund_date', '').strip()
        notes = request.form.get('notes', '').strip()
        username = session.get('username', 'system')

        get_db_mgr().update_clubhouse_deposit(
            deposit_id=deposit_id,
            deposit_status=deposit_status,
            refund_date=refund_date if refund_date else None,
            notes=notes if notes else None,
            username=username
        )
        flash(f"Deposit #{deposit_id} status updated to '{deposit_status}'.", "success")
    except Exception as e:
        log_info(f"Web UI Error: Failed to update deposit #{deposit_id}. {e}")
        flash(f"Database error updating deposit: {e}", "danger")

    return redirect(url_for('deposits'))

@app.route('/deposits/delete/<int:deposit_id>', methods=['POST'])
@login_required
def delete_deposit(deposit_id):
    try:
        username = session.get('username', 'system')
        get_db_mgr().delete_clubhouse_deposit(deposit_id, username=username)
        flash(f"Deposit #{deposit_id} deleted successfully.", "success")
    except Exception as e:
        log_info(f"Web UI Error: Failed to delete deposit #{deposit_id}. {e}")
        flash(f"Database error deleting deposit: {e}", "danger")

    return redirect(url_for('deposits'))

@app.route('/doors')
@login_required
def doors():
    try:
        door_list = get_db_mgr().get_door_details()
        audit_logs = get_db_mgr().list_audit_logs()
        return render_template('doors.html', doors=door_list, audit_logs=audit_logs)
    except Exception as e:
        log_info(f"Web UI Error: Failed to load door details. {e}")
        flash(f"Error loading doors from database: {e}", "danger")
        return render_template('doors.html', doors=[], audit_logs=[])

@app.route('/doors/unlock/<int:door_id>', methods=['POST'])
@login_required
def unlock_door_route(door_id):
    try:
        from door_controller.common_lib.data_manager import DataManager
        from door_controller.common_lib.utils import load_config
        
        doors_info = get_db_mgr().get_door_details()
        target_door = next((d for d in doors_info if d['door_id'] == door_id), None)
        
        if not target_door:
            flash(f"Door ID {door_id} not found.", "warning")
            return redirect(url_for('doors'))
            
        door_no = target_door['door_no']
        door_desc = target_door['door_desc']
        controller_ip = target_door['controller_ip']
        
        config = load_config()
        username = config.get('settings', {}).get('username')
        password = config.get('settings', {}).get('password')
        # Convert to IP address from CIDR
        if controller_ip.find('/32')>0:
            controller_ip = controller_ip[0:len(controller_ip)-3]
            log_info(controller_ip)
        controller_url = f"http://{controller_ip}"
        log_info(controller_url)
        # Log into the proper door controller
        data_mgr = DataManager(controller_url, username, password)
        response = data_mgr.unlock_door(door_desc, door_no)
        
        current_user = session.get('username', 'system')
        with get_db_mgr()._get_connection() as conn:
            with conn.cursor() as cur:
                get_db_mgr().log_audit_action(
                    cur,
                    current_user,
                    "Remote Door Unlock",
                    f"Unlocked door '{door_desc}' (Door #{door_no}) on controller {controller_ip}"
                )
            conn.commit()
            
        if response:
            flash(f"Remote unlock signal successfully sent to '{door_desc}'!", "success")
        else:
            flash(f"Failed to send remote unlock command to '{door_desc}'. Check controller response.", "danger")
    except Exception as e:
        log_info(f"Web UI Error: Failed to unlock door {door_id}. {e}")
        flash(f"Error executing remote door unlock: {e}", "danger")

    return redirect(url_for('doors'))

@app.route('/api/properties/search')
@login_required
def api_search_properties():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    try:
        results = get_db_mgr().search_properties(query)
        return jsonify([dict(r) for r in results])
    except Exception as e:
        log_info(f"API Error: Failed to search properties. {e}")
        return jsonify([]), 500

@app.route('/access_rules', methods=['GET', 'POST'])
@secretary_or_sysadmin_required
def access_rules():
    if request.method == 'POST':
        group_id_str = request.form.get('group_id', '').strip()
        door_id_str = request.form.get('door_id', '').strip()
        start_month = request.form.get('start_month', '').strip()
        start_day = request.form.get('start_day', '').strip()
        end_month = request.form.get('end_month', '').strip()
        end_day = request.form.get('end_day', '').strip()
        unlock_time = request.form.get('unlock_time', '').strip()
        lock_time = request.form.get('lock_time', '').strip()

        if not group_id_str or not door_id_str or not start_month or not start_day or not end_month or not end_day:
            flash("Group, Door, Start Month/Day, and End Month/Day are required.", "warning")
            return redirect(url_for('access_rules'))

        try:
            group_id = int(group_id_str)
            door_id = int(door_id_str)
            username = session.get('username', 'system')

            get_db_mgr().add_access_rule(
                group_id=group_id,
                door_id=door_id,
                start_month=start_month,
                start_day=start_day,
                end_month=end_month,
                end_day=end_day,
                start_time=unlock_time if unlock_time else None,
                end_time=lock_time if lock_time else None,
                allow=True,
                username=username
            )
            flash("Allow access rule created successfully.", "success")
        except ValueError as ve:
            flash(str(ve), "danger")
        except Exception as e:
            log_info(f"Web UI Error: Failed to add access rule. {e}")
            flash(f"Database error: {e}", "danger")

        return redirect(url_for('access_rules'))

    # GET request
    try:
        rules = get_db_mgr().list_access_rules()
        doors = get_db_mgr().get_door_details()
        groups = get_db_mgr().list_groups()
        return render_template('access_rules.html', rules=rules, doors=doors, groups=groups)
    except Exception as e:
        log_info(f"Web UI Error: Failed to load access rules page. {e}")
        flash(f"Error loading access rules: {e}", "danger")
        return render_template('access_rules.html', rules=[], doors=[], groups=[])

@app.route('/access_rules/delete/<int:perm_id>', methods=['POST'])
@secretary_or_sysadmin_required
def delete_access_rule_route(perm_id):
    try:
        username = session.get('username', 'system')
        deleted = get_db_mgr().delete_access_rule(perm_id, username=username)
        if deleted:
            flash(f"Access rule {perm_id} deleted successfully.", "success")
        else:
            flash(f"Access rule {perm_id} not found.", "warning")
    except Exception as e:
        log_info(f"Web UI Error: Failed to delete access rule {perm_id}. {e}")
        flash(f"Database error: {e}", "danger")

    return redirect(url_for('access_rules'))

@app.route('/access_rules/update/<int:perm_id>', methods=['POST'])
@secretary_or_sysadmin_required
def update_access_rule_times_route(perm_id):
    unlock_time = request.form.get('unlock_time', '').strip()
    lock_time = request.form.get('lock_time', '').strip()

    try:
        username = session.get('username', 'system')
        updated = get_db_mgr().update_access_rule_times(
            perm_id,
            start_time=unlock_time if unlock_time else None,
            end_time=lock_time if lock_time else None,
            username=username
        )
        if updated:
            flash(f"Times for access rule #{perm_id} updated successfully.", "success")
        else:
            flash(f"Access rule #{perm_id} not found.", "warning")
    except Exception as e:
        log_info(f"Web UI Error: Failed to update access rule {perm_id}. {e}")
        flash(f"Database error: {e}", "danger")

    return redirect(url_for('access_rules'))

@app.route('/calendar', methods=['GET'])
@login_required
def calendar_view():
    try:
        now = datetime.datetime.now()
        year = request.args.get('year', type=int, default=now.year)
        month = request.args.get('month', type=int, default=now.month)

        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1

        cal = calendar.Calendar(firstweekday=6) # 6 = Sunday
        month_days = cal.monthdatescalendar(year, month)

        prev_year = year if month > 1 else year - 1
        prev_month = month - 1 if month > 1 else 12
        next_year = year if month < 12 else year + 1
        next_month = month + 1 if month < 12 else 1

        month_name = datetime.date(year, month, 1).strftime('%B')

        raw_reservations = get_db_mgr().list_reservations()
        
        reservations_by_date = {}
        for r in raw_reservations:
            r_dict = dict(r)
            r_date = r_dict.get('reservation_date')
            date_str = r_date.strftime('%Y-%m-%d') if hasattr(r_date, 'strftime') else str(r_date)
            r_dict['reservation_date'] = date_str

            if 'from_time' in r_dict and r_dict['from_time'] is not None:
                r_dict['from_time'] = r_dict['from_time'].strftime('%H:%M') if hasattr(r_dict['from_time'], 'strftime') else str(r_dict['from_time'])
            
            if 'to_time' in r_dict and r_dict['to_time'] is not None:
                r_dict['to_time'] = r_dict['to_time'].strftime('%H:%M') if hasattr(r_dict['to_time'], 'strftime') else str(r_dict['to_time'])

            if 'created_at' in r_dict and r_dict['created_at'] is not None:
                r_dict['created_at'] = r_dict['created_at'].isoformat() if hasattr(r_dict['created_at'], 'isoformat') else str(r_dict['created_at'])

            if 'fee' in r_dict and r_dict['fee'] is not None:
                r_dict['fee'] = float(r_dict['fee'])

            if date_str not in reservations_by_date:
                reservations_by_date[date_str] = []
            reservations_by_date[date_str].append(r_dict)

        return render_template(
            'calendar.html',
            year=year,
            month=month,
            month_name=month_name,
            month_days=month_days,
            prev_year=prev_year,
            prev_month=prev_month,
            next_year=next_year,
            next_month=next_month,
            current_date_str=now.strftime('%Y-%m-%d'),
            reservations_by_date=reservations_by_date
        )
    except Exception as e:
        log_info(f"Web UI Error: Failed to load calendar view. {e}")
        flash(f"Error loading calendar view: {e}", "danger")
        return redirect(url_for('reservations'))

@app.route('/calendar/embed', methods=['GET'])
def calendar_embed():
    """
    Public, view-only embedded calendar route suitable for <iframe> integration on 3rd party websites.
    Does not require login authentication.
    """
    try:
        now = datetime.datetime.now()
        year = request.args.get('year', type=int, default=now.year)
        month = request.args.get('month', type=int, default=now.month)
        theme = request.args.get('theme', default='dark').strip().lower()

        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1

        cal = calendar.Calendar(firstweekday=6) # 6 = Sunday
        month_days = cal.monthdatescalendar(year, month)

        prev_year = year if month > 1 else year - 1
        prev_month = month - 1 if month > 1 else 12
        next_year = year if month < 12 else year + 1
        next_month = month + 1 if month < 12 else 1

        month_name = datetime.date(year, month, 1).strftime('%B')

        raw_reservations = get_db_mgr().list_reservations()
        
        reservations_by_date = {}
        for r in raw_reservations:
            r_dict = dict(r)
            r_date = r_dict.get('reservation_date')
            date_str = r_date.strftime('%Y-%m-%d') if hasattr(r_date, 'strftime') else str(r_date)
            r_dict['reservation_date'] = date_str

            if 'from_time' in r_dict and r_dict['from_time'] is not None:
                r_dict['from_time'] = r_dict['from_time'].strftime('%H:%M') if hasattr(r_dict['from_time'], 'strftime') else str(r_dict['from_time'])
            
            if 'to_time' in r_dict and r_dict['to_time'] is not None:
                r_dict['to_time'] = r_dict['to_time'].strftime('%H:%M') if hasattr(r_dict['to_time'], 'strftime') else str(r_dict['to_time'])

            if 'created_at' in r_dict and r_dict['created_at'] is not None:
                r_dict['created_at'] = r_dict['created_at'].isoformat() if hasattr(r_dict['created_at'], 'isoformat') else str(r_dict['created_at'])

            if 'fee' in r_dict and r_dict['fee'] is not None:
                r_dict['fee'] = float(r_dict['fee'])

            if date_str not in reservations_by_date:
                reservations_by_date[date_str] = []
            reservations_by_date[date_str].append(r_dict)

        return render_template(
            'calendar_embed.html',
            year=year,
            month=month,
            month_name=month_name,
            month_days=month_days,
            prev_year=prev_year,
            prev_month=prev_month,
            next_year=next_year,
            next_month=next_month,
            current_date_str=now.strftime('%Y-%m-%d'),
            reservations_by_date=reservations_by_date,
            embed_theme=theme
        )
    except Exception as e:
        log_info(f"Web UI Error: Failed to load embedded calendar view. {e}")
        return f"Error loading calendar embed: {e}", 500

def main(args=None):
    import argparse
    parser = argparse.ArgumentParser(description="BeSeen Door Controller Web Interface")
    parser.add_argument("--host", default=os.environ.get("FLASK_HOST", "0.0.0.0"), help="Host IP to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FLASK_PORT", 5000)), help="Port to listen on (default: 5000)")
    parser.add_argument("--ssl", action="store_true", help="Enable SSL/TLS security")
    parser.add_argument("--cert", help="Path to SSL certificate file (.crt / .pem)")
    parser.add_argument("--key", help="Path to SSL private key file (.key)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    parsed_args = parser.parse_args(args)

    ssl_cfg = get_ssl_config(parsed_args)
    ssl_context = get_ssl_context(ssl_cfg)
    configure_app_security(app, ssl_enabled=(ssl_context is not None))

    log_info("Starting BeSeen Door Controller Web Interface...")
    if ssl_context:
        log_info(f"SSL/TLS Security ENABLED on https://{parsed_args.host}:{parsed_args.port}")
    else:
        log_info(f"Running without SSL/TLS on http://{parsed_args.host}:{parsed_args.port}")

    app.run(host=parsed_args.host, port=parsed_args.port, debug=parsed_args.debug, ssl_context=ssl_context)

if __name__ == '__main__':
    main()
