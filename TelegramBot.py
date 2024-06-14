import asyncio
import logging
import aiosqlite
import json
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)

# Замените "YOUR_BOT_TOKEN" на токен, который вы получили от BotFather
API_TOKEN = ''
# Имя БД
DB_NAME = 'quiz_bot.db'
# Имя файла с вопросами квиза
QUIZ_DATA = 'QuizData.json'
# Объект бота
bot = Bot(token=API_TOKEN)
# Ответы пользователя
responses = ""


# Диспетчер
dp = Dispatcher()

# Получение данных квиза из файла
with open(os.path.dirname(os.path.abspath(__file__)) + '\\' + QUIZ_DATA, encoding='utf-8') as f:
    quiz_data = json.load(f)


async def create_table():
    # Создаем соединение с базой данных (если она не существует, то она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Выполняем SQL-запрос к базе данных
        await db.execute('CREATE TABLE IF NOT EXISTS quiz_state (user_id INTEGER PRIMARY KEY, question_index INTEGER)')

        await db.execute('CREATE TABLE IF NOT EXISTS quiz_results (user_id INTEGER PRIMARY KEY, responses INTEGER)')
        # Сохраняем изменения
        await db.commit()

async def update_quiz_index(user_id, index):
    # Создаем соединение с базой данных (если она не существует, она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Вставляем новую запись или заменяем ее, если с данным user_id уже существует
        await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, question_index) VALUES (?, ?)', (user_id, index))
        # Сохраняем изменения
        await db.commit()

async def update_quiz_result(user_id, responses):
    # Создаем соединение с базой данных (если она не существует, она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Вставляем новую запись или заменяем ее, если с данным user_id уже существует
        await db.execute('INSERT OR REPLACE INTO quiz_results (user_id, responses) VALUES (?, ?)', (user_id, responses))
        # Сохраняем изменения
        await db.commit()

async def get_quiz_index(user_id):
     # Подключаемся к базе данных
     async with aiosqlite.connect(DB_NAME) as db:
        # Получаем запись для заданного пользователя
        async with db.execute('SELECT question_index FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            # Возвращаем результат
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0

async def get_quiz_result(user_id):
     # Подключаемся к базе данных
     async with aiosqlite.connect(DB_NAME) as db:
        # Получаем запись для заданного пользователя
        async with db.execute('SELECT responses FROM quiz_results WHERE user_id = (?)', (user_id, )) as cursor:
            # Возвращаем результат
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0

async def new_quiz(message):
    # получаем id пользователя, отправившего сообщение
    user_id = message.from_user.id

    # сбрасываем счёт квиза
    await quiz_result(0, "new")

    # сбрасываем значение текущего индекса вопроса квиза в 0
    current_question_index = 0
    await update_quiz_index(user_id, current_question_index)

    # запрашиваем новый вопрос для квиза
    await get_question(message, user_id)

async def quiz_results(user_id, score):
    # Создаем соединение с базой данных (если она не существует, она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Вставляем новую запись или заменяем ее, если с данным user_id уже существует
        await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, last_score) VALUES (?, ?)', (user_id, last_score))
        # Сохраняем изменения
        await db.commit()

async def quiz_result(number, extra):
    global responses
    # Если был переданн new то обнуляем ответы
    if extra == "new":
        responses = ""
    # Если был переданн plus то добавляем переданный ответ
    elif extra == "plus":
        responses = responses + str(number)

async def get_question(message, user_id):
    
    # Запрашиваем из базы текущий индекс для вопроса
    current_question_index = await get_quiz_index(user_id)
    # Получаем индекс правильного ответа для текущего вопроса
    correct_index = quiz_data[current_question_index]['correct_option']
    # Получаем список вариантов ответа для текущего вопроса
    opts = quiz_data[current_question_index]['options']

    # Функция генерации кнопок для текущего вопроса квиза
    # В качестве аргументов передаем варианты ответов и значение правильного ответа (не индекс!)
    kb = generate_options_keyboard(opts, opts[correct_index])
    # Отправляем в чат сообщение с вопросом, прикрепляем сгенерированные кнопки
    await message.answer(f"{quiz_data[current_question_index]['question']}", reply_markup=kb)

def generate_options_keyboard(answer_options, right_answer):
  # Создаем сборщика клавиатур типа Inline
    builder = InlineKeyboardBuilder()
    question_number = 0
    # В цикле создаем 4 Inline кнопки, а точнее Callback-кнопки
    for option in answer_options:
        builder.add(types.InlineKeyboardButton(
            # Текст на кнопках соответствует вариантам ответов
            text = option,
            # Присваиваем данные для колбэк запроса.
            # Если ответ верный сформируется колбэк-запрос с данными 'r_a'
            # Если ответ неверный сформируется колбэк-запрос с данными 'w_a'
            callback_data = option + "@" + str(question_number) + "@" + "r_a" if option == right_answer else option + "@" + str(question_number) + "@" + "w_a")
        )
        question_number += 1

    question_number = 0
    # Выводим по одной кнопке в столбик
    builder.adjust(1)
    return builder.as_markup()

