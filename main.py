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

# 以下略（其餘邏輯與之前相同）
