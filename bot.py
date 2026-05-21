import os
import time
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================================
# ENVIRONMENT VARIABLES — Set these in Railway or your .env
# ============================================================
BOT_TOKEN     = os.getenv("BOT_TOKEN")       # From @BotFather on Telegram
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY") # From HeyGen dashboard

# ============================================================
# HEYGEN SETTINGS — You can change these from HeyGen's site
# ============================================================
# Default avatar: a realistic-looking person
# Go to https://app.heygen.com/avatars to find avatar IDs you like
AVATAR_ID = os.getenv("AVATAR_ID", "josh_lite3_20230714")

# Saudi Arabic voice — use /voices command in Telegram to browse and pick one
# Then update this value in Railway Variables
VOICE_ID = os.getenv("VOICE_ID", "2d5b0e6cf36f460aa7fc47e3eee4ba54")

HEYGEN_BASE = "https://api.heygen.com"

# ============================================================
# FIXED RULES — These are applied automatically to EVERY video
# The user never has to type these, they're always active
# ============================================================
FIXED_RULES = (
    "أنت خبير في كتابة نصوص الفيديو. "
    "اكتب حواراً أو نصاً طبيعياً بناءً على طلب المستخدم. "
    "القواعد الثابتة التي يجب اتباعها في كل فيديو:\n"
    "1. اللهجة السعودية الخليجية الطبيعية — كأنك شخص حقيقي يتحدث في الواقع\n"
    "2. الأسلوب واقعي وسينمائي، لا يوجد أي شيء غريب أو خيالي أو غير طبيعي\n"
    "3. الجودة عالية جداً، تفاصيل دقيقة، إضاءة احترافية\n"
    "4. الصوت طبيعي تماماً — فيه أصوات البيئة المحيطة كالطبيعي (لا عزل صوتي)\n"
    "5. الكلام يبدو كشخص حقيقي في مكان حقيقي\n"
    "6. لا تضف أي وصف أو تعليق — فقط اكتب النص الذي سيُقال في الفيديو\n\n"
    "طلب المستخدم:\n"
)


# ============================================================
# HEYGEN VIDEO CREATION
# ============================================================
def create_video(user_prompt: str) -> str | None:
    """
    Sends a request to HeyGen to generate a video.
    Returns the video URL when done, or None if it failed.
    """

    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json"
    }

    # Combine fixed rules + user prompt into the final script
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
                    "value": "#f5f5f0"   # neutral clean background
                }
            }
        ],
        "dimension": {
            "width": 1920,
            "height": 1080   # 1080p — HeyGen max on paid plan
        },
        "test": False        # Set True for free test watermarked videos
    }

    # Step 1: Create the video job
    resp = requests.post(
        f"{HEYGEN_BASE}/v2/video/generate",
        headers=headers,
        json=payload,
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

    # Step 2: Poll every 8 seconds until done (max 8 minutes)
    for attempt in range(60):
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

    print("[HeyGen] Timed out waiting for video.")
    return None


# ============================================================
# TELEGRAM HANDLERS
# ============================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 أهلاً وسهلاً!\n\n"
        "أنا جاهز أصنع لك فيديوهات احترافية بلهجة سعودية وجودة سينمائية عالية.\n\n"
        "📝 فقط اكتب لي وصف الفيديو اللي تبيه وسأرسله لك خلال دقيقتين أو ثلاثة.\n\n"
        "مثال:\n"
        "• رجل يجلس في مكتبه ويتحدث عن أهمية الوقت\n"
        "• شخص يشرح كيفية التخطيط للمستقبل\n"
        "• محادثة بين صديقين في مقهى"
    )


