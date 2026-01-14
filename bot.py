import os
import time
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =====================
# 🔐 基本設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")

# 管理員 Telegram ID（只通知你）
ADMIN_ID = 7757022123

# 收款地址（TRC20 USDT）
RECEIVE_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

# 匯率設定
FIXED_RATE_TRX = 3.2     # 1 USDT = 3.2 TRX
FEE_RATE = 0.05          # 5%
MIN_USDT = 5.0
DISPLAY_USDT = 10.0

# 輪詢設定
POLL_INTERVAL = 30  # 秒
last_checked_timestamp = 0


# =====================
# 💱 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查看 10 USDT 可兌換多少 TRX\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n"
        "🌐 網路：TRC20"
    )


async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(DISPLAY_USDT * final_rate, 2)

    text = (
        "💱 <b>USDT → TRX 兌換報價</b><br><br>"
        f"USDT：{DISPLAY_USDT}<br>"
        f"可兌換 TRX：約 <b>{trx_amount}</b><br><br>"
        f"🔻 最低兌換金額：{MIN_USDT} USDT<br><br>"
        "📥 <b>TRC20 USDT 收款地址</b><br>"
        "<i>（點擊地址即可複製）</i><br><br>"
        f"{RECEIVE_ADDRESS}<br><br>"
        "⚠️ 請務必使用 TRC20 網路轉帳<br>"
        "轉帳完成後請耐心等待處理"
    )

    await update.message.reply_text(text, parse_mode="HTML")


# =====================
# 🔎 鏈上監聽（只抓「轉入」）
# =====================

async def check_trc20_transfers(app):
    global last_checked_timestamp

    headers = {
        "TRON-PRO-API-KEY": TRONGRID_API_KEY
    }

    url = (
        "https://api.trongrid.io/v1/accounts/"
        f"{RECEIVE_ADDRESS}/transactions/trc20"
    )

    params = {
        "only_confirmed": True,
        "limit": 20,
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])

        for tx in data:
            ts = int(tx["block_timestamp"])
            if ts <= last_checked_timestamp:
                continue

            to_addr = tx["to"].lower()
            from_addr = tx["from"].lower()

            # ❗ 核心修正：只顯示「轉入」
            if to_addr != RECEIVE_ADDRESS.lower():
                continue

            amount = int(tx["value"]) / 1_000_000
            if amount < MIN_USDT:
                continue

            final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(amount * final_rate, 2)

            msg = (
                "✅ <b>偵測到 USDT 入帳</b><br><br>"
                f"💰 金額：{amount} USDT<br>"
                f"👤 來源地址：<br>{from_addr}<br><br>"
                f"🚀 預計發送：<b>{trx_amount} TRX</b><br><br>"
                f"⏱ 時間：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts/1000))}"
            )

            await app.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML"
            )

            last_checked_timestamp = max(last_checked_timestamp, ts)

    except Exception as e:
        print("❌ 監聽錯誤：", e)


# =====================
# 🚀 主程式
# =====================

def main():
    if not BOT_TOKEN or not TRONGRID_API_KEY:
        raise RuntimeError("❌ BOT_TOKEN 或 TRONGRID_API_KEY 未設定")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    async def loop():
        while True:
            await check_trc20_transfers(app)
            await time.sleep(POLL_INTERVAL)

    app.create_task(loop())

    print("🤖 Bot 已啟動（只監聽 TRC20 USDT 轉入）")
    app.run_polling()


if __name__ == "__main__":
    main()
