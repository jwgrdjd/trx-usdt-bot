import os
import time
import requests
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =====================
# 🔧 基本設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")

if not BOT_TOKEN or not TRONGRID_API_KEY:
    raise RuntimeError("❌ BOT_TOKEN 或 TRONGRID_API_KEY 未設定")

ADMIN_ID = 7757022123  # 管理員 Telegram ID
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0
DISPLAY_USDT = 10.0

POLL_INTERVAL = 30  # 秒

# =====================
# 🔁 鏈上狀態
# =====================

SEEN_TX = set()
START_TIME = time.time()

TRONGRID_URL = (
    f"https://api.trongrid.io/v1/accounts/"
    f"{HOT_WALLET_ADDRESS}/transactions/trc20"
)

HEADERS = {
    "TRON-PRO-API-KEY": TRONGRID_API_KEY
}

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自动兑换机器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查看兑换报价\n\n"
        f"🔻 最低兑换金额：{MIN_USDT} USDT\n"
        "🌐 网络：TRC20\n"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

    text = (
        "💱 <b>USDT → TRX 实时汇率</b>\n\n"
        "USDT：10\n"
        f"可得：約 {trx_amount} TRX\n\n"
        "📥 <b>TRC20 USDT 换 TRX 地址（点击可复制）</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "⚠️ 请务必使用 TRC20 网络转账\n"
        "转账完成后请耐心等待处理，预计 3 分钟内完成闪兑"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )

# =====================
# 🔍 鏈上監聽（只抓轉入）
# =====================

def poll_trc20(app):
    try:
        r = requests.get(
            TRONGRID_URL,
            headers=HEADERS,
            params={"limit": 20},
            timeout=10,
        )
        r.raise_for_status()

        txs = r.json().get("data", [])

        for tx in txs:
            txid = tx["transaction_id"]

            if txid in SEEN_TX:
                continue

            # ❗只處理「轉入」熱錢包
            if tx.get("to") != HOT_WALLET_ADDRESS:
                SEEN_TX.add(txid)
                continue

            # 忽略啟動前的舊交易
            if tx["block_timestamp"] / 1000 < START_TIME:
                SEEN_TX.add(txid)
                continue

            usdt_amount = float(tx["value"]) / 1_000_000
            if usdt_amount < MIN_USDT:
                SEEN_TX.add(txid)
                continue

            from_addr = tx["from"]
            SEEN_TX.add(txid)

            final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(usdt_amount * final_rate, 2)

            msg = (
                "✅ <b>偵測到 USDT 入帳</b>\n\n"
                f"💰 金額：{usdt_amount} USDT\n"
                f"👤 來源地址：\n<code>{from_addr}</code>\n\n"
                f"📤 應付：{trx_amount} TRX\n"
                f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            app.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML",
            )

    except Exception as e:
        print("監聽錯誤：", e)

# =====================
# 🚀 主程式（穩定版）
# =====================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    print("🤖 Bot 已啟動（穩定監聽版）")
    print("✅ 熱錢包地址：", HOT_WALLET_ADDRESS)

    # 不用 JobQueue、不碰 asyncio
    def loop():
        while True:
            poll_trc20(app)
            time.sleep(POLL_INTERVAL)

    import threading
    threading.Thread(target=loop, daemon=True).start()

    app.run_polling()

if __name__ == "__main__":
    main()
