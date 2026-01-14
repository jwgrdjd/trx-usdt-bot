import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =====================
# 🔧 基本設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# 🔐 管理員 Telegram ID（只允許這些人）
ADMIN_IDS = [7757022123]  # ← 你的 ID

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

# 🔢 可調參數（可被後台指令修改）
FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0
DISPLAY_USDT = 10.0

# ⏸ 系統狀態
SYSTEM_PAUSED = False


# =====================
# 🔐 權限檢查
# =====================

def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS


async def deny(update: Update):
    await update.message.reply_text("⚠️ 權限不足")


# =====================
# 🤖 使用者指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查看兌換資訊\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n"
        "🌐 網路：TRC20"
    )


async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if SYSTEM_PAUSED:
        await update.message.reply_text("⏸ 目前兌換功能暫停中，請稍後再試")
        return

    final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(DISPLAY_USDT * final_rate, 2)

    text = (
        "💱 <b>USDT → TRX 兌換報價</b>\n\n"
        f"USDT：{DISPLAY_USDT}\n"
        f"可兌換 TRX：約 <b>{trx_amount}</b>\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n\n"
        "📥 <b>TRC20 USDT 收款地址</b>\n"
        "（點擊地址即可複製）\n\n"
        f"<code>{TRC20_ADDRESS}</code>\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "轉帳完成後請耐心等待處理"
    )

    await update.message.reply_text(text, parse_mode="HTML")


# =====================
# 🛠️ 後台指令
# =====================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny(update)
        return

    status_text = (
        "📊 系統狀態\n\n"
        f"狀態：{'⏸ 暫停中' if SYSTEM_PAUSED else '🟢 運行中'}\n"
        f"固定匯率：{FIXED_RATE_TRX}\n"
        f"手續費：{int(FEE_RATE * 100)}%\n"
        f"最低兌換：{MIN_USDT} USDT"
    )

    await update.message.reply_text(status_text)


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SYSTEM_PAUSED
    if not is_admin(update):
        await deny(update)
        return

    SYSTEM_PAUSED = True
    await update.message.reply_text("⏸ 已暫停兌換")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SYSTEM_PAUSED
    if not is_admin(update):
        await deny(update)
        return

    SYSTEM_PAUSED = False
    await update.message.reply_text("▶️ 已恢復兌換")


async def setrate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FIXED_RATE_TRX
    if not is_admin(update):
        await deny(update)
        return

    try:
        FIXED_RATE_TRX = float(context.args[0])
        await update.message.reply_text(
            f"✅ 固定匯率已更新\n1 USDT = {FIXED_RATE_TRX} TRX"
        )
    except Exception:
        await update.message.reply_text("❌ 用法：/setrate 3.1")


async def setfee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FEE_RATE
    if not is_admin(update):
        await deny(update)
        return

    try:
        FEE_RATE = float(context.args[0])
        await update.message.reply_text(
            f"✅ 手續費已更新為 {int(FEE_RATE * 100)}%"
        )
    except Exception:
        await update.message.reply_text("❌ 用法：/setfee 0.05")


# =====================
# 🚀 啟動
# =====================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN 未設定")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 使用者
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    # 後台
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("setrate", setrate))
    app.add_handler(CommandHandler("setfee", setfee))

    print("✅ Bot 已啟動（後台管理員 v1）")
    app.run_polling()


if __name__ == "__main__":
    main()
