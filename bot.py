import os
import time
import asyncio
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

ADMIN_ID = 7757022123  # 管理員 Telegram ID

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # USDT TRC20
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0

POLL_INTERVAL = 30
FEE_LIMIT_SUN = 10_000_000  # 10 TRX（燒 TRX 手續費）

# =====================
# 🔒 啟動前檢查
# =====================

if not BOT_TOKEN or not TRONGRID_API_KEY or not TRX_PRIVATE_KEY:
    raise RuntimeError("❌ BOT_TOKEN / TRONGRID_API_KEY / TRX_PRIVATE_KEY 未設定")

if len(TRX_PRIVATE_KEY) != 64:
    raise RuntimeError(f"❌ 私鑰長度錯誤（目前 {len(TRX_PRIVATE_KEY)}，必須是 64）")

# =====================
# 🔗 TRON 初始化
# =====================

tron = Tron(api_key=TRONGRID_API_KEY)
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))
hot_wallet = private_key.public_key.to_base58check_address()

print("✅ 熱錢包地址：", hot_wallet)

# =====================
# 🧠 狀態（避免吃舊交易）
# =====================

seen_tx = set()
START_TIME = time.time()

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "/usdt 查看兌換資訊\n"
        f"最低兌換：{MIN_USDT} USDT\n"
        "模式：自動出金（燒 TRX）"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(10 * rate, 2)

    text = (
        "💱 <b>USDT → TRX 兌換報價</b>\n\n"
        "USDT：10\n"
        f"可兌換 TRX：約 {trx_amount}\n\n"
        f"最低兌換：{MIN_USDT} USDT\n\n"
        "📥 <b>TRC20 USDT 收款地址</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "⚠️ 使用 TRC20 網路\n"
        "完成後系統將自動出金"
    )

    await update.message.reply_text(text, parse_mode="HTML")

# =====================
# 🔁 鏈上監聽 + 自動出金
# =====================

async def poll_trc20(context: ContextTypes.DEFAULT_TYPE):
    url = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
    headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

    try:
        r = requests.get(url, headers=headers, params={"limit": 20}, timeout=10)
        r.raise_for_status()
        txs = r.json().get("data", [])

        for tx in txs:
            txid = tx["transaction_id"]

            if txid in seen_tx:
                continue

            block_ts = tx["block_timestamp"] / 1000
            if block_ts < START_TIME:
                seen_tx.add(txid)
                continue

            if tx["to"] != HOT_WALLET_ADDRESS:
                continue  # ❗只吃「轉入」

            usdt_amount = float(tx["value"]) / 1_000_000
            if usdt_amount < MIN_USDT:
                seen_tx.add(txid)
                continue

            from_addr = tx["from"]
            seen_tx.add(txid)

            rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(usdt_amount * rate, 2)

            # 🚀 出金（燒 TRX）
            try:
                txn = (
                    tron.trx.transfer(
                        from_address=hot_wallet,
                        to_address=from_addr,
                        amount=int(trx_amount * 1_000_000),
                    )
                    .fee_limit(FEE_LIMIT_SUN)
                    .build()
                    .sign(private_key)
                    .broadcast()
                )

                status = "✅ 已出金"
            except Exception as e:
                status = f"❌ 出金失敗：{e}"

            msg = (
                "🔔 <b>USDT 入帳</b>\n\n"
                f"金額：{usdt_amount} USDT\n"
                f"來源：<code>{from_addr}</code>\n"
                f"應付：{trx_amount} TRX\n"
                f"狀態：{status}\n"
                f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML",
            )

    except Exception as e:
        print("監聽錯誤：", e)

# =====================
# 🚀 主程式
# =====================

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    async def loop():
        while True:
            await poll_trc20(app.bot)
            await asyncio.sleep(POLL_INTERVAL)

    asyncio.create_task(loop())

    print("🤖 真・自動出金 Bot 已啟動")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
