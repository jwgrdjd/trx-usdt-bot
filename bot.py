import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =====================
# 🔧 可自行調整設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2     # 固定匯率：1 USDT = 3.2 TRX
FEE_RATE = 0.05          # 手續費 5%（只改這行）
MIN_USDT = 5.0           # 最低兌換金額
DISPLAY_USDT = 10.0      # 顯示用金額（10 USDT）

# =====================
# 🤖 /start
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查看 10 USDT 可兌換多少 TRX\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n"
        "🌐 網路：TRC20\n"
        "💰 匯率：固定（含手續費）"
    )

    await update.message.reply_text(text)


# =====================
# 🤖 /usdt
# =====================

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# =====================
# 🚀 啟動
# =====================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN 未設定（請到 Railway Variables 設定）")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    print("✅ Bot 已啟動（固定匯率 / HTML code 模式）")
    app.run_polling()


if __name__ == "__main__":
    main()
