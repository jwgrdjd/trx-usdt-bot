import os
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ======================
# 基本設定
# ======================

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Railway Variables 設定
TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

DEFAULT_USDT = 10.0
MIN_USDT = 5.0
FEE_RATE = 0.05  # 5% 利差

# ======================
# 匯率取得
# ======================

def get_trx_price_usdt():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "tron",
            "vs_currencies": "usdt"
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return float(data["tron"]["usdt"])
    except Exception:
        return None

# ======================
# /start
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt\n\n"
        "🔻 最小兌換金額：5 USDT\n"
        "💰 即時匯率（含 5% 利差）\n"
        "🌐 網路：TRC20\n\n"
        "輸入 /usdt 查看最新兌換報價"
    )
    await update.message.reply_text(text)

# ======================
# /usdt
# ======================

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = get_trx_price_usdt()

    if price is None:
        await update.message.reply_text("⚠️ 目前無法取得匯率，請稍後再試")
        return

    effective_price = price * (1 + FEE_RATE)
    trx_amount = round(DEFAULT_USDT / effective_price, 2)

    text = (
        "💱 USDT → TRX 兌換報價\n\n"
        f"USDT：{DEFAULT_USDT}\n"
        f"可兌換 TRX：約 {trx_amount}\n\n"
        "📥 TRC20 USDT 收款地址（可直接複製）\n"
        f"{TRC20_ADDRESS}\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "轉帳完成後請耐心等待處理"
    )

    await update.message.reply_text(text)

# ======================
# 主程式
# ======================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN 未設定")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
