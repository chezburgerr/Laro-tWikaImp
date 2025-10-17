from flask import Blueprint, request, jsonify
from supabase import create_client
import os
from dotenv import load_dotenv
import requests
import traceback

load_dotenv()

level_bp = Blueprint("level_bp", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@level_bp.route("/api/lesson-content", methods=["GET"])
def get_lesson_content():
    lesson = request.args.get("lesson")   # 'tagalog', 'cebuano', or 'waray'
    level = request.args.get("level")     # e.g., '1'

    if lesson not in ["tagalog", "cebuano", "waray"]:
        return jsonify({"success": False, "error": "Invalid lesson type"}), 400

    table_name = f"{lesson}_lessons"
    column_name = lesson  # the column has the same name as the lesson

    try:
        # Query the table for the file name matching the level
        response = supabase.table(table_name).select(column_name).eq("level", int(level)).single().execute()
        
        if response.data and column_name in response.data:
            filename = response.data[column_name]
        else:
            return jsonify({"success": False, "error": "Lesson not found in database"}), 404

        # Get public URL of the file from Supabase Storage
        res = supabase.storage.from_('lessons').get_public_url(filename)
        print("🪵 Supabase get_public_url result:", res)

        # Determine URL format
        if isinstance(res, dict) and 'publicURL' in res:
            file_url = res['publicURL']
        elif isinstance(res, str):
            file_url = res
        else:
            return jsonify({"success": False, "error": "Unexpected Supabase response"}), 500

        print("📂 Fetching file from:", file_url)

        file_response = requests.get(file_url)
        if file_response.status_code == 200:
            return jsonify({"success": True, "content": file_response.text})
        else:
            return jsonify({"success": False, "error": f"Failed to fetch file content (status {file_response.status_code})"}), 404

    except Exception as e:
        print("❌ Exception occurred:", str(e))
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
