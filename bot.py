import asyncio
import random
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from supabase import create_client
from dotenv import load_dotenv

# ================= تنظیمات =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= توابع کمکی =================
def get_player(chat_id, user_id):
    res = supabase.table("players").select("*").eq("chat_id", chat_id).eq("user_id", user_id).execute()
    if not res.data:
        supabase.table("players").insert({"chat_id": chat_id, "user_id": user_id}).execute()
        return {"size": 10, "crowns": 0, "nickname": None, "wins": 0, "losses": 0}
    return res.data[0]

def is_owner(user_id):
    return user_id == OWNER_ID

# ================= دستورات اصلی =================

# 1. رشد روزانه
@dp.message(Command("grow"))
async def cmd_grow(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    get_player(chat_id, user_id) # اطمینان از وجود کاربر
    
    try:
        res = supabase.rpc("daily_grow", {"p_chat": chat_id, "p_user": user_id}).execute().data
    except Exception as e:
        await message.reply(f"خطا در دیتابیس: {str(e)}")
        return
    
    if res['status'] == 'wait':
        await message.reply(res['msg'])
        return
        
    change = res['change']
    new_size = res['new_size']
    
    if res['crown']:
        await message.reply(f"👑 **باااام!** شما به سایز 1000 رسیدید و یک جام گرفتید! سایز شما ریست شد.")
    else:
        if change > 0:
            await message.reply(f"📈 سایز شما **{change}+** افزایش یافت. (سایز فعلی: {new_size})")
        else:
            await message.reply(f"📉 بدشانسی! سایز شما **{change}** کاهش یافت. (سایز فعلی: {new_size})")

# 2. جدول طول
@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    chat_id = message.chat.id
    res = supabase.table("players").select("*").eq("chat_id", chat_id).order("size", desc=True).limit(10).execute()
    
    if not res.data:
        await message.reply("هنوز کسی در این گروه بازی نکرده است!")
        return
        
    text = "🏆 **جدول ۱۰ نفر برتر گروه:**\n\n"
    for i, p in enumerate(res.data, 1):
        try:
            member = await bot.get_chat_member(chat_id, p['user_id'])
            name = member.user.first_name
        except:
            name = "ناشناس"
            
        nickname = f" [{p['nickname']}]" if p['nickname'] else ""
        crown = " 👑" if p['crowns'] > 0 else ""
        text += f"{i}. {name}{nickname}{crown} : `{p['size']}`\n"
        
    await message.reply(text)

# 3. آمار
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    p = get_player(chat_id, user_id)
    
    text = (f"📊 **آمار شما:**\n\n"
            f"📏 سایز فعلی: `{p['size']}`\n"
            f"👑 جام‌ها: `{p['crowns']}`\n"
            f"⚔️ برد: `{p['wins']}` | باخت: `{p['losses']}`\n")
    if p['nickname']:
        text += f"🏷 لقب شما: {p['nickname']}\n"
        
    await message.reply(text)

# 4. مبارزه PVP
@dp.message(Command("pvp"))
async def cmd_pvp(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.reply("فرمت صحیح: `/pvp 50` (عدد باید سایز شرط باشد)")
        return
        
    amount = int(args[1])
    if amount <= 0:
        await message.reply("عدد باید بزرگتر از صفر باشد.")
        return
        
    me = get_player(chat_id, user_id)
    
    # پیدا کردن حریف تصادفی (به جز خودم)
    res = supabase.table("players").select("*").eq("chat_id", chat_id).neq("user_id", user_id).execute()
    if not res.data:
        await message.reply("حریفی برای مبارزه پیدا نشد! (حداقل باید 2 نفر در گروه بازی کرده باشند)")
        return
        
    opponent = random.choice(res.data)
    
    # تعیین شانسی برنده (وزن‌دار: هر کی سایز بیشتر، شانس بیشتر)
    if me['size'] <= 0: me_size_for_calc = 1
    else: me_size_for_calc = me['size']
    
    if opponent['size'] <= 0: opp_size_for_calc = 1
    else: opp_size_for_calc = opponent['size']
    
    chance = me_size_for_calc / (me_size_for_calc + opp_size_for_calc)
    is_winner = random.random() < chance
    
    winner_id = user_id if is_winner else opponent['user_id']
    loser_id = opponent['user_id'] if is_winner else user_id
    
    # اجرای مبارزه در دیتابیس
    try:
        fight_res = supabase.rpc("fight", {
            "p_chat": chat_id, "p_winner": winner_id, "p_loser": loser_id, "p_amount": amount
        }).execute().data
    except Exception as e:
        await message.reply(f"خطا در مبارزه: {str(e)}")
        return
        
    winner_name = "شما" if is_winner else "حریف"
    
    text = f"⚔️ **مبارزه!**\n\n"
    text += f"برنده: {winner_name} (+{amount})\n"
    text += f"بازنده: {'حریف' if is_winner else 'شما'} (-{amount})\n"
    
    if fight_res.get('w_crown'):
        text += f"\n👑 **{winner_name} به 1000 رسید و یک جام گرفت!**"
        
    await message.reply(text)

# 5. درخواست وام
@dp.message(Command("loan"))
async def cmd_loan(message: types.Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.reply("فرمت صحیح: `/loan 100` (مبلغ درخواستی)")
        return
    amount = int(args[1])
    if amount <= 0:
        await message.reply("مبلغ باید بزرگتر از صفر باشد.")
        return
        
    text = f"🤝 **درخواست وام**\n\n"
    text += f"کاربر {message.from_user.first_name} مبلغ **{amount}** سایز درخواست کرده است.\n"
    text += f"برای پیشنهاد سود و قبول وام، از دستور زیر استفاده کنید:\n"
    text += f"`/offer {amount} 5` (مثلاً 5 درصد سود)"
    
    await message.reply(text)

# 6. پیشنهاد وام (Offer)
@dp.message(Command("offer"))
async def cmd_offer(message: types.Message):
    args = message.text.split()
    if len(args) < 3 or not args[1].isdigit() or not args[2].isdigit():
        await message.reply("فرمت صحیح: `/offer 100 5` (مبلغ و درصد سود)")
        return
        
    amount = int(args[1])
    interest = int(args[2])
    lender_id = message.from_user.id
    chat_id = message.chat.id
    
    # پیدا کردن آخرین درخواست وام تایید نشده در گروه
    res = supabase.table("loans").select("*").eq("chat_id", chat_id).eq("amount", amount).eq("status", "pending").execute()
    
    if not res.data:
        await message.reply("درخواست وامی با این مبلغ پیدا نشد.")
        return
        
    loan = res.data[0]
    borrower_id = loan['borrower_id']
    
    if borrower_id == lender_id:
        await message.reply("شما نمی‌توانید به خودتان وام بدهید!")
        return
        
    # چک کردن موجودی وام دهنده
    lender = get_player(chat_id, lender_id)
    if lender['size'] < amount:
        await message.reply("شما سایز کافی برای این وام ندارید!")
        return
        
    # قبول وام
    try:
        supabase.table("loans").update({
            "lender_id": lender_id, 
            "interest_rate": interest,
            "due_at": (datetime.now() + timedelta(days=3)).isoformat(),
            "status": "accepted"
        }).eq("id", loan['id']).execute()
        
        # جابجایی سایز
        supabase.rpc("transfer_size", {"p_chat": chat_id, "p_from": lender_id, "p_to": borrower_id, "p_amount": amount}).execute()
    except Exception as e:
        await message.reply(f"خطا در تایید وام: {str(e)}")
        return
    
    await message.reply(f"✅ وام **{amount}** با سود **{interest}%** تایید شد! مبلغ به حساب وام‌گیرنده واریز شد.")

# 7. فصل و جام‌ها
@dp.message(Command("season"))
async def cmd_season(message: types.Message):
    chat_id = message.chat.id
    res = supabase.table("players").select("*").eq("chat_id", chat_id).order("crowns", desc=True).limit(10).execute()
    
    text = "👑 **جدول قهرمانان (جام‌داران):**\n\n"
    has_crowns = False
    for i, p in enumerate(res.data, 1):
        if p['crowns'] > 0:
            has_crowns = True
            try:
                member = await bot.get_chat_member(chat_id, p['user_id'])
                name = member.user.first_name
            except:
                name = "ناشناس"
            text += f"{i}. {name} : {p['crowns']} جام 👑\n"
            
    if not has_crowns:
        text += "هنوز کسی جام نگرفته است!"
        
    await message.reply(text)

# 8. راهنما
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📖 **راهنمای ربات:**\n\n"
        "/grow - رشد روزانه (شانسی)\n"
        "/top - جدول 10 نفر برتر\n"
        "/stats - آمار شخصی شما\n"
        "/pvp [عدد] - مبارزه با یک حریف تصادفی (مثلاً /pvp 50)\n"
        "/loan [عدد] - درخواست وام\n"
        "/offer [مبلغ] [سود] - قبول وام کسی (مثلاً /offer 100 5)\n"
        "/season - جدول جام‌داران\n"
    )
    if is_owner(message.from_user.id):
        text += "\n👑 **دستورات سازنده:**\n"
        text += "/setsize [آیدی] [عدد] - تغییر سایز\n"
        text += "/setnick [آیدی] [لقب] - تنظیم لقب"
    await message.reply(text)

# ================= دستورات مخفی سازنده =================
@dp.message(Command("setsize"))
async def cmd_setsize(message: types.Message):
    if not is_owner(message.from_user.id): return
    args = message.text.split()
    if len(args) < 3: 
        await message.reply("فرمت: `/setsize 12345678 500`")
        return
    try:
        target_id = int(args[1])
        new_size = int(args[2])
        supabase.table("players").update({"size": new_size}).eq("chat_id", message.chat.id).eq("user_id", target_id).execute()
        await message.reply("✅ سایز کاربر تغییر کرد.")
    except:
        await message.reply("فرمت اشتباه است.")

@dp.message(Command("setnick"))
async def cmd_setnick(message: types.Message):
    if not is_owner(message.from_user.id): return
    args = message.text.split(maxsplit=2)
    if len(args) < 3: 
        await message.reply("فرمت: `/setnick 12345678 لقب_جدید`")
        return
    try:
        target_id = int(args[1])
        nick = args[2]
        supabase.table("players").update({"nickname": nick}).eq("chat_id", message.chat.id).eq("user_id", target_id).execute()
        await message.reply("✅ لقب تنظیم شد.")
    except:
        await message.reply("فرمت اشتباه است.")

# ================= اجرای ربات =================
async def main():
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
