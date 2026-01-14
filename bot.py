import os
import asyncio
import time
import requests
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from tronpy import Tron
from tronpy.keys import PrivateKey

# =====================
# 🔧 基本設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")
TRX_PRIVATE_KEY = os.environ.get("TRX_PRIVATE_KEY")

ADMIN_ID = 7757022123  # 管理员 TG ID
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0

POLL_INTERVAL = 30  # 秒
FEE_LIMIT_SUN = 10_000_000  # 10 TRX 手续费上限

# =====================
# 🔒 安全檢查
# =====================

if not BOT_TOKEN or not TRONGRID_API_KEY or not TRX_PRIVATE_KEY:
    raise RuntimeError("❌ 缺少環境變數")

if len(TRX_PRIVATE_KEY) != 64:
    raise RuntimeError("❌ 私鑰必須是 64 位 HEX")

# =====================
# 🔗 Tron 初始化（只负责出金）
# =====================

tron = Tron()
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))
HOT_WALLET_FROM_PK = private_key.public_key.to_base58check_address()

print("✅ 熱錢包地址：", HOT_WALLET_FROM_PK)

# =====================
# 🧠 状态（只记 txid）
# =====================

seen_tx = set()

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自动兑换机器人\n\n"
        "/usdt 查看兑换报价\n"
        f"最低兑换：{MIN_USDT} USDT\n"
        "模式：自动出金"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)
    await update.message.reply_text(
        f"💱 USDT → TRX\n\n"
        f"USDT：10\n"
        f"可得：約 {trx_amount} TRX\n\n"
        f"📥 收款地址：\n<code>{HOT_WALLET_ADDRESS}</code>",
        parse_mode="HTML"
    )

# =====================
# 🔁 链上监听 + 自动出金（核心）
# =====================

async def poll_trc20(app):
    url = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
    headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

    try:
        r = requests.get(url, headers=headers, params={"limit": 20}, timeout=10)
        r.raise_for_status()
        txs = r.json().get("data", [])

        for tx in txs:
            txid = tx.get("transaction_id")
            if not txid or txid in seen_tx:
                continue

            # 👉 只处理「转入」
            to_addr = tx.get("to") or tx.get("to_address")
            if to_addr != HOT_WALLET_ADDRESS:
                continue

            usdt_amount = float(tx["value"]) / 1_000_000
            if usdt_amount < MIN_USDT:
                seen_tx.add(txid)
                continue

            from_addr = tx.get("from")
            seen_tx.add(txid)

            trx_amount = round(usdt_amount * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

            # ① 管理员通知（一定先发）
            await app.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 USDT 入账\n\n"
                    f"金额：{usdt_amount} USDT\n"
                    f"来源：{from_addr}\n"
                    f"应出：{trx_amount} TRX"
                )
            )

            # ② 自动出 TRX
            try:
                tron.trx.transfer(
                    HOT_WALLET_FROM_PK,
                    from_addr,
                    int(trx_amount * 1_000_000)
                ).fee_limit(FEE_LIMIT_SUN).build().sign(private_key).broadcast()

                await app.bot.send_message(
                    chat_id=ADMIN_ID,
                    text="✅ TRX 已自动出金"
                )

            except Exception as e:
                await app.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"❌ 出金失败：{e}"
                )

    except Exception as e:
        print("监听错误：", e)

# =====================
# 🚀 主程序（最稳：不用 JobQueue）
# =====================

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    async def loop():
        while True:
            await poll_trc20(app)
            await asyncio.sleep(POLL_INTERVAL)

    asyncio.create_task(loop())
    print("🤖 Bot 已啟動（B 最終穩定版）")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
