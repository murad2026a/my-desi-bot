import aiohttp
from aiohttp import web
import os
import json
import asyncio
import time
import urllib.parse

# ================= Render-এর জন্য pyfetch রিপ্লেসমেন্ট =================
class DummyResponse:
    def __init__(self, status, text_data):
        self.status = status
        self.text = text_data

    async def json(self):
        if not self.text or self.text.strip() == "null":
            return None
        try:
            return json.loads(self.text)
        except:
            return None

async def pyfetch(url, method="GET", headers=None, body=None):
    async with aiohttp.ClientSession() as session:
        try:
            if method == "GET":
                async with session.get(url, headers=headers) as resp:
                    return DummyResponse(resp.status, await resp.text())
            elif method == "PUT":
                async with session.put(url, headers=headers, data=body) as resp:
                    return DummyResponse(resp.status, await resp.text())
            elif method == "POST":
                async with session.post(url, headers=headers, data=body) as resp:
                    return DummyResponse(resp.status, await resp.text())
            elif method == "DELETE":
                async with session.delete(url, headers=headers) as resp:
                    return DummyResponse(resp.status, await resp.text())
        except Exception as e:
            print(f"Network error: {e}")
            return DummyResponse(500, "{}")

# ================= কনফিগারেশন =================
BOT_TOKEN = "8720888225:AAGVNXzmLCLDJfQUvZ5zdieOAhTxddbtrn0"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
ADMIN_ID = 5578674054
BOT_USERNAME = "DesiView_bot" 

# 🟢 আপনার ব্লগস্পট অ্যাড শো করার লিংক
WEB_APP_URL = "https://bjkbnbb577787787.blogspot.com/?m=1"

# ================= ফায়ারবেস কনফিগারেশন =================
FIREBASE_DB_URL = "https://earning-36434-default-rtdb.firebaseio.com"

users_db = set() 
videos_db = []   
admin_states = {} 

# ================= ফায়ারবেস API ফাংশনস =================
async def firebase_get_users():
    url = f"{FIREBASE_DB_URL}/users.json"
    try:
        response = await pyfetch(url, method="GET")
        if response.status == 200:
            data = await response.json()
            if not data:
                return set()
            if isinstance(data, dict):
                return set(int(k) for k in data.keys() if k.isdigit())
            elif isinstance(data, list):
                return set(int(v) for v in data if v is not None)
    except Exception as e:
        print(f"⚠️ [Firebase Load Users Error]: {e}")
    return set()

async def firebase_save_user(chat_id):
    url = f"{FIREBASE_DB_URL}/users/{chat_id}.json"
    try:
        await pyfetch(url, method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(True))
    except Exception as e:
        print(f"⚠️ [Firebase Save User Error]: {e}")

async def firebase_get_videos():
    url = f"{FIREBASE_DB_URL}/videos.json"
    try:
        response = await pyfetch(url, method="GET")
        if response.status == 200:
            data = await response.json()
            if not data:
                return []
            if isinstance(data, dict):
                return list(data.values())
            elif isinstance(data, list):
                return [v for v in data if v is not None]
    except Exception as e:
        print(f"⚠️ [Firebase Load Videos Error]: {e}")
    return []

async def firebase_save_video(video):
    url = f"{FIREBASE_DB_URL}/videos/{video['id']}.json"
    try:
        await pyfetch(url, method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(video))
    except Exception as e:
        print(f"⚠️ [Firebase Save Video Error]: {e}")

async def firebase_delete_video(video_id):
    url = f"{FIREBASE_DB_URL}/videos/{video_id}.json"
    try:
        await pyfetch(url, method="DELETE")
    except Exception as e:
        print(f"⚠️ [Firebase Delete Video Error]: {e}")

# ================= TELEGRAM API ফাংশন =================
async def telegram_api_call(method, payload=None):
    url = BASE_URL + method
    headers = {"Content-Type": "application/json"}
    try:
        if payload:
            response = await pyfetch(url, method="POST", headers=headers, body=json.dumps(payload))
        else:
            response = await pyfetch(url, method="GET")
        
        res_json = await response.json()
        if response.status == 200:
            return res_json
        else:
            print(f"❌ [Telegram API Error ({method})]: {res_json.get('description', 'Unknown Error')}")
    except Exception as e:
        print(f"⚠️ [Network Error ({method})]: {e}")
    return None

