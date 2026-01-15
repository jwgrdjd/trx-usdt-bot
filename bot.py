import os
import time
import asyncio
import requests
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

# =====================
# 🔧 環境變數
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")
TRX_PRIVATE_KEY = os.environ.get("TRX_PRIVATE_KEY")

if not BOT_TOKEN or not TRONGRID_API_KEY:
    raise RuntimeError("❌ BOT_TOKEN 或 TRONGRID_API_KEY 未設定")

# =====================
# 🔒 模式開關
# =====================
AUTO_PAYOUT = True       # 是否開啟自動出金
NIGHT_AUTO_ONLY = True   # 是否僅夜間自動
AUTO_START_HOUR = 0      # 00:00
AUTO_END_HOUR = 10       # 10:00

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5
MAX_USDT = 100

ADMIN_ID = 7757022123
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

# =====================
# 🔗 Tron 初始化 (帶入 API Key 防止 429)
# =====================
provider = HTTPProvider(api_key=TRONGRID_API_KEY)
tron = Tron(provider)
private_key = None

if AUTO_PAYOUT:
    if not TRX_PRIVATE_KEY or len(TRX_PRIVATE_KEY) != 64:
        raise RuntimeError("❌ TRX_PRIVATE_KEY 必須是 64 位 HEX")
    private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))

# =====================
# 🔁 監聽設定
# =====================
SEEN_TX = set()
START_TIME = time.time()
POLL_INTERVAL = 30
TRONGRID_URL = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
HEADERS = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

# =====================
# 🤖 Telegram 指令
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

    text = (
        "💱 <b>USDT → TRX 实时汇率</b>\n\n"
        "USDT：10\n"
        f"可得：約 {trx_amount} TRX\n\n"
        "📥 <b>TRC20 USDT 换 TRX 地址（点击可复制）</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "⚠️ 请务必使用 TRC20 网络转账\n"
        "转账完成后请耐心等待处理，预计 3 分钟内完成闪兑"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )

# =====================
# 🔍 核心監聽邏輯 (改為 async)
# =====================
def in_auto_time():
    h = datetime.now().hour
    return AUTO_START_HOUR <= h < AUTO_END_HOUR

async def poll_trc20(app):
    try:
        # 使用請求庫獲取數據
        r = requests.get(TRONGRID_URL, headers=HEADERS, params={"limit": 20}, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])

        for tx in data:
            txid = tx["transaction_id"]
            if txid in SEEN_TX: continue
            SEEN_TX.add(txid)

            if tx.get("to") != HOT_WALLET_ADDRESS: continue
            if tx["block_timestamp"] / 1000 < START_TIME: continue

            usdt_amount = float(tx["value"]) / 1_000_000
            from_addr = tx["from"]
            rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(usdt_amount * rate, 2)

            auto_ok = AUTO_PAYOUT and (not NIGHT_AUTO_ONLY or in_auto_time())
            
            # 只有金額在限制內才自動出金
            if usdt_amount < MIN_USDT or usdt_amount > MAX_USDT:
                auto_ok = False

            status = "🟡 待人工處理"

            if auto_ok:
                try:
                    # 發送 TRX
                    txn = tron.trx.transfer(HOT_WALLET_ADDRESS, from_addr, int(trx_amount * 1_000_000))
                    txn.build().sign(private_key).broadcast()
                    status = "✅ 已自動出金"
                except Exception as e:
                    status = f"❌ 出金失敗：{str(e)}"

            msg = (
                "🔔 <b>USDT 入帳通知</b>\n\n"
                f"金額：{usdt_amount} USDT\n"
                f"來源：<code>{from_addr}</code>\n"
                f"應付：{trx_amount} TRX\n"
                f"狀態：<b>{status}</b>"
            )

            # 重要：使用 await 發送訊息
            await app.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML"
            )

    except Exception as e:
        print(f"監聽錯誤：{e}")

# =====================
# 🚀 啟動邏輯 (修正事件循環衝突)
# =====================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    # 啟動 Bot
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    print(f"🤖 Bot 已啟動 | 自動出金: {AUTO_PAYOUT} | 夜間模式: {NIGHT_AUTO_ONLY}")

    # 異步監聽循環
    try:
        while True:
            await poll_trc20(app)
            await asyncio.sleep(POLL_INTERVAL)
    finally:
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("停止機器人")

