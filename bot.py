import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =====================
# 🔧 可自行調整設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

TRC20_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

DISPLAY_USDT = 10.0     # 顯示用金額（10 USDT）
MIN_USDT = 5.0          # 最低兌換金額
FIXED_RATE_TRX = 3.2    # 固定匯率：1 USDT = 3.2 TRX
FEE_RATE = 0.05         # 手續費 5%（之後只改這行）

# =====================
# 🤖 /start
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>USDT → TRX 自動兌換機器人</b>\n\n"
        "📌 <b>使用方式</b>\n"
        "/usdt － 查看兌換報價\n\n"
        f"🔻 最低兌換金額：<b>{MIN_USDT} USDT</b>\n"
        "🌐 網路：<b>TRC20</b>\n"
        "💰 匯率：<b>固定</b>",
        parse_mode="HTML"
    )

# =====================
# 🤖 /usdt
# =====================

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    final_rate = FIXED_RATE_TRX * (1 - FEE_RATE)
    trx_amount = round(DISPLAY_USDT * final_rate, 2)

    text = (
        "💱 <b>USDT → TRX 兌換報價</b>\n\n"
        f"USDT：<b>{DISPLAY_USDT}</b>\n"
        f"可兌換 TRX：約 <b>{trx_amount}</b>\n\n"
        f"🔻 最低兌換金額：<b>{MIN_USDT} USDT</b>\n\n"
        "📥 <b>TRC20 USDT 收款地址</b>\n"
        "<i>（點擊地址即可複製）</i>\n\n"
        f"<code>{TRC20_ADDRESS}</code>\n\n"
        "⚠️ 請務必使用 <b>TRC20</b> 網路轉帳\n"
        "轉帳完成後請耐心等待處理"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# =====================
# 🚀 啟動
# =====================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN 未設定（請到 Railway Variables 設定）")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    print("✅ Bot 已啟動（穩定固定匯率版）")
    app.run_polling()

if __name__ == "__main__":
    main()