# ================= হেল্পার ফাংশনস =================
def get_admin_keyboard():
    return {
        "keyboard": [[{"text": "📤 POST Video"}]],
        "resize_keyboard": True,
        "is_persistent": True
    }

def get_video_keyboard(chat_id, video, is_admin=False, is_unlocked=False):
    """কীবোর্ড এবং লাইক ইমোজি ডাইনামিকভাবে জেনারেট করার ফাংশন"""
    vid_id = video.get('id', '')
    video_file_id = video.get('video_id', '')
    likes = video.get('likes', 0)
    liked_by = video.get('liked_by', [])
    
    # 🟢 লাইক দিলে ইমোজি পরিবর্তন (❤️)
    like_text = f"❤️ {likes}" if chat_id in liked_by else f"👍 {likes}"
    
    if is_admin:
        return {
            "inline_keyboard": [
                [
                    {"text": "🗑️ Delete Video", "callback_data": f"del_{vid_id}"},
                    {"text": like_text, "callback_data": f"like_{vid_id}"}
                ]
            ]
        }
    
    if is_unlocked:
        share_text = urllib.parse.quote(f"🔥 চমৎকার সব প্রিমিয়াম ভিডিও ফ্রিতে দেখতে আমাদের বটে যুক্ত হোন!\n\n👉 @{BOT_USERNAME}")
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text={share_text}"
        return {
            "inline_keyboard": [
                [
                    {"text": like_text, "callback_data": f"like_{vid_id}"},
                    {"text": "📢 Share Bot", "url": share_url}
                ]
            ]
        }
    else:
        url_separator = "&" if "?" in WEB_APP_URL else "?"
        final_web_url = f"{WEB_APP_URL}{url_separator}chat_id={chat_id}&file_id={video_file_id}"
        return {
            "inline_keyboard": [
                [
                    {"text": "🔓 Unlock Video 🔓", "web_app": {"url": final_web_url}},
                    {"text": like_text, "callback_data": f"like_{vid_id}"}
                ]
            ]
        }

async def broadcast_to_users(video_info):
    print(f"📢 ব্রডকাস্ট শুরু হচ্ছে... টার্গেট ইউজার: {len(users_db)} জন।")
    for user_id in list(users_db):
        if int(user_id) != int(ADMIN_ID):
            asyncio.create_task(send_video_post(user_id, video_info, is_admin=False))

async def send_video_post(chat_id, video, is_admin=False):
    if not video or not isinstance(video, dict):
        return
        
    title = video.get('title', 'No Title')
    desc = video.get('desc', 'No Description')
    thumb_id = video.get('thumb_id', '')
    video_file_id = video.get('video_id', '')

    if not thumb_id:
        return

    caption = f"🎬 <b>{title}</b>\n\n📄 {desc}"
    keyboard = get_video_keyboard(chat_id, video, is_admin, is_unlocked=False)

    payload = {
        "chat_id": chat_id,
        "photo": thumb_id,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": keyboard
    }
    
    # 🟢 ইউজারদের জন্য ডাউনলোড এবং ফরওয়ার্ড বন্ধ করা হলো
    if not is_admin:
        payload["protect_content"] = True

    res = await telegram_api_call("sendPhoto", payload)
    
    if res and res.get("ok"):
        msg_id = res["result"]["message_id"]
        url = f"{FIREBASE_DB_URL}/msg_tracks/{chat_id}_{video_file_id}.json"
        await pyfetch(url, method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(msg_id))

