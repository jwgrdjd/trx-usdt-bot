import os
import time
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

BOT_TOKEN = os.environ.get("BOT_TOKEN")

ADMIN_CHAT_ID = 7757022123  # ← 換成你的 Telegram 數字 ID

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"  # Trust Wallet
USDT_CONTRACT = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"  # TRC20 USDT

MIN_USDT = 5.0
FEE_RATE = 0.05            # 5% 利差
FALLBACK_TRX_PRICE = 0.306
CHECK_INTERVAL = 30        # 秒

# ======================
# 匯率快取（5 分鐘）
# ======================

RATE_CACHE_SECONDS = 300
_last_price = None
_last_update = 0

def get_trx_price():
    global _last_price, _last_update
    now = time.time()

    if _last_price and (now - _last_update) < RATE_CACHE_SECONDS:
        return _last_price

    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "tron", "vs_currencies": "usd"},
            timeout=8,
        )
        r.raise_for_status()
        price = float(r.json()["tron"]["usd"])
        _last_price = price
        _last_update = now
        return price
    except Exception:
        return _last_price or FALLBACK_TRX_PRICE

# ======================
# TronScan
# ======================

TRONSCAN_API = "https://apilist.tronscan.org/api/token_trc20/transfers"
processed_txids = set()

def fetch_usdt_transfers():
    params = {
        "limit": 20,
        "start": 0,
        "sort": "-timestamp",
        "toAddress": TRC20_ADDRESS,
        "contract_address": USDT_CONTRACT,
    }
    r = requests.get(TRONSCAN_API, params=params, timeout=10)
    return r.json().get("data", [])

# ======================
# 背景監聽（只通知管理員）
# ======================

async def watch_usdt(context: ContextTypes.DEFAULT_TYPE):
    try:
        transfers = fetch_usdt_transfers()
    except Exception:
        return

    trx_price = get_trx_price()
    price_with_fee = trx_price * (1 + FEE_RATE)

    for tx in transfers:
        txid = tx.get("transaction_id")
        from_addr = tx.get("from_address")
        amount = float(tx.get("quant")) / 1_000_000

        if txid in processed_txids:
            continue

        processed_txids.add(txid)

        if amount < MIN_USDT:
            continue

        trx_amount = round(amount / price_with_fee, 2)

        text = (
            "🟢【USDT 入帳通知】\n\n"
            f"金額：{amount} USDT\n"
            f"應付 TRX：約 {trx_amount}\n\n"
            f"來自地址：{from_addr}\n"
            f"TXID：{txid}\n\n"
            "請使用 Trust Wallet 發送對應 TRX"
        )

        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text
        )

# ======================
# /start
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "/usdt 查看收款資訊\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n"
        "🌐 網路：TRC20"
    )

# ======================
# /usdt（用戶只看到地址）
# ======================

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💱 USDT → TRX 兌換\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n\n"
        "📥 TRC20 USDT 收款地址（可直接複製）\n"
        f"`{TRC20_ADDRESS}`\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "轉帳完成後請耐心等待處理"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )

# ======================
# 主程式
# ======================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    app.job_queue.run_repeating(
        watch_usdt,
        interval=CHECK_INTERVAL,
        first=10
    )

    print("🤖 Bot running (C-Safe / admin only)")
    app.run_polling()

if __name__ == "__main__":
    main()
