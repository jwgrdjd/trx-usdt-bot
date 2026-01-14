import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =====================
# 🔧 可自行調整的設定
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Railway Variables 設定
RECEIVE_ADDRESS = "TTCHVb7hfcLRcE452ytBQN5PL5TXMnWEKo"

FIXED_RATE_TRX = 3.2     # 固定匯率：1 USDT = 3.2 TRX
FEE_RATE = 0.05           # 手續費 5%（之後你只改這行）
MIN_USDT = 5           # 最低兌換金額

# =====================
# 🤖 指令
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 USDT → TRX 自動兌換機器人\n\n"
        "📌 使用方式：\n"
        "/usdt － 查看兌換資訊\n\n"
        f"最低兌換金額：{MIN_USDT} USDT\n"
        "網路：TRC20\n"
        "匯率：固定"
    )

async def usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usdt_amount = MIN_USDT

    fee_trx = FIXED_RATE_TRX * FEE_RATE
    final_rate = FIXED_RATE_TRX - fee_trx
    trx_amount = round(usdt_amount * final_rate, 2)

    await update.message.reply_text(
        "💱 USDT → TRX 兌換報價\n\n"
        f"USDT：{usdt_amount}\n"
        f"可兌換 TRX：約 {trx_amount}\n\n"
        f"🔻 最低兌換金額：{MIN_USDT} USDT\n\n"
        "📥 TRC20 USDT 收款地址（可直接複製）\n"
        f"```\n{RECEIVE_ADDRESS}\n```\n"
        "⚠️ 請務必使用 TRC20 網路轉帳\n"
        "轉帳完成後請耐心等待處理"
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

    print("✅ Bot 已啟動（固定匯率模式）")
    app.run_polling()

if __name__ == "__main__":
    main()






