import time
import requests
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= কনফিগারেশন =================
BOT_TOKEN = "8720888225:AAFviTzCxBgRfxqi3Yx87sIKhFr3n7b8vsI"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
ADMIN_ID = 5578674054
BOT_USERNAME = "DesiView_bot" 

# ================= ফায়ারবেস ক্লাউড মেমোরি =================
FIREBASE_DB_URL = "https://earning-36434-default-rtdb.firebaseio.com"

users_db = set() 
videos_db = []   
admin_states = {} 

# ================= Render পোর্টের জন্য হেলথ চেক ওয়েব সার্ভার =================
class HealthCheckServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot Engine is Live and Running 24/7!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckServer)
    print(f"🌍 হেলথ চেক সার্ভার চালু হয়েছে পোর্ট: {port}")
    server.serve_forever()

# ================= ফায়ারবেস API ফাংশনস =================
def firebase_get_users():
    url = f"{FIREBASE_DB_URL}/users.json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if not data: return set()
            if isinstance(data, dict):
                return set(int(k) for k in data.keys() if k.isdigit())
            elif isinstance(data, list):
                return set(int(v) for v in data if v is not None)
    except Exception as e:
        print(f"⚠️ [Firebase Users Load Error]: {e}")
    return set()

def firebase_save_user(chat_id):
    url = f"{FIREBASE_DB_URL}/users/{chat_id}.json"
    try:
        requests.put(url, json=True, timeout=10)
    except Exception as e:
        print(f"⚠️ [Firebase Save User Error]: {e}")

def firebase_get_videos():
    url = f"{FIREBASE_DB_URL}/videos.json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if not data: return []
            if isinstance(data, dict): return list(data.values())
            elif isinstance(data, list): return [v for v in data if v is not None]
    except Exception as e:
        print(f"⚠️ [Firebase Videos Load Error]: {e}")
    return []

def firebase_save_video(video):
    url = f"{FIREBASE_DB_URL}/videos/{video['id']}.json"
    try:
        requests.put(url, json=video, timeout=10)
    except Exception as e:
        print(f"⚠️ [Firebase Save Video Error]: {e}")

def firebase_delete_video(video_id):
    url = f"{FIREBASE_DB_URL}/videos/{video_id}.json"
    try:
        requests.delete(url, timeout=10)
    except Exception as e:
        print(f"⚠️ [Firebase Delete Video Error]: {e}")

# ================= TELEGRAM API কোর ফাংশন =================
def telegram_api_call(method, payload=None):
    url = BASE_URL + method
    try:
        if payload:
            response = requests.post(url, json=payload, timeout=15)
        else:
            response = requests.get(url, timeout=15)
        
        res_json = response.json()
        if response.status_code == 200:
            return res_json
        else:
            print(f"❌ [Telegram Error ({method})]: {res_json.get('description', 'Unknown Error')}")
    except Exception as e:
        print(f"⚠️ [Network Error ({method})]: {e}")
    return None

# ================= ভিডিও পোস্ট ও ব্রডকাস্ট লজিক =================
def send_video_post(chat_id, video, is_admin=False):
    if not video or not isinstance(video, dict): return
        
    vid_id = video.get('id', '')
    title = video.get('title', 'No Title')
    desc = video.get('desc', 'No Description')
    thumb_id = video.get('thumb_id', '')
    likes = video.get('likes', 0)

    if not thumb_id: return

    caption = f"🎬 <b>{title}</b>\n\n📄 {desc}"
    
    if is_admin:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🗑️ Delete Video", "callback_data": f"del_{vid_id}"},
                    {"text": f"👍 {likes}", "callback_data": f"like_{vid_id}"}
                ]
            ]
        }
    else:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🔓 Unlock Video 🔓", "callback_data": f"unlock_{vid_id}"},
                    {"text": f"👍 {likes}", "callback_data": f"like_{vid_id}"}
                ]
            ]
        }

    telegram_api_call("sendPhoto", {
        "chat_id": chat_id,
        "photo": thumb_id,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": keyboard
    })

def broadcast_to_users(video_info):
    print(f"📢 সরাসরি মেইন পোস্ট ব্রডকাস্ট শুরু হচ্ছে... টার্গেট: {len(users_db)} জন।")
    for user_id in list(users_db):
        if int(user_id) != int(ADMIN_ID):
            send_video_post(user_id, video_info, is_admin=False)

