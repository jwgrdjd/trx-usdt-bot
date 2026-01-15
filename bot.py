import os
import time
import asyncio
import requests
import json
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
AUTO_PAYOUT = True       
NIGHT_AUTO_ONLY = False  
AUTO_START_HOUR = 0      
AUTO_END_HOUR = 10       

FIXED_RATE_TRX = 3.2
FEE_RATE = 0.05
MIN_USDT = 5
MAX_USDT = 100
FUEL_AMOUNT = 5          

ADMIN_ID = 7757022123
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"
FUEL_DB = "fuel_status.json"

# =====================
# 🔗 Tron 初始化
# =====================
provider = HTTPProvider(api_key=TRONGRID_API_KEY)
tron = Tron(provider)
private_key = None

if AUTO_PAYOUT:
    if not TRX_PRIVATE_KEY or len(TRX_PRIVATE_KEY) != 64:
        raise RuntimeError("❌ TRX_PRIVATE_KEY 必須是 64 位 HEX")
    private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY))

# =====================
# 💾 信用數據庫操作
# =====================
def get_fuel_status(address):
    if not os.path.exists(FUEL_DB): return None
    with open(FUEL_DB, "r") as f:
        return json.load(f).get(address)

def update_fuel_status(address, status):
    data = {}
    if os.path.exists(FUEL_DB):
        with open(FUEL_DB, "r") as f: data = json.load(f)
    if status is None: data.pop(address, None)
    else: data[address] = status
    with open(FUEL_DB, "w") as f: json.dump(data, f)

# =====================
# 🤖 Telegram 指令
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自动兑换机器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查看兑换报价\n"
        f"/fuel [地址] － 预支 {FUEL_AMOUNT} TRX 手续费\n"
        f"⚠️ 注意：预支的 TRX 将在下次兑换时从应付金额中扣除。\n\n"
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
    await update.message.reply_text(text, parse_mode="HTML")

async def fuel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ 格式：/fuel TXXXXXXXX")
        return
    addr = context.args[0]
    if get_fuel_status(addr) == "pending":
        await update.message.reply_text("⚠️ 您有一笔借款尚未归还，请完成兑换后再借。")
        return
    try:
        txn = tron.trx.transfer(HOT_WALLET_ADDRESS, addr, int(FUEL_AMOUNT * 1_000_000)).build().sign(private_key)
        txn.broadcast()
        update_fuel_status(addr, "pending")
        await update.message.reply_text(f"✅ 已预支 {FUEL_AMOUNT} TRX！下次兑换时將自動扣回。")
    except Exception as e:
        await update.message.reply_text(f"❌ 借款失败：{e}")

async def pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not os.path.exists(FUEL_DB):
        await update.message.reply_text("目前没有借款纪录。")
        return
    with open(FUEL_DB, "r") as f: data = json.load(f)
    pending_addrs = [addr for addr, status in data.items() if status == "pending"]
    if not pending_addrs:
        await update.message.reply_text("✅ 目前没有未归还的借款。")
        return
    text = f"📋 <b>未归还借款清单 ({len(pending_addrs)} 筆)</b>\n\n"
    for i, addr in enumerate(pending_addrs, 1):
        text += f"{i}. <code>{addr}</code>\n"
    await update.message.reply_text(text, parse_mode="HTML")

# =====================
# 🔍 核心監聽邏輯
# =====================
SEEN_TX = set()
START_TIME = time.time()
TRONGRID_URL = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
HEADERS = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

async def poll_trc20(app):
    try:
        r = requests.get(TRONGRID_URL, headers=HEADERS, params={"limit": 20}, timeout=10)
        r.raise_for_status()
        for tx in r.json().get("data", []):
            txid = tx["transaction_id"]
            if txid in SEEN_TX or tx.get("to") != HOT_WALLET_ADDRESS: continue
            if tx["block_timestamp"] / 1000 < START_TIME: continue
            SEEN_TX.add(txid)

            usdt_amount = float(tx["value"]) / 1_000_000
            from_addr = tx["from"]
            
            rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            raw_trx_amount = round(usdt_amount * rate, 2)
            
            is_repaying = (get_fuel_status(from_addr) == "pending")
            loan_text = f"有 (需扣除 {FUEL_AMOUNT} TRX)" if is_repaying else "无"
            final_pay = round(raw_trx_amount - (FUEL_AMOUNT if is_repaying else 0), 2)

            auto_ok = AUTO_PAYOUT and (MIN_USDT <= usdt_amount <= MAX_USDT)
            
            status_display = "🟡 待人工處理"
            if auto_ok:
                try:
                    txn = tron.trx.transfer(HOT_WALLET_ADDRESS, from_addr, int(final_pay * 1_000_000)).build().sign(private_key)
                    txn.broadcast()
                    if is_repaying: update_fuel_status(from_addr, None)
                    status_display = "✅ <b>已自動出金</b>"
                except Exception as e:
                    status_display = f"❌ <b>自動出金失敗</b>：{str(e)}"

            msg = (
                "🔔 <b>USDT 入帳通知</b>\n\n"
                f"<b>金額</b>：{usdt_amount} USDT\n"
                f"<b>來源</b>：<code>{from_addr}</code>\n"
                f"--------------------------\n"
                f"<b>應付總計</b>：{raw_trx_amount} TRX\n"
                f"<b>有無借款</b>：{loan_text}\n"
                f"<b>扣除後應發</b>：<u>{final_pay} TRX</u>\n"
                f"--------------------------\n"
                f"<b>狀態</b>：{status_display}"
            )
            await app.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="HTML")
    except Exception as e:
        print(f"監聽錯誤：{e}")

# =====================
# 🚀 啟動邏輯
# =====================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))
    app.add_handler(CommandHandler("fuel", fuel))
    app.add_handler(CommandHandler("pending", pending_list))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    print(f"🤖 Bot 已啟動 | 自動出金: {AUTO_PAYOUT}")

    try:
        while True:
            await poll_trc20(app)
            await asyncio.sleep(POLL_INTERVAL)
    finally:
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("停止機器人")
