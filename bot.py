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

from tronpy import Tron
from tronpy.keys import PrivateKey

# =====================
# 🔧 基本設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")
TRX_PRIVATE_KEY = os.environ.get("TRX_PRIVATE_KEY")

ADMIN_ID = 7757022123  # 你的 Telegram ID
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05

MIN_USDT = 5.0
MAX_USDT = 100.0

POLL_INTERVAL = 30
FEE_LIMIT_SUN = 10_000_000  # 10 TRX

# =====================
# 🔒 檢查
# =====================

if not BOT_TOKEN or not TRONGRID_API_KEY or not TRX_PRIVATE_KEY:
    raise RuntimeError("❌ 環境變數未設定")

if len(TRX_PRIVATE_KEY) != 64:
    raise RuntimeError("❌ 私鑰必須是 64 位 HEX")

# =====================
# 🔗 Tron（只負責出金）
# =====================

tron = Tron()
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))
HOT_WALLET_ADDRESS = private_key.public_key.to_base58check_address()

print("✅ 熱錢包地址：", HOT_WALLET_ADDRESS)

# =====================
# 🧠 狀態
# =====================

seen_tx = set()
START_TIME = time.time()

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "/usdt 查看兌換資訊\n\n"
        f"最低：{MIN_USDT} USDT\n"
        f"最高自動：{MAX_USDT} USDT\n"
        "模式：全時段 ≤100 USDT 自動出金"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

    text = (
        "💱 <b>USDT → TRX 兌換報價</b>\n\n"
        "USDT：10\n"
        f"可得：約 {trx_amount} TRX\n\n"
        "📥 <b>TRC20 USDT 收款地址</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "≤100 USDT 將自動完成出金"
    )

    await update.message.reply_text(text, parse_mode="HTML")

# =====================
# 🔁 鏈上監聽 + 自動出金
# =====================

def poll_trc20(context: ContextTypes.DEFAULT_TYPE):
    url = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
    headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

    try:
        r = requests.get(url, headers=headers, params={"limit": 20}, timeout=10)
        r.raise_for_status()

        for tx in r.json().get("data", []):
            txid = tx["transaction_id"]

            if txid in seen_tx:
                continue

            seen_tx.add(txid)

            # 只处理转入
            if tx.get("to") != HOT_WALLET_ADDRESS:
                continue

            # 忽略启动前交易
            if tx["block_timestamp"] / 1000 < START_TIME:
                continue

            usdt_amount = float(tx["value"]) / 1_000_000
            from_addr = tx["from"]

            # 通知管理員（一定）
            context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "📥 USDT 入帳偵測\n\n"
                    f"金額：{usdt_amount} USDT\n"
                    f"來源：{from_addr}\n"
                )
            )

            # 金額不符合 → 不出金
            if usdt_amount < MIN_USDT or usdt_amount > MAX_USDT:
                continue

            trx_amount = round(usdt_amount * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

            try:
                tron.trx.transfer(
                    HOT_WALLET_ADDRESS,
                    from_addr,
                    int(trx_amount * 1_000_000)
                ).fee_limit(FEE_LIMIT_SUN).build().sign(private_key).broadcast()

                status = f"✅ 已自動出金 {trx_amount} TRX"

            except Exception as e:
                status = f"❌ 出金失敗：{e}"

            context.bot.send_message(
                chat_id=ADMIN_ID,
                text=status
            )

    except Exception as e:
        print("監聽錯誤：", e)

# =====================
# 🚀 啟動
# =====================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    app.job_queue.run_repeating(
        poll_trc20,
        interval=POLL_INTERVAL,
        first=5
    )

    print("🤖 Bot 已啟動（最終穩定版）")
    app.run_polling()

if __name__ == "__main__":
    main()
