import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

TRX_RATE = 0.305
USDT_AMOUNT = 10
TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"


async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = USDT_AMOUNT / TRX_RATE

    text = (
        "💱 USDT → TRX 兌換報價\n\n"
        f"USDT：{USDT_AMOUNT}\n"
        f"可兌換 TRX：約 {trx_amount:.2f}\n\n"
        "📥 TRC20 USDT 收款地址（可直接複製）\n"
        f"`{TRC20_ADDRESS}`\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "轉帳完成後請耐心等待處理"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("usdt", usdt))
    app.run_polling()


if __name__ == "__main__":
    main()
