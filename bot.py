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
NIGHT_AUTO_ONLY = False  

# 匯率與限制
FIXED_RATE_TRX = 3.2     # 1 USDT = 3.2 TRX
FEE_RATE = 0.05          # 5% 手續費
MIN_USDT = 5             
MAX_USDT = 100           
FUEL_AMOUNT = 5          # 預支 TRX 金額
POLL_INTERVAL = 30       # 掃描間隔(秒)

ADMIN_ID = 7757022123
HOT_WALLET_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"
FUEL_DB = "fuel_status.json"

# =====================
# 🔗 Tron 初始化
# =====================
provider = HTTPProvider(api_key=TRONGRID_API_KEY)
tron = Tron(provider)
private_key = PrivateKey(bytes.fromhex(TRX_PRIVATE_KEY)) if AUTO_PAYOUT else None

# =====================
# 💾 信用數據庫操作 (支援雙重檢查)
# =====================
def get_fuel_status(address, user_id):
    if not os.path.exists(FUEL_DB): return None
    with open(FUEL_DB, "r") as f:
        try:
            data = json.load(f)
            # 同時檢查地址或 TG ID 是否在欠款清單中
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
        # 清除紀錄 (用於還款後)
        data.pop(address, None)
        data.pop(str(user_id), None)
    else:
        # 標記為欠款
        data[address] = status
        data[str(user_id)] = status
        
    with open(FUEL_DB, "w") as f: json.dump(data, f)

# =====================
# 🤖 客戶端指令 (簡體中文)
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 <b>USDT → TRX 自动兑换系统</b>\n\n"
        "本机器人为您提供 24 小时极速换汇服务。\n\n"
        "📌 <b>快速操作：</b>\n"
        "• /usdt － 获取实时汇率与收款地址\n"
        "• <b>直接发送钱包地址</b> － 领取 5 TRX 预支TRX\n\n"
        f"💡 <i>预支说明：若您的钱包余额不足，请直接贴上地址，系统将预支 {FUEL_AMOUNT} TRX 给您作为转账手续费。此款项将于您完成首次兑换时自动扣除。</i>\n\n"
        f"🔻 最低兑换：{MIN_USDT} USDT\n"
        "🌐 网络：TRON (TRC20)"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_amount = round(10 * FIXED_RATE_TRX * (1 - FEE_RATE), 2)
    text = (
        "💱 <b>USDT → TRX 实时汇率</b>\n\n"
        "USDT：10\n"
        f"可得：约 {trx_amount} TRX\n\n"
        "📥 <b>TRC20 收款地址（点击可复制）</b>\n"
        f"<code>{HOT_WALLET_ADDRESS}</code>\n\n"
        "--------------------------\n"
        "💡 <b>温馨提示：</b>\n"
        "若您的钱包 TRX 余额不足，无法进行兑换，请直接在此<b>发送您的 TRX 钱包地址</b>，系统将为您预支 5 TRX 手续费（兑换成功后自动扣回）。"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ✨ 核心功能：直接偵測地址並自動轉帳預支款
async def handle_address_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # 判斷是否為 TRON 地址格式
    if len(text) == 34 and text.startswith("T"):
        addr = text
        if get_fuel_status(addr, user_id) == "pending":
            await update.message.reply_text("⚠️ 系统检测到您已领取过预支TRX，请完成一次兑换以解除锁定。")
            return
        try:
            # 執行轉帳
            txn = tron.trx.transfer(HOT_WALLET_ADDRESS, addr, int(FUEL_AMOUNT * 1_000_000)).build().sign(private_key)
            txn.broadcast()
            
            # 紀錄借款狀態
            update_fuel_status(addr, user_id, "pending")
            
            await update.message.reply_text(
                f"✅ <b>预支TRX发放成功！</b>\n\n"
                f"已向您的地址发送 {FUEL_AMOUNT} TRX。\n"
                "该笔预支将在您完成兑换时自动扣回。",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"發放預支失敗: {e}")
            await update.message.reply_text("❌ 发放失败，请联系管理员。")

# =====================
# 📋 管理員指令 (繁體中文)
# =====================
async def pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not os.path.exists(FUEL_DB):
        await update.message.reply_text("目前沒有借款紀錄。")
        return
    with open(FUEL_DB, "r") as f:
        try: data = json.load(f)
        except: data = {}
    # 過濾出 pending 狀態的項目
    p_list = [f"<code>{k}</code>" for k, v in data.items() if v == "pending"]
    if not p_list:
        await update.message.reply_text("✅ 目前沒有未歸還的借款。")
        return
    await update.message.reply_text(f"📋 <b>未歸還清單 (地址與ID)：</b>\n\n" + "\n".join(p_list), parse_mode="HTML")

# =====================
# 🔍 核心監聽邏輯 (維持繁體管理通知)
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
            
            # 匯率計算
            rate = FIXED_RATE_TRX * (1 - FEE_RATE)
            raw_trx_amount = round(usdt_amount * rate, 2)
            
            # 檢查預支狀態 (僅能透過地址匹配)
            is_repaying = (get_fuel_status(from_addr, "DUMMY_ID") == "pending")
            loan_text = f"有 (需扣除 {FUEL_AMOUNT} TRX)" if is_repaying else "無"
            final_pay = round(raw_trx_amount - (FUEL_AMOUNT if is_repaying else 0), 2)

            # 判定是否符合自動出金
            auto_ok = AUTO_PAYOUT and (MIN_USDT <= usdt_amount <= MAX_USDT)
            
            status_display = "🟡 待人工處理"
            if auto_ok:
                try:
                    # 執行出金
                    txn = tron.trx.transfer(HOT_WALLET_ADDRESS, from_addr, int(final_pay * 1_000_000)).build().sign(private_key)
                    txn.broadcast()
                    
                    # 出金成功後清除信用紀錄 (解鎖 ID 與 地址)
                    if is_repaying:
                        update_fuel_status(from_addr, "CLEAN_ID", None)
                    
                    status_display = "✅ <b>已自動出金</b>"
                except Exception as e:
                    status_display = f"❌ <b>自動出金失敗</b>：{str(e)}"

            # 發送詳細通知給管理員
            msg = (
                "🔔 <b>USDT 入帳通知</b>\n\n"
                f"<b>金額</b>：{usdt_amount} USDT\n"
                f"<b>來源</b>：<code>{from_addr}</code>\n"
                "--------------------------\n"
                f"<b>應付總計</b>：{raw_trx_amount} TRX\n"
                f"<b>有無預支</b>：{loan_text}\n"
                f"<b>扣除後應發</b>：<u>{final_pay} TRX</u>\n"
                "--------------------------\n"
                f"<b>狀態</b>：{status_display}"
            )
            await app.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="HTML")
            
    except Exception as e:
        print(f"監聽掃描出錯: {e}")

# =====================
# 🚀 啟動邏輯
# =====================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 指令處理
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))
    app.add_handler(CommandHandler("pending", pending_list))
    
    # 訊息監聽 (判斷地址)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_address_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    print(f"🤖 Bot 已啟動 | 語言分流模式 | 自動出金: {AUTO_PAYOUT}")

    try:
        while True:
            await poll_trc20(app)
            await asyncio.sleep(POLL_INTERVAL)
    finally:
        if app.updater.running: await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("機器人已停止")
