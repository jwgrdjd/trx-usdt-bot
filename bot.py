import os
import time
import asyncio
import requests
import json
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, PicklePersistence

from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

# =====================
# 📁 數據持久化設定 (GitHub/雲端環境專用)
# =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 將持久化路徑指向絕對路徑
PERSISTENCE_FILE = os.path.join(BASE_DIR, "bot_persistence_data")

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
# 🤖 客戶端指令
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
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 初始化 bot_data (這會被持久化)
        if "stats" not in context.bot_data or context.bot_data["stats"].get("date") != today:
            context.bot_data["stats"] = {"date": today, "count": 0}
        if "records" not in context.bot_data:
            context.bot_data["records"] = {}

        # 1. 檢查限制
        if context.bot_data["stats"]["count"] >= DAILY_LIMIT:
            await update.message.reply_text("🔴 <b>今日预支名额已满，请明天再试。</b>", parse_mode="HTML")
            return
            
        # 2. 檢查重複
        if text in context.bot_data["records"] or str(user.id) in context.bot_data["records"]:
            await update.message.reply_text("🟡 <b>提示：您已领取过预支 TRX，请完成兑换后再领。</b>", parse_mode="HTML")
            return

        # 🔥 先寫入紀錄
        context.bot_data["records"][text] = "pending"
        context.bot_data["records"][str(user.id)] = "pending"

        try:
            # 3. 發款
            txn = tron.trx.transfer(HOT_WALLET_ADDRESS, text, int(FUEL_AMOUNT * 1_000_000)).build().sign(private_key)
            txn.broadcast()
            
            # 4. 更新計數
            context.bot_data["stats"]["count"] += 1
            
            await update.message.reply_text(f"✅ <b>预支TRX发放成功！</b>\n\n已向您的地址发送 <code>{FUEL_AMOUNT}</code> TRX。", parse_mode="HTML")
            
            admin_notice = (
                "⛽ <b>預支發放通知</b>\n\n"
                f"👤 <b>用戶：</b> @{user.username if user.username else user.id}\n"
                f"📥 <b>地址：</b> <code>{text}</code>\n"
                f"📊 <b>今日進度：</b> {context.bot_data['stats']['count']} / {DAILY_LIMIT}"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notice, parse_mode="HTML")
        except Exception as e:
            # 失敗才移除
            context.bot_data["records"].pop(text, None)
            await update.message.reply_text("❌ <b>发放失败，请联系客服处理。</b>", parse_mode="HTML")

# =====================
# 📋 管理員功能 (掃描轉帳)
# =====================
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
            
            # 檢查是否有欠款
            is_repaying = False
            # 從持久化數據中檢查
            if "records" in app.bot_data and (from_addr in app.bot_data["records"] or str(from_addr) in app.bot_data["records"]):
                is_repaying = True

            rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            raw_trx_amount = round(usdt_amount * rate, 2)
            final_pay = round(raw_trx_amount - (FUEL_AMOUNT if is_repaying else 0), 2)
            
            if AUTO_PAYOUT and (MIN_USDT <= usdt_amount <= MAX_USDT):
                try:
                    txn = tron.trx.transfer(HOT_WALLET_ADDRESS, from_addr, int(final_pay * 1_000_000)).build().sign(private_key)
                    txn.broadcast()
                    # 清除紀錄
                    if is_repaying and "records" in app.bot_data:
                        app.bot_data["records"].pop(from_addr, None)
                    status = "✅ <b>自動出金成功</b>"
                except Exception as e: status = f"❌ <b>失敗: {e}</b>"
            else: status = "🟡 <b>待人工處理</b>"

            msg = (f"🔔 <b>USDT 入帳</b>\n💰 金額: {usdt_amount} USDT\n👤 來源: <code>{from_addr}</code>\n"
                   f"⛽ 預支扣除: {'🚩 是' if is_repaying else '否'}\n💸 應發: {final_pay} TRX\n📢 狀態: {status}")
            await app.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="HTML")
    except Exception as e: print(f"Error: {e}")

# =====================
# 🚀 啟動
# =====================
async def main():
    # 使用官方持久化工具
    persistence = PicklePersistence(filepath=PERSISTENCE_FILE)
    
    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_address_message))
    
    await app.initialize(); await app.start(); await app.updater.start_polling()
    print(f"🤖 GitHub Mode Bot Started")
    
    try:
        while True:
            await poll_trc20(app); await asyncio.sleep(POLL_INTERVAL)
    finally:
        await app.stop(); await app.shutdown()

SEEN_TX = set(); START_TIME = time.time(); TRONGRID_URL = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"; HEADERS = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Stopped")
