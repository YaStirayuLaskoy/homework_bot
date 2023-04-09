import requests
import os
import logging
import time
import telegram
from http import HTTPStatus
from exceptions import MissingTokens
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
PAYLOAD = {'from_date': 0}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(level=logging.INFO,
                    filename='main.log',
                    filemode='w',
                    format='%(asctime)s, %(levelname)s, %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('my_logger.log',
                              maxBytes=50000000,
                              backupCount=5)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных, необходиме для работы программы."""
    if PRACTICUM_TOKEN != os.getenv('PRACTICUM_TOKEN'):
        logging.critical('Ошибка доступности переменных')
        raise MissingTokens('Отсутствуют необходимые токены')
    elif TELEGRAM_TOKEN != os.getenv('TELEGRAM_TOKEN'):
        logging.critical('Ошибка доступности переменных')
        raise MissingTokens('Отсутствуют необходимые токены')
    elif TELEGRAM_CHAT_ID != os.getenv('TELEGRAM_CHAT_ID'):
        logging.critical('Ошибка доступности переменных')
        raise MissingTokens('Отсутствуют необходимые токены')


def send_message(bot, message):
    """отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Ошибка отправки сообщение в Telegram чат.: {error}')
    logging.debug(f'Сообщение отправлено: {message}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        logging.info('Запрос к экндпоинту API')
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=timestamp)

    except Exception as error:
        logging.error(f'Запрос к экндпоинту API не сработал {error}')
        raise TypeError(f'Запрос к экндпоинту API не сработал {error}')
    if response.status_code != HTTPStatus.OK:
        raise HTTPStatus('Код ответа не 200')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logging.error('API не словарь')
        raise TypeError('response не в словаре')
    if 'homeworks' not in response:
        logging.error('ключа homeworks нет')
        raise TypeError('ключа homeworks нет')
    if not isinstance(response.get('homeworks'), list):
        logging.error('ключа homeworks нет')
        raise TypeError('ключа homeworks нет')
    return response.get('homeworks')[0]


def parse_status(homework):
    """Статус о домашней работе этой работы."""
    if 'status' not in homework:
        logging.error('Ошибка пустое значение status')
        raise KeyError('Нет ключа status')
    if 'homework_name' not in homework:
        logging.error('Ошибка пустое значение homework_name:')
        raise KeyError('нет ключа homework_name')

    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        logging.error('status не в HOMEWORK_VERDICT')
        raise TypeError('status не в HOMEWORK_VERDICT')
    verdict = HOMEWORK_VERDICTS[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        SystemExit.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    # timestamp = int(time.time())
    tmp_status = 'reviewing'

    while True:
        try:
            check_tokens()
            response = get_api_answer(PAYLOAD)
            homework = check_response(response)
            if homework and tmp_status != homework['status']:
                message = parse_status(homework)
                send_message(bot, message)
                time.sleep(RETRY_PERIOD)
            logging.info('Всё по прежнему')
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.error(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
