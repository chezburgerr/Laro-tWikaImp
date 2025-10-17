from flask import Blueprint, render_template, request, jsonify, Response, session
import json
import time
from supabase import create_client, Client
from dotenv import load_dotenv
import os
# Load .env file
load_dotenv()
speech_bp = Blueprint('speech', __name__)

# === Supabase setup ===
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === ROUTES ===
@speech_bp.route('/get_words')
def get_words():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    # 🔍 Get user's lesson language from the users table
    user = supabase.table("users") \
        .select("lesson_language") \
        .eq("id", user_id) \
        .single() \
        .execute().data

    if not user:
        return jsonify({"error": "User not found"}), 404

    language = user.get("lesson_language", "tagalog")  # default fallback

    # 🔢 Get boss level number from query params (e.g., ?level=1)
    level = int(request.args.get('level', 1))

    # 🧠 Query boss level table using the current lesson language
    response = supabase.table('boss_levels') \
        .select('*') \
        .eq('boss', level) \
        .order('itemnum') \
        .execute()

    rows = response.data

    if not rows:
        return jsonify({language: []})

    # 🎯 Build the word list using the correct language column
    words = [{"word": row.get(language), "type": row.get("type")} for row in rows]

    return jsonify({language: words})


@speech_bp.route('/stream')
def stream_text():
    def generate():
        try:
            # Import Vosk only when needed
            from vosk import Model, KaldiRecognizer
            import pyaudio
            
            # Try to find the model path
            model_path = r"D:\finalproject1\vosk-model-tl-ph-generic-0.6"
            if not os.path.exists(model_path):
                # Try alternative paths
                alternative_paths = [
                    "./vosk-model-tl-ph-generic-0.6",
                    "../vosk-model-tl-ph-generic-0.6",
                    os.path.join(os.getcwd(), "vosk-model-tl-ph-generic-0.6")
                ]
                for path in alternative_paths:
                    if os.path.exists(path):
                        model_path = path
                        break
                else:
                    yield f"data: Error: Vosk model not found\n\n"
                    return
            
            model = Model(model_path)
            recognizer = KaldiRecognizer(model, 16000)
            
            # Try to find a working audio device
            mic = pyaudio.PyAudio()
            device_index = None
            
            # Try different device indices
            for i in range(mic.get_device_count()):
                try:
                    device_info = mic.get_device_info_by_index(i)
                    if int(device_info['maxInputChannels']) > 0:
                        device_index = i
                        break
                except:
                    continue
            
            if device_index is None:
                yield f"data: Error: No audio input device found\n\n"
                return
            
            stream = mic.open(format=pyaudio.paInt16,
                              channels=1,
                              rate=16000,
                              input=True,
                              input_device_index=device_index,
                              frames_per_buffer=8192)
            stream.start_stream()

            while True:
                data = stream.read(4096, exception_on_overflow=False)
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    yield f"data: {result.get('text', '')}\n\n"
                else:
                    partial = json.loads(recognizer.PartialResult())
                    yield f"data: {partial.get('partial', '')}\n\n"
                time.sleep(0.1)
                
        except ImportError:
            yield f"data: Error: Vosk or PyAudio not installed\n\n"
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"
        finally:
            try:
                if 'stream' in locals():
                    stream.stop_stream()
                    stream.close()
                if 'mic' in locals():
                    mic.terminate()
            except:
                pass

    return Response(generate(), mimetype='text/event-stream')


# === NEW: Get user's potions ===
@speech_bp.route('/get_potions')
def get_potions():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify([])

    # Get user's owned potions
    user_items = supabase.table("user_items") \
        .select("item_id, quantity") \
        .eq("user_id", user_id) \
        .execute().data

    if not user_items:
        return jsonify([])

    item_ids = [item["item_id"] for item in user_items]

    # Fetch item details
    items_data = supabase.table("items") \
        .select("id, description, filename") \
        .in_("id", item_ids) \
        .execute().data

    # Merge quantities into items
    item_map = {item["item_id"]: item["quantity"] for item in user_items}
    for item in items_data:
        item["quantity"] = item_map.get(item["id"], 0)

    return jsonify(items_data)


# === NEW: Get block challenge question ===
@speech_bp.route('/get_block_question')
def get_block_question():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    # Get user's lesson language
    user = supabase.table("users") \
        .select("lesson_language") \
        .eq("id", user_id) \
        .single() \
        .execute().data

    if not user:
        return jsonify({"error": "User not found"}), 404

    language = user.get("lesson_language", "tagalog")

    # Get current boss level for question difficulty
    boss_level = request.args.get('level', 1, type=int)
    
    # Get a random question from the questionanswer table
    # We'll get questions from the same level as the boss
    response = supabase.table('questionanswer') \
        .select('*') \
        .eq('level', boss_level) \
        .execute()

    questions = response.data
    if not questions:
        # Fallback to any question if none found for this level
        response = supabase.table('questionanswer') \
            .select('*') \
            .limit(1) \
            .execute()
        questions = response.data

    if not questions:
        return jsonify({"error": "No questions available"}), 404

    # Select a random question
    import random
    question = random.choice(questions)
    
    # Return the question in the user's lesson language
    return jsonify({
        "question": question.get(language, question.get("english", "")),
        "answer": question.get(language, question.get("english", "")),  # Use same language as question
        "english_answer": question.get("english", ""),  # Keep English for reference
        "type": question.get("type", "speak")
    })


# === NEW: Use a potion ===
@speech_bp.route('/use-potion/<int:item_id>', methods=['POST'])
def use_potion(item_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not logged in"})

    # Check if the user has this potion
    result = supabase.table("user_items") \
        .select("id, quantity") \
        .eq("user_id", user_id) \
        .eq("item_id", item_id) \
        .single() \
        .execute()

    entry = result.data

    if not entry or entry["quantity"] < 1:
        return jsonify({"success": False, "message": "You don't have this potion."})

    # === Apply Potion Effect ===
    effect = {}
    if item_id == 1:
        # HP potion: heal 30% of max HP
        effect = {"type": "hp", "value": 30}
    elif item_id == 2:
        # MP potion: restore 50% energy
        effect = {"type": "energy", "value": 50}
    elif item_id == 3:
        # Damage Boost: increase damage by 20% (can be extended)
        effect = {"type": "damageBoost", "value": 30}
    elif item_id == 4:
        # Time Slow: slow enemy for 5 seconds (can be extended)
        effect = {"type": "timeSlow", "duration": 5}
    else:
        effect = {"type": "none"}

    # === Update quantity in DB ===
    new_qty = entry["quantity"] - 1
    if new_qty <= 0:
        supabase.table("user_items").delete().eq("id", entry["id"]).execute()
    else:
        supabase.table("user_items").update({"quantity": new_qty}).eq("id", entry["id"]).execute()

    return jsonify({
        "success": True,
        "message": "Potion used!",
        "effect": effect,
        "remaining": new_qty
    })