async def update_all_likes(video):
    """যেকোনো ইউজার লাইক দিলে সবার স্ক্রিনে লাইক কাউন্ট ও ইমোজি লাইভ আপডেট হবে"""
    video_file_id = video.get('video_id', '')
    
    tracks_resp = await pyfetch(f"{FIREBASE_DB_URL}/msg_tracks.json", method="GET")
    tracks = await tracks_resp.json() if tracks_resp.status == 200 else {}
    
    unlocks_resp = await pyfetch(f"{FIREBASE_DB_URL}/active_unlocks.json", method="GET")
    unlocks = await unlocks_resp.json() if unlocks_resp.status == 200 else {}
    
    if not tracks or not isinstance(tracks, dict):
        return
        
    active_unlocked_keys = set(unlocks.keys()) if isinstance(unlocks, dict) else set()
    
    for key, msg_id in tracks.items():
        if key.endswith(f"_{video_file_id}"):
            chat_id_str = key.split("_")[0]
            try:
                chat_id = int(chat_id_str)
            except:
                continue
            
            is_unlocked = key in active_unlocked_keys
            is_admin = (chat_id == ADMIN_ID)
            
            # সবার জন্য নতুন কীবোর্ড (নতুন লাইক নাম্বারসহ) জেনারেট হচ্ছে
            kb = get_video_keyboard(chat_id, video, is_admin, is_unlocked)
            
            await telegram_api_call("editMessageReplyMarkup", {
                "chat_id": chat_id,
                "message_id": int(msg_id),
                "reply_markup": kb
            })
            await asyncio.sleep(0.05) # রেট লিমিট থেকে বাঁচতে ছোট্ট ডিলে

# ================= অটো-ডেলিভারি এবং টাইমার ফাংশনস =================
async def check_ad_unlock_requests():
    """অ্যাড দেখার পর ভিডিও আনলক করার প্রক্রিয়া"""
    while True:
        try:
            url = f"{FIREBASE_DB_URL}/unlock_requests.json"
            response = await pyfetch(url, method="GET")
            if response.status == 200:
                requests = await response.json()
                if requests and isinstance(requests, dict):
                    for req_id, req_data in requests.items():
                        chat_id = req_data.get("chat_id")
                        file_id = req_data.get("file_id")
                        
                        if chat_id and file_id:
                            track_url = f"{FIREBASE_DB_URL}/msg_tracks/{chat_id}_{file_id}.json"
                            track_resp = await pyfetch(track_url, method="GET")
                            
                            video_item = next((v for v in videos_db if v["video_id"] == file_id), None)
                            if not video_item:
                                continue
                            
                            title = video_item.get("title", "Premium Video")
                            desc = video_item.get("desc", "")
                            caption_text = f"🎬 <b>{title}</b>\n\n📄 {desc}\n\n🎉 <i>ভিডিওটি আনলক করা হয়েছে (১৫ মিনিট পর পুনরায় লক হয়ে যাবে)।</i>"

                            unlocked_keyboard = get_video_keyboard(chat_id, video_item, is_admin=False, is_unlocked=True)

                            if track_resp.status == 200 and track_resp.text:
                                msg_id = await track_resp.json()
                                if msg_id:
                                    # থাম্বনেইল পরিবর্তন করে ভিডিও বসানো হচ্ছে
                                    await telegram_api_call("editMessageMedia", {
                                        "chat_id": chat_id,
                                        "message_id": int(msg_id),
                                        "media": {
                                            "type": "video",
                                            "media": file_id,
                                            "caption": caption_text,
                                            "parse_mode": "HTML"
                                        },
                                        "reply_markup": unlocked_keyboard
                                    })
                                    
                                    # ১৫ মিনিটের টাইমারের জন্য রেকর্ড ফায়ারবেসে সেভ
                                    unlock_record = {
                                        "chat_id": chat_id,
                                        "message_id": int(msg_id),
                                        "file_id": file_id,
                                        "unlock_time": time.time()
                                    }
                                    await pyfetch(f"{FIREBASE_DB_URL}/active_unlocks/{chat_id}_{file_id}.json", method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(unlock_record))
                                    
                                    await pyfetch(f"{FIREBASE_DB_URL}/unlock_requests/{req_id}.json", method="DELETE")
                                    continue
                            
                            await pyfetch(f"{FIREBASE_DB_URL}/unlock_requests/{req_id}.json", method="DELETE")
        except Exception as e:
            pass
        await asyncio.sleep(2)

