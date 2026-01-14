from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import requests

# ===== 基本設定 =====
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")


# 固定顯示的兌換金額（USDT）
DEFAULT_USDT_AMOUNT = 10.0

# TRC20 USDT 收款地址
TRC20_USDT_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

# 匯差（0.90 = 少給 10% TRX）
FEE_RATE = 0.93


# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "USDT → TRX 兌換機器人 🤖\n"
        "輸入 /usdt 查看兌換報價"
    )


# ===== /usdt（直接顯示兌換報價 + 可複製地址）=====
async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=TRXUSDT"
        response = requests.get(url, timeout=5)
        data = response.json()
        market_price = float(data["price"])
    except Exception:
        await update.message.reply_text("⚠️ 目前無法取得匯率，請稍後再試")
        return

    used_price = market_price / FEE_RATE
    trx_amount = DEFAULT_USDT_AMOUNT / used_price

    await update.message.reply_text(
        f"💱 USDT → TRX 兌換報價\n\n"
        f"USDT：{DEFAULT_USDT_AMOUNT}\n"
        f"可兌換 TRX：約 {trx_amount:.2f}\n\n"
        f"📥 TRC20 USDT 收款地址（點擊即可複製）\n"
        f"<code>{TRC20_USDT_ADDRESS}</code>\n\n"
        f"⚠️ 請務必使用 TRC20 網路轉帳\n"
        f"轉帳完成後請耐心等待處理",
        parse_mode="HTML"
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    print("Bot 已啟動（地址可一鍵複製）...")
    app.run_polling()


if __name__ == "__main__":
    main()


