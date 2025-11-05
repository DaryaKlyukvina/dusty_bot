import asyncio
from collections import defaultdict
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo
)
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()  

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMINS = list(map(int, os.getenv("ADMINS").split(",")))

print(f"Loaded config:\nCHANNEL_ID={CHANNEL_ID}\nADMINS={ADMINS}\nTOKEN={bool(API_TOKEN)}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

SIGNATURE = ". ₊ ⊹ .  ⟡  . ⊹ ₊ .\n\n🧶 написать тейк можно сюда\n╰┈➤  @DustyStillage_Bot ˎˊ˗"
pending_actions = {}

# временное хранилище для альбомов
albums_buffer = defaultdict(list)

# ================== Старт ==================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Приветик! 🧶\nЭто предложка Пыльного Стеллажа, отправь мне свой тейк — я передам это модераторам.\n\nНе забудь о правильном хештеге в конце и мы опубликуем тейк быстрее. Если не были нарушены правила, публикация займет до 2х суток.")

# ================== Обработка текста от админа ==================
@dp.message(F.text)
async def handle_admin_text(message: types.Message):
    if message.from_user.id not in pending_actions:
        return

    action_data = pending_actions.pop(message.from_user.id)
    action = action_data[0]

    if action == "edit":
        user_id, msg_id = action_data[1], action_data[2]
        await bot.send_message(CHANNEL_ID, message.text + "\n\n" + SIGNATURE)
        await message.answer("✅ Опубликовано с редактированием")
        await bot.send_message(user_id, "✅ Ваше предложение опубликовано с редактированием!")

    elif action == "reply":
        user_id = action_data[1]
        await bot.send_message(user_id, f"💬 Ответ от администратора:\n\n{message.text}")
        await message.answer("✅ Сообщение отправлено пользователю")

# ================== Пользовательские сообщения ==================
@dp.message
async def proposal_handler(message: types.Message):
    # Если это админ и он сейчас отвечает/редактирует -> пропускаем
    if message.from_user.id in ADMINS and message.from_user.id in pending_actions:
        return

    user_id = message.from_user.id

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"approve:{user_id}:{message.message_id}"),
        InlineKeyboardButton(text="✏ Редактировать", callback_data=f"edit:{user_id}:{message.message_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{user_id}:{message.message_id}"),
        InlineKeyboardButton(text="💬 Ответить пользователю", callback_data=f"reply:{user_id}:{message.message_id}")
    ]])

    if message.media_group_id:
        # это часть альбома
        albums_buffer[message.media_group_id].append((message, kb))
        await asyncio.sleep(0.5)

        if albums_buffer.get(message.media_group_id):
            msgs = albums_buffer.pop(message.media_group_id)
            media = []
            for i, (msg, _) in enumerate(msgs):
                if msg.photo:
                    media.append(InputMediaPhoto(media=msg.photo[-1].file_id,
                                                 caption=msg.caption if i == 0 else None))
                elif msg.video:
                    media.append(InputMediaVideo(media=msg.video.file_id,
                                                 caption=msg.caption if i == 0 else None))

            for admin in ADMINS:
                await bot.send_media_group(admin, media)
                await bot.send_message(admin, f"📌 Модерация альбома от @{message.from_user.username or user_id}", reply_markup=kb)

            # сохраняем альбом для публикации
            pending_actions[f"album:{user_id}:{message.media_group_id}"] = media

    else:
        # одиночное сообщение
        for admin in ADMINS:
            if message.text:
                await bot.send_message(admin, message.text)
            elif message.photo:
                await bot.send_photo(admin, message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                await bot.send_video(admin, message.video.file_id, caption=message.caption)
            elif message.document:
                await bot.send_document(admin, message.document.file_id, caption=message.caption)
            elif message.audio:
                await bot.send_audio(admin, message.audio.file_id, caption=message.caption)

            await bot.send_message(admin, f"📌 Модерация предложения от @{message.from_user.username or user_id}", reply_markup=kb)

    await message.answer("Твой тейк отправлен на модерацию\nദ്ദി(˵ •̀ ⩊ - ˵ ) ✧")

# ================== Модерация админов ==================
@dp.callback_query(F.data.startswith(("approve", "reject", "edit", "reply")))
async def moderation_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("Ты не админ!", show_alert=True)
        return

    action, user_id, msg_id = callback.data.split(":")
    user_id, msg_id = int(user_id), int(msg_id)

    if action == "approve":
        try:
            # проверяем, альбом ли это
            album_key = f"album:{user_id}:{msg_id}"
            if album_key in pending_actions:
                media = pending_actions.pop(album_key)
                # добавляем подпись + SIGNATURE к первому элементу
                if media and media[0].caption:
                    media[0].caption += "\n\n" + SIGNATURE
                elif media:
                    media[0].caption = SIGNATURE
                await bot.send_media_group(CHANNEL_ID, media)

            else:
                # одиночное сообщение
                orig_msg = await bot.forward_message(chat_id=callback.from_user.id, from_chat_id=user_id, message_id=msg_id)
                await orig_msg.delete()

                if orig_msg.text:
                    await bot.send_message(CHANNEL_ID, orig_msg.text + "\n\n" + SIGNATURE)
                elif orig_msg.photo:
                    await bot.send_photo(CHANNEL_ID, orig_msg.photo[-1].file_id, caption=(orig_msg.caption or "") + "\n\n" + SIGNATURE)
                elif orig_msg.video:
                    await bot.send_video(CHANNEL_ID, orig_msg.video.file_id, caption=(orig_msg.caption or "") + "\n\n" + SIGNATURE)
                elif orig_msg.document:
                    await bot.send_document(CHANNEL_ID, orig_msg.document.file_id, caption=(orig_msg.caption or "") + "\n\n" + SIGNATURE)
                elif orig_msg.audio:
                    await bot.send_audio(CHANNEL_ID, orig_msg.audio.file_id, caption=(orig_msg.caption or "") + "\n\n" + SIGNATURE)

        except Exception as e:
            await callback.message.answer(f"Ошибка при публикации: {e}")

        await callback.message.edit_text("✅ Опубликовано админом")
        await callback.answer("Опубликовано")
        await bot.send_message(user_id, "✅ Ваше предложение опубликовано!")

    elif action == "reject":
        await callback.message.edit_text("❌ Отклонено админом")
        await callback.answer("Отклонено")
        await bot.send_message(user_id, "❌ Ваше предложение отклонено")

    elif action == "edit":
        pending_actions[callback.from_user.id] = ("edit", user_id, msg_id)
        await callback.message.answer("✏ Отправьте новый текст для публикации")
        await callback.answer()

    elif action == "reply":
        pending_actions[callback.from_user.id] = ("reply", user_id)
        await callback.message.answer("💬 Напишите сообщение пользователю:")
        await callback.answer()

# ================== Настройка подписи ==================
@dp.message(Command("set_signature"))
async def set_signature(message: types.Message):
    global SIGNATURE
    if message.from_user.id not in ADMINS:
        return await message.answer("У тебя нет прав!")

    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        return await message.answer("Используй: /set_signature новый_текст (можно с переносами)")

    SIGNATURE = parts[1]
    await message.answer(f"✍ Новая подпись установлена:\n\n{SIGNATURE}")

# ================== Добавление нового админа ==================
@dp.message(Command("add_admin"))
async def add_admin(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("У тебя нет прав!")

    parts = message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Используй: /add_admin user_id")

    new_admin_id = int(parts[1])
    if new_admin_id not in ADMINS:
        ADMINS.append(new_admin_id)
        await message.answer(f"✅ Новый админ добавлен: {new_admin_id}")
    else:
        await message.answer("Этот пользователь уже админ!")

# ================== Просмотр списка админов ==================
@dp.message(Command("list_admins"))
async def list_admins(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("У тебя нет прав!")

    if not ADMINS:
        await message.answer("Список админов пуст.")
    else:
        text = "👑 Список админов:\n" + "\n".join([str(a) for a in ADMINS])
        await message.answer(text)

# ================== Удаление админа ==================
@dp.message(Command("remove_admin"))
async def remove_admin(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("У тебя нет прав!")

    parts = message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Используй: /remove_admin user_id")

    remove_admin_id = int(parts[1])
    if remove_admin_id in ADMINS:
        ADMINS.remove(remove_admin_id)
        await message.answer(f"✅ Админ удалён: {remove_admin_id}")
    else:
        await message.answer("Такого админа нет в списке!")

# ================== Запуск бота ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())






