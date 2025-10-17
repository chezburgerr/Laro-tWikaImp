from flask import Flask, render_template, jsonify, request, redirect, Response
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
import os
import random
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from flask import session, redirect, url_for
from functools import wraps
import requests
import base64
from speech_routes import speech_bp
from admin import admin_bp
from level_lesson import level_bp  # Import your blueprint
import json
import time

# Add database connection helper
def ensure_db_connection():
    """Test database connection and reconnect if needed"""
    global supabase
    try:
        # Simple test query
        supabase.table("users").select("id").limit(1).execute()
        return True
    except Exception as e:
        print(f"❌ Database connection error: {str(e)}")
        try:
            # Try to recreate the connection
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✅ Database connection reestablished")
            return True
        except Exception as reconnect_error:
            print(f"❌ Failed to reconnect to database: {str(reconnect_error)}")
            return False

# Load environment variables from .env file

load_dotenv()

app = Flask(__name__)
app.register_blueprint(speech_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(level_bp)


# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
app.secret_key = os.getenv("FLASK_SECRET_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Gemini AI setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")



# Home (Signup Page)
@app.route('/')
def index():
    return render_template('signup.html')  # update this if your file is named differently

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))  # or your login page
        return f(*args, **kwargs)
    return decorated_function

# Signup Route
@app.route("/signup", methods=["POST"])
def signup():
    email = request.form.get("email")
    username = request.form.get("username")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    if password != confirm_password:
        return "❌ Passwords do not match", 400

    # Check if email already exists
    existing_user = supabase.table("users").select("*").eq("email", email).execute()
    if existing_user.data:
        return "❌ Email already registered", 400

    # Insert new user
    response = supabase.table("users").insert({
        "email": email,
        "username": username,
        "password": generate_password_hash(password),
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    if response.data:
        return redirect('/')
    else:
        return f"❌ Supabase Error: {response}", 500

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")

    user_data = supabase.table("users").select("*").eq("email", email).execute()
    if not user_data.data:
        return "❌ Email not found", 400

    user = user_data.data[0]

    if not check_password_hash(user["password"], password):
        return "❌ Incorrect password", 400

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user.get("role", "user")  # 👈 add this

    # Redirect to admin dashboard if role is admin
    if session["role"] == "admin":
         return redirect(url_for('admin.dashboard'))
    else:
        return redirect("/select_lesson")


@app.route('/logout')
def logout():
    session.clear()  # or session.pop('user_id', None)
    return redirect('/')

@app.route('/tutorial')
@login_required
def tutorial():
    return render_template('div.html', page='tutorial.html')


@app.route('/api/google-tts', methods=['POST'])
@login_required
def google_tts():
    data = request.get_json()
    text = data.get("text")
    language_code = data.get("language", "id-ID")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Clean the text - remove extra spaces and trim
    text = text.strip()
    if not text:
        return jsonify({"error": "Empty text after cleaning"}), 400

    # Map language codes to supported Google TTS codes
    language_mapping = {
        'fil-PH': 'id-ID',  # Filipino -> Indonesian (better support)
        'waray': 'id-ID',   # Waray -> Indonesian
        'cebuano': 'id-ID', # Cebuano -> Indonesian
        'tagalog': 'id-ID'  # Tagalog -> Indonesian
    }
    
    # Use mapped language code or fallback to id-ID
    mapped_language = language_mapping.get(language_code, language_code)
    if mapped_language not in ['id-ID', 'en-US', 'en-GB']:
        mapped_language = 'id-ID'  # Default fallback

    GOOGLE_TTS_API_KEY = os.getenv("GOOGLE_TTS_API_KEY")
    if not GOOGLE_TTS_API_KEY:
        return jsonify({"error": "Google TTS API key not configured"}), 500

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_TTS_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": mapped_language,
            "ssmlGender": "MALE"
        },
        "audioConfig": {
            "audioEncoding": "MP3"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            audio_content = response.json()["audioContent"]
            return jsonify({"audio": audio_content})
        else:
            error_details = response.text
            print(f"Google TTS API Error: {response.status_code} - {error_details}")
            return jsonify({
                "error": "TTS failed", 
                "details": error_details,
                "language_code": language_code,
                "mapped_language": mapped_language
            }), 500
            
    except requests.exceptions.RequestException as e:
        print(f"Google TTS Request Error: {str(e)}")
        return jsonify({"error": "TTS request failed", "details": str(e)}), 500

@app.route('/profile')
@login_required
def profile():
    user_id = session['user_id']
    result = supabase.table('users').select('*').eq('id', user_id).single().execute()
    user = result.data

    # Fallback image
    if not user.get('profile_picture'):
        user['profile_picture_url'] = url_for('static', filename='avatars/default.png')
    else:
        user['profile_picture_url'] = f"https://uktdymsgfgodbwesdvsj.supabase.co/storage/v1/object/public/avatars/{user['profile_picture']}"

    # EXP Progress Calculation
    account_level = user.get("account_level", 1)
    current_exp = user.get("current_exp", 0)
    required_exp = 50 * (1.05 ** (account_level - 1))
    exp_percent = round((current_exp / required_exp) * 100, 1)

    user["required_exp"] = round(required_exp, 2)
    user["exp_percent"] = min(exp_percent, 100)

    return render_template('div.html', page='profile.html', user=user)


@app.route('/api/update-preferred-language', methods=['POST'])
@login_required
def update_preferred_language():
    user_id = session['user_id']
    data = request.get_json()
    language = data.get("language")

    if language not in ["english", "tagalog", "waray", "cebuano"]:
        return jsonify({"success": False, "message": "Invalid language."})

    result = supabase.table("users").update({
        "preferred_language": language
    }).eq("id", user_id).execute()

    if result.data:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False})



@app.route('/select-avatar')
@login_required
def select_avatar():
    user_id = session.get("user_id")

    # Get all avatar_ids the user has bought
    user_avatars = supabase.table("user_avatars").select("avatar_id").eq("user_id", user_id).execute().data
    unlocked_avatar_ids = [ua['avatar_id'] for ua in user_avatars]

    # Fetch avatar data for those ids only
    if unlocked_avatar_ids:
        avatars = supabase.table("avatars").select("*").in_("id", unlocked_avatar_ids).execute().data
    else:
        avatars = []

    # Add full Supabase public URL to each avatar
    for avatar in avatars:
        avatar["url"] = f"https://uktdymsgfgodbwesdvsj.supabase.co/storage/v1/object/public/avatars/{avatar['filename']}"

    return render_template("div.html", page="select_avatar.html", avatars=avatars)



@app.route('/select-avatar', methods=['POST'])
@login_required
def set_avatar():
    avatar_id = request.form.get("avatar_id")
    user_id = session.get("user_id")

    # Get filename of selected avatar
    avatar_data = supabase.table("avatars").select("filename").eq("id", avatar_id).single().execute().data

    if avatar_data:
        # Save selected avatar to user's profile
        supabase.table("users").update({
            "profile_picture": avatar_data["filename"]
        }).eq("id", user_id).execute()

    return redirect('/profile')

