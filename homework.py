import os
import logging
import time
import requests
import telegram
from telegram import TelegramError
import sys
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в telegram."""
    logging.debug('Запуск функции send_message')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info('Сообщение успешно отправлено')
    except TelegramError as error:
        message_error = f'Ошибка при выполении функции send_message: {error}'
        logging.error(message_error)
        raise TelegramError(message_error)


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API."""
    logging.debug('Запуск функции get_api_answer')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message = 'Ошибка при выполнении запроса к серверу '
            logging.error(message)
            raise Exception(message)
    except (requests.exceptions.RequestException,
            ConnectionResetError) as error:
        message = f'Эндпоинт недоступен: {error}'
        logging.error(message)
        raise Exception(message)
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    logging.debug('Запуск функции check_response')
    error = 'Ответ API не соответствует ожиданиям!'
    if response is None:
        raise Exception(f'{error} {type(response)}')
    if not isinstance(response, dict):
        raise TypeError(f'{error} {type(response)}')
    if 'homeworks' not in response:
        raise KeyError(error)
    return response['homeworks'][0]


def parse_status(homework):
    """
    Обрабатывает информацию о конкретной домашней работе.
    Извлекает ее статус.
    """
    logging.debug('Запуск функции parse_status')
    verdict = ''
    try:
        homework_name = homework['homework_name']
    except Exception:
        raise KeyError('В ответе API отсутствует homework_name')
    try:
        homework_status = homework['status']
    except Exception:
        raise KeyError('В ответе API отсутствует status')
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except Exception as error:
        message = f'Получен некорректный ответ от API: {error}'
        logging.error(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    logging.debug('Запуск функции check_tokens')
    return all((
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    ))


def main():
    """Основная логика работы бота."""
    logging.debug('Бот запущен')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if check_tokens():
        logging.debug('Проверка токенов завершена успешно.')
    else:
        message = 'При проверке токенов произошла ошибка!'
        logging.critical(message)
        send_message(bot, message)
        sys.exit(message)
    current_timestamp = int(time.time())
    status_homework = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if status_homework != message:
                send_message(bot, message)
                status_homework = message
            else:
                message = 'Статус работы не обновился'
                logging.info(message)
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
