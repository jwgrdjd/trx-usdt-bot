import os
import asyncio
import requests
import redis
import time
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

# =====================
# 🗄️ Redis 雲端資料庫連線 (永久鎖定紀錄)
# =====================
REDIS_URL = "redis://default:AY6VAAIncDFkMzVhM2FjMDgyMDA0YWI0OTBmMDI1MWViNzJhYjg5OXAxMzY1MDE@promoted-condor-36501.upstash.io:6379"

try:
    r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
    r.ping()
    print("✅ Upstash Redis 連線成功，已開啟永久鎖定模式 (預支 4 TRX)")
except Exception as e:
    r = None
    print(f"❌ Redis 連線失敗: {e}")

# =====================
# 🔧 核心參數設定
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY")
TRX_PRIVATE_KEY = os.environ.get("TRX_PRIVATE_KEY")

AUTO_PAYOUT = True       
FIXED_RATE_TRX = 3.2     
FEE_RATE = 0.05          
MIN_USDT = 5             
MAX_USDT = 100           
FUEL_AMOUNT = 4          # 已修改為 4 TRX
POLL_INTERVAL = 30       
DAILY_LIMIT = 20         

ADMIN_ID = 7757022123
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

provider = HTTPProvider(api_key=TRONGRID_API_KEY)
tron = Tron(provider)
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY)) if TRX_PRIVATE_KEY else None

# =====================
# 💾 數據存取邏輯 (永久存儲)
# =====================
def has_claimed(address, user_id):
    if not r: 
        print("🚨 資料庫未連線，為防止刷錢，暫停預支發放")
        return True 
    return r.exists(f"lock:addr:{address}") or r.exists(f"lock:user:{user_id}")

def mark_as_claimed(address, user_id):
    if r:
        r.set(f"lock:addr:{address}", "claimed")
        r.set(f"lock:user:{user_id}", "claimed")
        print(f"🔒 已永久鎖定領取紀錄：{address}")

def get_daily_count():
    if not r: return 0
    today = datetime.now().strftime("%Y-%m-%d")
    count = r.get(f"daily:count:{today}")
    return int(count) if count else 0

def incr_daily_count():
    if r:
        today = datetime.now().strftime("%Y-%m-%d")
        r.incr(f"daily:count:{today}")
        r.expire(f"daily:count:{today}", 86400)

# =====================
# 🤖 客戶端指令 (繁簡分流：客戶端簡體)
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 <b>USDT → TRX 自动兑换系统</b>\n\n"
        "🔵 <b>快速操作：</b>\n"
        "• /usdt － 获取实时汇率与收款地址\n"
        "• <b>直接发送钱包地址</b> － 预支 4 TRX 手续费\n\n"
        f"💡 <i>温馨提示：若您的钱包 TRX 余额不足无法转账，请在此直接发送您的 TRX 钱包地址，系统将为您预支 {FUEL_AMOUNT} TRX 手续费。</i>\n\n"
        f"🔴 <b>USDT → TRX 最低兑换：{MIN_USDT} USDT</b>"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rate = round(FIXED_RATE_TRX * (1 - FEE_RATE), 2)
    trx_amount = round(10 * rate, 2)
    text = (
        "💱 <b>USDT → TRX 实时汇率</b>\n\n"
        f"<b>当前汇率：</b> 1 USDT = <code>{rate}</code> TRX\n"
        f"<b>参考兑换：</b> 10 USDT ≈ <code>{trx_amount}</code> TRX\n\n"
        "📥 <b>TRC20 收款地址 (点击可复制)</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "--------------------------\n"
        "⚠️ <b>温馨提示：</b>\n"
        "转账完成后请耐心等待处理，预计 3 分钟内完成闪兑\n\n"
        "🔴若您的钱包 TRX 余额不足无法转账，请在此直接<b>发送您的 TRX 钱包地址</b>，系统将为您预支 4 TRX 手续费。"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def handle_address_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    
    if len(text) == 34 and text.startswith("T"):
        if has_claimed(text, user.id):
            await update.message.reply_text("🟡 <b>提示：您已领取过预支 TRX，请完成兑换后再领。</b>", parse_mode="HTML")
            return
            
        if get_daily_count() >= DAILY_LIMIT:
            await update.message.reply_text("🔴 <b>今日预支名额已满，请明天再试。</b>", parse_mode="HTML")
            return

        mark_as_claimed(text, user.id)

        try:
            # 發放金額已改為 4 TRX
            txn = tron.trx.transfer(HOT_WALLET_ADDRESS, text, int(FUEL_AMOUNT * 1_000_000)).build().sign(private_key)
            txn.broadcast()
            incr_daily_count()
            await update.message.reply_text(f"✅ <b>预支TRX发放成功！</b>\n\n已向您的地址发送 <code>{FUEL_AMOUNT}</code> TRX。", parse_mode="HTML")
            
            admin_msg = f"⛽ <b>【發放成功 (4 TRX)】</b>\n地址：<code>{text}</code>\n今日進度：{get_daily_count()}/{DAILY_LIMIT}"
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="HTML")
        except Exception as e:
            if r: 
                r.delete(f"lock:addr:{text}")
                r.delete(f"lock:user:{user.id}")
            await update.message.reply_text(f"❌ 发放失败: {e}", parse_mode="HTML")

# =====================
# 📋 掃描與自動出金 (管理端繁體)
# =====================
async def poll_trc20(app):
    try:
        url = f"https://api.trongrid.io/v1/accounts/{HOT_WALLET_ADDRESS}/transactions/trc20"
        headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}
        r_api = requests.get(url, headers=headers, params={"limit": 10}, timeout=10)
        data = r_api.json().get("data", [])
        
        for tx in data:
            txid = tx["transaction_id"]
            if txid in SEEN_TX or tx.get("to") != HOT_WALLET_ADDRESS: continue
            if tx["block_timestamp"] / 1000 < START_TIME: continue
            SEEN_TX.add(txid)
            
            val = float(tx["value"]) / 1_000_000
            from_addr = tx["from"]
            
            is_repaying = r.exists(f"lock:addr:{from_addr}") if r else False
            rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            raw_trx = round(val * rate, 2)
            # 這裡會根據 FUEL_AMOUNT (4) 自動扣除
            final_pay = round(raw_trx - (FUEL_AMOUNT if is_repaying else 0), 2)
            
            if val >= MIN_USDT and AUTO_PAYOUT:
                try:
                    txn = tron.trx.transfer(HOT_WALLET_ADDRESS, from_addr, int(final_pay * 1_000_000)).build().sign(private_key)
                    txn.broadcast()
                    if r: r.delete(f"lock:addr:{from_addr}")
                    status = "✅ 自動出金成功"
                except Exception as e: status = f"❌ 失敗: {e}"
            else: status = "🟡 待處理"

            msg = (f"🔔 <b>【USDT 入帳】</b>\n金額: {val} USDT\n來源: <code>{from_addr}</code>\n"
                   f"扣除預支: {'是 (4 TRX)' if is_repaying else '否'}\n實發: {final_pay} TRX\n狀態: {status}")
            await app.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="HTML")
    except Exception as e: print(f"Scan Error: {e}")

# =====================
# 🚀 啟動
# =====================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_address_message))
    
    await app.initialize(); await app.start(); await app.updater.start_polling()
    print("🤖 機器人已在 4 TRX 永久鎖定模式下啟動")
    
    while True: 
        await poll_trc20(app)
        await asyncio.sleep(POLL_INTERVAL)

SEEN_TX = set(); START_TIME = time.time()
if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Stopped")

