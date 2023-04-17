import requests
import os
import logging
from datetime import datetime
import time
import telegram
from http import HTTPStatus
from exceptions import MissingTokens, TelegramError
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
                    encoding='utf-8',
                    filename='main.log',
                    filemode='w',
                    format='%(asctime)s, %(levelname)s, %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('my_logger.log',
                              encoding='utf-8',
                              maxBytes=50000000,
                              backupCount=5)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных, необходиме для работы программы."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """отправляет сообщение в Telegram чат."""
    try:
        logging.info(f'Отправка сообщения: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Ошибка отправки сообщение в Telegram чат: {error}')
        raise TelegramError(f'Ошибка отправки телеграм сообщения: {error}')
    else:
        logging.debug(f'Сообщение успешно отправлено: {message}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = int(time.time())
    request_params = {
        'url': ENDPOINT,
        'headers': {'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
        'params': {'from_date': timestamp}
    }

    try:
        logging.info(
            (
                'Начинаем подключение к эндпоинту {url}, с параметрами'
                ' headers = {headers} ;params= {params}.'
            ).format(**request_params)
        )
        response = requests.get(**request_params)

        if response.status_code != HTTPStatus.OK:
            raise MissingTokens(
                'Ответ сервера не является успешным:'
                f' request params = {request_params};'
                f' http_code = {response.status_code};'
                f' reason = {response.reason}; content = {response.text}'
            )

    except Exception as error:
        raise ConnectionError(
            (
                'Во время подключения к эндпоинту {url} произошла'
                ' непредвиденная ошибка: {error}'
                ' headers = {headers}; params = {params};'
            ).format(
                error=error,
                **request_params
            )
        )
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
    return response.get('homeworks')


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
    # Делаем проверку токенов
    if not check_tokens():
        message = (
            'Отсутсвуют обязательные переменные окружения: PRACTICUM_TOKEN,'
            ' TELEGRAM_TOKEN, TELEGRAM_CHAT_ID.'
            ' Программа принудительно остановлена.'
        )
        logging.critical(message)
        SystemExit.exit(message)

    # Создаем бота и получаем время
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    timestamp_normal = datetime.now().date()

    # Cловарь для хранения текущего сообщения
    current_report = {'name': '', 'output': ''}
    # Словарь для хранения предыдущего сообщения
    prev_report = current_report.copy()

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date', timestamp)
            new_homeworks = check_response(response)

            if new_homeworks:
                current_report['name'] = new_homeworks[0]['homework_name']
                current_report['output'] = parse_status(new_homeworks[0])
            else:
                current_report = (
                    f'За период от {timestamp_normal} до настоящего момента'
                    ' домашних работ нет.'
                )

            if current_report != prev_report:
                send_message(bot, current_report)
                prev_report = current_report.copy()
            else:
                logging.debug('В ответе нет новых статусов.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            current_report['output'] = message
            logging.error(message, exc_info=True)
            if current_report != prev_report:
                send_message(bot, current_report)
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
