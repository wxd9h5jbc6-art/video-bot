# -*- coding: utf-8 -*-
import os
import time
import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================
BOT_TOKEN      = os.getenv("BOT_TOKEN")
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
AVATAR_ID      = os.getenv("AVATAR_ID", "josh_lite3_20230714")
VOICE_ID       = os.getenv("VOICE_ID", "2d5b0e6cf36f460aa7fc47e3eee4ba54")

HEYGEN_BASE = "https://api.heygen.com"

# ============================================================
# FIXED RULES — applied to EVERY video automatically
# Written in English so the API handles it correctly
# ============================================================
FIXED_RULES = (
    "You are a professional video script writer. "
    "Write a natural, realistic script based on the user request below. "
    "MANDATORY rules for every video:\n"
    "1. Saudi Arabian Arabic dialect (Gulf accent) — sounds like a real person speaking naturally\n"
    "2. 100% realistic and cinematic — nothing weird, supernatural, or unrealistic\n"
    "3. Ultra-high quality, sharp details, professional cinematic lighting\n"
    "4. Natural ambient sound during speech — background sounds of the environment (NO soundproofing effect)\n"
    "5. Speech sounds like a real person in a real place\n"
    "6. Write ONLY the spoken script/dialogue — no descriptions, no stage directions\n\n"
    "User request: "
)


# ============================================================
# HEYGEN VIDEO CREATION
# ============================================================
def create_video(user_prompt: str):
    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json; charset=utf-8"
    }

    full_script = FIXED_RULES + user_prompt

    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": AVATAR_ID,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": full_script,
                    "voice_id": VOICE_ID,
                    "speed": 1.0
                },
                "background": {
                    "type": "color",
                    "value": "#f5f5f0"
                }
            }
        ],
        "dimension": {
            "width": 1920,
            "height": 1080
        },
        "test": False
    }

    # Encode payload as UTF-8 explicitly
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    resp = requests.post(
        f"{HEYGEN_BASE}/v2/video/generate",
        headers=headers,
        data=payload_bytes,
        timeout=30
    )

    if resp.status_code != 200:
        print(f"[HeyGen] Create failed: {resp.status_code} — {resp.text}")
        return None

    video_id = resp.json().get("data", {}).get("video_id")
    if not video_id:
        print("[HeyGen] No video_id returned.")
        return None

    print(f"[HeyGen] Video job started: {video_id}")

    for attempt in range(150):
        time.sleep(8)
        status_resp = requests.get(
            f"{HEYGEN_BASE}/v1/video_status.get?video_id={video_id}",
            headers=headers,
            timeout=15
        )

        if status_resp.status_code != 200:
            continue

        data   = status_resp.json().get("data", {})
        status = data.get("status")
        print(f"[HeyGen] Attempt {attempt+1} — status: {status}")

        if status == "completed":
            return data.get("video_url")
        elif status in ("failed", "error"):
            print(f"[HeyGen] Video failed: {data}")
            return None

    print("[HeyGen] Timed out.")
    return None


# ============================================================
# HELPERS
# ============================================================
def fetch_arabic_voices():
    headers = {"X-Api-Key": HEYGEN_API_KEY}
    resp = requests.get(f"{HEYGEN_BASE}/v2/voices", headers=headers, timeout=15)
    if resp.status_code != 200:
        return None
    voices = resp.json().get("data", {}).get("voices", [])
    return [
        v for v in voices
        if "arabic" in v.get("language", "").lower()
        or "ar" in v.get("locale", "").lower()
    ]


def fetch_avatars():
    headers = {"X-Api-Key": HEYGEN_API_KEY}
    resp = requests.get(f"{HEYGEN_BASE}/v2/avatars", headers=headers, timeout=15)
    if resp.status_code != 200:
        return None
    return resp.json().get("data", {}).get("avatars", [])


# ============================================================
# TELEGRAM HANDLERS
# ============================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Send me a description of the video you want.\n\n"
        "Example: A man sitting in his office talking about the importance of saving money\n\n"
        "Rules applied automatically to every video:\n"
        "- Saudi Arabic dialect\n"
        "- Realistic & cinematic\n"
        "- 1080p high quality\n"
        "- Natural sound (no soundproofing)\n"
        "- Nothing weird or unrealistic"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "How to use:\n\n"
        "1. Type a description of your video\n"
        "2. Wait 2-4 minutes\n"
        "3. Receive your video here\n\n"
        "Commands:\n"
        "/voices - Show available Arabic voices\n"
        "/avatars - Show available avatars"
    )


async def cmd_voices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Fetching Arabic voices...")
    try:
        voices = fetch_arabic_voices()
        if not voices:
            await update.message.reply_text("No Arabic voices found or API key error.")
            return
        lines = ["Available Arabic voices:\n"]
        for v in voices[:20]:
            name     = v.get("display_name") or v.get("name", "No name")
            voice_id = v.get("voice_id", "")
            gender   = v.get("gender", "")
            lines.append(f"- {name} ({gender})\n  ID: {voice_id}\n")
        lines.append("\nTo use a voice: go to Railway Variables and change VOICE_ID")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def cmd_avatars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Fetching avatars...")
    try:
        avatars = fetch_avatars()
        if not avatars:
            await update.message.reply_text("No avatars found or API key error.")
            return
        lines = ["Available avatars (first 15):\n"]
        for av in avatars[:15]:
            name      = av.get("avatar_name", "No name")
            avatar_id = av.get("avatar_id", "")
            lines.append(f"- {name}\n  ID: {avatar_id}\n")
        lines.append("\nTo use an avatar: go to Railway Variables and change AVATAR_ID")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        await update.message.reply_text("Please type a video description.")
        return

    status_msg = await update.message.reply_text(
        "Generating your video... This can take 5-25 minutes, please wait."
    )

    try:
        video_url = create_video(user_text)

        if not video_url:
            await status_msg.edit_text(
                "Error creating video. Check your HEYGEN_API_KEY and try again."
            )
            return

        await status_msg.edit_text("Video ready! Sending...")

        video_resp = requests.get(video_url, timeout=120)
        if video_resp.status_code != 200:
            await status_msg.edit_text("Could not download video. Try again.")
            return

        await update.message.reply_video(
            video=video_resp.content,
            caption="Your video is ready!",
            supports_streaming=True
        )
        await status_msg.delete()

    except Exception as err:
        print(f"[ERROR] {err}")
        await status_msg.edit_text(f"Unexpected error: {str(err)}\n\nPlease try again.")


# ============================================================
# MAIN
# ============================================================
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set!")
    if not HEYGEN_API_KEY:
        raise ValueError("HEYGEN_API_KEY is not set!")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("voices",  cmd_voices))
    app.add_handler(CommandHandler("avatars", cmd_avatars))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
