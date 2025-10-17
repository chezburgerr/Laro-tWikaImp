from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from functools import wraps
import os
from datetime import datetime, timedelta
import json # For handling JSON data from user_progress
import uuid
from collections import Counter, defaultdict
from werkzeug.utils import secure_filename
import re, requests

# For password hashing (Highly Recommended!)
from werkzeug.security import generate_password_hash, check_password_hash

# 📘 Blueprint setup
admin_bp = Blueprint('admin', __name__, template_folder='templates/admin')

# 🔐 Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 📅 Inject current year for layout template footer
@admin_bp.context_processor
def inject_year():
    """Injects the current year into the template context for use in footers."""
    return {'year': datetime.now().year}

# 🔒 Admin-only access decorator
def admin_required(f):
    """Decorator to restrict access to admin users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in and has 'admin' role
        if 'user_id' not in session or session.get('role') != 'admin':
            # Flash a message for unauthorized access
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for('index')) # Redirect to a non-admin page, e.g., home
        return f(*args, **kwargs)
    return decorated_function

# --- User Management ---

@admin_bp.route('/dashboard')
@admin_required
def manage_users():
    """Displays the admin dashboard with a list of users."""
    # Pagination settings
    page = request.args.get('page', 1, type=int)
    per_page = 10 # Number of users per page
    offset = (page - 1) * per_page

    # Search and Filter parameters
    search_query = request.args.get('search', '')
    role_filter = request.args.get('role', '')
    level_filter = request.args.get('account_level', '', type=str) # Keep as string for empty check

    # Base query for users
    query = supabase.table('users').select('*', count='exact')

    # Apply search filter
    if search_query:
        # Search by username or email (case-insensitive contains)
        query = query.or_(f"username.ilike.%{search_query}%,email.ilike.%{search_query}%")

    # Apply role filter
    if role_filter:
        query = query.eq('role', role_filter)

    # Apply account level filter
    if level_filter:
        try:
            # Ensure level_filter is an integer if present
            query = query.eq('account_level', int(level_filter))
        except ValueError:
            # Handle cases where account_level is not a valid integer
            flash("Invalid account level filter.", "warning")
            pass # Continue without applying this specific filter


    # Fetch users with pagination
    # Supabase uses range for pagination (start_index, end_index)
    data, count = query.order('created_at', desc=True).range(offset, offset + per_page - 1).execute()

    users = data[1] if data else [] # The actual user data is in the second element of the tuple
    total_users = count[1] if count else 0 # The total count is in the second element of the tuple

    # Calculate total pages for pagination
    total_pages = (total_users + per_page - 1) // per_page

    return render_template('user_list.html',
                           users=users,
                           page=page,
                           total_pages=total_pages,
                           search_query=search_query,
                           role_filter=role_filter,
                           level_filter=level_filter)


@admin_bp.route('/user/<uuid:user_id>')
@admin_required
def user_detail(user_id):
    """Displays the detailed profile of a specific user."""
    
    # Fetch basic user info
    user_response = supabase.table('users').select('*').eq('id', str(user_id)).single().execute()
    user = user_response.data if user_response.data else None

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('admin.admin_dashboard'))

    # Current avatar
    user_avatar_response = supabase.table('user_avatars').select('avatars(*)') \
        .eq('user_id', str(user_id)).limit(1).execute()
    user_avatar = user_avatar_response.data[0]['avatars'] if user_avatar_response.data and user_avatar_response.data[0] and 'avatars' in user_avatar_response.data[0] else None

    # All avatars (still needed for context, even if not used for selection form)
    all_avatars_response = supabase.table('avatars').select('*').execute()
    all_avatars = all_avatars_response.data if all_avatars_response.data else []

    # Fetch user_items (item_id, quantity)
    user_items_raw = supabase.table("user_items") \
        .select("item_id, quantity") \
        .eq("user_id", str(user_id)) \
        .execute().data

    # Get item details for user's items
    user_items = []
    if user_items_raw:
        item_ids = [item["item_id"] for item in user_items_raw]
        item_data = supabase.table("items").select("id, name, description, filename, price").in_("id", item_ids).execute().data
        
        # Merge item details with user_item quantities
        for item_detail in item_data:
            matching_user_item = next((ui for ui in user_items_raw if ui["item_id"] == item_detail["id"]), None)
            if matching_user_item:
                item_detail["quantity"] = matching_user_item.get("quantity", 0)
                # Ensure the correct Supabase Storage bucket for items (should match inventory: /shopitems/)
                item_detail["image_url"] = f"https://uktdymsgfgodbwesdvsj.supabase.co/storage/v1/object/public/shopitems/{item_detail['filename']}"
                user_items.append(item_detail)

    # All available items (still needed for context, even if not used for adding form)
    all_items_response = supabase.table('items').select('*').execute()
    all_items = all_items_response.data if all_items_response.data else []

    # ✅ Fetch user's progress data
    user_progress_data_response = supabase.table('user_progress').select('*') \
                                          .eq('user_id', str(user_id)).execute()
    user_progress_data = user_progress_data_response.data if user_progress_data_response.data else []

    # --- DETAILED PROGRESS ---
    detailed_progress = []
    for progress in user_progress_data:
        lesson = progress.get('lesson')
        highest_unlocked = progress.get('highest_unlocked', 1)
        level_mastery = progress.get('level_mastery') or {}
        if isinstance(level_mastery, str):
            import json
            level_mastery = json.loads(level_mastery)
        # For each level up to highest_unlocked, get best score and question count
        levels = []
        for lvl in range(1, highest_unlocked + 1):
            best_score = level_mastery.get(str(lvl), 0)
            # If best_score is a dict, extract the score value
            if isinstance(best_score, dict):
                score_value = best_score.get("score", 0)
            else:
                score_value = best_score
            # Get total questions for this level in this lesson
            q_count_resp = supabase.table('questionanswer').select('id').eq('level', lvl).execute()
            total_questions = len(q_count_resp.data) if q_count_resp.data else 0
            # Mastered if score_value >= 80
            mastered = score_value >= 80
            levels.append({
                'level': lvl,
                'best_score': score_value,
                'total_questions': total_questions,
                'mastered': mastered
            })
        detailed_progress.append({
            'lesson': lesson,
            'highest_unlocked': highest_unlocked,
            'levels': levels
        })

    return render_template('user_detail.html',
                           user=user,
                           user_avatar=user_avatar,
                           all_avatars=all_avatars, # Still passing, but not used in template for avatar change
                           user_items=user_items,
                           all_items=all_items, # Still passing, but not used in template for item add
                           user_progress_data=user_progress_data, # Pass progress data
                           detailed_progress=detailed_progress # Pass detailed progress
    )


@admin_bp.route('/user/<uuid:user_id>/edit', methods=['POST'])
@admin_required
def edit_user(user_id):
    """Handles updating a user's information."""
    if request.method == 'POST':
        # Retrieve form data
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        coins = request.form.get('coins', type=int)
        lives = request.form.get('lives', type=int)
        preferred_language = request.form.get('preferred_language')
        lesson_language = request.form.get('lesson_language')
        account_level = request.form.get('account_level', type=int)
        current_exp = request.form.get('current_exp', type=float)

        # Build update data dictionary
        update_data = {
            'username': username,
            'email': email,
            'role': role,
            'coins': coins,
            'lives': lives,
            'preferred_language': preferred_language,
            'lesson_language': lesson_language,
            'account_level': account_level,
            'current_exp': current_exp
        }

        # Update user in Supabase
        response = supabase.table('users').update(update_data).eq('id', str(user_id)).execute()

        if response.data:
            flash(f"User '{username}' updated successfully!", "success")
        else:
            flash(f"Failed to update user '{username}'.", "danger")

    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/user/<uuid:user_id>/reset_password', methods=['POST'])
