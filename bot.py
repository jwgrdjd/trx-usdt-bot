import os
import time
import threading
import requests
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from tronpy import Tron
from tronpy.keys import PrivateKey

# =====================
# 🔧 環境變數
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")
TRX_PRIVATE_KEY = os.environ.get("TRX_PRIVATE_KEY")

if not BOT_TOKEN or not TRONGRID_API_KEY:
    raise RuntimeError("❌ BOT_TOKEN 或 TRONGRID_API_KEY 未設定")

# =====================
# 🔒 模式開關（只改這裡）
# =====================

AUTO_PAYOUT = True   # 🔥 要真自動出金 → 改成 True,不出金改False
NIGHT_AUTO_ONLY = True  # 夜間才自動

# =====================
# 💰 兌換參數
# =====================

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05

MIN_USDT = 5
MAX_USDT = 100

# 夜間自動時間（24h）
AUTO_START_HOUR = 0     # 00:00
AUTO_END_HOUR = 10      # 10:00

# =====================
# 📌 錢包 & 管理員
# =====================

ADMIN_ID = 7757022123
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

# =====================
# 🔗 Tron（只在自動出金時用）
# =====================

tron = Tron()
private_key = None

if AUTO_PAYOUT:
    if not TRX_PRIVATE_KEY or len(TRX_PRIVATE_KEY) != 64:
        raise RuntimeError("❌ TRX_PRIVATE_KEY 必須是 64 位 HEX")
    private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))

# =====================
# 🔁 鏈上監聽設定
# =====================

SEEN_TX = set()
START_TIME = time.time()
POLL_INTERVAL = 30

TRONGRID_URL = (
    f"https://api.trongrid.io/v1/accounts/"
    f"{HOT_WALLET_ADDRESS}/transactions/trc20"
)

HEADERS = {
    "TRON-PRO-API-KEY": TRONGRID_API_KEY
}

# =====================
# 🤖 Telegram 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自动兑换机器人\n\n"
        "/usdt 查看兑换报价\n\n"
        f"🔻最低：{MIN_USDT} USDT\n"
        f"🔺最高：{MAX_USDT} USDT\n"
        "🌐网络：TRC20"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(10 * rate, 2)

    await update.message.reply_text(
        "💱 <b>💱 USDT → TRX 实时汇率</b>\n\n"
        f"USDT：10\n"
        f"可得：約 {trx_amount} TRX\n\n"
        "📥 收款地址：\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>",
        parse_mode="HTML"
        "⚠️ 请务必使用 TRC20 网络转账\n"
        "转账完成后请耐心等待处理，预计 3 分钟内完成闪兑"
    )

# =====================
# 🔍 核心監聽邏輯
# =====================

def in_auto_time():
    h = datetime.now().hour
    return AUTO_START_HOUR <= h < AUTO_END_HOUR

def poll_trc20(app):
    try:
        r = requests.get(
            TRONGRID_URL,
            headers=HEADERS,
            params={"limit": 20},
            timeout=10
        )
        r.raise_for_status()

        for tx in r.json().get("data", []):
            txid = tx["transaction_id"]
            if txid in SEEN_TX:
                continue

            SEEN_TX.add(txid)

            if tx.get("to") != HOT_WALLET_ADDRESS:
                continue

            if tx["block_timestamp"] / 1000 < START_TIME:
                continue

            usdt_amount = float(tx["value"]) / 1_000_000
            if usdt_amount < MIN_USDT or usdt_amount > MAX_USDT:
                continue

            from_addr = tx["from"]
            rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            trx_amount = round(usdt_amount * rate, 2)

            auto_ok = (
                AUTO_PAYOUT
                and (not NIGHT_AUTO_ONLY or in_auto_time())
            )

            status = "🟡 待人工处理"

            if auto_ok:
                try:
                    tron.trx.transfer(
                        HOT_WALLET_ADDRESS,
                        from_addr,
                        int(trx_amount * 1_000_000)
                    ).build().sign(private_key).broadcast()
                    status = "✅ 已自动出金"
                except Exception as e:
                    status = f"❌ 出金失败：{e}"

            msg = (
                "🔔 <b>USDT 入账</b>\n\n"
                f"金额：{usdt_amount} USDT\n"
                f"来源：\n<code>{from_addr}</code>\n\n"
                f"应付：{trx_amount} TRX\n"
                f"{status}"
            )

            app.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML"
            )

    except Exception as e:
        print("监听错误：", e)

# =====================
# 🚀 启动
# =====================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    def loop():
        while True:
            poll_trc20(app)
            time.sleep(POLL_INTERVAL)

    threading.Thread(target=loop, daemon=True).start()

    print("🤖 Bot 已启动")
    print("自动出金：", AUTO_PAYOUT)
    app.run_polling()

if __name__ == "__main__":
    main()




