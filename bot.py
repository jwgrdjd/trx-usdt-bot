import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

RECEIVE_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0
DISPLAY_USDT = 10.0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot 正常運作中\n請輸入 /usdt")

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(DISPLAY_USDT * final_rate, 2)

    text = (
        "💱 USDT → TRX 兌換報價\n\n"
        f"USDT：{DISPLAY_USDT}\n"
        f"可兌換 TRX：約 {trx_amount}\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n\n"
        "📥 TRC20 USDT 收款地址（點擊可複製）\n"
        f"<code>{RECEIVE_ADDRESS}</code>\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳"
    )

    await update.message.reply_text(text, parse_mode="HTML")

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN 未設定")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    print("🤖 Bot 已啟動（最小穩定版）")
    app.run_polling()

if __name__ == "__main__":
    main()
