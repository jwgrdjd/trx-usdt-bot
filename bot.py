import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =====================
# 🔧 基本設定（只改這裡）
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Railway Variables 裡設定
RECEIVE_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_TRX_PRICE = 0.315   # 1 TRX = 0.315 USDT（固定匯率）
FEE_RATE = 0.05           # 5% 手續費
MIN_USDT = 5.0            # 最低兌換金額

# =====================
# 🤖 指令處理
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查詢兌換說明\n\n"
        f"最低兌換金額：{MIN_USDT} USDT\n"
        "網路：TRC20"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usdt_amount = MIN_USDT

    trx_amount = (usdt_amount / FIXED_TRX_PRICE) * (1 - FEE_RATE)
    trx_amount = round(trx_amount, 2)

    await update.message.reply_text(
        "💱 USDT → TRX 兌換\n\n"
        f"🔒 固定匯率：\n"
        f"1 TRX = {FIXED_TRX_PRICE} USDT（含 5% 手續費）\n\n"
        f"最低兌換金額：{MIN_USDT} USDT\n\n"
        "📥 TRC20 USDT 收款地址（可直接複製）\n"
        f"{RECEIVE_ADDRESS}\n\n"
        "📌 兌換說明：\n"
        "・系統採固定匯率計算\n"
        "・實際發送 TRX 以「實際入帳 USDT」為準\n"
        "・請務必使用 TRC20 網路\n\n"
        "轉帳完成後請耐心等待處理"
    )

# =====================
# 🚀 啟動 Bot
# =====================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN 未設定（請到 Railway Variables 設定）")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usdt", usdt))

    print("✅ Bot 已啟動（固定匯率模式）")
    app.run_polling()

if __name__ == "__main__":
    main()
