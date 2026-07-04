import aiohttp
from aiohttp import web
import json
import asyncio
import time
import urllib.parse
import os

# ================= কনফিগারেশন =================
BOT_TOKEN = "8631547598:AAEtZkJKYxN6JOp-qWG8TM99QSelezHeV-4"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
ADMIN_ID = 5578674054
BOT_USERNAME = "BdView2026te_bot" 
WEB_APP_URL = "https://bjkbnbb577787787.blogspot.com/?m=1"
FIREBASE_DB_URL = "https://earning-36434-default-rtdb.firebaseio.com"

users_db = set() 
videos_db = []   
admin_states = {} 

# ================= API হেল্পার ফাংশন =================
async def fetch(url, method="GET", payload=None):
    async with aiohttp.ClientSession() as session:
        kwargs = {}
        if payload:
            kwargs['json'] = payload
            if method == "GET": method = "POST"
        try:
            async with session.request(method, url, **kwargs) as response:
                text_data = await response.text()
                try:
                    json_data = json.loads(text_data)
                except:
                    json_data = None
                return response.status, json_data, text_data
        except Exception as e:
            print(f"Network error: {e}")
            return 500, None, None

# ================= ফায়ারবেস API ফাংশনস =================
async def firebase_get_users():
    status, data, _ = await fetch(f"{FIREBASE_DB_URL}/users.json")
    if status == 200 and data:
        if isinstance(data, dict):
            return set(int(k) for k in data.keys() if k.isdigit())
        elif isinstance(data, list):
            return set(int(v) for v in data if v is not None)
    return set()

async def firebase_save_user(chat_id):
    await fetch(f"{FIREBASE_DB_URL}/users/{chat_id}.json", method="PUT", payload=True)

async def firebase_get_videos():
    status, data, _ = await fetch(f"{FIREBASE_DB_URL}/videos.json")
    if status == 200 and data:
        if isinstance(data, dict):
            return list(data.values())
        elif isinstance(data, list):
            return [v for v in data if v is not None]
    return []

async def firebase_save_video(video):
    await fetch(f"{FIREBASE_DB_URL}/videos/{video['id']}.json", method="PUT", payload=video)

async def firebase_delete_video(video_id):
    await fetch(f"{FIREBASE_DB_URL}/videos/{video_id}.json", method="DELETE")

# ================= TELEGRAM API ফাংশন =================
async def telegram_api_call(method, payload=None):
    status, data, _ = await fetch(BASE_URL + method, payload=payload)
    if status == 200 and data:
        return data
    else:
        print(f"❌ API Error ({method}): {data}")
        return None

# ================= হেল্পার ফাংশনস =================
def get_admin_keyboard():
    return {"keyboard": [[{"text": "📤 POST Video"}]], "resize_keyboard": True, "is_persistent": True}

async def broadcast_to_users(video_info):
    for user_id in list(users_db):
        if int(user_id) != int(ADMIN_ID):
            asyncio.create_task(send_video_post(user_id, video_info, is_admin=False))

async def send_video_post(chat_id, video, is_admin=False):
    if not video or not isinstance(video, dict) or not video.get('thumb_id'): return
    
    vid_id = video.get('id', '')
    title = video.get('title', 'No Title')
    desc = video.get('desc', 'No Description')
    likes = video.get('likes', 0)
    
    caption = f"🎬 <b>{title}</b>\n\n📄 {desc}"
    
    if is_admin:
        keyboard = {"inline_keyboard": [[{"text": "🗑️ Delete", "callback_data": f"del_{vid_id}"}, {"text": f"👍 {likes}", "callback_data": f"like_{vid_id}"}]]}
    else:
        final_web_url = f"{WEB_APP_URL}{'&' if '?' in WEB_APP_URL else '?'}chat_id={chat_id}&file_id={video.get('video_id', '')}"
        keyboard = {"inline_keyboard": [[{"text": "🔓 Unlock Video 🔓", "web_app": {"url": final_web_url}}, {"text": f"👍 {likes}", "callback_data": f"like_{vid_id}"}]]}

    res = await telegram_api_call("sendPhoto", {"chat_id": chat_id, "photo": video['thumb_id'], "caption": caption, "parse_mode": "HTML", "reply_markup": keyboard})
    if res and res.get("ok"):
        msg_id = res["result"]["message_id"]
        await fetch(f"{FIREBASE_DB_URL}/msg_tracks/{chat_id}_{video.get('video_id', '')}.json", method="PUT", payload=msg_id)