@app.route('/api/boss-reward', methods=['POST'])
@login_required
def reward_boss_level():
    user_id = session.get("user_id")
    data = request.json
    boss_num = data.get("boss")
    lesson = data.get("lesson")

    if not boss_num or not lesson:
        return jsonify({"message": "Missing boss number or lesson"}), 400

    # Get previous boss reward from user's progress
    previous_boss_reward = 0
    if int(boss_num) > 1:
        # Get the previous boss reward from user's progress
        progress_data = supabase.table("user_progress") \
            .select("boss_rewards") \
            .eq("user_id", user_id) \
            .eq("lesson", lesson) \
            .single() \
            .execute().data
        
        if progress_data and progress_data.get("boss_rewards"):
            boss_rewards = progress_data["boss_rewards"]
            if isinstance(boss_rewards, str):
                try:
                    boss_rewards = json.loads(boss_rewards)
                except:
                    boss_rewards = {}
            
            previous_boss_reward = boss_rewards.get(str(int(boss_num) - 1), 0)
    
    # Calculate new reward: 30% higher than previous, or base reward for first boss
    if previous_boss_reward > 0:
        reward = int(round(previous_boss_reward * 1.3))  # 30% increase
    else:
        reward = 200  # Base reward for first boss
    
    print(f"🧮 Boss {boss_num} reward calculation:")
    print(f"   Previous boss reward: {previous_boss_reward}")
    print(f"   New reward: {reward}")

    # Get current coin count
    user_data = (
        supabase.table("users")
        .select("coins")
        .eq("id", user_id)
        .single()
        .execute()
    )

    user = user_data.data
    if not user:
        print("❌ User not found.")
        return jsonify({"message": "User not found"}), 404

    current_coins = user.get("coins", 0)
    new_coins = current_coins + reward
    print(f"💰 Coins before: {current_coins}, after: {new_coins}")

    # Update coins
    supabase.table("users").update({"coins": new_coins}).eq("id", user_id).execute()

    # Store this boss reward for future calculations
    progress_data = supabase.table("user_progress") \
        .select("boss_rewards") \
        .eq("user_id", user_id) \
        .eq("lesson", lesson) \
        .single() \
        .execute().data
    
    boss_rewards = {}
    if progress_data and progress_data.get("boss_rewards"):
        stored_rewards = progress_data["boss_rewards"]
        if isinstance(stored_rewards, str):
            try:
                boss_rewards = json.loads(stored_rewards)
            except:
                boss_rewards = {}
        else:
            boss_rewards = stored_rewards
    
    boss_rewards[str(boss_num)] = reward
    
    # Update or insert the boss rewards
    if progress_data:
        supabase.table("user_progress").update({
            "boss_rewards": json.dumps(boss_rewards)
        }).eq("user_id", user_id).eq("lesson", lesson).execute()
    else:
        supabase.table("user_progress").insert({
            "user_id": user_id,
            "lesson": lesson,
            "highest_unlocked": 1,
            "boss_rewards": json.dumps(boss_rewards)
        }).execute()

    return jsonify({
        "message": "✅ Boss coins rewarded!",
        "reward": reward,
        "new_balance": new_coins,
        "previous_reward": previous_boss_reward
    })



@app.route('/api/reward', methods=['POST'])
@login_required
def reward_user():
    try:
        # Ensure database connection
        if not ensure_db_connection():
            return jsonify({
                "message": "Database connection error",
                "error": "Unable to connect to database",
                "reward": 0,
                "new_balance": 0,
                "discovered_words": 0
            }), 503
        
        user_id = session.get("user_id")
        data = request.json or {}
        level = data.get("level")
        lesson = data.get("lesson")
        base_reward = 10  # Initial reward for level 1

        if not level or not lesson:
            return jsonify({"message": "Missing level or lesson"}), 400

        # Get highest unlocked level for this user and lesson
        progress = (
            supabase.table("user_progress")
            .select("highest_unlocked")
            .eq("user_id", user_id)
            .eq("lesson", lesson)
            .single()
            .execute()
            .data
        )

        highest_unlocked = progress["highest_unlocked"] if progress else 1
        # Only treat as repeat if level is less than the most recently completed level
        is_repeat = int(level) < int(highest_unlocked) - 1

        # Calculate reward:
        reward = base_reward * (1.15 ** (int(level) - 1))
        if is_repeat:
            reward *= 0.5  # 50% penalty for repeated levels
        reward = int(round(reward))

        # Get current coin count
        user = (
            supabase.table("users")
            .select("coins")
            .eq("id", user_id)
            .single()
            .execute()
            .data
        )
        current_coins = user.get("coins", 0)
        new_coins = current_coins + reward

        # Update coins
        supabase.table("users").update({"coins": new_coins}).eq("id", user_id).execute()

        # ✅ Step: Count discovered words based on completed levels
        last_level = highest_unlocked
        # exclude the next locked level
        if last_level < 1:
            word_count = 0
        else:
            # Only count new words if this is the most recently completed level
            if int(level) == int(highest_unlocked) - 1:
                question_data = supabase.table("questionanswer") \
                    .select("itemnum, level, english, tagalog, waray, cebuano") \
                    .eq("level", level) \
                    .execute().data

                language_column = lesson.lower()
                word_set = set()

                for row in question_data:
                    raw = row.get(language_column, "")
                    cleaned = ''.join(c for c in raw if c.isalnum() or c.isspace()).title()
                    word_set.update(cleaned.split())

                word_count = len(word_set)
            else:
                word_count = 0
            

        return jsonify({
            "message": "✅ Coins rewarded!",
            "reward": reward,
            "new_balance": new_coins,
            "discovered_words": word_count
        })
    except Exception as e:
        print(f"❌ ERROR in reward_user: {str(e)}")
        return jsonify({
            "message": "Error processing reward",
            "error": str(e),
            "reward": 0,
            "new_balance": 0,
            "discovered_words": 0
        }), 500





@app.route('/select_lesson', methods=['GET', 'POST'])
@login_required
def select_lesson():
    user_id = session["user_id"]

    if request.method == 'POST':
        data = request.get_json()
        lesson_lang = data.get("lesson_language")

        if lesson_lang:
            # Update user's current selected lesson
            supabase.table("users").update({
                "lesson_language": lesson_lang
            }).eq("id", user_id).execute()

            # Check if user_progress entry exists
            existing = supabase.table("user_progress") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("lesson", lesson_lang) \
                .execute()

            if not existing.data:
                # Insert new progress with level 1
                supabase.table("user_progress").insert({
                    "user_id": user_id,
                    "lesson": lesson_lang,
                    "highest_unlocked": 1
                }).execute()

            return jsonify({"message": "✅ Lesson selected!", "redirect": f"/levelscreen?lesson={lesson_lang}"})

        return jsonify({"message": "❌ No lesson language selected."}), 400

    # Get user data for the dashboard
    user_data = supabase.table("users").select("*").eq("id", user_id).single().execute().data
    
    return render_template("div.html", page="select_lesson.html", user=user_data)






@app.route('/shop')
@login_required
def avatar_shop():
    user_id = session.get("user_id")

    # Get user data (coins + account level)
    user_result = supabase.table("users").select("coins", "account_level").eq("id", user_id).single().execute()
    coins = user_result.data["coins"]
    account_level = user_result.data["account_level"]

    # Get all avatars
    avatar_data = supabase.table("avatars").select("*").execute().data

    # Get owned avatar ids
    owned_avatars = supabase.table("user_avatars").select("avatar_id").eq("user_id", user_id).execute().data
    owned_avatar_ids = {item["avatar_id"] for item in owned_avatars}

    # Get all items
    item_data = supabase.table("items").select("*").execute().data

    # Get owned item ids
    owned_items = supabase.table("user_items").select("item_id").eq("user_id", user_id).execute().data
    owned_item_ids = {item["item_id"] for item in owned_items}

    return render_template("div.html", 
        page="shop.html", 
        avatars=avatar_data, 
        owned=owned_avatar_ids, 
        coins=coins,
        items=item_data,
        owned_items=owned_item_ids,
        account_level=account_level  # 🧠 add this
    )



