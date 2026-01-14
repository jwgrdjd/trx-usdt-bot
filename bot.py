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

ADMIN_ID = 7757022123  # 你的 Telegram ID（數字）

HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05

MIN_USDT = 5.0
MAX_USDT = 100.0   # 白天 / 夜間共用上限（你之後可再拆）

POLL_INTERVAL = 30         # 秒
FEE_LIMIT_SUN = 10_000_000 # 10 TRX

# =====================
# 🔒 環境檢查
# =====================

if not BOT_TOKEN or not TRONGRID_API_KEY or not TRX_PRIVATE_KEY:
    raise RuntimeError("❌ 缺少 BOT_TOKEN / TRONGRID_API_KEY / TRX_PRIVATE_KEY")

if len(TRX_PRIVATE_KEY) != 64:
    raise RuntimeError("❌ TRX 私鑰必須是 64 位 HEX")

# =====================
# 🔗 Tron（只負責出金）
# =====================

tron = Tron()
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))
HOT_WALLET_DERIVED = private_key.public_key.to_base58check_address()

print("✅ 熱錢包地址：", HOT_WALLET_DERIVED)

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
        "/usdt 查看报价\n\n"
        f"最低：{MIN_USDT} USDT\n"
        f"最高：{MAX_USDT} USDT\n"
        "网络：TRC20\n"
        "模式：自动出金"
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
        "预计 3 分钟内完成自动出金"
    )

    await update.message.reply_text(text, parse_mode="HTML")

# =====================
# 🔁 鏈上監聽 + 自動出金（JobQueue）
# =====================

def poll_trc20(context: ContextTypes.DEFAULT_TYPE):
    url = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
    headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

    try:
        r = requests.get(url, headers=headers, params={"limit": 20}, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])

        for tx in data:
            txid = tx["transaction_id"]

            if txid in SEEN_TX:
                continue

            SEEN_TX.add(txid)

            # 只看转入
            if tx.get("to") != HOT_WALLET_ADDRESS:
                continue

            # 忽略启动前的交易
            if tx["block_timestamp"] / 1000 < START_TIME:
                continue

            usdt_amount = float(tx["value"]) / 1_000_000

            if usdt_amount < MIN_USDT or usdt_amount > MAX_USDT:
                continue

            from_addr = tx["from"]

            trx_amount = round(usdt_amount * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

            # ===== 先通知「已收到」=====
            try:
                context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        "📥 <b>USDT 入账侦测</b>\n\n"
                        f"金额：{usdt_amount} USDT\n"
                        f"来源：<code>{from_addr}</code>\n"
                        f"应付：{trx_amount} TRX"
                    ),
                    parse_mode="HTML"
                )
                print("✅ 已发送入账通知")

            except Exception as e:
                print("❌ 入账通知失败：", e)

            # ===== 自动出金 =====
            try:
                tron.trx.transfer(
                    HOT_WALLET_DERIVED,
                    from_addr,
                    int(trx_amount * 1_000_000)
                ).fee_limit(FEE_LIMIT_SUN).build().sign(private_key).broadcast()

                status = f"✅ 已自动出金 {trx_amount} TRX"

            except Exception as e:
                status = f"❌ 出金失败：{e}"

            # ===== 出金结果通知 =====
            try:
                context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=status
                )
                print("📤 出金通知已发送")

            except Exception as e:
                print("❌ 出金通知失败：", e)

    except Exception as e:
        print("🚨 监控错误：", e)

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

    print("🤖 Bot 已启动（稳定最终版）")
    app.run_polling()

if __name__ == "__main__":
    main()