async def check_expired_unlocks():
    """১৫ মিনিট (৯০০ সেকেন্ড) পর ভিডিও পুনরায় লক করার প্রক্রিয়া"""
    while True:
        try:
            url = f"{FIREBASE_DB_URL}/active_unlocks.json"
            response = await pyfetch(url, method="GET")
            if response.status == 200:
                unlocks = await response.json()
                if unlocks and isinstance(unlocks, dict):
                    current_time = time.time()
                    for key, record in unlocks.items():
                        chat_id = record.get("chat_id")
                        msg_id = record.get("message_id")
                        file_id = record.get("file_id")
                        unlock_time = record.get("unlock_time", 0)
                        
                        # ৯০০ সেকেন্ড = ১৫ মিনিট
                        if current_time - unlock_time >= 900:
                            video = next((v for v in videos_db if v["video_id"] == file_id), None)
                            if video:
                                title = video.get("title", "Premium Video")
                                desc = video.get("desc", "")
                                thumb_id = video.get("thumb_id", "")
                                caption = f"🎬 <b>{title}</b>\n\n📄 {desc}\n\n🔒 <i>সময় শেষ! ভিডিওটি পুনরায় লক হয়ে গেছে। আবার দেখতে আনলক করুন।</i>"
                                
                                locked_keyboard = get_video_keyboard(chat_id, video, is_admin=False, is_unlocked=False)
                                
                                # পুনরায় থাম্বনেইল ফটো বসানো হচ্ছে
                                await telegram_api_call("editMessageMedia", {
                                    "chat_id": chat_id,
                                    "message_id": int(msg_id),
                                    "media": {
                                        "type": "photo",
                                        "media": thumb_id,
                                        "caption": caption,
                                        "parse_mode": "HTML"
                                    },
                                    "reply_markup": locked_keyboard
                                })
                                
                                track_url = f"{FIREBASE_DB_URL}/msg_tracks/{chat_id}_{file_id}.json"
                                await pyfetch(track_url, method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(msg_id))
                            
                            await pyfetch(f"{FIREBASE_DB_URL}/active_unlocks/{key}.json", method="DELETE")
        except Exception as e:
            pass
        await asyncio.sleep(5)

# ================= মূল আপডেট হ্যান্ডলার =================
async def process_message(msg):
    global videos_db
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    
    if chat_id not in users_db:
        users_db.add(chat_id)
        asyncio.create_task(firebase_save_user(chat_id))

    if text.startswith("/start"):
        if chat_id == ADMIN_ID:
            await telegram_api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "👨‍💻 <b>স্বাগতম অ্যাডমিন!</b>\nনিচের <b>POST Video</b> বাটনে ক্লিক করে নতুন ভিডিও আপলোড করুন।\n\n<i>নিচে আপনার আপলোড করা আগের ভিডিওগুলো দেওয়া হলো (যদি থাকে):</i>",
                "parse_mode": "HTML",
                "reply_markup": get_admin_keyboard()
            })
            
            if not videos_db:
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "এখনো কোনো ভিডিও আপলোড করা হয়নি।"})
            else:
                for video in videos_db:
                    await send_video_post(chat_id, video, is_admin=True)
                    await asyncio.sleep(0.5) 
        else:
            await telegram_api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "🌟 <b>স্বাগতম!</b>\nএখানে আমাদের সব প্রিমিয়াম ভিডিও দেওয়া আছে।",
                "parse_mode": "HTML",
                "reply_markup": {"remove_keyboard": True}
            })
            
            if "_" in text:
                target_id = text.split("_")[1]
                specific_video = next((v for v in videos_db if v["id"] == target_id), None)
                if specific_video:
                    await send_video_post(chat_id, specific_video, is_admin=False)
                    return
            
            if not videos_db:
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "এখনো কোনো ভিডিও আপলোড করা হয়নি।"})
            else:
                for video in videos_db:
                    await send_video_post(chat_id, video, is_admin=False)
        return

    if chat_id == ADMIN_ID:
        if text in ["📤 POST Video", "POST Video"]:
            admin_states[chat_id] = {"step": "title"}
            await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "📝 <b>ধাপ ১:</b> ভিডিওর Title (নাম) দিন:", "parse_mode": "HTML"})
            return
            
        state = admin_states.get(chat_id)
        if state:
            if state["step"] == "title" and text:
                state["title"] = text
                state["step"] = "desc"
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "📄 <b>ধাপ ২:</b> ভিডিওর Description (বর্ণনা) দিন:", "parse_mode": "HTML"})
            
            elif state["step"] == "desc" and text:
                state["desc"] = text
                state["step"] = "thumb"
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "🖼️ <b>ধাপ ৩:</b> ভিডিওর Thumbnail (ছবি) পাঠান:", "parse_mode": "HTML"})
            
            elif state["step"] == "thumb" and "photo" in msg:
                photo_id = msg["photo"][-1]["file_id"]
                state["thumb_id"] = photo_id
                state["step"] = "video"
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "🎥 <b>ধাপ ৪:</b> এবার মূল Video টি পাঠান:", "parse_mode": "HTML"})
            
            elif state["step"] == "video" and "video" in msg:
                video_id = msg["video"]["file_id"]
                video_uid = str(int(time.time() * 1000))
                
                new_video = {
                    "id": video_uid, 
                    "title": state["title"],
                    "desc": state["desc"],
                    "thumb_id": state["thumb_id"],
                    "video_id": video_id,
                    "likes": 0,
                    "liked_by": []
                }
                
                videos_db.append(new_video)
                asyncio.create_task(firebase_save_video(new_video))
                
                if chat_id in admin_states:
                    del admin_states[chat_id] 
                
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "✅ <b>ভিডিও সফলভাবে আপলোড ও ডেটাবেসে সেভ হয়েছে!</b>", "parse_mode": "HTML"})
                await send_video_post(chat_id, new_video, is_admin=True)
                await broadcast_to_users(new_video)

