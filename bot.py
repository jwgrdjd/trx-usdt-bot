import os
import time
import threading
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =====================
# 🔧 基本設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")

# 你的 Telegram ID（只通知你）
ADMIN_IDS = [7757022123]

# 收款地址
TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

# USDT TRC20 合約（官方）
USDT_CONTRACT = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"

# 兌換設定
FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0

# 監聽設定
CHECK_INTERVAL = 30  # 秒

# 已處理交易（記憶體）
PROCESSED_TX = set()


# =====================
# 🔍 查 TRC20 USDT 轉帳
# =====================

def fetch_trc20_transfers():
    url = f"https://api.trongrid.io/v1/accounts/{TRC20_ADDRESS}/transactions/trc20"
    headers = {
        "TRON-PRO-API-KEY": TRONGRID_API_KEY
    }
    params = {
        "only_confirmed": "true",
        "limit": 20
    }

    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("data", [])


# =====================
# 🔁 背景監聽（穩定版）
# =====================

def monitor_loop(app):
    print("🔍 TRC20 USDT 監聽啟動（半自動）")

    while True:
        try:
            transfers = fetch_trc20_transfers()

            for tx in transfers:
                txid = tx["transaction_id"]

                if txid in PROCESSED_TX:
                    continue

                if tx["token_info"]["address"] != USDT_CONTRACT:
                    continue

                amount = int(tx["value"]) / (10 ** int(tx["token_info"]["decimals"]))
                from_addr = tx["from"]

                if amount < MIN_USDT:
                    PROCESSED_TX.add(txid)
                    continue

                final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
                trx_amount = round(amount * final_rate, 2)

                message = (
                    "💰 <b>新 USDT 入帳通知</b>\n\n"
                    f"📥 金額：<b>{amount} USDT</b>\n"
                    f"👤 來源地址：\n<code>{from_addr}</code>\n\n"
                    f"💸 應發送：<b>{trx_amount} TRX</b>\n\n"
                    "⚠️ 請使用 Trust Wallet 人工轉帳"
                )

                for admin_id in ADMIN_IDS:
                    app.bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode="HTML"
                    )

                PROCESSED_TX.add(txid)

        except Exception as e:
            print("監聽錯誤：", e)

        time.sleep(CHECK_INTERVAL)


# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 兌換機器人\n\n"
        "🔒 已啟用「半自動鏈上監聽」\n"
        "轉帳完成後無需回傳 TXID\n"
        "系統將自動通知管理員"
    )


# =====================
# 🚀 啟動
# =====================

def main():
    if not BOT_TOKEN or not TRONGRID_API_KEY:
        raise RuntimeError("❌ BOT_TOKEN 或 TRONGRID_API_KEY 未設定")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # 啟動背景監聽 Thread
    t = threading.Thread(target=monitor_loop, args=(app,), daemon=True)
    t.start()

    print("✅ Bot 已啟動（半自動監聽穩定版）")
    app.run_polling()

if __name__ == "__main__":
    main()
