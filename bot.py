import os
import requests
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ========= 基本設定 =========

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Railway 變數
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

DEFAULT_USDT = 10.0
MIN_USDT = 5.0
FEE_RATE = 0.05            # 5%
FALLBACK_TRX_PRICE = 0.30.6  # 備用匯率（USDT）

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ========= 匯率 =========

def get_trx_price_usdt() -> float:
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "tron",
            "vs_currencies": "usdt"
        }
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        return float(data["tron"]["usdt"])
    except Exception:
        return FALLBACK_TRX_PRICE

# ========= 指令 =========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt\n\n"
        f"🔻 最小兌換金額：{MIN_USDT} USDT\n"
        "💼 即時匯率\n"
        "🌐 網路：TRC20"
    )
    await update.message.reply_text(text)

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usdt_amount = DEFAULT_USDT

    if usdt_amount < MIN_USDT:
        await update.message.reply_text("❌ 低於最小兌換金額")
        return

    trx_price = get_trx_price_usdt()
    effective_price = trx_price * (1 + FEE_RATE)
    trx_amount = round(usdt_amount / effective_price, 2)

    text = (
        "💱 USDT → TRX 兌換報價\n\n"
        f"USDT：{usdt_amount}\n"
        f"可兌換 TRX：約 {trx_amount}\n\n"
        "📥 TRC20 USDT 收款地址（可直接複製）\n"
        f"{TRC20_ADDRESS}\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "轉帳完成後請耐心等待系統處理"
    )

    await update.message.reply_text(text)

# ========= 主程式 =========

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    logging.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