# ================= আপডেট প্রসেসর =================
def process_message(msg):
    global videos_db
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    
    if chat_id not in users_db:
        users_db.add(chat_id)
        firebase_save_user(chat_id)

    if text == "/start":
        if chat_id == ADMIN_ID:
            telegram_api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "👨‍💻 <b>স্বাগতম অ্যাডমিন!</b>\nনিচের বোতাম চেপে ভিডিও পোস্ট করুন।",
                "parse_mode": "HTML",
                "reply_markup": {"keyboard": [[{"text": "📤 POST Video"}]], "resize_keyboard": True, "is_persistent": True}
            })
        else:
            telegram_api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "🌟 <b>স্বাগতম!</b>\nএখানে আমাদের সব প্রিমিয়াম ভিডিও দেওয়া আছে।",
                "parse_mode": "HTML",
                "reply_markup": {"remove_keyboard": True}
            })
            if not videos_db:
                telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "এখনো কোনো ভিডিও আপলোড করা হয়নি।"})
            else:
                for video in videos_db:
                    send_video_post(chat_id, video, is_admin=False)
        return

    if chat_id == ADMIN_ID:
        if text in ["📤 POST Video", "POST Video"]:
            admin_states[chat_id] = {"step": "title"}
            telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "📝 <b>ধাপ ১:</b> ভিডিওর Title দিন:"})
            return
            
        state = admin_states.get(chat_id)
        if state:
            if state["step"] == "title" and text:
                state["title"] = text
                state["step"] = "desc"
                telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "📄 <b>ধাপ ২:</b> ভিডিওর Description দিন:"})
            elif state["step"] == "desc" and text:
                state["desc"] = text
                state["step"] = "thumb"
                telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "🖼️ <b>ধাপ ৩:</b> ভিডিওর Thumbnail (ছবি) পাঠান:"})
            elif state["step"] == "thumb" and "photo" in msg:
                state["thumb_id"] = msg["photo"][-1]["file_id"]
                state["step"] = "video"
                telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "🎥 <b>ধাপ ৪:</b> এবার মূল Video ফাইলটি পাঠান:"})
            elif state["step"] == "video" and "video" in msg:
                video_id = msg["video"]["file_id"]
                video_uid = str(int(time.time() * 1000))
                
                new_video = {
                    "id": video_uid, "title": state["title"], "desc": state["desc"],
                    "thumb_id": state["thumb_id"], "video_id": video_id, "likes": 0
                }
                
                videos_db.append(new_video)
                firebase_save_video(new_video)
                del admin_states[chat_id]
                
                telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "✅ <b>ভিডিও আপলোড সফল হয়েছে!</b>"})
                send_video_post(chat_id, new_video, is_admin=True)
                
                broadcast_to_users(new_video)

def process_callback(cq):
    global videos_db
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    data = cq["data"]
    callback_id = cq["id"]
    
    if data.startswith("unlock_"):
        vid_id = data.split("_")[1]
        video = next((v for v in videos_db if v["id"] == vid_id), None)
        if video:
            telegram_api_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "📺 বিজ্ঞাপন লোড হচ্ছে... ৩ সেকেন্ড অপেক্ষা করুন।", "show_alert": True})
            time.sleep(3)
            
            telegram_api_call("editMessageMedia", {
                "chat_id": chat_id, "message_id": message_id,
                "media": {"type": "video", "media": video["video_id"], "caption": f"🎬 <b>{video['title']}</b>\n\n📄 {video['desc']}", "parse_mode": "HTML"},
                "reply_markup": {"inline_keyboard": [[{"text": f"👍 {video.get('likes', 0)}", "callback_data": f"like_{vid_id}"}, {"text": "🔄 Share", "url": f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}"}]]}
            })
            
    elif data.startswith("like_"):
        vid_id = data.split("_")[1]
        video = next((v_idx for v_idx in videos_db if v_idx["id"] == vid_id), None)
        if video:
            video['likes'] = video.get('likes', 0) + 1
            firebase_save_video(video)
            telegram_api_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "❤️ Liked!"})
            
            current_keyboard = cq["message"]["reply_markup"]
            for row in current_keyboard["inline_keyboard"]:
                for btn in row:
                    if btn.get("callback_data") == data: btn["text"] = f"👍 {video['likes']}"
            telegram_api_call("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id, "reply_markup": current_keyboard})

    elif data.startswith("del_") and chat_id == ADMIN_ID:
        vid_id = data.split("_")[1]
        videos_db = [v for v in videos_db if v["id"] != vid_id]
        firebase_delete_video(vid_id)
        telegram_api_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "🗑️ Deleted!"})
        telegram_api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

# ================= সার্ভার মেইন রানার লুপ =================
if __name__ == "__main__":
    # Render-এর জন্য হেলথ চেক সার্ভার ব্যাকগ্রাউন্ড থ্রেডে চালু করা হচ্ছে
    threading.Thread(target=run_health_server, daemon=True).start()

    print("🚀 সার্ভার ব্যাকগ্রাউন্ড ইঞ্জিন চালু হচ্ছে...")
    users_db = firebase_get_users()
    raw_vids = firebase_get_videos()
    videos_db = [v for v in raw_vids if isinstance(v, dict) and 'id' in v]
    print(f"📊 ডেটা সিঙ্ক কমপ্লিট। ইউজার: {len(users_db)} | ভিডিও: {len(videos_db)}")
    
    offset = 0
    telegram_api_call("getUpdates", {"offset": -1})
    
    while True:
        try:
            updates = telegram_api_call("getUpdates", {"offset": offset, "timeout": 10})
            if updates and updates.get("ok") and updates.get("result"):
                for update in updates["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update:
                        process_message(update["message"])
                    elif "callback_query" in update:
                        process_callback(update["update_query" if "update_query" in update else "callback_query"])
        except Exception as e:
            print(f"♻️ [সার্ভার অটো-রিকভারি সচল]: {e}")
            time.sleep(5)
        time.sleep(0.5)
