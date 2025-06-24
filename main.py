import os
import re
import json
import base64
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, VideoMessage,
    TextSendMessage, ImageSendMessage, VideoSendMessage
)
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
GROUP_IDS = os.getenv("GROUP_IDS", "").split(",")
IMAGEKIT_API_KEY = os.getenv("IMAGEKIT_API_KEY")
IMAGEKIT_UPLOAD_URL = os.getenv("IMAGEKIT_UPLOAD_URL")

SCHEDULE_FILE = "schedule.json"
collecting = False
collected_data = []
start_time = None

if not os.path.exists(SCHEDULE_FILE):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump([], f)

def upload_to_imagekit(binary_data, filename):
    b64 = base64.b64encode(binary_data).decode("utf-8")
    data = {
        "file": f"data:application/octet-stream;base64,{b64}",
        "fileName": filename
    }
    headers = {"Authorization": f"Basic {base64.b64encode((IMAGEKIT_API_KEY + ':').encode()).decode()}"}
    response = requests.post(IMAGEKIT_UPLOAD_URL, data=data, headers=headers)
    if response.status_code == 200:
        return response.json()["url"]
    else:
        print("❗ImageKit 上傳失敗：", response.text)
        return None

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print("❗錯誤:", e)
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    global collecting, collected_data, start_time
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text.startswith("/Send "):
        time_str = text[6:].strip()
        try:
            start_time = datetime.strptime(time_str, "%H:%M").time()
            collecting = True
            collected_data = []
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"開始收集，將於 {time_str} 推播")
            )
        except:
            pass
    elif text.startswith("/End "):
        time_str = text[5:].strip()
        try:
            end_time = datetime.strptime(time_str, "%H:%M").time()
            collecting = False
            with open(SCHEDULE_FILE, "r+") as f:
                data = json.load(f)
                data.append({
                    "start": start_time.strftime("%H:%M"),
                    "end": end_time.strftime("%H:%M"),
                    "contents": collected_data
                })
                f.seek(0)
                json.dump(data, f)
                f.truncate()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="收集結束，已排程推播")
            )
        except:
            pass
    elif text == "/list":
        with open(SCHEDULE_FILE, "r") as f:
            data = json.load(f)
        msg = "\n".join([f"{s['start']} ~ {s['end']}" for s in data]) or "目前沒有排程"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
    elif text.startswith("/use ") or text.startswith("/group "):
        print("⚙️ DEBUG 指令:", text)
    elif collecting:
        collected_data.append({"type": "text", "text": text})

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    if collecting:
        content = line_bot_api.get_message_content(event.message.id)
        image_bytes = content.content
        url = upload_to_imagekit(image_bytes, "image.jpg")
        if url:
            collected_data.append({"type": "image", "url": url})

@handler.add(MessageEvent, message=VideoMessage)
def handle_video(event):
    if collecting:
        content = line_bot_api.get_message_content(event.message.id)
        video_bytes = content.content
        url = upload_to_imagekit(video_bytes, "video.mp4")
        if url:
            collected_data.append({"type": "video", "url": url})

@app.route("/cron", methods=["GET"])
def cron():
    now = datetime.utcnow() + timedelta(hours=8)
    current_time = now.strftime("%H:%M")
    with open(SCHEDULE_FILE, "r+") as f:
        data = json.load(f)
        remaining = []
        for item in data:
            if item["end"] == current_time:
                for gid in GROUP_IDS:
                    for c in item["contents"]:
                        if c["type"] == "text":
                            line_bot_api.push_message(gid, TextSendMessage(text=c["text"]))
                        elif c["type"] == "image":
                            line_bot_api.push_message(gid, ImageSendMessage(original_content_url=c["url"], preview_image_url=c["url"]))
                        elif c["type"] == "video":
                            line_bot_api.push_message(gid, VideoSendMessage(original_content_url=c["url"], preview_image_url=c["url"]))
            else:
                remaining.append(item)
        f.seek(0)
        json.dump(remaining, f)
        f.truncate()
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
