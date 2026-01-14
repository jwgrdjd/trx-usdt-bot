import os
import time
import asyncio
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

ADMIN_ID = 7757022123
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0

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
hot_wallet = private_key.public_key.to_base58check_address()

print("✅ 熱錢包地址：", hot_wallet)

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
        "🤖 USDT → TRX 自动兑换机器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查看兑换报价\n\n"
        f"🔻 最低兑换金额：{MIN_USDT} USDT\n"
        "🌐 网络：TRC20\n"
    )


async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

    await update.message.reply_text(
        f"💱 <b>USDT → TRX 实时汇率</b>\n\n"
        f"USDT：{DISPLAY_USDT}\n"
        f"可兑换 TRX：约 {trx_amount}\n\n"
        f"🔻 最低兑换金额：{MIN_USDT} USDT\n\n"
        "📥 <b>TRC20 USDT 换 TRX地址（点击地址自动复制）</b>\n"
        "<code>"
        f"{HOT_WALLET_ADDRESS}"
        "</code>\n\n"
        "⚠️ 请务必使用 TRC20 网络转账\n"
        "转账完成后请耐心等待处理，预计3分钟内完成闪兑"
    )


# =====================
# 🔁 鏈上監聽 + 出金
# =====================

async def poll_trc20(app):
    url = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
    headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

    try:
        r = requests.get(url, headers=headers, params={"limit": 20}, timeout=10)
        r.raise_for_status()

        for tx in r.json().get("data", []):
            txid = tx["transaction_id"]
            if txid in seen_tx:
                continue

            if tx["to"] != HOT_WALLET_ADDRESS:
                continue

            if tx["block_timestamp"] / 1000 < START_TIME:
                seen_tx.add(txid)
                continue

            usdt_amount = float(tx["value"]) / 1_000_000
            if usdt_amount < MIN_USDT:
                seen_tx.add(txid)
                continue

            from_addr = tx["from"]
            seen_tx.add(txid)

            trx_amount = round(usdt_amount * FIXED_RATE_TRX * (1 - FEE_RATE), 2)

            try:
                tron.trx.transfer(
                    hot_wallet,
                    from_addr,
                    int(trx_amount * 1_000_000)
                ).fee_limit(FEE_LIMIT_SUN).build().sign(private_key).broadcast()

                status = "✅ 已出金"
            except Exception as e:
                status = f"❌ 出金失敗：{e}"

            await app.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🔔 USDT 入帳\n"
                    f"{usdt_amount} USDT\n"
                    f"來源：{from_addr}\n"
                    f"應付：{trx_amount} TRX\n"
                    f"{status}"
                )
            )

    except Exception as e:
        print("監聽錯誤：", e)

# =====================
# 🚀 主程式（❗重點在這）
# =====================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    # ✅ 用 PTB 的 job_queue（它自己管 loop）
    app.job_queue.run_repeating(
        lambda ctx: poll_trc20(app),
        interval=POLL_INTERVAL,
        first=5
    )

    print("🤖 Bot 已啟動（最終穩定版）")
    app.run_polling()

if __name__ == "__main__":
    main()

