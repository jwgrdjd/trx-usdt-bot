import os
import time
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ========= 基本設定 =========
BOT_TOKEN = os.environ.get("BOT_TOKEN")

USDT_AMOUNT = 10          # 顯示金額
MIN_USDT = 5.0             # 最低兌換限額
FEE_RATE = 0.07            # 7% 利差
FALLBACK_TRX_PRICE = 0.30 # 備用匯率（USDT）

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

# ========= 匯率快取設定 =========
RATE_CACHE_SECONDS = 300   # 5 分鐘
_last_price = None
_last_update = 0


# ========= 取得 TRX 價格（含快取） =========
def get_trx_price():
    global _last_price, _last_update

    now = time.time()

    # 若快取還有效，直接用
    if _last_price is not None and (now - _last_update) < RATE_CACHE_SECONDS:
        return _last_price

    # 嘗試抓即時匯率
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "tron", "vs_currencies": "usd"},
            timeout=8,
        )
        r.raise_for_status()
        price = float(r.json()["tron"]["usd"])

        # 更新快取
        _last_price = price
        _last_update = now
        return price

    except Exception:
        # 即時失敗 → 用最後一次成功的價格
        if _last_price is not None:
            return _last_price
        # 再不行 → 用備用
        return FALLBACK_TRX_PRICE


# ========= /start =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt\n\n"
        f"🔻 最低兌換限額：{MIN_USDT} USDT\n"
        "💰 匯率：每 5 分鐘更新（含 5% 利差）\n"
        "🌐 網路：TRC20"
    )


# ========= /usdt =========
async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_price = get_trx_price()
    price_with_fee = trx_price * (1 + FEE_RATE)
    trx_amount = USDT_AMOUNT / price_with_fee

    text = (
        "💱 USDT → TRX 兌換報價\n\n"
        f"USDT：{USDT_AMOUNT}\n"
        f"可兌換 TRX：約 {trx_amount:.2f}\n\n"
        f"🔻 最低兌換限額：{MIN_USDT} USDT\n\n"
        "📥 TRC20 USDT 收款地址（可直接複製）\n"
        f"`{TRC20_ADDRESS}`\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "系統將以實際入帳時匯率為準"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ========= 主程式 =========
def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN 尚未設定")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    print("🤖 Bot 已啟動（5 分鐘匯率快取）")
    app.run_polling()


if __name__ == "__main__":
    main()
