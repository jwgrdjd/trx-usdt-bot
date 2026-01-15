import os
import time
import asyncio
import requests
import json
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

# =====================
# 🔧 環境變數與設定
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")
TRX_PRIVATE_KEY = os.environ.get("TRX_PRIVATE_KEY")

if not BOT_TOKEN or not TRONGRID_API_KEY:
    raise RuntimeError("❌ 缺少必要的環境變數 BOT_TOKEN 或 TRONGRID_API_KEY")

AUTO_PAYOUT = True       
FIXED_RATE_TRX = 3.2     
FEE_RATE = 0.05          
MIN_USDT = 5             
MAX_USDT = 100           
FUEL_AMOUNT = 5          
POLL_INTERVAL = 30       
DAILY_LIMIT = 20         

ADMIN_ID = 7757022123
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"
FUEL_DB = "fuel_status.json"
STATS_DB = "daily_stats.json" 

# =====================
# 🔗 Tron 初始化
# =====================
provider = HTTPProvider(api_key=TRONGRID_API_KEY)
tron = Tron(provider)
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY)) if AUTO_PAYOUT else None

# =====================
# 📊 數據管理
# =====================
def check_daily_limit():
    today = datetime.now().strftime("%Y-%m-%d")
    data = {"date": today, "count": 0}
    if os.path.exists(STATS_DB):
        with open(STATS_DB, "r") as f:
            try:
                data = json.load(f)
                if data.get("date") != today: data = {"date": today, "count": 0}
            except: pass
    if data["count"] >= DAILY_LIMIT: return False, data["count"]
    return True, data["count"]

def increment_daily_count():
    today = datetime.now().strftime("%Y-%m-%d")
    data = {"date": today, "count": 0}
    if os.path.exists(STATS_DB):
        with open(STATS_DB, "r") as f:
            try: data = json.load(f)
            except: pass
    data["count"] += 1
    with open(STATS_DB, "w") as f: json.dump(data, f)

def get_fuel_status(address, user_id):
    if not os.path.exists(FUEL_DB): return None
    with open(FUEL_DB, "r") as f:
        try:
            data = json.load(f)
            if data.get(address) == "pending" or data.get(str(user_id)) == "pending": return "pending"
            return None
        except: return None

def update_fuel_status(address, user_id, status):
    data = {}
    if os.path.exists(FUEL_DB):
        with open(FUEL_DB, "r") as f:
            try: data = json.load(f)
            except: data = {}
    if status is None:
        data.pop(address, None); data.pop(str(user_id), None)
    else:
        data[address] = status; data[str(user_id)] = status
    with open(FUEL_DB, "w") as f: json.dump(data, f)