async def cmd_voices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches Arabic voices from HeyGen API and shows them in Telegram"""
    await update.message.reply_text("🔍 جاري جلب الأصوات العربية من HeyGen...")

    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        resp = requests.get(f"{HEYGEN_BASE}/v2/voices", headers=headers, timeout=15)

        if resp.status_code != 200:
            await update.message.reply_text(
                f"❌ تعذّر جلب الأصوات.\n"
                f"تأكد أن HEYGEN_API_KEY صحيح.\n"
                f"كود الخطأ: {resp.status_code}"
            )
            return

        voices = resp.json().get("data", {}).get("voices", [])

        # Filter Arabic voices only
        arabic_voices = [
            v for v in voices
            if "arabic" in v.get("language", "").lower()
            or "ar" in v.get("locale", "").lower()
            or "arabic" in v.get("name", "").lower()
        ]

        if not arabic_voices:
            await update.message.reply_text(
                "⚠️ ما وجدت أصوات عربية في حسابك.\n"
                "تأكد أن خطتك في HeyGen تدعم الأصوات العربية."
            )
            return

        # Build a readable list
        lines = ["🎙 الأصوات العربية المتاحة:\n"]
        for v in arabic_voices[:20]:  # Show max 20
            name     = v.get("display_name") or v.get("name", "بدون اسم")
            voice_id = v.get("voice_id", "")
            gender   = v.get("gender", "")
            locale   = v.get("locale", "")
            lines.append(f"• {name} ({gender} | {locale})\n  ID: `{voice_id}`\n")

        lines.append(
            "\n💡 لاختيار صوت:\n"
            "اذهب إلى Railway → Variables\n"
            "غيّر قيمة VOICE_ID للـ ID اللي تريده"
        )

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")


async def cmd_avatars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches available avatars from HeyGen API"""
    await update.message.reply_text("🔍 جاري جلب الأفاتارات المتاحة...")

    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        resp = requests.get(f"{HEYGEN_BASE}/v2/avatars", headers=headers, timeout=15)

        if resp.status_code != 200:
            await update.message.reply_text(
                f"❌ تعذّر جلب الأفاتارات.\n"
                f"كود الخطأ: {resp.status_code}"
            )
            return

        avatars = resp.json().get("data", {}).get("avatars", [])

        if not avatars:
            await update.message.reply_text("⚠️ ما وجدت أفاتارات في حسابك.")
            return

        lines = ["🧑 الأفاتارات المتاحة (أول 15):\n"]
        for av in avatars[:15]:
            name      = av.get("avatar_name", "بدون اسم")
            avatar_id = av.get("avatar_id", "")
            lines.append(f"• {name}\n  ID: `{avatar_id}`\n")

        lines.append(
            "\n💡 لاختيار أفاتار:\n"
            "اذهب إلى Railway → Variables\n"
            "غيّر قيمة AVATAR_ID للـ ID اللي تريده"
        )

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 طريقة الاستخدام:\n\n"
        "1️⃣ اكتب وصف الفيديو الذي تريده بأي تفاصيل\n"
        "2️⃣ انتظر 2-4 دقائق\n"
        "3️⃣ سيصلك الفيديو مباشرة هنا\n\n"
        "⚙️ القواعد المطبقة تلقائياً في كل فيديو:\n"
        "✅ لهجة سعودية طبيعية\n"
        "✅ واقعي وسينمائي 100%\n"
        "✅ جودة عالية 1080p\n"
        "✅ صوت طبيعي بدون عزل صوتي\n"
        "✅ لا شيء غريب أو خيالي\n\n"
        "💡 تلميح: كلما أعطيت تفاصيل أكثر، كان الفيديو أفضل!\n\n"
        "🛠 أوامر إضافية:\n"
        "/voices — عرض الأصوات العربية المتاحة في حسابك\n"
        "/avatars — عرض الأفاتارات المتاحة في حسابك"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if not user_text:
        await update.message.reply_text("⚠️ من فضلك اكتب وصف الفيديو الذي تريده.")
        return

    # Send a "working" status message that we'll update later
    status_msg = await update.message.reply_text(
        "⏳ جاري إنشاء الفيديو...\n"
        "هذا يستغرق عادةً من 2 إلى 4 دقائق، يرجى الانتظار 🙏"
    )

    try:
        video_url = create_video(user_text)

        if not video_url:
            await status_msg.edit_text(
                "❌ حدث خطأ أثناء إنشاء الفيديو.\n"
                "تأكد من صحة HEYGEN_API_KEY وحاول مرة أخرى."
            )
            return

        # Download the video into memory
        await status_msg.edit_text("✅ الفيديو جاهز! جاري الإرسال...")

        video_resp = requests.get(video_url, timeout=120)
        if video_resp.status_code != 200:
            await status_msg.edit_text("❌ تعذّر تنزيل الفيديو. حاول مرة أخرى.")
            return

        # Send the video
        await update.message.reply_video(
            video=video_resp.content,
            caption="🎬 فيديوك جاهز! بالتوفيق 🚀",
            supports_streaming=True
        )

        # Remove the status message
        await status_msg.delete()

    except Exception as err:
        print(f"[ERROR] {err}")
        await status_msg.edit_text(
            f"❌ خطأ غير متوقع:\n{str(err)}\n\nحاول مرة أخرى."
        )


# ============================================================
# MAIN — Start the bot
# ============================================================
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set! Add it to your environment variables.")
    if not HEYGEN_API_KEY:
        raise ValueError("HEYGEN_API_KEY is not set! Add it to your environment variables.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("voices",  cmd_voices))   # List Arabic voices
    app.add_handler(CommandHandler("avatars", cmd_avatars))  # List avatars
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot is running and waiting for messages...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