# Хэндлер на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем сборщика клавиатур типа Reply
    builder = ReplyKeyboardBuilder()
    # Добавляем в сборщик одну кнопку
    builder.add(types.KeyboardButton(text="Начать игру"))
    # Прикрепляем кнопки к сообщению
    await message.answer("Добро пожаловать в квиз!", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.callback_query(F.data.contains("r_a"))
async def right_answer(callback: types.CallbackQuery):
    # редактируем текущее сообщение с целью убрать кнопки (reply_markup=None)
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )

    # Получение текущего вопроса для данного пользователя
    current_question_index = await get_quiz_index(callback.from_user.id)
    
    await callback.message.answer("Ваш ответ: " + callback.data.rsplit('@')[0])
    # Отправляем в чат сообщение, что ответ верный
    await callback.message.answer("Верно!")

    # Обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index)

    await quiz_result(callback.data.rsplit('@')[1], "plus")

    # Проверяем достигнут ли конец квиза
    if current_question_index < len(quiz_data):
        # Следующий вопрос
        await get_question(callback.message, callback.from_user.id)
    else:
        
        # Запись результатов квиза
        global responses
        await update_quiz_result(callback.from_user.id, responses)
        # Уведомление об окончании квиза
        await callback.message.answer("Это был последний вопрос. Квиз завершен!")
        

@dp.callback_query(F.data.contains("w_a"))
async def wrong_answer(callback: types.CallbackQuery):
    # редактируем текущее сообщение с целью убрать кнопки (reply_markup=None)
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )

    # Получение текущего вопроса для данного пользователя
    current_question_index = await get_quiz_index(callback.from_user.id)

    correct_option = quiz_data[current_question_index]['correct_option']

    await callback.message.answer("Ваш ответ: " + callback.data.rsplit('@')[0])
    # Отправляем в чат сообщение об ошибке с указанием верного ответа
    await callback.message.answer(f"Неправильно. Правильный ответ: {quiz_data[current_question_index]['options'][correct_option]}")

    # Обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index)

    

    await quiz_result(callback.data.rsplit('@')[1], "plus")

    # Проверяем достигнут ли конец квиза
    if current_question_index < len(quiz_data):
        # Следующий вопрос
        await get_question(callback.message, callback.from_user.id)
    else:
        global responses
        # Запись результатов квиза
        await update_quiz_result(callback.from_user.id, responses)
        # Уведомление об окончании квиза
        await callback.message.answer("Это был последний вопрос. Квиз завершен!")

# Хэндлер на команды /quiz
@dp.message(F.text=="Начать игру")
@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message):
    # Отправляем новое сообщение без кнопок
    await message.answer(f"Давайте начнем квиз!")
    # Запускаем новый квиз
    await new_quiz(message)

@dp.message(Command("result"))
async def cmd_result(message: types.Message):
    
    user_id = message.from_user.id
    
    # Получаем прошлый результат из БД
    user_responses_int = await get_quiz_result(user_id)

    if user_responses_int != 0:

        user_responses_list = list(map(int, str(user_responses_int)))

        # Список для сравнения ответов
        i = 0
        r_or_w = list()

        for answer in user_responses_list:
            if answer == quiz_data[i]['correct_option']:
                r_or_w.append("ВЕРНО")
            else:
                r_or_w.append("НЕВЕРНО")
            i += 1

        # Формирование ответов и их правильность
        user_responses_list_format = f'''
        1. {quiz_data[0]['options'][user_responses_list[0]]} ({r_or_w[0]})
        2. {quiz_data[1]['options'][user_responses_list[1]]} ({r_or_w[1]})
        3. {quiz_data[2]['options'][user_responses_list[2]]} ({r_or_w[2]})
        4. {quiz_data[3]['options'][user_responses_list[3]]} ({r_or_w[3]})
        5. {quiz_data[4]['options'][user_responses_list[4]]} ({r_or_w[4]})
        6. {quiz_data[5]['options'][user_responses_list[5]]} ({r_or_w[5]})
        7. {quiz_data[6]['options'][user_responses_list[6]]} ({r_or_w[6]})
        8. {quiz_data[7]['options'][user_responses_list[7]]} ({r_or_w[7]})
        9. {quiz_data[8]['options'][user_responses_list[8]]} ({r_or_w[8]})
        10. {quiz_data[9]['options'][user_responses_list[9]]} ({r_or_w[9]})
        '''
        # Выводим результат
        await message.answer(f'Ваш последний результат: {user_responses_list_format}')
    else:
        # Если прошлые ответы отсутствуют
        await message.answer(f'Вы ещё не проходили квиз')

# Запуск процесса поллинга новых апдейтов
async def main():

    # Запускаем создание таблицы базы данных
    await create_table()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())