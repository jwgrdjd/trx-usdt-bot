import os
import asyncio
import requests
from datetime import datetime, time as dtime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

# =====================
# 🔧 基本設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")
RAW_PRIVATE_KEY = os.environ.get("TRX_PRIVATE_KEY")
AUTO_PAYOUT_ENABLED = os.environ.get("AUTO_PAYOUT_ENABLED") == "true"

ADMIN_ID = 7757022123

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05

MIN_USDT = 5.0
MAX_AUTO_USDT = 100.0

POLL_INTERVAL = 30

ALLOWED_START = dtime(0, 0)
ALLOWED_END = dtime(10, 0)

# =====================
# 🔑 私鑰防呆清洗
# =====================

if not RAW_PRIVATE_KEY:
    raise RuntimeError("❌ TRX_PRIVATE_KEY 未設定")

TRX_PRIVATE_KEY = RAW_PRIVATE_KEY.strip().lower()

if len(TRX_PRIVATE_KEY) != 64:
    raise RuntimeError(f"❌ 私鑰長度錯誤（目前 {len(TRX_PRIVATE_KEY)}，必須是 64）")

# =====================
# 🔁 鏈上狀態
# =====================

last_seen_tx = set()

TRONGRID_URL = f"https://api.trongrid.io/v1/accounts/{TRC20_ADDRESS}/transactions/trc20"
HEADERS = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

# =====================
# 🔐 TRON Client
# =====================

tron = Tron(
    provider=HTTPProvider(
        api_key=TRONGRID_API_KEY
    )
)

pk = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))
OWNER_ADDRESS = pk.public_key.to_base58check_address()

print("✅ 熱錢包地址：", OWNER_ADDRESS)

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "/usdt 查看兌換資訊"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(10 * final_rate, 2)

    text = (
        "💱 <b>USDT → TRX 兌換</b>\n\n"
        "USDT：10\n"
        f"可兌換 TRX：約 {trx_amount}\n\n"
        f"最低兌換：{MIN_USDT} USDT\n\n"
        "<b>TRC20 USDT 收款地址</b>\n"
        f"<code>{TRC20_ADDRESS}</code>"
    )

    await update.message.reply_text(text, parse_mode="HTML")

# =====================
# 🔍 監聽 + 自動出金
# =====================

async def poll_trc20(app):
    try:
        r = requests.get(
            TRONGRID_URL,
            headers=HEADERS,
            params={"limit": 10},
            timeout=10
        )
        r.raise_for_status()
        data = r.json().get("data", [])

        for tx in data:
            txid = tx["transaction_id"]
            if txid in last_seen_tx:
                continue

            last_seen_tx.add(txid)

            # 只處理「轉入」
            if tx.get("to") != TRC20_ADDRESS:
                continue

            usdt_amount = float(tx["value"]) / 1_000_000
            from_addr = tx["from"]

            if usdt_amount < MIN_USDT:
                continue

            now = datetime.now().time()
            in_time = ALLOWED_START <= now <= ALLOWED_END

            final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(usdt_amount * final_rate, 6)

            status = "❌ 未出金"
            trx_txid = None

            if (
                AUTO_PAYOUT_ENABLED
                and usdt_amount <= MAX_AUTO_USDT
                and in_time
            ):
                try:
                    txn = (
                        tron.trx.transfer(
                            OWNER_ADDRESS,
                            from_addr,
                            int(trx_amount * 1_000_000)
                        )
                        .build()
                        .sign(pk)
                        .broadcast()
                    )
                    trx_txid = txn["txid"]
                    status = "✅ 已自動出金"
                except Exception as e:
                    status = f"⚠️ 出金失敗：{e}"

            msg = (
                "🔔 <b>USDT 入帳</b>\n\n"
                f"金額：{usdt_amount} USDT\n"
                f"來源：<code>{from_addr}</code>\n"
                f"應付：{trx_amount} TRX\n"
                f"狀態：{status}\n"
            )

            if trx_txid:
                msg += f"\nTRX TXID：<code>{trx_txid}</code>"

            await app.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML"
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

    async def loop():
        while True:
            await poll_trc20(app)
            await asyncio.sleep(POLL_INTERVAL)

    async def on_start(app):
        await poll_trc20(app)  # 啟動時吃掉舊交易
        app.create_task(loop())

    app.post_init = on_start
    app.run_polling()

if __name__ == "__main__":
    main()
