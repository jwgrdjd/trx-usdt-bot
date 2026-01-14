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

POLL_INTERVAL = 30          # 秒
FEE_LIMIT_SUN = 10_000_000  # 10 TRX

# 夜間全自動（00:00～10:00）
NIGHT_START = 0
NIGHT_END = 10

# =====================
# 🔒 檢查
# =====================

if not BOT_TOKEN or not TRONGRID_API_KEY or not TRX_PRIVATE_KEY:
    raise RuntimeError("❌ 環境變數未設定")

if len(TRX_PRIVATE_KEY) != 64:
    raise RuntimeError("❌ TRX_PRIVATE_KEY 必須是 64 位 HEX")

# =====================
# 🔗 Tron 出金初始化
# =====================

tron = Tron()
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))
HOT_WALLET_REAL = private_key.public_key.to_base58check_address()

print("✅ 熱錢包地址：", HOT_WALLET_REAL)

# =====================
# 🧠 狀態
# =====================

SEEN_TX = set()
START_TIME = time.time()

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自动兑换机器人\n\n"
        "/usdt 查看兑换报价\n\n"
        f"最低：{MIN_USDT} USDT\n"
        f"最高：{MAX_USDT} USDT\n"
        "模式：自动出金"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

    text = (
        "💱 <b>USDT → TRX 报价</b>\n\n"
        "USDT：10\n"
        f"可得：約 {trx_amount} TRX\n\n"
        "📥 <b>TRC20 USDT 收款地址</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "⚠️ 请务必使用 TRC20 网络转账"
    )

    await update.message.reply_text(text, parse_mode="HTML")

# =====================
# 🔁 鏈上監聽 + 出金
# =====================

def is_night():
    h = datetime.now().hour
    return NIGHT_START <= h < NIGHT_END

def poll_trc20(context: ContextTypes.DEFAULT_TYPE):
    app = context.application

    url = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
    headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

    try:
        r = requests.get(url, headers=headers, params={"limit": 20}, timeout=10)
        r.raise_for_status()

        for tx in r.json().get("data", []):
            txid = tx["transaction_id"]

            if txid in SEEN_TX:
                continue

            if tx.get("to") != HOT_WALLET_ADDRESS:
                continue

            if tx["block_timestamp"] / 1000 < START_TIME:
                continue

            usdt_amount = float(tx["value"]) / 1_000_000
            if not (MIN_USDT <= usdt_amount <= MAX_USDT):
                continue

            from_addr = tx["from"]

            # ✅ 到這裡才標記
            SEEN_TX.add(txid)

            trx_amount = round(usdt_amount * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

            auto = is_night() or usdt_amount <= MAX_USDT

            status = "⏸ 未自动出金（人工）"

            if auto:
                try:
                    tron.trx.transfer(
                        HOT_WALLET_REAL,
                        from_addr,
                        int(trx_amount * 1_000_000)
                    ).fee_limit(FEE_LIMIT_SUN).build().sign(private_key).broadcast()

                    status = "✅ 已自动出金"
                except Exception as e:
                    status = f"❌ 出金失败：{e}"

            app.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 USDT 入账\n\n"
                    f"金额：{usdt_amount} USDT\n"
                    f"来源：{from_addr}\n"
                    f"应付：{trx_amount} TRX\n"
                    f"状态：{status}"
                )
            )

    except Exception as e:
        print("监控错误：", e)

# =====================
# 🚀 启动
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

    print("🤖 Bot 已启动（最终稳定版）")
    app.run_polling()

if __name__ == "__main__":
    main()
