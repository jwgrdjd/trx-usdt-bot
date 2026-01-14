import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === 基本設定 ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

MIN_USDT = 5.0          # 最小金額
SPREAD_RATE = 0.05      # 5% 利差
DISPLAY_USDT = 5.0      # 顯示用金額（固定）

# CoinGecko API（免費）
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=tron&vs_currencies=usdt"
)


# === 抓即時匯率 ===
def get_trx_price():
    r = requests.get(COINGECKO_URL, timeout=5)
    data = r.json()
    return float(data["tron"]["usdt"])


# === /usdt 指令 ===
async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        market_price = get_trx_price()
    except Exception:
        await update.message.reply_text("⚠️ 目前無法取得匯率，請稍後再試")
        return

    # 套用 5% 利差
    used_price = market_price * (1 + SPREAD_RATE)

    trx_amount = DISPLAY_USDT / used_price

    text = (
        "💱 USDT → TRX 兌換報價（即時）\n\n"
        f"USDT：{DISPLAY_USDT}\n"
        f"可兌換 TRX：約 {trx_amount:.2f}\n\n"
        f"🔻 最小兌換金額：{MIN_USDT} USDT\n\n"
        "📥 TRC20 USDT 收款地址（點擊即可複製）\n"
        f"<code>{TRC20_ADDRESS}</code>\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "轉帳完成後請耐心等待處理"
    )

    await update.message.reply_text(text, parse_mode="HTML")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("usdt", usdt))

    print("Bot is running with dynamic rate...")
    app.run_polling()


if __name__ == "__main__":
    main()
