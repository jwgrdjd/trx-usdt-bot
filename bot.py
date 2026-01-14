import os
import time
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =====================
# 🔐 基本設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")

ADMIN_ID = 7757022123
RECEIVE_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0
DISPLAY_USDT = 10.0

POLL_INTERVAL = 30
last_checked_timestamp = 0


# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查看兌換報價\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n"
        "🌐 網路：TRC20"
    )


async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(DISPLAY_USDT * rate, 2)

    text = (
        "<b>💱 USDT → TRX 兌換報價</b><br><br>"
        f"USDT：{DISPLAY_USDT}<br>"
        f"可兌換 TRX：約 <b>{trx_amount}</b><br><br>"
        f"最低兌換金額：{MIN_USDT} USDT<br><br>"
        "<b>📥 TRC20 USDT 收款地址</b><br>"
        "<code>"
        f"{RECEIVE_ADDRESS}"
        "</code><br><br>"
        "⚠️ 請務必使用 TRC20 網路轉帳"
    )

    await update.message.reply_text(text, parse_mode="HTML")






# =====================
# 🔎 鏈上監聽（只抓轉入）
# =====================

async def check_trc20_transfers(app):
    global last_checked_timestamp

    headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}
    url = f"https://api.trongrid.io/v1/accounts/{RECEIVE_ADDRESS}/transactions/trc20"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])

        for tx in data:
            ts = int(tx["block_timestamp"])
            if ts <= last_checked_timestamp:
                continue

            if tx["to"].lower() != RECEIVE_ADDRESS.lower():
                continue  # ❌ 忽略轉出

            amount = int(tx["value"]) / 1_000_000
            if amount < MIN_USDT:
                continue

            final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(amount * final_rate, 2)

            msg = (
                "✅ <b>偵測到 USDT 入帳</b><br><br>"
                f"💰 金額：{amount} USDT<br>"
                f"👤 來源地址：<br>{tx['from']}<br><br>"
                f"🚀 預計發送：<b>{trx_amount} TRX</b><br>"
                f"⏱ 時間：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts/1000))}"
            )

            await app.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML"
            )

            last_checked_timestamp = ts

    except Exception as e:
        print("監聽錯誤：", e)


# =====================
# 🚀 啟動（正確方式）
# =====================

async def post_init(app):
    async def loop():
        while True:
            await check_trc20_transfers(app)
            await asyncio.sleep(POLL_INTERVAL)

    asyncio.create_task(loop())


def main():
    if not BOT_TOKEN or not TRONGRID_API_KEY:
        raise RuntimeError("❌ BOT_TOKEN 或 TRONGRID_API_KEY 未設定")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)  # ✅ 關鍵修正
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    print("🤖 Bot 已啟動（穩定版，僅監聽轉入）")
    app.run_polling()


if __name__ == "__main__":
    main()




