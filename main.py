import os
import re
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
GROUP_ID = os.getenv("GROUP_ID")

collecting = False
collected_data = []
send_time = None

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

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    global collecting, collected_data, send_time

    user_text = event.message.text.strip()
    log_group_id(event)

    if user_text.startswith("/Send"):
        match = re.match(r"/Send\s+(\d{1,2}):(\d{2})", user_text)
        if match:
            hh, mm = map(int, match.groups())
            now = datetime.now() + timedelta(hours=8)
            send_time = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if send_time < now:
                send_time += timedelta(days=1)
            collecting = True
            collected_data = []
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=f"開始收集，將於 {send_time.strftime('%H:%M')} 推播")
            )
        return

    elif user_text.startswith("/End"):
        match = re.match(r"/End\s+(\d{1,2}):(\d{2})", user_text)
        if match and collecting:
            collecting = False
            scheduler.add_job(
                func=send_collected,
                trigger='date',
                run_date=send_time - timedelta(hours=8),
                id=f"job_{send_time.timestamp()}",
                args=[collected_data.copy()]
            )
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=f"收集結束，已排程推播")
            )
        return

    if collecting:
        collected_data.append(user_text)

def send_collected(texts):
    if not GROUP_ID:
        print("⚠️ 尚未設定 GROUP_ID")
        return
    for text in texts:
        try:
            line_bot_api.push_message(GROUP_ID, TextSendMessage(text=text))
        except Exception as e:
            print("❗推播錯誤:", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