@app.route('/inventory')
@login_required
def inventory():
    user_id = session["user_id"]

    # Get user items with quantity
    user_items = supabase.table("user_items") \
        .select("item_id, quantity") \
        .eq("user_id", user_id) \
        .execute().data

    if not user_items:
        return render_template("div.html", page="inventory.html", items=[])

    # Get item IDs
    item_ids = [item["item_id"] for item in user_items]

    # Fetch item details
    item_data = supabase.table("items") \
        .select("*") \
        .in_("id", item_ids) \
        .execute().data

    # Add quantity and full image URL to each item
    for item in item_data:
        matching = next((ui for ui in user_items if ui["item_id"] == item["id"]), {})
        item["quantity"] = matching.get("quantity", 1)
        item["image_url"] = f"https://uktdymsgfgodbwesdvsj.supabase.co/storage/v1/object/public/shopitems/{item['filename']}"

    return render_template("div.html", page="inventory.html", items=item_data)


@app.route('/buy-lives', methods=['POST'])
@login_required
def buy_lives():
    user_id = session['user_id']
    data = request.get_json()
    amount = int(data.get('amount', 0))

    PRICES = {1: 10, 3: 25, 5: 40}
    if amount not in PRICES:
        return jsonify({"success": False, "message": "Invalid amount."})

    user = supabase.table("users").select("*").eq("id", user_id).single().execute().data
    current_coins = user.get("coins", 0)
    current_lives = user.get("lives", 5)

    if current_lives >= 5:
        return jsonify({"success": False, "message": "You already have max lives."})

    cost = PRICES[amount]
    if current_coins < cost:
        return jsonify({"success": False, "message": "Not enough coins."})

    new_lives = min(5, current_lives + amount)
    supabase.table("users").update({
        "coins": current_coins - cost,
        "lives": new_lives,
        "life_regen_start": None,
        "next_life_time": None
    }).eq("id", user_id).execute()

    return jsonify({"success": True, "message": f"✅ You bought {amount} lives!"})



@app.route('/api/buy-full-health', methods=['POST'])
@login_required
def buy_full_health():
    user_id = session['user_id']
    user = supabase.table("users").select("*").eq("id", user_id).single().execute().data

    coins = user.get("coins", 0)
    if coins < 80:
        return jsonify({"success": False, "message": "Not enough coins."})

    # Update lives and subtract coins
    supabase.table("users").update({
        "lives": 5,
        "coins": coins - 80,
        "life_regen_start": None,
        "next_life_time": None
    }).eq("id", user_id).execute()

    return jsonify({"success": True, "new_lives": 5})





@app.route('/buy-avatar/<int:avatar_id>', methods=['POST'])
@login_required
def buy_avatar(avatar_id):
    user_id = session.get("user_id")

    # Check if user already owns it
    existing = supabase.table("user_avatars").select("*").eq("user_id", user_id).eq("avatar_id", avatar_id).execute()
    if existing.data:
        return jsonify({"success": False, "message": "You already own this avatar."})

    # Get avatar price
    avatar = supabase.table("avatars").select("*").eq("id", avatar_id).single().execute()
    if not avatar.data:
        return jsonify({"success": False, "message": "Avatar not found."})

    # Check user's coin balance
    user = supabase.table("users").select("*").eq("id", user_id).single().execute().data
    if user["coins"] < avatar.data["price"]:
        return jsonify({"success": False, "message": "Not enough coins."})

    # Deduct coins and grant avatar
    supabase.table("users").update({"coins": user["coins"] - avatar.data["price"]}).eq("id", user_id).execute()
    supabase.table("user_avatars").insert({"user_id": user_id, "avatar_id": avatar_id}).execute()

    return jsonify({"success": True, "message": "✅ Avatar purchased!"})

@app.route('/buy-item/<int:item_id>', methods=['POST'])
@login_required
def buy_item(item_id):
    user_id = session.get("user_id")
    data = request.get_json()
    quantity = int(data.get("quantity", 1))  # default to 1 if not specified

    if quantity < 1:
        return jsonify({"success": False, "message": "Invalid quantity."})

    # Get item info
    item_resp = supabase.table("items").select("*").eq("id", item_id).single().execute()
    item = item_resp.data
    if not item:
        return jsonify({"success": False, "message": "Item not found."})

    total_price = item["price"] * quantity

    # Check user coins
    user_resp = supabase.table("users").select("coins").eq("id", user_id).single().execute()
    user = user_resp.data
    if user["coins"] < total_price:
        return jsonify({"success": False, "message": "Not enough coins."})

    # Deduct coins
    supabase.table("users").update({
        "coins": user["coins"] - total_price
    }).eq("id", user_id).execute()

    # Check if user already has the item
    existing_resp = supabase.table("user_items") \
        .select("id", "quantity") \
        .eq("user_id", user_id) \
        .eq("item_id", item_id) \
        .execute()

    existing_data = existing_resp.data[0] if existing_resp.data else None

    if existing_data:
        # Update quantity
        new_quantity = existing_data["quantity"] + quantity
        supabase.table("user_items").update({
            "quantity": new_quantity
        }).eq("id", existing_data["id"]).execute()
    else:
        # Insert new record
        supabase.table("user_items").insert({
            "user_id": user_id,
            "item_id": item_id,
            "quantity": quantity
        }).execute()

    return jsonify({"success": True, "message": f"✅ Bought {quantity} x {item['description']}!"})





@app.route('/levelscreen')
@login_required
def level_home():
    user_id = session["user_id"]
    
    # Get lives and selected lesson_language
    user_data = supabase.table("users").select("lives", "lesson_language").eq("id", user_id).single().execute().data

    lives = user_data.get("lives", 5)
    selected_lesson = user_data.get("lesson_language")

    return render_template("div.html", lives=lives, selected_lesson=selected_lesson, page="levelscreen.html")



# Load language level HTML
@app.route('/level')
@login_required
def quiz():
    level = request.args.get('level', 1)
    user = supabase.table("users").select("lives").eq("id", session['user_id']).single().execute().data

    if user['lives'] <= 0:
        return render_template('div.html', level_file=None, error="No lives left")

    return render_template('div.html', level_file="levels/quiz.html", user_lives=user["lives"], level=level)



@app.route('/api/lose-life', methods=['POST'])
@login_required
def lose_life():
    user_id = session["user_id"]
    user = supabase.table("users").select("lives", "life_regen_start").eq("id", user_id).single().execute().data
    current_lives = user.get("lives", 5)

    if current_lives > 0:
        new_lives = current_lives - 1
        updates = {"lives": new_lives}

        if new_lives < 5 and not user.get("life_regen_start"):
            now = datetime.now(timezone.utc)
            updates["life_regen_start"] = now.isoformat()
            updates["next_life_time"] = (now + timedelta(minutes=2)).isoformat()

        supabase.table("users").update(updates).eq("id", user_id).execute()
        return jsonify({"lives": new_lives})
    else:
        return jsonify({"lives": 0})

