import os
import asyncio
import requests
from datetime import datetime, time as dtime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =====================
# 🔧 環境變數
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")
TRX_PRIVATE_KEY = os.environ.get("TRX_PRIVATE_KEY")  # 熱錢包私鑰（HEX）

ADMIN_ID = 7757022123

# =====================
# 💱 兌換設定
# =====================

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5.0
DISPLAY_USDT = 10.0

# =====================
# 🔒 自動出金條件
# =====================

AUTO_MAX_USDT = 100.0
AUTO_START = dtime(0, 0)
AUTO_END   = dtime(10, 0)

# =====================
# ⏱️ 輪詢
# =====================

POLL_INTERVAL = 30
last_seen_tx = set()

TRONGRID_TRC20 = f"https://api.trongrid.io/v1/accounts/{TRC20_ADDRESS}/transactions/trc20"
TRONGRID_SEND = "https://api.trongrid.io/wallet/easytransferbyprivate"

HEADERS = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

# =====================
# 🧠 判斷
# =====================

def is_auto_allowed(usdt_amount: float, now: datetime) -> bool:
    if usdt_amount > AUTO_MAX_USDT:
        return False
    return AUTO_START <= now.time() <= AUTO_END

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "/usdt － 查看兌換報價\n\n"
        f"最低：{MIN_USDT} USDT\n"
        "網路：TRC20\n"
        "狀態：自動出金啟用（限額/限時）"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(DISPLAY_USDT * final_rate, 2)
    text = (
        "💱 <b>USDT → TRX 兌換報價</b>\n\n"
        f"USDT：{DISPLAY_USDT}\n"
        f"可兌換 TRX：約 {trx_amount}\n\n"
        f"最低：{MIN_USDT} USDT\n\n"
        "📥 <b>TRC20 USDT 收款地址</b>\n"
        f"<code>{TRC20_ADDRESS}</code>\n\n"
        "⚠️ 使用 TRC20 轉帳"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# =====================
# 💸 出金（TRX）
# =====================

def send_trx(to_addr: str, amount_trx: float) -> dict:
    payload = {
        "privateKey": TRX_PRIVATE_KEY,
        "toAddress": to_addr,
        "amount": int(amount_trx * 1_000_000),  # TRX -> sun
    }
    r = requests.post(TRONGRID_SEND, headers=HEADERS, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()

# =====================
# 🔍 監聽
# =====================

async def poll_trc20(app):
    global last_seen_tx
    try:
        r = requests.get(TRONGRID_TRC20, headers=HEADERS, params={"limit": 10}, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])

        for tx in data:
            txid = tx["transaction_id"]
            if txid in last_seen_tx:
                continue

            value = float(tx["value"]) / 1_000_000
            from_addr = tx["from"]
            to_addr = tx["to"]

            if to_addr.lower() != TRC20_ADDRESS.lower():
                continue
            if value < MIN_USDT:
                continue

            last_seen_tx.add(txid)

            final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(value * final_rate, 2)
            now = datetime.now()

            if is_auto_allowed(value, now):
                try:
                    result = send_trx(from_addr, trx_amount)
                    status = "🟢 已自動出金"
                    detail = f"TXID：{result.get('txid', 'N/A')}"
                except Exception as e:
                    status = "🔴 出金失敗（已停）"
                    detail = str(e)
            else:
                status = "🟡 不符合自動出金（需人工）"
                detail = "-"

            msg = (
                "🔔 <b>USDT 入帳</b>\n\n"
                f"金額：{value} USDT\n"
                f"來源：<code>{from_addr}</code>\n\n"
                f"應付：{trx_amount} TRX\n"
                f"狀態：{status}\n"
                f"{detail}\n\n"
                f"時間：{now.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await app.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="HTML")

    except Exception as e:
        print("監聽錯誤：", e)

# =====================
# 🚀 啟動
# =====================

def main():
    if not all([BOT_TOKEN, TRONGRID_API_KEY, TRX_PRIVATE_KEY]):
        raise RuntimeError("❌ 缺少環境變數")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    async def bg():
        while True:
            await poll_trc20(app)
            await asyncio.sleep(POLL_INTERVAL)

    async def on_start(app):
        app.create_task(bg())

    app.post_init = on_start
    app.run_polling()

if __name__ == "__main__":
    main()
