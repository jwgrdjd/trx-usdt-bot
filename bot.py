import os
import time
import requests
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

# 管理員（你）
ADMIN_IDS = [7757022123]

# 收款地址
TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

# USDT TRC20 合約（TRON 官方）
USDT_CONTRACT = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"

# 匯率設定
FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0

# 監聽設定
CHECK_INTERVAL = 30  # 秒

# 已處理交易（記憶體版，重啟會清空）
PROCESSED_TX = set()


# =====================
# 🔐 權限
# =====================

def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS


# =====================
# 🔍 查 TRC20 USDT 交易
# =====================

def fetch_trc20_transfers():
    url = "https://api.trongrid.io/v1/accounts/{}/transactions/trc20".format(TRC20_ADDRESS)
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
# 🔁 監聽任務
# =====================

async def monitor_trc20(context: ContextTypes.DEFAULT_TYPE):
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

            # 計算應付 TRX
            final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(amount * final_rate, 2)

            message = (
                "✅ <b>已收到 USDT</b>\n\n"
                f"金額：{amount}\n"
                f"來源地址：{from_addr}\n"
                f"應發送：<b>{trx_amount} TRX</b>"
            )

            # 回給管理員
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML"
                )

            PROCESSED_TX.add(txid)

    except Exception as e:
        print("監聽錯誤：", e)


# =====================
# 🤖 基本指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "系統已啟用鏈上自動監聽\n"
        "轉帳完成後無需回傳 TXID"
    )


# =====================
# 🚀 啟動
# =====================

def main():
    if not BOT_TOKEN or not TRONGRID_API_KEY:
        raise RuntimeError("❌ BOT_TOKEN 或 TRONGRID_API_KEY 未設定")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # 每 30 秒監聽一次
    app.job_queue.run_repeating(
        monitor_trc20,
        interval=CHECK_INTERVAL,
        first=10
    )

    print("✅ Bot 已啟動（TRC20 USDT 自動監聽中）")
    app.run_polling()


if __name__ == "__main__":
    main()