@app.route('/api/regenerate-lives')
@login_required
def regenerate_lives():
    user_id = session["user_id"]
    now = datetime.now(timezone.utc)

    user = supabase.table("users").select("*").eq("id", user_id).single().execute().data
    lives = user.get("lives", 5)
    regen_start = user.get("life_regen_start")

    if lives >= 5 or not regen_start:
        return jsonify({"lives": lives, "next_life_in": None})

    # Fix: Handle naive datetime from DB
    regen_start_dt = datetime.fromisoformat(regen_start)
    if regen_start_dt.tzinfo is None:
        regen_start_dt = regen_start_dt.replace(tzinfo=timezone.utc)

    elapsed_seconds = (now - regen_start_dt).total_seconds()
    lives_gained = int(elapsed_seconds // 120)
    new_lives = min(5, lives + lives_gained)

    if new_lives >= 5:
        supabase.table("users").update({
            "lives": 5,
            "life_regen_start": None,
            "next_life_time": None
        }).eq("id", user_id).execute()
        return jsonify({"lives": 5, "next_life_in": None})

    next_life_in = 120 - (elapsed_seconds % 120)
    new_start_time = regen_start_dt + timedelta(seconds=lives_gained * 120)
    next_life_time = new_start_time + timedelta(minutes=2)

    supabase.table("users").update({
        "lives": new_lives,
        "life_regen_start": new_start_time.isoformat(),
        "next_life_time": next_life_time.isoformat()
    }).eq("id", user_id).execute()

    return jsonify({"lives": new_lives, "next_life_in": int(next_life_in)})



@app.route('/api/lives')
@login_required
def get_lives():
    user_id = session["user_id"]
    user = supabase.table("users").select("lives").eq("id", user_id).single().execute().data
    return jsonify({"lives": user["lives"]})


# /api/unlocked_level
@app.route('/api/unlocked_level', methods=['GET'])
def get_unlocked_level():
    user_id = session["user_id"]
    lesson = request.args.get('lesson')
    result = supabase.table('user_progress') \
        .select('highest_unlocked, level_mastery') \
        .eq('user_id', user_id) \
        .eq('lesson', lesson) \
        .single() \
        .execute()

    if result.data:
        level_mastery = result.data.get('level_mastery', {})
        
        # Handle case where level_mastery might be a string
        if isinstance(level_mastery, str):
            try:
                level_mastery = json.loads(level_mastery)
            except:
                level_mastery = {}
        
        return jsonify({
            'highest_unlocked': result.data['highest_unlocked'],
            'level_mastery': level_mastery
        })
    else:
        supabase.table('user_progress').insert({
            'user_id': user_id,
            'lesson': lesson,
            'highest_unlocked': 1,
            'level_mastery': '{}'
        }).execute()
        return jsonify({
            'highest_unlocked': 1,
            'level_mastery': {}
        })


# /api/complete_level
@app.route('/api/complete_level', methods=['POST'])
def complete_level():
    try:
        # Ensure database connection
        if not ensure_db_connection():
            return jsonify({
                'message': 'Database connection error',
                'error': 'Unable to connect to database',
                'level_mastered': False,
                'can_unlock_next': False,
                'next_level_unlocked': None,
                'mastery_stats': {}
            }), 503
        
        data = request.json or {}
        user_id = session["user_id"]
        lesson = data.get('lesson')
        completed_level = int(data.get('level', 1))  # Ensure it's an integer
        is_perfect_score = data.get('perfect_score', False)
        total_questions = data.get('total_questions', 0)
        correct_answers = data.get('correct_answers', 0)
        
        if not lesson:
            return jsonify({'message': 'Missing lesson parameter'}), 400
        
        print(f"🔍 DEBUG: Level {completed_level}, Perfect: {is_perfect_score}, Score: {correct_answers}/{total_questions}")
        print(f"🔍 DEBUG: Raw data received: {data}")
        print(f"🔍 DEBUG: perfect_score type: {type(is_perfect_score)}, value: {is_perfect_score}")
        print(f"🔍 DEBUG: correct_answers type: {type(correct_answers)}, value: {correct_answers}")
        print(f"🔍 DEBUG: total_questions type: {type(total_questions)}, value: {total_questions}")
        print(f"🔍 DEBUG: Calculated percentage: {(correct_answers / total_questions) * 100 if total_questions > 0 else 0}%")
        print(f"🔍 DEBUG: Lesson: {lesson}")
        print(f"🔍 DEBUG: User ID: {user_id}")

        # Get current progress
        result = supabase.table('user_progress') \
            .select('highest_unlocked, level_mastery') \
            .eq('user_id', user_id) \
            .eq('lesson', lesson) \
            .single() \
            .execute()

        current_progress = result.data if result.data else {
            'highest_unlocked': 1,
            'level_mastery': {}
        }
        
        # Ensure highest_unlocked is an integer
        current_progress['highest_unlocked'] = int(current_progress['highest_unlocked'])
        
        level_mastery = current_progress.get('level_mastery', {})
        if not isinstance(level_mastery, dict):
            # Handle case where level_mastery might be a string
            if isinstance(level_mastery, str):
                try:
                    level_mastery = json.loads(level_mastery)
                except:
                    level_mastery = {}
            else:
                level_mastery = {}
        
        # Update mastery for this level
        level_key = str(completed_level)
        if level_key not in level_mastery:
            level_mastery[level_key] = {
                'attempts': 0,
                'best_score': 0,
                'perfect_attempts': 0,
                'mastered': False
            }
        
        level_mastery[level_key]['attempts'] += 1
        current_score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        # Double-check perfect score calculation
        calculated_perfect = correct_answers == total_questions and total_questions > 0
        print(f"🔍 DEBUG: Calculated perfect score: {calculated_perfect} (correct: {correct_answers}, total: {total_questions})")
        print(f"🔍 DEBUG: Received perfect_score: {is_perfect_score}")
        print(f"🔍 DEBUG: Current score: {current_score}%")
        
        if current_score > level_mastery[level_key]['best_score']:
            level_mastery[level_key]['best_score'] = current_score
            print(f"🔍 DEBUG: New best score: {current_score}%")
        
        # Use the calculated perfect score if there's a mismatch
        final_perfect_score = is_perfect_score or calculated_perfect
        
        if final_perfect_score:
            level_mastery[level_key]['perfect_attempts'] += 1
            level_mastery[level_key]['mastered'] = True
            print(f"🔍 DEBUG: Perfect score confirmed! Setting mastered = True")
        else:
            print(f"🔍 DEBUG: Not perfect score. mastered remains {level_mastery[level_key]['mastered']}")
        
        # Check if we can unlock the next level - NOW REQUIRES PERFECT SCORE
        can_unlock_next = False
        new_highest_unlocked = current_progress['highest_unlocked']

        # Only unlock the next level if this is the current highest unlocked level AND user got a perfect score
        if completed_level == current_progress['highest_unlocked'] and final_perfect_score:
            can_unlock_next = True
            new_highest_unlocked = completed_level + 1
            print(f"🔍 DEBUG: Perfect score achieved! Unlocking next level! New highest: {new_highest_unlocked}")
        elif completed_level == current_progress['highest_unlocked'] and not final_perfect_score:
            print(f"🔍 DEBUG: Level completed but not perfect score. Need perfect score to unlock next level.")
        else:
            print(f"🔍 DEBUG: Not unlocking. Level match: {completed_level == current_progress['highest_unlocked']}, Perfect: {final_perfect_score}")
        
        # Update the database
        print(f"🔍 DEBUG: About to save - highest_unlocked: {new_highest_unlocked}, level_mastery: {level_mastery}")
        
        # Convert level_mastery to proper JSON string for Supabase
        level_mastery_json = json.dumps(level_mastery)
        print(f"🔍 DEBUG: JSON serialized level_mastery: {level_mastery_json}")
        
        # Use update if record exists, insert if it doesn't
        if result.data:
            # Record exists, use update
            print(f"🔍 DEBUG: Updating existing record for user {user_id}, lesson {lesson}")
            update_result = supabase.table('user_progress').update({
                'highest_unlocked': new_highest_unlocked,
                'level_mastery': level_mastery_json
            }).eq('user_id', user_id).eq('lesson', lesson).execute()
            print(f"🔍 DEBUG: Update result: {update_result}")
        else:
            # Record doesn't exist, use insert
            print(f"🔍 DEBUG: Inserting new record for user {user_id}, lesson {lesson}")
            insert_result = supabase.table('user_progress').insert({
                'user_id': user_id,
                'lesson': lesson,
                'highest_unlocked': new_highest_unlocked,
                'level_mastery': level_mastery_json
            }).execute()
            print(f"🔍 DEBUG: Insert result: {insert_result}")
        
        print(f"🔍 DEBUG: Database update completed")

        return jsonify({
            'message': 'Progress updated',
            'level_mastered': level_mastery[level_key]['mastered'],
            'can_unlock_next': can_unlock_next,
            'next_level_unlocked': new_highest_unlocked if can_unlock_next else None,
            'mastery_stats': level_mastery[level_key]
        })
    except Exception as e:
        print(f"❌ ERROR in complete_level: {str(e)}")
        return jsonify({
            'message': 'Error updating progress',
            'error': str(e),
            'level_mastered': False,
            'can_unlock_next': False,
            'next_level_unlocked': None,
            'mastery_stats': {}
        }), 500


@app.route('/api/debug-mastery', methods=['GET'])
@login_required
def debug_mastery():
    user_id = session["user_id"]
    lesson = request.args.get('lesson', 'tagalog')
    
    result = supabase.table('user_progress') \
        .select('highest_unlocked, level_mastery') \
        .eq('user_id', user_id) \
        .eq('lesson', lesson) \
        .single() \
        .execute()
    
    if result.data:
        level_mastery = result.data.get('level_mastery', {})
        
        # Handle case where level_mastery might be a string
        if isinstance(level_mastery, str):
            try:
                level_mastery = json.loads(level_mastery)
            except:
                level_mastery = {}
        
        print(f"🔍 DEBUG MASTERY: Raw data from DB: {result.data}")
        print(f"🔍 DEBUG MASTERY: Parsed level_mastery: {level_mastery}")
        
        return jsonify({
            'highest_unlocked': result.data['highest_unlocked'],
            'level_mastery': level_mastery,
            'user_id': user_id,
            'lesson': lesson,
            'raw_data': result.data
        })
    else:
        return jsonify({
            'highest_unlocked': 1,
            'level_mastery': {},
            'user_id': user_id,
            'lesson': lesson,
            'note': 'No progress record found'
        })

@app.route('/api/set-mastery', methods=['POST'])
@login_required
def set_mastery():
    """Manual endpoint to set mastery for testing"""
    try:
        user_id = session["user_id"]
        data = request.json or {}
        lesson = data.get('lesson', 'tagalog')
        level = int(data.get('level', 1))
        mastered = data.get('mastered', True)
        best_score = data.get('best_score', 100.0)
        
        # Get current progress
        result = supabase.table('user_progress') \
            .select('highest_unlocked, level_mastery') \
            .eq('user_id', user_id) \
            .eq('lesson', lesson) \
            .single() \
            .execute()

        current_progress = result.data if result.data else {
            'highest_unlocked': 1,
            'level_mastery': {}
        }
        
        level_mastery = current_progress.get('level_mastery', {})
        if isinstance(level_mastery, str):
            try:
                level_mastery = json.loads(level_mastery)
            except:
                level_mastery = {}
        
        # Set mastery for the specified level
        level_key = str(level)
        level_mastery[level_key] = {
            'attempts': 1,
            'best_score': best_score,
            'perfect_attempts': 1 if mastered else 0,
            'mastered': mastered
        }
        
        # Check if we should unlock the next level
        current_highest = current_progress.get('highest_unlocked', 1)
        new_highest_unlocked = current_highest
        
        if level == current_highest and mastered:
            new_highest_unlocked = level + 1
            print(f"🔍 DEBUG: Setting mastery and unlocking next level! New highest: {new_highest_unlocked}")
        
        # Update database
        level_mastery_json = json.dumps(level_mastery)
        
        if result.data:
            supabase.table('user_progress').update({
                'highest_unlocked': new_highest_unlocked,
                'level_mastery': level_mastery_json
            }).eq('user_id', user_id).eq('lesson', lesson).execute()
        else:
            supabase.table('user_progress').insert({
                'user_id': user_id,
                'lesson': lesson,
                'highest_unlocked': new_highest_unlocked,
                'level_mastery': level_mastery_json
            }).execute()
        
        return jsonify({
            'message': f'Level {level} mastery set to {mastered}',
            'level_mastery': level_mastery,
            'new_highest_unlocked': new_highest_unlocked,
            'level_mastered': mastered
        })
    except Exception as e:
        print(f"❌ ERROR in set_mastery: {str(e)}")
        return jsonify({
            'message': 'Error setting mastery',
            'error': str(e)
        }), 500




@app.route('/api/test-mastery', methods=['POST'])
@login_required
def test_mastery():
    try:
        user_id = session["user_id"]
        data = request.json or {}
        lesson = data.get('lesson', 'tagalog')
        level = int(data.get('level', 1))
        
        # Get current progress
        result = supabase.table('user_progress') \
            .select('highest_unlocked, level_mastery') \
            .eq('user_id', user_id) \
            .eq('lesson', lesson) \
            .single() \
            .execute()

        current_progress = result.data if result.data else {
            'highest_unlocked': 1,
            'level_mastery': {}
        }
        
        level_mastery = current_progress.get('level_mastery', {})
        if isinstance(level_mastery, str):
            try:
                level_mastery = json.loads(level_mastery)
            except:
                level_mastery = {}
        
        # Set mastery for the specified level
        level_key = str(level)
        level_mastery[level_key] = {
            'attempts': 1,
            'best_score': 100.0,
            'perfect_attempts': 1,
            'mastered': True
        }
        
        # Check if we should unlock the next level - NOW REQUIRES PERFECT SCORE
        current_highest = current_progress.get('highest_unlocked', 1)
        new_highest_unlocked = current_highest
        
        # Only unlock the next level if this level is mastered (perfect score) and it's the current highest unlocked level
        if level == current_highest and level_mastery[level_key]['mastered']:
            new_highest_unlocked = level + 1
            print(f"🔍 DEBUG: Perfect score achieved! Unlocking next level! New highest: {new_highest_unlocked}")
        elif level == current_highest and not level_mastery[level_key]['mastered']:
            print(f"🔍 DEBUG: Level completed but not perfect score. Need perfect score to unlock next level.")
        else:
            print(f"🔍 DEBUG: Not unlocking. Level match: {level == current_highest}, Mastered: {level_mastery[level_key]['mastered']}")
        
        # Update database - use update if record exists, insert if it doesn't
        level_mastery_json = json.dumps(level_mastery)
        
        if result.data:
            # Record exists, use update
            supabase.table('user_progress').update({
                'highest_unlocked': new_highest_unlocked,
                'level_mastery': level_mastery_json
            }).eq('user_id', user_id).eq('lesson', lesson).execute()
        else:
            # Record doesn't exist, use insert
            supabase.table('user_progress').insert({
                'user_id': user_id,
                'lesson': lesson,
                'highest_unlocked': new_highest_unlocked,
                'level_mastery': level_mastery_json
            }).execute()
        
        return jsonify({
            'message': f'Level {level} mastery set for testing. Next level unlocked: {new_highest_unlocked > current_highest}',
            'level_mastery': level_mastery,
            'new_highest_unlocked': new_highest_unlocked,
            'requires_perfect_score': True,
            'level_mastered': level_mastery[level_key]['mastered']
        })
    except Exception as e:
        print(f"❌ ERROR in test_mastery: {str(e)}")
        return jsonify({
            'message': 'Error setting mastery for testing',
            'error': str(e),
            'level_mastery': {}
        }), 500


@app.route('/api/words-discovered', methods=['POST'])
@login_required
def words_discovered():
    try:
        user_id = session["user_id"]
        data = request.json
        level = data.get("level", 1)
        words = data.get("words", [])
        
        # For now, just return a simple response
        # You can implement word tracking logic here later
        return jsonify({
            "new_words": len(words),
            "total_words": len(words)  # This would be total words discovered across all levels
        })
    except Exception as e:
        print(f"❌ ERROR in words_discovered: {str(e)}")
        return jsonify({
            "new_words": 0,
            "total_words": 0,
            "error": str(e)
        }), 500


@app.route('/api/gain-exp', methods=['POST'])
@login_required
def gain_exp():
    try:
        # Ensure database connection
        if not ensure_db_connection():
            return jsonify({
                "message": "Database connection error",
                "error": "Unable to connect to database",
                "account_level": 1,
                "current_exp": 0,
                "required_exp": 50,
                "leveled_up": False,
                "level_up_coins": 0
            }), 503
        
        user_id = session["user_id"]
        data = request.get_json()
        level = int(data.get("level", 1))
        wrong_count = int(data.get("wrong_count", 0))

        base_exp = 50 + (level - 1) * 10
        penalty = base_exp * 0.10 * wrong_count
        gained_exp = max(base_exp - penalty, 0)

        # Get user's current level, exp, and coins
        user = supabase.table("users").select("account_level", "current_exp", "coins").eq("id", user_id).single().execute().data
        account_level = user.get("account_level", 1)
        current_exp = user.get("current_exp", 0)
        current_coins = user.get("coins", 0)

        # Calculate required EXP for next level
        required_exp = 50 * (1.05 ** (account_level - 1))

        current_exp += gained_exp
        leveled_up = False
        level_up_coins = 0
        new_coins = current_coins

        while current_exp >= required_exp:
            current_exp -= required_exp
            account_level += 1
            required_exp *= 1.05
            leveled_up = True

            # Calculate level up coin reward: 50 * (1.2^(account_level-1))
            level_up_coins += int(round(50 * (1.2 ** (account_level - 1))))
            new_coins += level_up_coins

        # Update user's level, exp, and coins
        supabase.table("users").update({
            "account_level": account_level,
            "current_exp": current_exp,
            "coins": new_coins
        }).eq("id", user_id).execute()

        return jsonify({
            "message": f"✅ Gained {gained_exp:.2f} EXP",
            "account_level": account_level,
            "current_exp": current_exp,
            "required_exp": required_exp,
            "leveled_up": leveled_up,
            "level_up_coins": level_up_coins,
            "new_coin_balance": new_coins
        })
    except Exception as e:
        print(f"❌ ERROR in gain_exp: {str(e)}")
        return jsonify({
            "message": "Error gaining EXP",
            "error": str(e),
            "account_level": 1,
            "current_exp": 0,
            "required_exp": 50,
            "leveled_up": False,
            "level_up_coins": 0
        }), 500

@app.route('/my-words')
@login_required
def my_words():
    user_id = session["user_id"]

    # Get selected lesson
    user = supabase.table("users").select("lesson_language").eq("id", user_id).single().execute().data
    lesson = user.get("lesson_language", "tagalog")

    # Get highest completed level
    progress = supabase.table("user_progress") \
        .select("highest_unlocked") \
        .eq("user_id", user_id) \
        .eq("lesson", lesson) \
        .single() \
        .execute().data

    last_level = progress["highest_unlocked"] - 1  # Show words from level 1 up to this

    # ✅ FIX: Get words from all completed levels
    data = supabase.table("questionanswer") \
        .select("itemnum, level, english, tagalog, waray, cebuano") \
        .lte("level", last_level) \
        .execute().data

    language_column = lesson.lower()

    words = []
    for row in data:
        raw = row.get(language_column, "")
        cleaned = ''.join(c for c in raw if c.isalnum() or c.isspace()).title()
        words.extend(cleaned.split())

    unique_words = sorted(set(words))

    return render_template("div.html", page="my_words.html", words=unique_words, level=last_level, lesson=lesson.title())



@app.route("/api/word-info", methods=["POST"])
@login_required
def get_word_info():
    data = request.json
    word = data.get("word")
    user_id = session["user_id"]

    if not word:
        return jsonify({"error": "Missing word"}), 400

    # Get user lesson language and preferred display language
    user = supabase.table("users").select("lesson_language", "preferred_language").eq("id", user_id).single().execute().data
    lesson_lang = user.get("lesson_language", "waray").lower()
    preferred_lang = user.get("preferred_language", "tagalog").lower()

    rows = supabase.table("questionanswer") \
        .select("english, tagalog, waray, cebuano") \
        .ilike(lesson_lang, f"%{word}%") \
        .execute().data


    if not rows:
        return jsonify({"error": "Word not found in context"}), 404

    # Find the most likely matching sentence
    matched = next((r for r in rows if word.lower() in r.get(lesson_lang, "").lower()), rows[0])
    english_text = matched["english"]

    # Prompt Gemini using the English phrase as the correct context
    prompt = f"""
    [Target Language: {preferred_lang.upper()}]
    The learner is studying the word "{word}" from the {lesson_lang} language.
    It appears in this English phrase: "{english_text}"

    Based on that context, give:
    1. A short definition of the word in {preferred_lang}.
    2. A simple example sentence using the word (translated to {preferred_lang} if possible).
    """

    try:
        response = model.generate_content(prompt)
        return jsonify({"definition": response.text.strip()})
    except:
        return jsonify({"definition": "⚠️ Definition unavailable at the moment."})




@app.route('/leaderboard')
def leaderboard():
    lessons = ['tagalog', 'waray', 'cebuano']
    lesson_leaderboards = {}

    for lesson in lessons:
        response = supabase.table('user_progress') \
            .select('user_id, highest_unlocked, users(username)') \
            .eq('lesson', lesson) \
            .order('highest_unlocked', desc=True) \
            .limit(10) \
            .execute()
        lesson_leaderboards[lesson] = response.data

    # Account Level Leaderboard
    level_response = supabase.table('users') \
        .select('username, account_level') \
        .order('account_level', desc=True) \
        .limit(10) \
        .execute()
    top_by_level = level_response.data

    # Coin Leaderboard
    coins_response = supabase.table('users') \
        .select('username, coins') \
        .order('coins', desc=True) \
        .limit(10) \
        .execute()
    top_by_coins = coins_response.data

    return render_template("div.html", page="leaderboard.html",
                           lesson_leaderboards=lesson_leaderboards,
                           top_by_coins=top_by_coins,
                           top_by_level=top_by_level)



import random
from flask import jsonify

@app.route('/api/questions/<int:level>')
@login_required
def get_questions(level):
    user_id = session['user_id']

    user = supabase.table("users").select("preferred_language", "lesson_language").eq("id", user_id).single().execute().data
    preferred = user.get("preferred_language", "tagalog")
    lesson = user.get("lesson_language", "waray")
    target_lang = lesson

    questions = supabase.table("questionanswer").select("*").eq("level", level).order("itemnum").execute().data
    distractors = supabase.table("distractor").select("*").eq("level", level).order("itemnum").execute().data

    combined = []

    for q in questions:
        itemnum = q["itemnum"]
        qtype = q.get("type")
        d = next((d for d in distractors if d["itemnum"] == itemnum), {})

        if qtype == "fillblank-t":
            # Fill in the blank (Target language)
            sentence = q.get(target_lang, "")
            words = sentence.split()
            if len(words) < 2:
                continue
            blank_index = random.randint(0, len(words) - 1)
            correct_word = words[blank_index]
            sentence_with_blank = words.copy()
            sentence_with_blank[blank_index] = "_____"
            distractor_pool = d.get(target_lang, "").split()
            choices = list(set(distractor_pool + [correct_word]))
            random.shuffle(choices)

            # Add preferred language equivalent
            preferred_equivalent = q.get(preferred, "")

            combined.append({
                "question": f'Fill in the blank: "{' '.join(sentence_with_blank)}"',
                "answer": [correct_word],
                "choices": choices,
                "type": "fillblank",
                "choices_language": target_lang,
                "preferred_equivalent": preferred_equivalent
            })

        elif qtype == "choice-t2p":
            # Translate from Target ➡ Preferred
            correct_answer = q[preferred].split()
            choices = list(set(d.get(preferred, "").split() + correct_answer))
            random.shuffle(choices)

            combined.append({
                "question": f'Translate this phrase: "{q[target_lang]}"',
                "answer": correct_answer,
                "choices": choices,
                "audio": None,
                "type": "choice",
                "choices_language": preferred
            })

        elif qtype == "choice-p2t":
            # Translate from Preferred ➡ Target
            correct_answer = q[target_lang].split()
            choices = list(set(d.get(target_lang, "").split() + correct_answer))
            random.shuffle(choices)

            combined.append({
                "question": f'Translate this phrase: "{q[preferred]}"',
                "answer": correct_answer,
                "choices": choices,
                "audio": None,
                "type": "choice",
                "choices_language": target_lang
            })

        elif qtype == "audio-choice":
            # Listen and choose (Target language)
            correct_answer = q[target_lang].split()
            choices = list(set(d.get(target_lang, "").split() + correct_answer))
            random.shuffle(choices)

            combined.append({
                "question": "🎧 Listen and choose the correct word:",
                "answer": correct_answer,
                "choices": choices,
                "audio": q.get(target_lang),
                "type": "choice",
                "choices_language": target_lang
            })

        elif qtype == "audio-input":
            # Listen and type (Target language)
            combined.append({
                "question": "🎧 Listen and type what you hear:",
                "answer": [q[target_lang]],
                "choices": [],
                "audio": q.get(target_lang),
                "type": "input",
                "choices_language": target_lang
            })

    return jsonify(combined)




@app.route('/combat/combat.html')
@login_required
def combat():
    return render_template('combat/combat.html')





@app.route('/api/streak-reward', methods=['POST'])
@login_required
def streak_reward():
    try:
        # Ensure database connection
        if not ensure_db_connection():
            return jsonify({
                "message": "Database connection error",
                "error": "Unable to connect to database",
                "streak_bonus": 0,
                "new_balance": 0
            }), 503
        
        user_id = session["user_id"]
        data = request.json or {}
        streak = int(data.get("streak", 0))
        
        if streak <= 0:
            return jsonify({
                "message": "No streak bonus",
                "streak_bonus": 0,
                "new_balance": 0
            })
        
        # Calculate streak bonus: 1 coin per correct answer in streak
        streak_bonus = streak
        
        # Get current coin count
        user = (
            supabase.table("users")
            .select("coins")
            .eq("id", user_id)
            .single()
            .execute()
            .data
        )
        current_coins = user.get("coins", 0)
        new_coins = current_coins + streak_bonus

        # Update coins
        supabase.table("users").update({"coins": new_coins}).eq("id", user_id).execute()

        return jsonify({
            "message": f"🔥 Streak Bonus: +{streak_bonus} coins!",
            "streak_bonus": streak_bonus,
            "new_balance": new_coins
        })
    except Exception as e:
        print(f"❌ ERROR in streak_reward: {str(e)}")
        return jsonify({
            "message": "Error processing streak reward",
            "error": str(e),
            "streak_bonus": 0,
            "new_balance": 0
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to test database connectivity"""
    try:
        if ensure_db_connection():
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'timestamp': datetime.now().isoformat()
            }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/dashboard-stats')
@login_required
def get_dashboard_stats():
    user_id = session['user_id']
    
    # Get user's overall stats
    user = supabase.table("users").select("*").eq("id", user_id).single().execute().data
    
    # Get the maximum level based on boss_levels table
    boss_data = supabase.table("boss_levels").select("boss").execute().data
    max_boss = max([row["boss"] for row in boss_data]) if boss_data else 1
    max_level = max_boss * 10  # Each boss represents 10 levels
    
    # Get progress for all languages
    languages = ['tagalog', 'waray', 'cebuano']
    progress_data = {}
    
    for lang in languages:
        progress = supabase.table("user_progress") \
            .select("highest_unlocked") \
            .eq("user_id", user_id) \
            .eq("lesson", lang) \
            .single() \
            .execute().data
        
        progress_data[lang] = progress["highest_unlocked"] if progress else 1
    
    # Calculate total words learned
    total_words = 0
    for lang, level in progress_data.items():
        if level > 1:  # Only count if they've completed at least level 1
            words_data = supabase.table("questionanswer") \
                .select("itemnum, level, english, tagalog, waray, cebuano") \
                .lte("level", level - 1) \
                .execute().data
            
            language_column = lang.lower()
            word_set = set()
            
            for row in words_data:
                raw = row.get(language_column, "")
                cleaned = ''.join(c for c in raw if c.isalnum() or c.isspace()).title()
                word_set.update(cleaned.split())
            
            total_words += len(word_set)
    
    # Get recent achievements (mock data for now)
    achievements = [
        {"type": "level_up", "title": f"Account Level {user.get('account_level', 1)}", "icon": "⭐"},
        {"type": "coins", "title": f"Earned {user.get('coins', 0)} coins", "icon": "🪙"},
        {"type": "progress", "title": f"Learned {total_words} words", "icon": "📚"}
    ]
    
    # Calculate required EXP for current level
    account_level = user.get("account_level", 1)
    current_exp = user.get("current_exp", 0)
    required_exp = 50 * (1.05 ** (account_level - 1))
    
    return jsonify({
        "user_stats": {
            "account_level": account_level,
            "current_exp": current_exp,
            "required_exp": required_exp,
            "coins": user.get("coins", 0),
            "lives": user.get("lives", 5),
            "total_words": total_words
        },
        "progress": progress_data,
        "max_level": max_level,
        "achievements": achievements
    })


@app.route('/api/test-boss-levels')
@login_required
def test_boss_levels():
    """Test endpoint to check boss_levels table"""
    try:
        # Test if boss_levels table exists
        response = supabase.table('boss_levels').select('*').limit(5).execute()
        
        return jsonify({
            "success": True,
            "table_exists": True,
            "data": response.data,
            "count": len(response.data) if response.data else 0
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "table_exists": False,
            "error": str(e)
        }), 500


@app.route('/api/boss-exp-reward', methods=['POST'])
@login_required
def reward_boss_exp():
    user_id = session.get("user_id")
    data = request.json
    boss_num = data.get("boss")
    lesson = data.get("lesson")

    if not boss_num or not lesson:
        return jsonify({"message": "Missing boss number or lesson"}), 400

    # Get previous boss EXP reward from user's progress
    previous_boss_exp = 0
    if int(boss_num) > 1:
        # Get the previous boss EXP reward from user's progress
        progress_data = supabase.table("user_progress") \
            .select("boss_exp_rewards") \
            .eq("user_id", user_id) \
            .eq("lesson", lesson) \
            .single() \
            .execute().data
        
        if progress_data and progress_data.get("boss_exp_rewards"):
            boss_exp_rewards = progress_data["boss_exp_rewards"]
            if isinstance(boss_exp_rewards, str):
                try:
                    boss_exp_rewards = json.loads(boss_exp_rewards)
                except:
                    boss_exp_rewards = {}
            
            previous_boss_exp = boss_exp_rewards.get(str(int(boss_num) - 1), 0)
    
    # Calculate new EXP reward: 30% higher than previous, or base reward for first boss
    if previous_boss_exp > 0:
        exp_reward = int(round(previous_boss_exp * 1.3))  # 30% increase
    else:
        exp_reward = 300  # Base EXP reward for first boss (boss level * 100 * 3)
    
    print(f"⭐ Boss {boss_num} EXP calculation:")
    print(f"   Previous boss EXP: {previous_boss_exp}")
    print(f"   New EXP reward: {exp_reward}")

    # Get user's current level, exp, and coins
    user = supabase.table("users").select("account_level", "current_exp", "coins").eq("id", user_id).single().execute().data
    account_level = user.get("account_level", 1)
    current_exp = user.get("current_exp", 0)
    current_coins = user.get("coins", 0)

    # Calculate required EXP for next level
    required_exp = 50 * (1.05 ** (account_level - 1))

    current_exp += exp_reward
    leveled_up = False
    level_up_coins = 0
    new_coins = current_coins

    while current_exp >= required_exp:
        current_exp -= required_exp
        account_level += 1
        required_exp *= 1.05
        leveled_up = True

        # Calculate level up coin reward: 50 * (1.2^(account_level-1))
        level_up_coins += int(round(50 * (1.2 ** (account_level - 1))))
        new_coins += level_up_coins

    # Update user's EXP, level, and coins
    supabase.table("users").update({
        "account_level": account_level,
        "current_exp": current_exp,
        "coins": new_coins
    }).eq("id", user_id).execute()

    # Store this boss EXP reward for future calculations
    progress_data = supabase.table("user_progress") \
        .select("boss_exp_rewards") \
        .eq("user_id", user_id) \
        .eq("lesson", lesson) \
        .single() \
        .execute().data
    
    boss_exp_rewards = {}
    if progress_data and progress_data.get("boss_exp_rewards"):
        stored_rewards = progress_data["boss_exp_rewards"]
        if isinstance(stored_rewards, str):
            try:
                boss_exp_rewards = json.loads(stored_rewards)
            except:
                boss_exp_rewards = {}
        else:
            boss_exp_rewards = stored_rewards
    
    boss_exp_rewards[str(boss_num)] = exp_reward
    
    # Update or insert the boss EXP rewards
    if progress_data:
        supabase.table("user_progress").update({
            "boss_exp_rewards": json.dumps(boss_exp_rewards)
        }).eq("user_id", user_id).eq("lesson", lesson).execute()
    else:
        supabase.table("user_progress").insert({
            "user_id": user_id,
            "lesson": lesson,
            "highest_unlocked": 1,
            "boss_exp_rewards": json.dumps(boss_exp_rewards)
        }).execute()

    return jsonify({
        "message": f"✅ Gained {exp_reward} EXP from boss!",
        "exp_reward": exp_reward,
        "account_level": account_level,
        "current_exp": current_exp,
        "required_exp": required_exp,
        "leveled_up": leveled_up,
        "level_up_coins": level_up_coins,
        "new_coin_balance": new_coins,
        "previous_exp": previous_boss_exp
    })


@app.route('/api/debug-boss-rewards', methods=['GET'])
@login_required
def debug_boss_rewards():
    """Debug endpoint to check current boss rewards"""
    user_id = session["user_id"]
    lesson = request.args.get('lesson', 'tagalog')
    
    progress_data = supabase.table("user_progress") \
        .select("boss_rewards, boss_exp_rewards") \
        .eq("user_id", user_id) \
        .eq("lesson", lesson) \
        .single() \
        .execute().data
    
    if progress_data:
        boss_rewards = progress_data.get("boss_rewards", {})
        boss_exp_rewards = progress_data.get("boss_exp_rewards", {})
        
        # Parse JSON strings if needed
        if isinstance(boss_rewards, str):
            try:
                boss_rewards = json.loads(boss_rewards)
            except:
                boss_rewards = {}
        
        if isinstance(boss_exp_rewards, str):
            try:
                boss_exp_rewards = json.loads(boss_exp_rewards)
            except:
                boss_exp_rewards = {}
        
        return jsonify({
            "user_id": user_id,
            "lesson": lesson,
            "boss_rewards": boss_rewards,
            "boss_exp_rewards": boss_exp_rewards,
            "raw_data": progress_data
        })
    else:
        return jsonify({
            "user_id": user_id,
            "lesson": lesson,
            "boss_rewards": {},
            "boss_exp_rewards": {},
            "note": "No progress record found"
        })


@app.route('/api/boss-reward-reduced', methods=['POST'])
@login_required
def reward_boss_reduced():
    user_id = session.get("user_id")
    data = request.json
    boss_num = data.get("boss")
    lesson = data.get("lesson")
    reduced_amount = data.get("reduced_amount", 0)

    if not boss_num or not lesson:
        return jsonify({"message": "Missing boss number or lesson"}), 400

    print(f"💀 Reduced boss reward: {reduced_amount} coins for boss {boss_num}")

    # Get current coin count
    user_data = (
        supabase.table("users")
        .select("coins")
        .eq("id", user_id)
        .single()
        .execute()
    )

    user = user_data.data
    if not user:
        print("❌ User not found.")
        return jsonify({"message": "User not found"}), 404

    current_coins = user.get("coins", 0)
    new_coins = current_coins + reduced_amount
    print(f"💰 Coins before: {current_coins}, after: {new_coins}")

    # Update coins
    supabase.table("users").update({"coins": new_coins}).eq("id", user_id).execute()

    return jsonify({
        "message": "✅ Reduced boss coins rewarded!",
        "reward": reduced_amount,
        "new_balance": new_coins
    })


@app.route('/api/boss-exp-reward-reduced', methods=['POST'])
@login_required
def reward_boss_exp_reduced():
    user_id = session.get("user_id")
    data = request.json
    boss_num = data.get("boss")
    lesson = data.get("lesson")
    reduced_amount = data.get("reduced_amount", 0)

    if not boss_num or not lesson:
        return jsonify({"message": "Missing boss number or lesson"}), 400

    print(f"💀 Reduced boss EXP: {reduced_amount} EXP for boss {boss_num}")

    # Get user's current level, exp, and coins
    user = supabase.table("users").select("account_level", "current_exp", "coins").eq("id", user_id).single().execute().data
    account_level = user.get("account_level", 1)
    current_exp = user.get("current_exp", 0)
    current_coins = user.get("coins", 0)

    # Calculate required EXP for next level
    required_exp = 50 * (1.05 ** (account_level - 1))

    current_exp += reduced_amount
    leveled_up = False
    level_up_coins = 0
    new_coins = current_coins

    while current_exp >= required_exp:
        current_exp -= required_exp
        account_level += 1
        required_exp *= 1.05
        leveled_up = True

        # Calculate level up coin reward: 50 * (1.2^(account_level-1))
        level_up_coins += int(round(50 * (1.2 ** (account_level - 1))))
        new_coins += level_up_coins

    # Update user's EXP, level, and coins
    supabase.table("users").update({
        "account_level": account_level,
        "current_exp": current_exp,
        "coins": new_coins
    }).eq("id", user_id).execute()

    return jsonify({
        "message": f"✅ Gained {reduced_amount} reduced EXP from boss!",
        "exp_reward": reduced_amount,
        "account_level": account_level,
        "current_exp": current_exp,
        "required_exp": required_exp,
        "leveled_up": leveled_up,
        "level_up_coins": level_up_coins,
        "new_coin_balance": new_coins
    })

@app.route('/api/items-by-level/<int:level>')
@login_required
def get_items_by_level(level):
    """Get items that unlock at a specific level"""
    try:
        items = supabase.table("items").select("*").eq("required_level", level).execute().data
        return jsonify({
            "success": True,
            "items": items
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "items": []
    })

@app.route('/api/feedback', methods=['POST'])
@login_required
def get_feedback():
    data = request.json
    user_id = session['user_id']
    user = supabase.table("users").select("preferred_language").eq("id", user_id).single().execute().data
    lang = user.get("preferred_language", "tagalog")

    prompt = f"""
    [Language: {lang.upper()}]
    A student just answered a language quiz.
    Question: {data.get("question", "")}
    Correct Answer: {data.get("correct_answer", "")}
    Student's Answer: {data.get("user_answer", "")}
    
    Give a friendly, educational feedback in {lang}. Help the student understand why their answer is correct or not, and a tip to improve.
    """
    try:
        response = model.generate_content(prompt)
        return jsonify({"feedback": response.text.strip()})
    except:
        return jsonify({"feedback": "AI feedback is unavailable at the moment."})



        
if __name__ == "__main__":
    app.run(debug=False)