@admin_required
def reset_password(user_id):
    """Resets a user's password. Requires proper hashing!"""
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not new_password or not confirm_password:
        flash("New password and confirmation are required.", "danger")
        return redirect(url_for('admin.user_detail', user_id=user_id))

    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for('admin.user_detail', user_id=user_id))

    # --- IMPORTANT: HASH THE PASSWORD BEFORE STORING! ---
    hashed_password = generate_password_hash(new_password) # Use hashing!
    update_data = {'password': hashed_password}

    response = supabase.table('users').update(update_data).eq('id', str(user_id)).execute()

    if response.data:
        flash("Password reset successfully.", "success")
    else:
        flash("Failed to reset password.", "danger")

    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/user/<uuid:user_id>/remove_item/<int:item_id_to_remove>', methods=['POST'])
@admin_required
def remove_user_item(user_id, item_id_to_remove):
    """Removes an item from a user's inventory."""
    response = supabase.table('user_items').delete() \
                       .eq('user_id', str(user_id)).eq('item_id', item_id_to_remove).execute()

    if response.data:
        flash("Item removed from user's inventory!", "success")
    else:
        flash("Failed to remove item from user's inventory.", "danger")

    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/user/<uuid:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Deletes a user and their associated data (avatars, items, progress)."""
    # Order of deletion is important due to foreign key constraints.
    # Delete from user_avatars
    supabase.table('user_avatars').delete().eq('user_id', str(user_id)).execute()
    # Delete from user_items
    supabase.table('user_items').delete().eq('user_id', str(user_id)).execute()
    # Delete from user_progress
    supabase.table('user_progress').delete().eq('user_id', str(user_id)).execute()

    # Finally, delete the user from the users table
    response = supabase.table('users').delete().eq('id', str(user_id)).execute()

    if response.data:
        flash("User and all associated data deleted successfully!", "success")
    else:
        flash("Failed to delete user. Please check server logs.", "danger")

    return redirect(url_for('admin.admin_dashboard'))






             
  # ITEM MANAGEMENT AND AVATAR MANAGEMENT
@admin_bp.route('/items')
@admin_required
def manage_items():
    try:
        response = supabase.table('items').select('*').execute()
        items = response.data
        return render_template('items/list.html', items=items, title='Manage Items')
    except Exception as e:
        flash(f"Error fetching items: {e}", "danger")
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/items/add', methods=['GET', 'POST'])
@admin_required
def add_item():
    if request.method == 'POST':
        filename = request.form['filename']
        name = request.form['name']
        price = request.form['price']
        description = request.form.get('description')
        required_level = request.form['required_level']

        # Basic validation
        if not filename or not name or not price or not required_level:
            flash("All fields except Description are required.", "danger")
            return render_template('items/add.html', title='Add Item')

        try:
            price = int(price)
            required_level = int(required_level)
            if price < 0:
                flash("Price cannot be negative.", "danger")
                return render_template('items/add.html', title='Add Item')
        except ValueError:
            flash("Price and Required Level must be valid numbers.", "danger")
            return render_template('items/add.html', title='Add Item')

        try:
            response = supabase.table('items').insert({
                'filename': filename,
                'name': name,
                'price': price,
                'description': description,
                'required_level': required_level
            }).execute()
            flash("Item added successfully!", "success")
            return redirect(url_for('admin.manage_items'))
        except Exception as e:
            flash(f"Error adding item: {e}", "danger")

    return render_template('items/add.html', title='Add Item')

@admin_bp.route('/items/edit/<int:item_id>', methods=['GET', 'POST'])
@admin_required
def edit_item(item_id):
    if request.method == 'POST':
        filename = request.form['filename']
        name = request.form['name']
        price = request.form['price']
        description = request.form.get('description')
        required_level = request.form['required_level']

        # Basic validation
        if not filename or not name or not price or not required_level:
            flash("All fields except Description are required.", "danger")
            return redirect(url_for('admin.edit_item', item_id=item_id))

        try:
            price = int(price)
            required_level = int(required_level)
            if price < 0:
                flash("Price cannot be negative.", "danger")
                return redirect(url_for('admin.edit_item', item_id=item_id))
        except ValueError:
            flash("Price and Required Level must be valid numbers.", "danger")
            return redirect(url_for('admin.edit_item', item_id=item_id))

        try:
            response = supabase.table('items').update({
                'filename': filename,
                'name': name,
                'price': price,
                'description': description,
                'required_level': required_level
            }).eq('id', item_id).execute()

            if response.data:
                flash("Item updated successfully!", "success")
            else:
                flash("Item not found or no changes made.", "warning")
            return redirect(url_for('admin.manage_items'))
        except Exception as e:
            flash(f"Error updating item: {e}", "danger")
            return redirect(url_for('admin.edit_item', item_id=item_id))
    else:
        try:
            response = supabase.table('items').select('*').eq('id', item_id).single().execute()
            item = response.data
            if not item:
                flash("Item not found.", "danger")
                return redirect(url_for('admin.manage_items'))
            return render_template('items/edit.html', item=item, title=f'Edit Item: {item.get("name", item_id)}')
        except Exception as e:
            flash(f"Error fetching item for editing: {e}", "danger")
            return redirect(url_for('admin.manage_items'))

@admin_bp.route('/items/delete/<int:item_id>', methods=['POST'])
@admin_required
def delete_item(item_id):
    try:
        response = supabase.table('items').delete().eq('id', item_id).execute()
        if response.data:
            flash("Item deleted successfully!", "success")
        else:
            flash("Item not found or could not be deleted.", "warning")
    except Exception as e:
        flash(f"Error deleting item: {e}", "danger")
    return redirect(url_for('admin.manage_items'))


# --- Avatar Management Routes ---

@admin_bp.route('/avatars')
@admin_required
def manage_avatars():
    try:
        response = supabase.table('avatars').select('*').execute()
        avatars = response.data
        return render_template('avatars/list.html', avatars=avatars, title='Manage Avatars')
    except Exception as e:
        flash(f"Error fetching avatars: {e}", "danger")
        return redirect(url_for('admin.manage_avatars'))

@admin_bp.route('/avatars/add', methods=['GET', 'POST'])
@admin_required
def add_avatar():
    if request.method == 'POST':
        image_file = request.files.get('image')
        price = request.form.get('price')
        description = request.form.get('description')

        if not image_file or not price:
            flash("Image and Price are required.", "danger")
            return render_template('avatars/add.html', title='Add Avatar')

        try:
            ext = image_file.filename.rsplit('.', 1)[-1].lower()
            unique_filename = f"{uuid.uuid4()}.{ext}"
            file_bytes = image_file.read()

            upload_response = supabase.storage.from_('avatars').upload(
                path=unique_filename,
                file=file_bytes,
                file_options={
                    "content-type": image_file.mimetype,
                    "x-upsert": "true"
                }
            )

            if not upload_response or not hasattr(upload_response, 'path'):
                raise Exception("Image upload failed.")

            # Insert filename, price, and description into DB
            supabase.table('avatars').insert({
                'filename': unique_filename,
                'price': int(price),
                'description': description
            }).execute()

            flash("Avatar uploaded and added successfully!", "success")
            return redirect(url_for('admin.manage_avatars'))

        except Exception as e:
            flash(f"Error uploading avatar: {e}", "danger")

    return render_template('avatars/add.html', title='Add Avatar')





@admin_bp.route('/avatars/edit/<int:avatar_id>', methods=['GET', 'POST'])
@admin_required
def edit_avatar(avatar_id):
    if request.method == 'POST':
        filename = request.form['filename']
        price = request.form['price']
        description = request.form.get('description')

        # Basic validation
        if not filename or not price:
            flash("Filename and Price are required.", "danger")
            return redirect(url_for('admin.edit_avatar', avatar_id=avatar_id))

        try:
            price = int(price)
            if price < 0:
                flash("Price cannot be negative.", "danger")
                return redirect(url_for('admin.edit_avatar', avatar_id=avatar_id))
        except ValueError:
            flash("Price must be a valid number.", "danger")
            return redirect(url_for('admin.edit_avatar', avatar_id=avatar_id))

        try:
            response = supabase.table('avatars').update({
                'filename': filename,
                'price': price,
                'description': description
            }).eq('id', avatar_id).execute()

            if response.data:
                flash("Avatar updated successfully!", "success")
            else:
                flash("Avatar not found or no changes made.", "warning")
            return redirect(url_for('admin.manage_avatars'))
        except Exception as e:
            flash(f"Error updating avatar: {e}", "danger")
            return redirect(url_for('admin.edit_avatar', avatar_id=avatar_id))
    else:
        try:
            response = supabase.table('avatars').select('*').eq('id', avatar_id).single().execute()
            avatar = response.data
            if not avatar:
                flash("Avatar not found.", "danger")
                return redirect(url_for('admin.manage_avatars'))
            return render_template('avatars/edit.html', avatar=avatar, title=f'Edit Avatar: {avatar.get("filename", avatar_id)}')
        except Exception as e:
            flash(f"Error fetching avatar for editing: {e}", "danger")
            return redirect(url_for('admin.manage_avatars'))

@admin_bp.route('/avatars/delete/<int:avatar_id>', methods=['POST'])
@admin_required
def delete_avatar(avatar_id):
    try:
        response = supabase.table('avatars').delete().eq('id', avatar_id).execute()
        if response.data:
            flash("Avatar deleted successfully!", "success")
        else:
            flash("Avatar not found or could not be deleted.", "warning")
    except Exception as e:
        flash(f"Error deleting avatar: {e}", "danger")
    return redirect(url_for('admin.manage_avatars'))





@admin_bp.route('/lessons/upload', methods=['GET', 'POST'])
def upload_lesson():
    if request.method == 'POST':
        file = request.files.get('lesson_file')
        if not file or file.filename == '':
            flash("No file selected", "danger")
            return redirect(request.url)

        filename = secure_filename(file.filename)

        # Validate .txt file
        if not filename.endswith('.txt'):
            flash("Only .txt files are allowed", "danger")
            return redirect(request.url)

        # Validate naming convention
        match = re.match(r"^(tagalog|waray|cebuano)_lvl(\d+)\.txt$", filename)
        if not match:
            flash("Filename must follow naming convention: tagalog_lvlX.txt / waray_lvlX.txt / cebuano_lvlX.txt", "danger")
            return redirect(request.url)

        lang, level = match.groups()
        level = int(level)

        # Check if file already exists
        existing_files = supabase.storage.from_('lessons').list()
        if any(f['name'] == filename for f in existing_files):
            flash("A lesson with this filename already exists.", "danger")
            return redirect(request.url)

        try:
            # Read file content
            file_bytes = file.read()
            content = filename

            # Upload to Supabase bucket
            supabase.storage.from_('lessons').upload(
                path=filename,
                file=file_bytes,
                file_options={"content-type": "text/plain", "x-upsert": "false"}
            )

            # Insert into DB
            table_name = f"{lang}_lessons"
            column = lang

            supabase.table(table_name).insert({
                column: content,
                "level": level
            }).execute()

            flash(f"{lang.capitalize()} lesson for level {level} uploaded successfully!", "success")
            return redirect(url_for('admin.upload_lesson'))

        except Exception as e:
            flash(f"Upload failed: {e}", "danger")
            return redirect(request.url)

    return render_template("admin/lessons/upload_lesson.html", title="Upload Lesson")


@admin_bp.route('/admin/lessons')
@admin_required
def manage_lessons():
    try:
        files = supabase.storage.from_('lessons').list(path="")
    except Exception as e:
        flash(f"Failed to list lesson files: {e}", "danger")
        return render_template("admin/lessons/manage_lessons.html", sections={})

    sections = {"tagalog": [], "waray": [], "cebuano": []}

    for f in files:
        filename = f['name']
        match = re.match(r"^(tagalog|waray|cebuano)_lvl(\d+)\.txt$", filename)
        if match:
            lang, level = match.groups()
            sections[lang].append({
                "filename": filename,
                "level": int(level)
            })

    return render_template("admin/lessons/manage_lessons.html", title="Manage Lessons", sections=sections)


@admin_bp.route('/admin/lessons/edit/<lang>/<int:level>', methods=['GET', 'POST'])
@admin_required
def edit_lesson(lang, level):
    filename = f"{lang}_lvl{level}.txt"
    file_url = f"https://uktdymsgfgodbwesdvsj.supabase.co/storage/v1/object/public/lessons/{filename}"

    if request.method == 'POST':
        updated_content = request.form.get('content', '')
        try:
            supabase.storage.from_('lessons').upload(
                path=filename,
                file=updated_content.encode('utf-8'),
                file_options={"content-type": "text/plain", "x-upsert": "true"}
            )
            flash(f"{filename} updated successfully!", "success")
            return redirect(url_for('admin.manage_lessons'))
        except Exception as e:
            flash(f"Update failed: {e}", "danger")

    try:
        res = requests.get(file_url)
        res.raise_for_status()
        content = res.text
    except Exception as e:
        flash(f"Failed to load file content: {e}", "danger")
        content = ""

    return render_template("admin/lessons/edit_lesson.html", title=f"Edit {filename}",
                           lang=lang, level=level, content=content, filename=filename)




@admin_bp.route('/admin/dashboard')
@admin_required
def dashboard():
    now = datetime.utcnow()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # 🔍 Fetch all users
    users_response = supabase.table('users').select('*').execute()
    users = users_response.data

    total_users = len(users)
    new_today = sum(1 for u in users if u.get('created_at', '')[:10] == today.isoformat())
    new_week = sum(1 for u in users if u.get('created_at', '')[:10] >= week_ago.date().isoformat())
    new_month = sum(1 for u in users if u.get('created_at', '')[:10] >= month_ago.date().isoformat())
    total_admins = sum(1 for u in users if u.get('role') == 'admin')

    # ✅ Active user logic: simulate "active" based on recent progress
    progress_response = supabase.table('user_progress').select('*').execute()
    progress = progress_response.data
    active_user_ids = {p['user_id'] for p in progress if p.get('lesson') and p.get('highest_unlocked', 0) > 1}
    active_users_today = len(active_user_ids)

    # 📊 Additional Platform Statistics
    # Fetch questions, items, avatars counts
    questions_response = supabase.table('questionanswer').select('*').execute()
    total_questions = len(questions_response.data) if questions_response.data else 0

    items_response = supabase.table('items').select('*').execute()
    total_items = len(items_response.data) if items_response.data else 0

    avatars_response = supabase.table('avatars').select('*').execute()
    total_avatars = len(avatars_response.data) if avatars_response.data else 0

    # 📊 Economy Overview
    total_coins = sum(u.get('coins', 0) for u in users)
    total_lives = sum(u.get('lives', 0) for u in users)
    avg_level = sum(u.get('account_level', 1) for u in users) / len(users) if users else 1

    # 📊 Top Performing Users (by level and EXP)
    top_users = sorted(users, key=lambda x: (x.get('account_level', 1), x.get('current_exp', 0)), reverse=True)[:10]

    # 📊 Recent Activity (simulated - you can enhance this with actual activity tracking)
    recent_activity = []
    for user in users[:5]:  # Show last 5 registered users as recent activity
        recent_activity.append({
            'username': user.get('username', 'Unknown'),
            'action': 'Registered',
            'timestamp': user.get('created_at', '')[:19] if user.get('created_at') else 'Unknown'
        })

    # 📊 Total Lessons (across all languages)
    tagalog_lessons = supabase.table('tagalog_lessons').select('*').execute()
    waray_lessons = supabase.table('waray_lessons').select('*').execute()
    cebuano_lessons = supabase.table('cebuano_lessons').select('*').execute()
    
    total_tagalog = len(tagalog_lessons.data) if tagalog_lessons.data else 0
    total_waray = len(waray_lessons.data) if waray_lessons.data else 0
    total_cebuano = len(cebuano_lessons.data) if cebuano_lessons.data else 0
    total_lessons = total_tagalog + total_waray + total_cebuano

    # 📊 Chart: Registration Trend
    reg_dates = [u['created_at'][:10] for u in users if u.get('created_at')]
    reg_counts = Counter(reg_dates)
    sorted_dates = sorted(reg_counts)
    reg_chart_data = {
        "labels": sorted_dates,
        "counts": [reg_counts[d] for d in sorted_dates]
    }

    # 📊 Chart: Role Distribution
    roles = [u.get('role', 'user') for u in users]
    role_counts = Counter(roles)

    # 📊 Chart: Preferred Language
    pref_langs = [u.get('preferred_language') for u in users if u.get('preferred_language')]
    pref_lang_counts = Counter(pref_langs)

    # --- NEW LOGIC FOR LESSON LANGUAGE AVERAGE UNLOCKED LEVELS ---
    lesson_progress_data = defaultdict(lambda: {'total_levels': 0, 'count': 0})

    # --- NEW LOGIC: Most Attempted/Stuck Level per Lesson ---
    lesson_level_attempts = defaultdict(lambda: defaultdict(int))  # lesson -> level -> attempts

    for entry in progress:
        lesson_type = entry.get('lesson') # e.g., 'tagalog', 'waray', 'cebuano'
        highest_unlocked = entry.get('highest_unlocked')
        level_mastery = entry.get('level_mastery')
        if isinstance(level_mastery, str):
            try:
                level_mastery = json.loads(level_mastery)
            except Exception:
                level_mastery = {}
        if lesson_type and highest_unlocked is not None:
            lesson_progress_data[lesson_type]['total_levels'] += highest_unlocked
            lesson_progress_data[lesson_type]['count'] += 1
            # Count attempts for each level in this lesson
            if isinstance(level_mastery, dict):
                for lvl, stats in level_mastery.items():
                    if isinstance(stats, dict):
                        attempts = stats.get('attempts', 0)
                        lesson_level_attempts[lesson_type][int(lvl)] += attempts

    lesson_lang_avg_levels = {}
    for lesson, data in lesson_progress_data.items():
        if data['count'] > 0:
            lesson_lang_avg_levels[lesson] = round(data['total_levels'] / data['count'], 2)
        else:
            lesson_lang_avg_levels[lesson] = 0 # Handle cases with no progress for a language

    # Find the most attempted/stuck level for each lesson
    lesson_most_attempted_levels = {}
    for lesson, level_attempts in lesson_level_attempts.items():
        if level_attempts:
            most_attempted_level = max(level_attempts.items(), key=lambda x: x[1])
            lesson_most_attempted_levels[lesson] = {'level': most_attempted_level[0], 'attempts': most_attempted_level[1]}
        else:
            lesson_most_attempted_levels[lesson] = None

    # Prepare data for the frontend chart
    lesson_lang_chart_labels = list(lesson_lang_avg_levels.keys())
    lesson_lang_chart_data = list(lesson_lang_avg_levels.values())

    # ✅ Render everything to template
    return render_template('admin/dashboard.html',
        total_users=total_users,
        new_today=new_today,
        new_week=new_week,
        new_month=new_month,
        total_admins=total_admins,
        active_users_today=active_users_today,
        total_questions=total_questions,
        total_items=total_items,
        total_avatars=total_avatars,
        total_lessons=total_lessons,
        total_coins=total_coins,
        total_lives=total_lives,
        avg_level=round(avg_level, 1),
        top_users=top_users,
        recent_activity=recent_activity,
        reg_chart_data=reg_chart_data,
        role_counts=role_counts,
        pref_lang_counts=pref_lang_counts,
        lesson_lang_chart_labels=lesson_lang_chart_labels,
        lesson_lang_chart_data=lesson_lang_chart_data,
        lesson_most_attempted_levels=lesson_most_attempted_levels,
        current_time=now.strftime('%B %d, %Y, %I:%M %p')
    )


@admin_bp.route('/questions')
def manage_questions():
    level = request.args.get("level")
    type_filter = request.args.get("type")

    query = supabase.table("questionanswer").select("*")

    if level:
        query = query.eq("level", int(level))
    if type_filter:
        query = query.eq("type", type_filter)

    result = query.order("level").order("itemnum").execute()
    questions = result.data

    return render_template("admin/questions/manage_questions.html", questions=questions, title="Manage Questions")




@admin_bp.route('/questions/add', methods=['GET', 'POST'])
def add_question():
    if request.method == 'POST':
        level = int(request.form["level"])
        itemnum = int(request.form["itemnum"])

        # 🔍 Check for duplicates (same level + itemnum)
        existing = supabase.table("questionanswer")\
            .select("id")\
            .eq("level", level)\
            .eq("itemnum", itemnum)\
            .execute()

        if existing.data:
            flash(f"Item number {itemnum} already exists for level {level}.", "danger")
            return redirect(request.url)

        # Proceed with insertion
        data = {
            "level": level,
            "itemnum": itemnum,
            "english": request.form["english"],
            "tagalog": request.form["tagalog"],
            "waray": request.form["waray"],
            "cebuano": request.form["cebuano"],
            "type": request.form["type"]
        }
        supabase.table("questionanswer").insert(data).execute()
        flash("Question added successfully!", "success")
        return redirect(url_for('admin.manage_questions'))

    return render_template("admin/questions/add_question.html", title="Add Question")



@admin_bp.route('/questions/edit/<int:question_id>', methods=['GET', 'POST'])
def edit_question(question_id):
    question = supabase.table("questionanswer")\
        .select("*").eq("id", question_id).single().execute().data

    if request.method == 'POST':
        level = int(request.form["level"])
        itemnum = int(request.form["itemnum"])

        # ❗ Check if another record (≠ this one) has the same level+itemnum
        duplicate = supabase.table("questionanswer")\
            .select("id")\
            .eq("level", level)\
            .eq("itemnum", itemnum)\
            .neq("id", question_id)\
            .execute()

        if duplicate.data:
            flash(f"Another question already exists with item number {itemnum} for level {level}.", "danger")
            return redirect(request.url)

        updated = {
            "level": level,
            "itemnum": itemnum,
            "english": request.form["english"],
            "tagalog": request.form["tagalog"],
            "waray": request.form["waray"],
            "cebuano": request.form["cebuano"],
            "type": request.form["type"]
        }
        supabase.table("questionanswer").update(updated).eq("id", question_id).execute()
        flash("Question updated successfully", "success")
        return redirect(url_for('admin.manage_questions'))

    return render_template("admin/questions/edit_question.html", question=question, title="Edit Question")



@admin_bp.route('/questions/delete/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    supabase.table("questionanswer").delete().eq("id", question_id).execute()
    flash("Question deleted", "danger")
    return redirect(url_for('admin.manage_questions'))


# --- Distractor Management Routes ---

@admin_bp.route('/distractors')
@admin_required
def manage_distractors():
    """Displays a list of all distractors with filtering options."""
    level = request.args.get("level", type=int)
    itemnum = request.args.get("itemnum", type=int)

    query = supabase.table("distractor").select("*")

    if level:
        query = query.eq("level", level)
    if itemnum:
        query = query.eq("itemnum", itemnum)

    result = query.order("level").order("itemnum").execute()
    distractors = result.data

    return render_template("admin/distractors/manage_distractors.html", 
                         distractors=distractors, 
                         title="Manage Distractors")


@admin_bp.route('/distractors/add', methods=['GET', 'POST'])
@admin_required
def add_distractor():
    """Add a new distractor."""
    if request.method == 'POST':
        level = int(request.form["level"])
        itemnum = int(request.form["itemnum"])

        # Check if the question exists
        question_exists = supabase.table("questionanswer")\
            .select("id")\
            .eq("level", level)\
            .eq("itemnum", itemnum)\
            .execute()

        if not question_exists.data:
            flash(f"No question found for level {level}, item {itemnum}. Please add the question first.", "danger")
            return redirect(request.url)

        # Check for duplicate distractor (same level + itemnum)
        existing = supabase.table("distractor")\
            .select("id")\
            .eq("level", level)\
            .eq("itemnum", itemnum)\
            .execute()

        if existing.data:
            flash(f"A distractor already exists for level {level}, item {itemnum}.", "danger")
            return redirect(request.url)

        # Proceed with insertion
        data = {
            "level": level,
            "itemnum": itemnum,
            "english": request.form["english"],
            "tagalog": request.form["tagalog"],
            "waray": request.form["waray"],
            "cebuano": request.form["cebuano"]
        }
        
        try:
            supabase.table("distractor").insert(data).execute()
            flash("Distractor added successfully!", "success")
            return redirect(url_for('admin.manage_distractors'))
        except Exception as e:
            flash(f"Error adding distractor: {e}", "danger")
            return redirect(request.url)

    return render_template("admin/distractors/add_distractor.html", title="Add Distractor")


@admin_bp.route('/distractors/edit/<int:distractor_id>', methods=['GET', 'POST'])
@admin_required
def edit_distractor(distractor_id):
    """Edit an existing distractor."""
    # Get the distractor
    distractor_response = supabase.table("distractor")\
        .select("*").eq("id", distractor_id).single().execute()
    
    if not distractor_response.data:
        flash("Distractor not found.", "danger")
        return redirect(url_for('admin.manage_distractors'))
    
    distractor = distractor_response.data

    if request.method == 'POST':
        level = int(request.form["level"])
        itemnum = int(request.form["itemnum"])

        # Check if the question exists
        question_exists = supabase.table("questionanswer")\
            .select("id")\
            .eq("level", level)\
            .eq("itemnum", itemnum)\
            .execute()

        if not question_exists.data:
            flash(f"No question found for level {level}, item {itemnum}. Please add the question first.", "danger")
            return redirect(request.url)

        # Check if another distractor has the same level+itemnum (excluding current one)
        duplicate = supabase.table("distractor")\
            .select("id")\
            .eq("level", level)\
            .eq("itemnum", itemnum)\
            .neq("id", distractor_id)\
            .execute()

        if duplicate.data:
            flash(f"Another distractor already exists for level {level}, item {itemnum}.", "danger")
            return redirect(request.url)

        updated = {
            "level": level,
            "itemnum": itemnum,
            "english": request.form["english"],
            "tagalog": request.form["tagalog"],
            "waray": request.form["waray"],
            "cebuano": request.form["cebuano"]
        }
        
        try:
            supabase.table("distractor").update(updated).eq("id", distractor_id).execute()
            flash("Distractor updated successfully!", "success")
            return redirect(url_for('admin.manage_distractors'))
        except Exception as e:
            flash(f"Error updating distractor: {e}", "danger")
            return redirect(request.url)

    return render_template("admin/distractors/edit_distractor.html", 
                         distractor=distractor, 
                         title="Edit Distractor")


@admin_bp.route('/distractors/delete/<int:distractor_id>', methods=['POST'])
@admin_required
def delete_distractor(distractor_id):
    """Delete a distractor."""
    try:
        supabase.table("distractor").delete().eq("id", distractor_id).execute()
        flash("Distractor deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting distractor: {e}", "danger")
    
    return redirect(url_for('admin.manage_distractors'))


@admin_bp.route('/distractors/bulk_add', methods=['GET', 'POST'])
@admin_required
def bulk_add_distractors():
    """Bulk add distractors for a specific level."""
    if request.method == 'POST':
        level = int(request.form["level"])
        
        # Get all questions for this level
        questions_response = supabase.table("questionanswer")\
            .select("level, itemnum")\
            .eq("level", level)\
            .order("itemnum")\
            .execute()
        
        questions = questions_response.data
        
        if not questions:
            flash(f"No questions found for level {level}. Please add questions first.", "danger")
            return redirect(request.url)
        
        # Get existing distractors for this level
        existing_distractors_response = supabase.table("distractor")\
            .select("level, itemnum")\
            .eq("level", level)\
            .execute()
        
        existing_distractors = {(d['level'], d['itemnum']) for d in existing_distractors_response.data}
        
        # Find questions without distractors
        questions_without_distractors = [
            q for q in questions 
            if (q['level'], q['itemnum']) not in existing_distractors
        ]
        
        if not questions_without_distractors:
            flash(f"All questions in level {level} already have distractors.", "info")
            return redirect(url_for('admin.manage_distractors'))
        
        return render_template("admin/distractors/bulk_add_distractors.html",
                             level=level,
                             questions=questions_without_distractors,
                             title=f"Bulk Add Distractors - Level {level}")
    
    return render_template("admin/distractors/bulk_add_form.html", title="Bulk Add Distractors")


@admin_bp.route('/distractors/bulk_add/process', methods=['POST'])
@admin_required
def process_bulk_add_distractors():
    """Process bulk addition of distractors."""
    level = int(request.form["level"])
    added_count = 0
    
    # Get all form data
    form_data = request.form.to_dict()
    
    for key, value in form_data.items():
        if key.startswith('itemnum_'):
            itemnum = int(key.replace('itemnum_', ''))
            
            # Check if this question already has a distractor
            existing = supabase.table("distractor")\
                .select("id")\
                .eq("level", level)\
                .eq("itemnum", itemnum)\
                .execute()
            
            if existing.data:
                continue  # Skip if distractor already exists
            
            # Get the distractor data for this item
            english = form_data.get(f'english_{itemnum}', '')
            tagalog = form_data.get(f'tagalog_{itemnum}', '')
            waray = form_data.get(f'waray_{itemnum}', '')
            cebuano = form_data.get(f'cebuano_{itemnum}', '')
            
            # Only add if at least one language field is filled
            if english or tagalog or waray or cebuano:
                data = {
                    "level": level,
                    "itemnum": itemnum,
                    "english": english,
                    "tagalog": tagalog,
                    "waray": waray,
                    "cebuano": cebuano
                }
                
                try:
                    supabase.table("distractor").insert(data).execute()
                    added_count += 1
                except Exception as e:
                    flash(f"Error adding distractor for item {itemnum}: {e}", "danger")
    
    if added_count > 0:
        flash(f"Successfully added {added_count} distractors for level {level}!", "success")
    else:
        flash("No new distractors were added.", "info")
    
    return redirect(url_for('admin.manage_distractors'))


# --- Boss Levels Management ---

@admin_bp.route('/boss_levels')
@admin_required
def manage_boss_levels():
    """Displays all boss levels."""
    try:
        response = supabase.table('boss_levels').select('*').order('boss').order('itemnum').execute()
        boss_levels = response.data
        return render_template('boss_levels/list.html', boss_levels=boss_levels, title='Manage Boss Levels')
    except Exception as e:
        flash(f"Error fetching boss levels: {e}", "danger")
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/boss_levels/add', methods=['GET', 'POST'])
@admin_required
def add_boss_level():
    if request.method == 'POST':
        boss = request.form.get('boss', type=int)
        itemnum = request.form.get('itemnum', type=int)
        tagalog = request.form.get('tagalog', '').strip()
        waray = request.form.get('waray', '').strip()
        cebuano = request.form.get('cebuano', '').strip()
        type_ = request.form.get('type', '').strip()

        # Basic validation
        if boss is None or itemnum is None or not tagalog or not waray or not cebuano or not type_:
            flash("All fields are required.", "danger")
            return render_template('boss_levels/add.html', title='Add Boss Level')

        try:
            # Check for duplicate (same boss + itemnum)
            existing = supabase.table('boss_levels').select('id').eq('boss', boss).eq('itemnum', itemnum).execute()
            if existing.data:
                flash(f"Item number {itemnum} already exists for boss {boss}.", "danger")
                return render_template('boss_levels/add.html', title='Add Boss Level')
            # Insert new boss level
            supabase.table('boss_levels').insert({
                'boss': boss,
                'itemnum': itemnum,
                'tagalog': tagalog,
                'waray': waray,
                'cebuano': cebuano,
                'type': type_
            }).execute()
            flash("Boss level added successfully!", "success")
            return redirect(url_for('admin.manage_boss_levels'))
        except Exception as e:
            flash(f"Error adding boss level: {e}", "danger")
    return render_template('boss_levels/add.html', title='Add Boss Level')

@admin_bp.route('/boss_levels/edit/<int:boss_level_id>', methods=['GET', 'POST'])
@admin_required
def edit_boss_level(boss_level_id):
    boss_level = supabase.table('boss_levels').select('*').eq('id', boss_level_id).single().execute().data
    if not boss_level:
        flash("Boss level not found.", "danger")
        return redirect(url_for('admin.manage_boss_levels'))
    if request.method == 'POST':
        boss = request.form.get('boss', type=int)
        itemnum = request.form.get('itemnum', type=int)
        tagalog = request.form.get('tagalog', '').strip()
        waray = request.form.get('waray', '').strip()
        cebuano = request.form.get('cebuano', '').strip()
        type_ = request.form.get('type', '').strip()
        # Basic validation
        if boss is None or itemnum is None or not tagalog or not waray or not cebuano or not type_:
            flash("All fields are required.", "danger")
            return render_template('boss_levels/edit.html', boss_level=boss_level, title='Edit Boss Level')
        try:
            # Check for duplicate (same boss + itemnum, not this id)
            duplicate = supabase.table('boss_levels').select('id').eq('boss', boss).eq('itemnum', itemnum).neq('id', boss_level_id).execute()
            if duplicate.data:
                flash(f"Another boss level already exists with item number {itemnum} for boss {boss}.", "danger")
                return render_template('boss_levels/edit.html', boss_level=boss_level, title='Edit Boss Level')
            # Update boss level
            supabase.table('boss_levels').update({
                'boss': boss,
                'itemnum': itemnum,
                'tagalog': tagalog,
                'waray': waray,
                'cebuano': cebuano,
                'type': type_
            }).eq('id', boss_level_id).execute()
            flash("Boss level updated successfully!", "success")
            return redirect(url_for('admin.manage_boss_levels'))
        except Exception as e:
            flash(f"Error updating boss level: {e}", "danger")
    return render_template('boss_levels/edit.html', boss_level=boss_level, title='Edit Boss Level')

@admin_bp.route('/boss_levels/delete/<int:boss_level_id>', methods=['POST'])
@admin_required
def delete_boss_level(boss_level_id):
    try:
        response = supabase.table('boss_levels').delete().eq('id', boss_level_id).execute()
        if response.data:
            flash("Boss level deleted successfully!", "success")
        else:
            flash("Boss level not found or could not be deleted.", "warning")
    except Exception as e:
        flash(f"Error deleting boss level: {e}", "danger")
    return redirect(url_for('admin.manage_boss_levels'))





