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
# 🗄️ Redis 雲端資料庫連線 (解決更新重置問題)
# =====================
REDIS_URL = "redis://default:AY6VAAIncDFkMzVhM2FjMDgyMDA0YWI0OTBmMDI1MWViNzJhYjg5OXAxMzY1MDE@promoted-condor-36501.upstash.io:6379"

try:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    print("✅ 成功連線到 Upstash Redis 雲端資料庫")
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
FUEL_AMOUNT = 5          
POLL_INTERVAL = 30       
DAILY_LIMIT = 20         

ADMIN_ID = 7757022123
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

provider = HTTPProvider(api_key=TRONGRID_API_KEY)
tron = Tron(provider)
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY)) if AUTO_PAYOUT else None

# =====================
# 💾 Redis 數據存取邏輯
# =====================
def has_claimed(address, user_id):
    if not r: return False
    return r.exists(f"claimed_addr:{address}") or r.exists(f"claimed_user:{user_id}")

def mark_as_claimed(address, user_id):
    if r:
        r.set(f"claimed_addr:{address}", "pending")
        r.set(f"claimed_user:{user_id}", "pending")

def get_daily_count():
    if not r: return 0
    today = datetime.now().strftime("%Y-%m-%d")
    count = r.get(f"daily_count:{today}")
    return int(count) if count else 0

def incr_daily_count():
    if r:
        today = datetime.now().strftime("%Y-%m-%d")
        r.incr(f"daily_count:{today}")
        r.expire(f"daily_count:{today}", 100000)

def remove_claim(address, user_id):
    if r:
        r.delete(f"claimed_addr:{address}")
        r.delete(f"user:{user_id}")

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
    rate = round(FIXED_RATE_TRX * (1 - FEE_RATE), 2)
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)
    text = (
        "💱 <b>USDT → TRX 实时汇率</b>\n\n"
        "<b>当前汇率：</b> 1 USDT = <code>" + str(round(FIXED_RATE_TRX * (1-FEE_RATE), 2)) + "</code> TRX\n"
        f"<b>参考兑换：</b> 10 USDT ≈ <code>{trx_amount}</code> TRX\n\n"
        "📥 <b>TRC20 收款地址 (点击可复制)</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "--------------------------\n"
        "⚠️ <b>温馨提示：</b>\n"
        "转账完成后请耐心等待处理，预计 3 分钟内完成闪兑\n"
        "若您的钱包 TRX 余额不足无法转账，请在此直接<b>发送您的 TRX 钱包地址</b>，系统将为您预支 5 TRX 手续费。"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def handle_address_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    
    if len(text) == 34 and text.startswith("T"):
        # 1. 向 Redis 查詢 (簡體回覆客人)
        if has_claimed(text, user.id):
            await update.message.reply_text("🟡 <b>提示：您已领取过预支 TRX，请完成兑换后再领。</b>", parse_mode="HTML")
            return
            
        if get_daily_count() >= DAILY_LIMIT:
            await update.message.reply_text("🔴 <b>今日预支名额已满，请明天再试。</b>", parse_mode="HTML")
            return

        # 鎖定紀錄
        mark_as_claimed(text, user.id)

        try:
            # 2. 執行發送
            txn = tron.trx.transfer(HOT_WALLET_ADDRESS, text, int(FUEL_AMOUNT * 1_000_000)).build().sign(private_key)
            txn.broadcast()
            
            incr_daily_count()
            # 簡體通知客人
            await update.message.reply_text(f"✅ <b>预支TRX发放成功！</b>\n\n已向您的地址发送 <code>{FUEL_AMOUNT}</code> TRX。", parse_mode="HTML")
            
            # 繁體通知管理員
            admin_notice = (
                "⛽ <b>【發放通知】</b>\n\n"
                f"👤 <b>用戶 ID：</b> <code>{user.id}</code>\n"
                f"📥 <b>錢包地址：</b> <code>{text}</code>\n"
                f"📊 <b>今日進度：</b> {get_daily_count()} / {DAILY_LIMIT}"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notice, parse_mode="HTML")

        except Exception as e:
            remove_claim(text, user.id)
            await update.message.reply_text("❌ <b>发放失败，请联系客服处理。</b>", parse_mode="HTML")

# =====================
# 📋 管理員通知邏輯 (繁體中文)
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
            
            # 檢查是否有預支紀錄
            is_repaying = False
            if r and r.exists(f"claimed_addr:{from_addr}"):
                is_repaying = True

            rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            raw_trx = round(val * rate, 2)
            final_pay = round(raw_trx - (FUEL_AMOUNT if is_repaying else 0), 2)
            
            if val >= MIN_USDT and AUTO_PAYOUT:
                try:
                    txn = tron.trx.transfer(HOT_WALLET_ADDRESS, from_addr, int(final_pay * 1_000_000)).build().sign(private_key)
                    txn.broadcast()
                    if is_repaying: remove_claim(from_addr, "UNKNOWN")
                    status = "✅ <b>自動出金成功</b>"
                except Exception as e: status = f"❌ <b>失敗: {e}</b>"
            else: status = "🟡 <b>待人工處理</b>"

            # 繁體通知管理員
            msg = (f"🔔 <b>【USDT 入帳通知】</b>\n\n"
                   f"💰 金額: <code>{val}</code> USDT\n"
                   f"👤 來源:
