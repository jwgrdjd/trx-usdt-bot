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

# 模式設定
AUTO_PAYOUT = True       

# 匯率與限制
FIXED_RATE_TRX = 3.2     
FEE_RATE = 0.05          
MIN_USDT = 5             
MAX_USDT = 100           
FUEL_AMOUNT = 5          
POLL_INTERVAL = 30       
DAILY_LIMIT = 20         # 每日預支總名額

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
# 📊 每日限額與信用管理
# =====================
def check_daily_limit():
    """檢查每日限額，跨天自動重置"""
    today = datetime.now().strftime("%Y-%m-%d")
    data = {"date": today, "count": 0}
    if os.path.exists(STATS_DB):
        with open(STATS_DB, "r") as f:
            try:
                data = json.load(f)
                if data.get("date") != today:
                    data = {"date": today, "count": 0}
            except: pass
    if data["count"] >= DAILY_LIMIT:
        return False, data["count"]
    return True, data["count"]

def increment_daily_count():
    """發放成功後增加計數"""
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
            if data.get(address) == "pending" or data.get(str(user_id)) == "pending":
                return "pending"
            return None
        except: return None

def update_fuel_status(address, user_id, status):
    data = {}
    if os.path.exists(FUEL_DB):
        with open(FUEL_DB, "r") as f:
            try: data = json.load(f)
            except: data = {}
    if status is None:
        data.pop(address, None)
        data.pop(str(user_id), None)
    else:
        data[address] = status
        data[str(user_id)] = status
    with open(FUEL_DB, "w") as f: json.dump(data, f)

# =====================
# 🤖 客戶端指令 (簡體中文)
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 <b>USDT → TRX 自动兑换系统</b>\n\n"
        "📌 <b>快速操作：</b>\n"
        "• /usdt － 获取实时汇率与收款地址\n"
        "• <b>直接发送钱包地址</b> － 预支 5 TRX 手续费\n\n"
        f"💡 <i>预支说明：若您的钱包TRX余额不足，直接发送地址可预支 {FUEL_AMOUNT} TRX 手续费。此款项将于您完成兑换时自动扣除。</i>\n\n"
        f"🔻 最低兑换：{MIN_USDT} USDT"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)
    text = (
        "💱 <b>USDT → TRX 实时汇率</b>\n\n"
        "USDT：10\n"
        f"可得：约 {trx_amount} TRX\n\n"
        "📥 <b>TRC20 收款地址</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "--------------------------\n"
        "💡 <b>温馨提示：</b>\n"
        "若您的钱包 TRX 余额不足无法进行兑換，请直接在此<b>发送您的 TRX 钱包地址</b>，系统将为您预支 5 TRX 手续费。"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def handle_address_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    if len(text) == 34 and text.startswith("T"):
        # 1. 檢查每日限制（額滿才提示）
        can_loan, _ = check_daily_limit()
        if not can_loan:
            await update.message.reply_text("今日预支名额已满，请明天再试。")
            return

        # 2. 檢查信用鎖定
        if get_fuel_status(text, user_id) == "pending":
            await update.message.reply_text("⚠️ 系统检测到您已领取过预支TRX，请完成兑换以解除锁定。")
            return

        try:
            # 執行轉帳 5 TRX
            txn = tron.trx.transfer(HOT_WALLET_ADDRESS, text, int(FUEL_AMOUNT * 1_000_000)).build().sign(private_key)
            txn.broadcast()
            
            # 更新紀錄
            update_fuel_status(text, user_id, "pending")
            increment_daily_count()
            
            await update.message.reply_text(f"✅ <b>预支TRX发放成功！</b>\n\n已向您的地址发送 {FUEL_AMOUNT} TRX。该款项将在您兑换成功时自动扣回。", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ 发放失败，请联系管理员。")

# =====================
# 📋 管理員指令 (繁體中文)
# =====================
async def pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    _, count = check_daily_limit()
    status_msg = f"📊 <b>今日進度：{count} / {DAILY_LIMIT} (人)</b>\n\n"
    
    if os.path.exists(FUEL_DB):
        with open(FUEL_DB, "r") as f:
            try: data = json.load(f)
            except: data = {}
        p_list = [f"<code>{k}</code>" for k, v in data.items() if v == "pending"]
        status_msg += "📋 <b>未歸還清單：</b>\n" + ("\n".join(p_list) if p_list else "暫無")
    
    await update.message.reply_text(status_msg, parse_mode="HTML")

# =====================
# 🔍 核心監聽邏輯 (通知管理員用繁體)
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
            
            # 判斷是否需要扣除預支款
            is_repaying = (get_fuel_status(from_addr, "DUMMY_ID") == "pending")
            final_pay = round(raw_trx_amount - (FUEL_AMOUNT if is_repaying else 0), 2)

            auto_ok = AUTO_PAYOUT and (MIN_USDT <= usdt_amount <= MAX_USDT)
            status_display = "🟡 待人工處理"

            if auto_ok:
                try:
                    txn = tron.trx.transfer(HOT_WALLET_ADDRESS, from_addr, int(final_pay * 1_000_000)).build().sign(private_key)
                    txn.broadcast()
                    # 歸還後解鎖地址與 ID
                    if is_repaying: update_fuel_status(from_addr, "SYSTEM", None)
                    status_display = "✅ <b>已自動出金</b>"
                except Exception as e:
                    status_display = f"❌ <b>出金失敗</b>：{str(e)}"

            msg = (f"🔔 <b>USDT 入帳通知</b>\n金額：{usdt_amount} USDT\n來源：<code>{from_addr}</code>\n"
                   f"預支還款：{'要扣除' if is_repaying else '無'}\n應發總計：{final_pay} TRX\n狀態：{status_display}")
            await app.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="HTML")
            
    except Exception as e:
        print(f"掃描錯誤: {e}")

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
    print(f"🤖 Bot 已啟動 | 每日限額: {DAILY_LIMIT}")

    try:
        while True:
            await poll_trc20(app)
            await asyncio.sleep(POLL_INTERVAL)
    finally:
        if app.updater.running: await app.updater.stop()
        await app.stop(); await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("停止機器人")