# ================= অটো-ডেলিভারি এবং টাইমার ফাংশনস =================
async def check_ad_unlock_requests():
    while True:
        try:
            status, requests, _ = await fetch(f"{FIREBASE_DB_URL}/unlock_requests.json")
            if status == 200 and requests and isinstance(requests, dict):
                for req_id, req_data in requests.items():
                    chat_id = req_data.get("chat_id")
                    file_id = req_data.get("file_id")
                    
                    if chat_id and file_id:
                        _, msg_id, _ = await fetch(f"{FIREBASE_DB_URL}/msg_tracks/{chat_id}_{file_id}.json")
                        video = next((v for v in videos_db if v["video_id"] == file_id), None)
                        if not video: continue
                        
                        share_text = urllib.parse.quote(f"🔥 চমৎকার এই ভিডিওটি দেখুন সম্পূর্ণ ফ্রিতে! 👇\n\nt.me/{BOT_USERNAME}?start=video_{video['id']}")
                        keyboard = {"inline_keyboard": [[{"text": f"👍 {video.get('likes', 0)}", "callback_data": f"like_{video['id']}"}, {"text": "📢 Share", "url": f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text={share_text}"}]]}
                        caption = f"🎬 <b>{video['title']}</b>\n\n📄 {video['desc']}\n\n🎉 <i>ভিডিওটি আনলক করা হয়েছে (১৫ মিনিট পর পুনরায় লক হয়ে যাবে)।</i>"

                        if msg_id:
                            await telegram_api_call("editMessageMedia", {"chat_id": chat_id, "message_id": int(msg_id), "media": {"type": "video", "media": file_id, "caption": caption, "parse_mode": "HTML"}, "reply_markup": keyboard})
                            await fetch(f"{FIREBASE_DB_URL}/active_unlocks/{chat_id}_{file_id}.json", method="PUT", payload={"chat_id": chat_id, "message_id": int(msg_id), "file_id": file_id, "unlock_time": time.time()})
                            await fetch(f"{FIREBASE_DB_URL}/msg_tracks/{chat_id}_{file_id}.json", method="DELETE")
                        
                        await fetch(f"{FIREBASE_DB_URL}/unlock_requests/{req_id}.json", method="DELETE")
        except Exception: pass
        await asyncio.sleep(3)

async def check_expired_unlocks():
    while True:
        try:
            status, unlocks, _ = await fetch(f"{FIREBASE_DB_URL}/active_unlocks.json")
            if status == 200 and unlocks and isinstance(unlocks, dict):
                for key, record in unlocks.items():
                    if time.time() - record.get("unlock_time", 0) >= 900:
                        video = next((v for v in videos_db if v["video_id"] == record["file_id"]), None)
                        if video:
                            caption = f"🎬 <b>{video['title']}</b>\n\n📄 {video['desc']}\n\n🔒 <i>সময় শেষ! ভিডিওটি পুনরায় লক হয়ে গেছে।</i>"
                            final_web_url = f"{WEB_APP_URL}{'&' if '?' in WEB_APP_URL else '?'}chat_id={record['chat_id']}&file_id={record['file_id']}"
                            keyboard = {"inline_keyboard": [[{"text": "🔓 Unlock Video 🔓", "web_app": {"url": final_web_url}}, {"text": f"👍 {video.get('likes', 0)}", "callback_data": f"like_{video['id']}"}]]}
                            
                            await telegram_api_call("editMessageMedia", {"chat_id": record["chat_id"], "message_id": int(record["message_id"]), "media": {"type": "photo", "media": video["thumb_id"], "caption": caption, "parse_mode": "HTML"}, "reply_markup": keyboard})
                            await fetch(f"{FIREBASE_DB_URL}/msg_tracks/{record['chat_id']}_{record['file_id']}.json", method="PUT", payload=record["message_id"])
                        await fetch(f"{FIREBASE_DB_URL}/active_unlocks/{key}.json", method="DELETE")
        except Exception: pass
        await asyncio.sleep(5)

# ================= মূল মেসেজ প্রসেসিং =================
async def process_message(msg):
    global videos_db
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    
    if chat_id not in users_db:
        users_db.add(chat_id)
        asyncio.create_task(firebase_save_user(chat_id))

    if text.startswith("/start"):
        if chat_id == ADMIN_ID:
            await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "👨‍💻 <b>স্বাগতম অ্যাডমিন!</b>", "parse_mode": "HTML", "reply_markup": get_admin_keyboard()})
        else:
            await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "🌟 <b>স্বাগতম!</b>", "parse_mode": "HTML", "reply_markup": {"remove_keyboard": True}})
            if "_" in text:
                vid = next((v for v in videos_db if v["id"] == text.split("_")[1]), None)
                if vid: await send_video_post(chat_id, vid, is_admin=False); return
            for video in videos_db: await send_video_post(chat_id, video, is_admin=False)
        return

    if chat_id == ADMIN_ID:
        if text in ["📤 POST Video", "POST Video"]:
            admin_states[chat_id] = {"step": "title"}
            await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "📝 Title দিন:", "parse_mode": "HTML"})
            return
        state = admin_states.get(chat_id)
        if state:
            if state["step"] == "title" and text:
                state["title"] = text; state["step"] = "desc"
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "📄 Description দিন:", "parse_mode": "HTML"})
            elif state["step"] == "desc" and text:
                state["desc"] = text; state["step"] = "thumb"
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "🖼️ Thumbnail পাঠান:", "parse_mode": "HTML"})
            elif state["step"] == "thumb" and "photo" in msg:
                state["thumb_id"] = msg["photo"][-1]["file_id"]; state["step"] = "video"
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "🎥 Video পাঠান:", "parse_mode": "HTML"})
            elif state["step"] == "video" and "video" in msg:
                new_video = {"id": str(int(time.time() * 1000)), "title": state["title"], "desc": state["desc"], "thumb_id": state["thumb_id"], "video_id": msg["video"]["file_id"], "likes": 0, "liked_by": []}
                videos_db.append(new_video)
                asyncio.create_task(firebase_save_video(new_video))
                del admin_states[chat_id]
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "✅ আপলোড সফল!"})
                await send_video_post(chat_id, new_video, is_admin=True)
                await broadcast_to_users(new_video)

