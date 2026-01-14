import os
import time
import requests
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =====================
# 🔧 基本設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")

ADMIN_ID = 7757022123  # 你的管理員 ID（已幫你填好）

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2     # 固定匯率
FEE_RATE = 0.05          # 手續費 5%
MIN_USDT = 5.0
DISPLAY_USDT = 10.0

POLL_INTERVAL = 30       # 30 秒輪詢一次

# =====================
# 🔁 鏈上狀態
# =====================

last_seen_tx = set()

TRONGRID_URL = (
    f"https://api.trongrid.io/v1/accounts/{TRC20_ADDRESS}/transactions/trc20"
)

HEADERS = {
    "TRON-PRO-API-KEY": TRONGRID_API_KEY
}

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查看兌換報價\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n"
        "🌐 網路：TRC20\n"
        "💱 匯率：固定"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(DISPLAY_USDT * final_rate, 2)

    text = (
        "💱 <b>USDT → TRX 兌換報價</b>\n\n"
        f"USDT：{DISPLAY_USDT}\n"
        f"可兌換 TRX：約 {trx_amount}\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n\n"
        "📥 <b>TRC20 USDT 收款地址</b>\n"
        "<code>"
        f"{TRC20_ADDRESS}"
        "</code>\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "轉帳完成後請耐心等待處理"
    )

    await update.message.reply_text(text, parse_mode="HTML")

# =====================
# 🔍 鏈上監聽（只通知管理員）
# =====================

async def poll_trc20(context: ContextTypes.DEFAULT_TYPE):
    global last_seen_tx

    try:
        r = requests.get(
            TRONGRID_URL,
            headers=HEADERS,
            params={"limit": 10},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("data", [])

        for tx in data:
            txid = tx["transaction_id"]
            if txid in last_seen_tx:
                continue

            value = float(tx["value"]) / 1_000_000
            from_addr = tx["from"]
            to_addr = tx["to"]

            # ✅ 只處理「轉入到自己地址」
            if to_addr.lower() != TRC20_ADDRESS.lower():
                continue

            if value < MIN_USDT:
                continue

            last_seen_tx.add(txid)

            final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(value * final_rate, 2)

            msg = (
                "✅ <b>偵測到 USDT 入帳</b>\n\n"
                f"💰 金額：{value} USDT\n"
                f"👤 來源地址：\n<code>{from_addr}</code>\n\n"
                f"📤 預計發送：{trx_amount} TRX\n\n"
                f"🕒 時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML",
            )

    except Exception as e:
        print("監聽錯誤：", e)


# =====================
# 🚀 啟動
# =====================

def main():
    if not BOT_TOKEN or not TRONGRID_API_KEY:
        raise RuntimeError("❌ BOT_TOKEN 或 TRONGRID_API_KEY 未設定")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    # 用 asyncio loop 取代 JobQueue（穩）
    async def loop_task():
        while True:
            await poll_trc20(app.bot_data["context"])
            await asyncio.sleep(POLL_INTERVAL)

    async def on_start(app):
        app.bot_data["context"] = app
        app.create_task(loop_task())

    app.post_init = on_start

    print("🤖 Bot 已啟動（管理員通知模式）")
    app.run_polling()

if __name__ == "__main__":
    import asyncio
    main()

