import os
import asyncio
import requests
import redis
import time
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

# =====================
# 🗄️ Redis 雲端資料庫連線
# =====================
REDIS_URL = "redis://default:AY6VAAIncDFkMzVhM2FjMDgyMDA0YWI0OTBmMDI1MWViNzJhYjg5OXAxMzY1MDE@promoted-condor-36501.upstash.io:6379"

try:
    r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
    r.ping()
    print("✅ Upstash Redis 連線成功 (含選單按鈕功能)")
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
FUEL_AMOUNT = 4          
POLL_INTERVAL = 30       
DAILY_LIMIT = 20         

ADMIN_ID = 7757022123
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

provider = HTTPProvider(api_key=TRONGRID_API_KEY)
tron = Tron(provider)
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY)) if TRX_PRIVATE_KEY else None

# =====================
# 💾 數據存取邏輯
# =====================
def has_claimed(address, user_id):
    if not r: return True
    return r.exists(f"lock:addr:{address}") or r.exists(f"lock:user:{user_id}")

def mark_as_claimed(address, user_id, username):
    if r:
        r.set(f"lock:addr:{address}", "claimed")
        r.set(f"lock:user:{user_id}", "claimed")
        r.set(f"who:{address}", username)

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
# 🎹 鍵盤選單設定 (參考您的圖片佈局)
# =====================
def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("✅TRX闪兑"), KeyboardButton("🕹️指令闪租")],
        [KeyboardButton("📝笔数套餐"), KeyboardButton("💥特价笔数")],
        [KeyboardButton("🔔地址监听"), KeyboardButton("🆘预支TRX")],
        [KeyboardButton("💎飞机会员"), KeyboardButton("💰纯白资收U")]
    ]
    # resize_keyboard=True 讓按鈕大小適中，one_time_keyboard=False 長期顯示
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =====================
# 🤖 客戶端指令
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 <b>USDT → TRX 自动兑换系统</b>\n\n"
        "🟢 <b>欢迎使用！请点击下方选单进行操作</b>\n\n"
        "• 点击 <b>✅TRX闪兑</b> 获取地址\n"
        "• 点击 <b>🆘预支TRX</b> 领取手续费\n\n"
        f"🔴 <b>最低兑换：{MIN_USDT} USDT</b>"
    )
    # 傳送訊息時附帶選單
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=main_menu_keyboard())

async def usdt_info(update: Update):
    rate = round(FIXED_RATE_TRX * (1 - FEE_RATE), 2)
    trx_amount = round(10 * rate, 2)
    text = (
        "💱 <b>USDT → TRX 实时汇率</b>\n\n"
        f"<b>当前汇率：</b> 1 USDT = <code>{rate}</code> TRX\n"
        f"<b>参考兑换：</b> 10 USDT ≈ <code>{trx_amount}</code> TRX\n\n"
        "📥 <b>TRC20 收款地址 (点击可复制)</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "--------------------------\n"
        "⚠️ <b>重要提示：</b>\n"
        "请务必使用<b>个人钱包</b>转账，禁止从交易所直接转账！"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())

# =====================
# 📥 處理按鈕文字與地址輸入
# =====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    username = f"@{user.username}" if user.username else f"{user.first_name}"

    # 1. 處理選單按鈕點擊
    if text == "✅TRX闪兑":
        await usdt_info(update)
        return
    elif text == "🆘预支TRX":
        await update.message.reply_text("💡 <b>请直接在此发送您的 TRX 钱包地址</b>，系统将为您预支 4 TRX 手续费。", parse_mode="HTML")
        return
    elif text in ["🕹️指令闪租", "📝笔数套餐", "💥特价笔数", "🔔地址监听", "💎飞机会员", "💰纯白资收U"]:
        await update.message.reply_text(f"🚧 <b>{text}</b> 功能暫未開放，請聯絡客服。", parse_mode="HTML")
        return

    # 2. 處理錢包地址輸入 (預支邏輯)
    if len(text) == 34 and text.startswith("T"):
        if has_claimed(text, user.id):
            await update.message.reply_text("🟡 <b>提示：您已领取过预支 TRX，请完成兑换后再领。</b>", parse_mode="HTML")
            return
        if get_daily_count() >= DAILY_LIMIT:
            await update.message.reply_text("🔴 <b>今日预支名额已满，请明天再试。</b>", parse_mode="HTML")
            return

        mark_as_claimed(text, user.id, username)

        try:
            txn = tron.trx.transfer(HOT_WALLET_ADDRESS, text, int(FUEL_AMOUNT * 1_000_000)).build().sign(private_key)
            txn.broadcast()
            incr_daily_count()
            await update.message.reply_text(f"✅ <b>预支TRX发放成功！</b>\n\n已向您的地址发送 <code>{FUEL_AMOUNT}</code> TRX。", parse_mode="HTML")
            
            admin_msg = f"⛽ <b>【發放成功】</b>\n👤 用戶：{username}\n📥 地址：<code>{text}</code>"
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="HTML")
        except Exception as e:
            if r: r.delete(f"lock:addr:{text}"); r.delete(f"lock:user:{user.id}"); r.delete(f"who:{text}")
            await update.message.reply_text(f"❌ 发放失败: {e}", parse_mode="HTML")

# =====================
# 📋 掃描邏輯 (略，與之前相同)
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
            who_claimed = r.get(f"who:{from_addr}") if r else None
            is_repaying = True if who_claimed else False
            rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            final_pay = round((val * rate) - (FUEL_AMOUNT if is_repaying else 0), 2)
            if val >= MIN_USDT and AUTO_PAYOUT:
                try:
                    txn = tron.trx.transfer(HOT_WALLET_ADDRESS, from_addr, int(final_pay * 1_000_000)).build().sign(private_key)
                    txn.broadcast()
                    if r: r.delete(f"lock:addr:{from_addr}"); r.delete(f"who:{from_addr}")
                    status = "✅ 自動出金成功"
                except Exception as e: status = f"❌ 失敗: {e}"
            else: status = "🟡 待處理"
            msg = (f"🔔 <b>【USDT 入帳】</b>\n金額: {val} U\n用戶: {who_claimed if who_claimed else '新客戶'}\n實發: {final_pay} TRX\n狀態: {status}")
            await app.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="HTML")
    except Exception as e: print(f"Scan Error: {e}")

# =====================
# 🚀 啟動
# =====================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    # 處理所有文字訊息（包含按鈕點擊）
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    await app.initialize(); await app.start(); await app.updater.start_polling()
    while True: await poll_trc20(app); await asyncio.sleep(POLL_INTERVAL)

SEEN_TX = set(); START_TIME = time.time()
if __name__ == "__main__": asyncio.run(main())
