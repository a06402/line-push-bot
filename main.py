import os
import re
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
GROUP_IDS = os.getenv("GROUP_IDS", "").split(",")

SCHEDULE_FILE = "schedule.json"
collecting = False
collected_data = []
start_time = None

# 初始化排程檔案
if not os.path.exists(SCHEDULE_FILE):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump([], f)

def log_group_id(event):
    if hasattr(event.source, "group_id"):
        print("🚩 群組 ID:", event.source.group_id)

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

@app.route("/cron", methods=["GET"])
def cron_trigger():
    now = datetime.utcnow() + timedelta(hours=8)
    now_str = now.strftime("%Y-%m-%d %H:%M")

    with open(SCHEDULE_FILE, "r") as f:
        schedules = json.load(f)

    remaining = []
    for item in schedules:
        if item["time"] == now_str:
            print(f"⏰ 推播時間到：{item['time']}，訊息數量：{len(item['messages'])}")
            for group_id in GROUP_IDS:
                for msg in item["messages"]:
                    try:
                        line_bot_api.push_message(group_id.strip(), TextSendMessage(text=msg))
                        print(f"✅ 已推播至 {group_id.strip()}：{msg}")
                    except Exception as e:
                        print(f"❗推播錯誤至 {group_id.strip()}：{e}")
        else:
            remaining.append(item)

    with open(SCHEDULE_FILE, "w") as f:
        json.dump(remaining, f)

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    global collecting, collected_data, start_time

    user_text = event.message.text.strip()
    log_group_id(event)

    if user_text.startswith("/Send"):
        match = re.match(r"/Send\s+(\d{1,2}):(\d{2})", user_text)
        if match:
            hh, mm = map(int, match.groups())
            now = datetime.utcnow() + timedelta(hours=8)
            start_time = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if start_time < now:
                start_time += timedelta(days=1)
            collecting = True
            collected_data = []
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"開始收集，將於 {start_time.strftime('%H:%M')} 推播")
            )
        return

    elif user_text.startswith("/End"):
        match = re.match(r"/End\s+(\d{1,2}):(\d{2})", user_text)
        if match and collecting:
            collecting = False
            schedule_time = start_time.strftime("%Y-%m-%d %H:%M")

            with open(SCHEDULE_FILE, "r") as f:
                schedules = json.load(f)

            schedules.append({
                "time": schedule_time,
                "messages": collected_data
            })

            with open(SCHEDULE_FILE, "w") as f:
                json.dump(schedules, f)

            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=f"收集結束，已排程推播")
            )
        return

    if collecting:
        collected_data.append(user_text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