# ================= কলব্যাক হ্যান্ডলার =================
async def process_callback(cq):
    global videos_db 
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    data = cq["data"]
    callback_id = cq["id"]
    
    if data.startswith("like_"):
        vid_id = data.split("_")[1]
        video = next((v for v in videos_db if v["id"] == vid_id), None)
        if video:
            liked_by = video.get('liked_by', [])
            if not isinstance(liked_by, list):
                liked_by = []
            
            if chat_id in liked_by:
                await telegram_api_call("answerCallbackQuery", {
                    "callback_query_id": callback_id, 
                    "text": "❌ আপনি ইতিমধ্যে এই ভিডিওটি লাইক করেছেন!",
                    "show_alert": True
                })
                return
            
            # লাইক কাউন্ট ও ইউজার যুক্ত করা
            video['likes'] = video.get('likes', 0) + 1
            liked_by.append(chat_id)
            video['liked_by'] = liked_by
            
            asyncio.create_task(firebase_save_video(video))
            await telegram_api_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "❤️ আপনি ভিডিওটি লাইক করেছেন!"})
            
            # 🟢 সবার কাছে লাইভ আপডেট পাঠানো হচ্ছে
            asyncio.create_task(update_all_likes(video))

    elif data.startswith("del_") and chat_id == ADMIN_ID:
        vid_id = data.split("_")[1]
        videos_db = [v for v in videos_db if v["id"] != vid_id]
        asyncio.create_task(firebase_delete_video(vid_id))
        
        await telegram_api_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "✅ ভিডিও ডিলেট করা হয়েছে!"})
        await telegram_api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

# ================= মূল বট লুপ ও সার্ভার স্টার্টার =================
async def start_bot():
    global users_db, videos_db
    print("✨ Render সার্ভারে টেলিগ্রাম বট সফলভাবে চালু হচ্ছে...")
    
    # Render "Web Service" এর জন্য একটি ডামি HTTP সার্ভার চালু করা হচ্ছে
    app = web.Application()
    app.router.add_get('/', lambda request: web.Response(text="Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Dummy web server started on port {port}")
    
    # ডেটাবেস লোড
    users_db = await firebase_get_users()
    raw_vids = await firebase_get_videos()
    videos_db = [v for v in raw_vids if isinstance(v, dict) and 'id' in v]
    
    # ব্যাকগ্রাউন্ড টাস্কগুলো শুরু করা হলো
    asyncio.create_task(check_ad_unlock_requests())
    asyncio.create_task(check_expired_unlocks())
    
    offset = 0
    await telegram_api_call("getUpdates", {"offset": -1})
    
    while True:
        updates = await telegram_api_call("getUpdates", {"offset": offset, "timeout": 2})
        if updates and updates.get("ok") and updates.get("result"):
            for update in updates["result"]:
                offset = update["update_id"] + 1
                try:
                    if "message" in update:
                        await process_message(update["message"])
                    elif "callback_query" in update:
                        await process_callback(update["callback_query"])
                except Exception as e:
                    print(f"Error Processing Update: {e}")
        await asyncio.sleep(1)

# ================= অ্যাপলিকেশন রান =================
if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("Bot stopped by user.")
