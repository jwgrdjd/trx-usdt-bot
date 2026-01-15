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
# 📁 數據持久化路徑 (絕對路徑加固)
# =====================
# 獲取目前程式碼所在的絕對資料夾路徑，確保更新時紀錄不丟失
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FUEL_DB = os.path.join(BASE_DIR, "fuel_status.json")
STATS_DB = os.path.join(BASE_DIR, "daily_stats.json")

# =====================
# 🔧 環境變數與核心設定
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")
TRX_PRIVATE_KEY = os.environ.get("TRX_PRIVATE_KEY")

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

# =====================
# 🔗 初始化 Tron
# =====================
provider = HTTPProvider(api_key=TRONGRID_API_KEY)
tron = Tron(provider)
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY)) if AUTO_PAYOUT else None

# =====================
# 💾 安全數據庫操作
# =====================
def get_fuel_status(address, user_id):
    if not os.path.exists(FUEL_DB): return None
    try:
        with open(FUEL_DB, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get(address) == "pending" or data.get(str(user_id)) == "pending":
                return "pending"
    except: pass
    return None

def update_fuel_status(address, user_id, status):
    data = {}
    if os.path.exists(FUEL_DB):
        try:
            with open(FUEL_DB, "r", encoding="utf-8") as f:
                data = json.load(f)
        except: data = {}
    
    if status is None:
        data.pop(address, None)
        data.pop(str(user_id), None)
    else:
        data[address] = status
        data[str(user_id)] = status
        
    with open(FUEL_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def check_daily_limit():
    today = datetime.now().strftime("%Y-%m-%d")
    data = {"date": today, "count": 0}
    if os.path.exists(STATS_DB):
        try:
            with open(STATS_DB, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") != today: data = {"date": today, "count": 0}
        except: pass
    return (data["count"] < DAILY_LIMIT), data["count"]

def increment_daily_count():
    today = datetime.now().strftime("%Y-%m-%d")
    data = {"date": today, "count": 0}
    if os.path.exists(STATS_DB):
        try:
            with open(STATS_DB, "r", encoding="utf-8") as f:
                data = json.load(f)
        except: pass
    data["count"] += 1
    with open(STATS_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =====================
# 🤖 客戶端指令 (簡體中文)
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 <b>USDT → TRX 自动兑换系统</b>\n\n"
        "🔵 <b>快速操作：</b>\n"
        "• /usdt － 获取实时汇率与收款地址\n"
        "• <b>直接发送钱包地址</b> － 预支 5 TRX 手续费\n\n"
        f"💡 <i>温馨提示：若您的钱包 TRX 余额不足无法转账，请在此直接发送您的 TRX 钱包地址，系统将为您预支 {FUEL_AMOUNT} TRX 手续费。</i>\n\n"
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
        "⚠️ <b>温馨提示：</b>\n"
        "若您的钱包 TRX 余额不足无法转账，请在此直接<b>发送您的 TRX 钱包地址</b>，系统将为您预支 5 TRX 手续费。\n\n"
        f"🔴 <b>USDT → TRX 最低兑换：{MIN_USDT} USDT</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def handle_address_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    if len(text) == 34 and text.startswith("T"):
        # 1. 檢查每日限額
        can_loan, current_count = check_daily_limit()
        if not can_loan:
            await update.message.reply_text("🔴 <b>今日预支名额已满，请明天再试。</b>", parse_mode="HTML")
            return
            
        # 2. 檢查是否領取過 (雙重判定)
        if get_fuel_status(text, user.id) == "pending":
            await update.message.reply_text("🟡 <b>提示：您已领取过预支 TRX，请完成兑换后再领。</b>", parse_mode="HTML")
            return

        # 🔥【先鎖定】: 在發送前就寫入資料庫，防止重複觸發
        update_fuel_status(text, user.id, "pending")

        try:
            # 3. 執行轉帳
            txn = tron.trx.transfer(HOT_WALLET_ADDRESS, text, int(FUEL_AMOUNT * 1_000_000)).build().sign(private_key)
            txn.broadcast()
            
            # 4. 更新每日計數
            increment_daily_count()
            
            # 5. 回覆與通知管理員
            await update.message.reply_text(f"✅ <b>预支TRX发放成功！</b>\n\n已向您的地址发送 <code>{FUEL_AMOUNT}</code> TRX。该款项将在您兑换成功时自动扣回。", parse_mode="HTML")
            
            admin_notice = (
                "⛽ <b>預支發放通知</b>\n\n"
                f"👤 <b>用戶 ID：</b> <code>{user.id}</code>\n"
                f"👤 <b>用戶名：</b> @{user.username if user.username else '無'}\n"
                f"📥 <b>錢包地址：</b> <code>{text}</code>\n"
                f"📊 <b>今日進度：</b> {current_count + 1} / {DAILY_LIMIT}"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notice, parse_mode="HTML")

        except Exception as e:
            # 如果轉帳失敗，才解除鎖定
            update_fuel_status(text, user.id, None)
            await update.message.reply_text("❌ <b>发放失败，请联系客服处理。</b>", parse_mode="HTML")
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ <b>預支發放錯誤：</b>\n{str(e)}")

# =====================
# 📋 管理員功能 (繁體中文)
# =====================
async def pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    _, count = check_daily_limit()
    status_msg = f"📊 <b>今日進度：{count} / {DAILY_LIMIT} (人)</b>\n\n"
    if os.path.exists(FUEL_DB):
        with open(FUEL_DB, "r", encoding="utf-8") as f:
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
    except Exception as e: print(f"Scan Error: {e}")

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
    print(f"🤖 Bot 已啟動 | 資料庫路徑: {BASE_DIR}")
    try:
        while True:
            await poll_trc20(app); await asyncio.sleep(POLL_INTERVAL)
    finally:
        if app.updater.running: await app.updater.stop()
        await app.stop(); await app.shutdown()

SEEN_TX = set(); START_TIME = time.time(); TRONGRID_URL = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"; HEADERS = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Stopped")