async def process_callback(cq):
    global videos_db 
    chat_id, msg_id, data, cb_id = cq["message"]["chat"]["id"], cq["message"]["message_id"], cq["data"], cq["id"]
    
    if data.startswith("like_"):
        vid = next((v for v in videos_db if v["id"] == data.split("_")[1]), None)
        if vid:
            if chat_id != ADMIN_ID and chat_id in vid.get('liked_by', []):
                await telegram_api_call("answerCallbackQuery", {"callback_query_id": cb_id, "text": "❌ ইতিমধ্যে লাইক করেছেন!", "show_alert": True})
                return
            vid['likes'] = vid.get('likes', 0) + 1
            if chat_id != ADMIN_ID: vid.setdefault('liked_by', []).append(chat_id)
            asyncio.create_task(firebase_save_video(vid))
            await telegram_api_call("answerCallbackQuery", {"callback_query_id": cb_id, "text": "❤️ লাইক দিয়েছেন!"})
            markup = cq["message"]["reply_markup"]
            for row in markup["inline_keyboard"]:
                for btn in row:
                    if btn.get("callback_data") == data: btn["text"] = f"👍 {vid['likes']}"
            await telegram_api_call("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": msg_id, "reply_markup": markup})
    elif data.startswith("del_") and chat_id == ADMIN_ID:
        vid_id = data.split("_")[1]
        videos_db = [v for v in videos_db if v["id"] != vid_id]
        asyncio.create_task(firebase_delete_video(vid_id))
        await telegram_api_call("answerCallbackQuery", {"callback_query_id": cb_id, "text": "✅ ডিলেট করা হয়েছে!"})
        await telegram_api_call("deleteMessage", {"chat_id": chat_id, "message_id": msg_id})

# ================= ওয়েব সার্ভার (Render এর জন্য) =================
async def handle_web(request):
    return web.Response(text="Bot is Live 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Web server running on port {port}")

# ================= মূল বট লুপ =================
async def start_bot():
    global users_db, videos_db
    print("✨ বটের সার্ভার চালু হচ্ছে...")
    await start_web_server()
    
    users_db = await firebase_get_users()
    videos_db = await firebase_get_videos()
    
    asyncio.create_task(check_ad_unlock_requests())
    asyncio.create_task(check_expired_unlocks())
    
    offset = 0
    await telegram_api_call("getUpdates", {"offset": -1})
    
    while True:
        updates = await telegram_api_call("getUpdates", {"offset": offset, "timeout": 10})
        if updates and isinstance(updates, dict) and updates.get("result"):
            for update in updates["result"]:
                offset = update["update_id"] + 1
                try:
                    if "message" in update: await process_message(update["message"])
                    elif "callback_query" in update: await process_callback(update["callback_query"])
                except Exception as e: print(f"Error: {e}")
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(start_bot())    thumb_id = video.get('thumb_id', '')
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
