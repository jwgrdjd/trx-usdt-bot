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

ADMIN_ID = 7757022123

HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

MIN_USDT = 5.0
MAX_USDT = 100.0

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05

POLL_INTERVAL = 30

# 夜间自动（00:00 ~ 10:00）
NIGHT_START = 0
NIGHT_END = 10

TRX_DECIMALS = 1_000_000
FEE_LIMIT_SUN = 10_000_000  # 10 TRX

# =====================
# 🔒 启动检查
# =====================

if not BOT_TOKEN or not TRONGRID_API_KEY or not TRX_PRIVATE_KEY:
    raise RuntimeError("❌ 缺少环境变量")

if len(TRX_PRIVATE_KEY) != 64:
    raise RuntimeError("❌ 私钥必须是 64 位 HEX")

tron = Tron()
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))
HOT_WALLET_FROM_PK = private_key.public_key.to_base58check_address()

print("✅ 热钱包地址：", HOT_WALLET_FROM_PK)
print("👂 监听地址：", HOT_WALLET_ADDRESS)

# =====================
# 🧠 状态
# =====================

seen_tx = set()
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
        "网络：TRC20"
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
# 🔍 链上监听 + 自动出金
# =====================

async def poll_trc20(context: ContextTypes.DEFAULT_TYPE):
    print("🔍 正在检查链上 USDT 入账…")

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

            if tx.get("to") != HOT_WALLET_ADDRESS:
                continue

            if tx["block_timestamp"] / 1000 < START_TIME:
                continue

            usdt_amount = float(tx["value"]) / 1_000_000
            from_addr = tx["from"]

            trx_amount = round(usdt_amount * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

            hour = datetime.now().hour
            is_night = NIGHT_START <= hour < NIGHT_END

            # 通知入账（一定发）
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 <b>USDT 入账</b>\n\n"
                    f"金额：{usdt_amount} USDT\n"
                    f"来源：<code>{from_addr}</code>\n"
                    f"应付：{trx_amount} TRX"
                ),
                parse_mode="HTML"
            )

            # 自动出金条件
            if not is_night:
                continue
            if usdt_amount < MIN_USDT or usdt_amount > MAX_USDT:
                continue

            try:
                tron.trx.transfer(
                    HOT_WALLET_ADDRESS,
                    from_addr,
                    int(trx_amount * TRX_DECIMALS)
                ).fee_limit(FEE_LIMIT_SUN).build().sign(private_key).broadcast()

                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🔥 已自动出金 {trx_amount} TRX\n➡️ {from_addr}"
                )

            except Exception as e:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"❌ 出金失败：{e}"
                )

    except Exception as e:
        print("❌ 监听错误：", e)

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

    print("🤖 Bot 已启动（自动出金版）")
    app.run_polling()

if __name__ == "__main__":
    main()