# =====================
# 🤖 客戶端指令 (簡體中文 + 顏色標記)
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 <b>USDT → TRX 自动兑换系统</b>\n\n"
        "🔵 <b>快速操作：</b>\n"
        "• /usdt － 获取实时汇率与收款地址\n"
        "• <b>直接发送钱包地址</b> － 预支 5 TRX 手续费\n\n"
        f"💡 <i>温馨提示：若钱包余额不足无法转账，直接貼上地址可预支 {FUEL_AMOUNT} TRX 手续费。</i>\n\n"
        f"🔴 <b>USDT → TRX 最低兑换：{MIN_USDT} USDT</b>"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)
    text = (
        "💱 <b>USDT → TRX 实时汇率</b>\n\n"
        "<b>当前汇率：</b> 1 USDT = <code>" + str(round(FIXED_RATE_TRX * (1-FEE_RATE), 2)) + "</code> TRX\n"
        f"<b>参考兑换：</b> 10 USDT ≈ <code>{trx_amount}</code> TRX\n\n"
        "📥 <b>TRC20 收款地址 (点击可复制)</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "--------------------------\n"
        "⚠️ <b>注意事项：</b>\n"
        "若您的錢包 TRX 餘額不足無法轉帳，請在此直接<b>發送您的 TRX 錢包地址</b>，系統將為您預支 5 TRX 手續費。\n\n"
        f"🔴 <b>USDT → TRX 最低兑换：{MIN_USDT} USDT</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def handle_address_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    if len(text) == 34 and text.startswith("T"):
        can_loan, _ = check_daily_limit()
        if not can_loan:
            await update.message.reply_text("🔴 <b>今日预支名额已满，请明天再试。</b>", parse_mode="HTML")
            return
        if get_fuel_status(text, user_id) == "pending":
            await update.message.reply_text("🟡 <b>提示：您已領取過預支 TRX，請完成兌換後再領。</b>", parse_mode="HTML")
            return
        try:
            txn = tron.trx.transfer(HOT_WALLET_ADDRESS, text, int(FUEL_AMOUNT * 1_000_000)).build().sign(private_key)
            txn.broadcast()
            update_fuel_status(text, user_id, "pending")
            increment_daily_count()
            await update.message.reply_text(f"✅ <b>预支TRX发放成功！</b>\n\n已向您的地址发送 <code>{FUEL_AMOUNT}</code> TRX。该款项将在您兑换成功时自动扣回。", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ <b>发放失败，请联系客服处理。</b>", parse_mode="HTML")

# =====================
# 📋 管理員通知 (繁體中文 + 顏色狀態)
# =====================
async def pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    _, count = check_daily_limit()
    status_msg = f"📊 <b>今日進度：{count} / {DAILY_LIMIT} (人)</b>\n\n"
    if os.path.exists(FUEL_DB):
        with open(FUEL_DB, "r") as f:
            try: data = json.load(f)
            except: data = {}
        p_list = [f"• <code>{k}</code>" for k, v in data.items() if v == "pending"]
        status_msg += "📋 <b>未歸還清單：</b>\n" + ("\n".join(p_list) if p_list else "暫無紀錄")
    await update.message.reply_text(status_msg, parse_mode="HTML")

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
            is_repaying = (get_fuel_status(from_addr, "DUMMY") == "pending")
            final_pay = round(raw_trx_amount - (FUEL_AMOUNT if is_repaying else 0), 2)
            
            auto_ok = AUTO_PAYOUT and (MIN_USDT <= usdt_amount <= MAX_USDT)
            status_display = "🟡 <b>待人工處理</b>"
            if auto_ok:
                try:
                    txn = tron.trx.transfer(HOT_WALLET_ADDRESS, from_addr, int(final_pay * 1_000_000)).build().sign(private_key)
                    txn.broadcast()
                    if is_repaying: update_fuel_status(from_addr, "CLEAN", None)
                    status_display = "✅ <b>已自動出金</b>"
                except Exception as e: status_display = f"❌ <b>失敗</b>：{str(e)}"

            msg = (f"🔔 <b>USDT 入帳通知</b>\n\n"
                   f"💰 <b>金額：</b> {usdt_amount} USDT\n"
                   f"👤 <b>來源：</b> <code>{from_addr}</code>\n"
                   f"⛽ <b>預支扣除：</b> {'🚩 扣除 5 TRX' if is_repaying else '無'}\n"
                   f"💸 <b>應發總計：</b> <u>{final_pay} TRX</u>\n\n"
                   f"📢 <b>狀態：</b> {status_display}")
            await app.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="HTML")
    except Exception as e: print(f"Error: {e}")

# =====================
# 🚀 啟動邏輯
# =====================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))
    app.add_handler(CommandHandler("pending", pending_list))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_address_message))
    await app.initialize(); await app.start(); await app.updater.start_polling()
    print(f"🤖 Bot Started | Daily Limit: {DAILY_LIMIT}")
    try:
        while True:
            await poll_trc20(app); await asyncio.sleep(POLL_INTERVAL)
    finally:
        if app.updater.running: await app.updater.stop()
        await app.stop(); await app.shutdown()

SEEN_TX = set(); START_TIME = time.time()
if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Stopped")
