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

ADMIN_ID = 7757022123  # 你的 Telegram ID
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

MIN_USDT = 5.0
FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05

POLL_INTERVAL = 30  # 秒

# =====================
# 🔒 檢查
# =====================

if not BOT_TOKEN or not TRONGRID_API_KEY:
    raise RuntimeError("❌ BOT_TOKEN 或 TRONGRID_API_KEY 未設定")

print("✅ 監聽錢包地址：", HOT_WALLET_ADDRESS)

# =====================
# 🧠 狀態
# =====================

seen_tx = set()
START_TIME = time.time()  # 只抓「現在之後」的交易

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自动兑换机器人\n\n"
        "/usdt 查看兑换报价\n\n"
        f"🔻 最低兑换金额：{MIN_USDT} USDT\n"
        "🌐 网络：TRC20"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

    text = (
        "💱 <b>USDT → TRX 兑换报价</b>\n\n"
        "USDT：10\n"
        f"可得：約 {trx_amount} TRX\n\n"
        "📥 <b>TRC20 USDT 收款地址</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "⚠️ 请务必使用 TRC20 网络转账\n"
        "到账后系统将自动处理"
    )

    await update.message.reply_text(text, parse_mode="HTML")

# =====================
# 🔍 链上监听（重点）
# =====================

async def poll_trc20(context: ContextTypes.DEFAULT_TYPE):
    print("🔍 正在检查链上 USDT 入账…")

    url = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
    headers = {
        "TRON-PRO-API-KEY": TRONGRID_API_KEY
    }

    try:
        r = requests.get(url, headers=headers, params={"limit": 20}, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])

        for tx in data:
            txid = tx["transaction_id"]

            if txid in seen_tx:
                continue

            # ❗只处理「转入」
            if tx.get("to") != HOT_WALLET_ADDRESS:
                seen_tx.add(txid)
                continue

            # ❗忽略启动前的旧交易
            if tx["block_timestamp"] / 1000 < START_TIME:
                seen_tx.add(txid)
                continue

            usdt_amount = float(tx["value"]) / 1_000_000
            from_addr = tx["from"]

            seen_tx.add(txid)

            if usdt_amount < MIN_USDT:
                print(f"⏭ 金额过小：{usdt_amount}")
                continue

            trx_amount = round(usdt_amount * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

            msg = (
                "✅ <b>检测到 USDT 入账</b>\n\n"
                f"💰 金额：{usdt_amount} USDT\n"
                f"👤 来源地址：\n<code>{from_addr}</code>\n\n"
                f"📤 应出金：{trx_amount} TRX\n"
                f"🕒 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML"
            )

            print("✅ 已通知管理员：", txid)

    except Exception as e:
        print("❌ 链上监听错误：", e)

# =====================
# 🚀 启动
# =====================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    # ✅ 正确使用 JobQueue（关键）
    app.job_queue.run_repeating(
        poll_trc20,
        interval=POLL_INTERVAL,
        first=5
    )

    print("🤖 Bot 已启动（监听中）")
    app.run_polling()

if __name__ == "__main__":
    main()
