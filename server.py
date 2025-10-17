from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import logging
import time
from datetime import datetime
import concurrent.futures
from dotenv import load_dotenv
import os
import json
import threading
import sqlite3
from collections import defaultdict

load_dotenv()

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
PRODUCTS_FILE = 'products.json'
ORDERS_DB = 'orders.db'

# Токен бота и ID чата
BOT_TOKEN = os.getenv("BOT_TOKEN")
SELLER_CHAT_ID = os.getenv("SELLER_CHAT_ID")
ADMIN_CHAT_IDS = os.getenv("ADMIN_CHAT_IDS")  # Добавляем ID администраторов

# Создаем пул потоков для асинхронной отправки
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)

# Глобальный словарь для хранения состояний пользователей
user_states = {}

# Глобальная переменная для продуктов
products = []

# Флаг для остановки long polling
stop_polling = False

def check_bot_availability():
    """Проверка доступности бота при запуске"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            bot_info = response.json()
            logging.info(f"Бот доступен: {bot_info['result']['first_name']} (@{bot_info['result']['username']})")
            return True
        else:
            logging.error(f"Бот недоступен. Код ответа: {response.status_code}")
            return False
            
    except Exception as e:
        logging.error(f"Ошибка проверки бота: {e}")
        return False

def send_to_telegram_async(message, chat_id=None):
    """Асинхронная отправка сообщения в Telegram"""
    return thread_pool.submit(send_to_telegram, message, chat_id)

def send_to_telegram(message, chat_id=None):
    """Отправка сообщения в Telegram с оптимизированными таймаутами"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id or SELLER_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        # Оптимизированные таймауты: connect=3s, read=10s
        response = requests.post(url, json=payload, timeout=(3, 10))
        
        if response.status_code == 200:
            logging.info("Сообщение успешно отправлено в Telegram")
            return True
        else:
            logging.error(f"Ошибка Telegram API: {response.status_code}, {response.text}")
            return False
                
    except requests.exceptions.Timeout:
        logging.warning("Таймаут при отправке в Telegram")
        return False
    except requests.exceptions.ConnectionError:
        logging.warning("Ошибка соединения с Telegram")
        return False
    except Exception as e:
        logging.error(f"Неожиданная ошибка при отправке в Telegram: {e}")
        return False

def format_order_message(order_data):
    """Форматирование сообщения о заказе"""
    try:
        items_text = "\n".join(
            f"• {item['name']} - {item['quantity']} {item['unit']} × {item['price']} ₽ = {item['quantity'] * item['price']} ₽"
            for item in order_data['items']
        )
        
        message = (
            f"🛒 <b>НОВЫЙ ЗАКАЗ</b>\n\n"
            f"👤 <b>{escape_html(order_data['customer']['name'])}</b>\n"
            f"📞 {escape_html(order_data['customer']['phone'])}\n"
            f"📍 {escape_html(order_data['customer']['address'])}\n\n"
            f"🚚 <b>Доставка:</b>\n"
            f"{escape_html(order_data['delivery']['date'])} {escape_html(order_data['delivery']['time'])}\n\n"
            f"📦 <b>Товары:</b>\n{items_text}\n\n"
            f"💰 <b>Итого: {order_data['totals']['total']} ₽</b>\n"
            f"(Товары: {order_data['totals']['subtotal']} ₽ + Доставка: {order_data['totals']['delivery']} ₽)\n\n"
        )
        
        if order_data.get('comment'):
            message += f"💬 <b>Комментарий:</b>\n{escape_html(order_data['comment'])}\n\n"
        
        payment_method = "Наличными" if order_data['payment'] == 'cash' else "Картой онлайн"
        message += f"💳 <b>Оплата:</b> {payment_method}\n"
        message += f"⏰ <b>Время заказа:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        return message
    except Exception as e:
        logging.error(f"Ошибка форматирования сообщения: {e}")
        return f"❌ Ошибка при обработке заказа: {e}"

def escape_html(text):
    """Экранирование HTML символов"""
    if not text:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def load_products():
    """Загрузка продуктов из файла"""
    global products
    try:
        if os.path.exists(PRODUCTS_FILE):
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                products = json.load(f)
                logging.info(f"Загружено {len(products)} продуктов из файла")
                return products
    except Exception as e:
        logging.error(f"Ошибка загрузки продуктов: {e}")
    
    products = get_default_products()
    save_products(products)
    return products

def save_products(products_list):
    """Сохранение продуктов в файл"""
    try:
        with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(products_list, f, ensure_ascii=False, indent=2)
        logging.info(f"Сохранено {len(products_list)} продуктов в файл")
        return True
    except Exception as e:
        logging.error(f"Ошибка сохранения продуктов: {e}")
        return False

def get_default_products():
    """Продукты по умолчанию"""
    return [
        {
            "id": 1,
            "name": "Свежая клубника",
            "price": 500,
            "image": "https://images.unsplash.com/photo-1570913190149-e2a64af5c30f?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80",
            "unit": "кг",
            "description": "Натуральная, сочная и сладкая клубника, собранная вручную с любовью.",
            "active": True
        },
        {
            "id": 2,
            "name": "Клубника в корзине",
            "price": 700,
            "image": "https://images.unsplash.com/photo-1464454709131-ffd692591ee5?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80",
            "unit": "корзина",
            "description": "Идеальный подарок для близких. Красиво, вкусно и натурально.",
            "active": True
        },
        {
            "id": 3,
            "name": "Клубника со сливками",
            "price": 850,
            "image": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80",
            "unit": "порция",
            "description": "Нежное сочетание свежей клубники и домашних сливок. Идеальный десерт.",
            "active": True
        }
    ]

def send_help_message(chat_id):
    """Отправка сообщения с помощью"""
    help_text = """
🤖 <b>Команды администратора:</b>

/start - Главное меню
/help - Показать это сообщение

📦 <b>Управление продуктами:</b>
/list - Показать все продукты
/add - Добавить новый продукт
/edit - Редактировать продукт
/delete - Удалить продукт

📊 <b>Статистика:</b>
/stats - Статистика за все время
/stats today - Статистика за сегодня
/stats week - Статистика за неделю
/stats month - Статистика за месяц

💡 <b>Как использовать:</b>
1. Используйте команды для управления продуктами
2. Следуйте инструкциям бота
3. Изменения сразу отобразятся на сайте
"""
    send_to_telegram(help_text, chat_id)

def send_products_list(chat_id):
    """Отправка списка продуктов"""
    global products
    if not products:
        send_to_telegram("📭 Список продуктов пуст", chat_id)
        return
    
    message = "📦 <b>Список продуктов:</b>\n\n"
    for i, product in enumerate(products, 1):
        status = "✅" if product.get('active', True) else "❌"
        message += f"{i}. {status} <b>{escape_html(product['name'])}</b>\n"
        message += f"   Цена: {product['price']} ₽/{product['unit']}\n"
        message += f"   ID: {product['id']}\n\n"
    
    message += "\n💡 Используйте /edit [ID] для редактирования или /delete [ID] для удаления"
    send_to_telegram(message, chat_id)

def handle_product_addition(chat_id, message_text):
    """Обработка добавления продукта"""
    global user_states
    
    if chat_id not in user_states or 'adding_product' not in user_states[chat_id]:
        # Начинаем процесс добавления
        user_states[chat_id] = {
            'adding_product': {
                'step': 'name',
                'data': {}
            }
        }
        send_to_telegram("Введите название продукта:", chat_id)
        return
    
    step = user_states[chat_id]['adding_product']['step']
    product_data = user_states[chat_id]['adding_product']['data']
    
    if step == 'name':
        product_data['name'] = message_text
        user_states[chat_id]['adding_product']['step'] = 'description'
        send_to_telegram("Введите описание продукта:", chat_id)
    
    elif step == 'description':
        product_data['description'] = message_text
        user_states[chat_id]['adding_product']['step'] = 'price'
        send_to_telegram("Введите цену продукта (только число):", chat_id)
    
    elif step == 'price':
        try:
            product_data['price'] = int(message_text)
            user_states[chat_id]['adding_product']['step'] = 'unit'
            send_to_telegram("Введите единицу измерения (кг, шт, корзина и т.д.):", chat_id)
        except ValueError:
            send_to_telegram("❌ Неверный формат цены. Введите число:", chat_id)
    
    elif step == 'unit':
        product_data['unit'] = message_text
        user_states[chat_id]['adding_product']['step'] = 'image'
        send_to_telegram("Введите URL изображения продукта:", chat_id)
    
    elif step == 'image':
        product_data['image'] = message_text
        # Завершаем добавление
        new_product = {
            'id': max([p['id'] for p in products], default=0) + 1,
            'name': product_data['name'],
            'description': product_data['description'],
            'price': product_data['price'],
            'unit': product_data['unit'],
            'image': product_data['image'],
            'active': True
        }
        
        products.append(new_product)
        save_products(products)
        
        # Очищаем состояние
        del user_states[chat_id]
        
        send_to_telegram(f"✅ Продукт '{new_product['name']}' успешно добавлен!", chat_id)
        send_products_list(chat_id)

def handle_product_edit(chat_id, product_id, message_text):
    """Обработка редактирования продукта"""
    global user_states
    
    product = next((p for p in products if p['id'] == product_id), None)
    if not product:
        send_to_telegram("❌ Продукт не найден", chat_id)
        return
    
    if chat_id not in user_states or 'editing_product' not in user_states[chat_id]:
        # Начинаем процесс редактирования
        user_states[chat_id] = {
            'editing_product': {
                'product_id': product_id,
                'step': 'field',
                'data': product.copy()
            }
        }
        message = f"✏️ <b>Редактирование:</b> {product['name']}\n\n"
        message += "Выберите поле для редактирования:\n"
        message += "1. name - Название\n"
        message += "2. description - Описание\n"
        message += "3. price - Цена\n"
        message += "4. unit - Единица измерения\n"
        message += "5. image - URL изображения\n"
        message += "6. active - Активность (true/false)\n\n"
        message += "Введите номер поля или название:"
        send_to_telegram(message, chat_id)
        return
    
    state = user_states[chat_id]['editing_product']
    
    if state['step'] == 'field':
        field_map = {
            '1': 'name', 'name': 'name',
            '2': 'description', 'description': 'description',
            '3': 'price', 'price': 'price',
            '4': 'unit', 'unit': 'unit',
            '5': 'image', 'image': 'image',
            '6': 'active', 'active': 'active'
        }
        
        field = field_map.get(message_text.lower())
        if not field:
            send_to_telegram("❌ Неверное поле. Попробуйте снова:", chat_id)
            return
        
        state['field'] = field
        state['step'] = 'value'
        
        if field == 'active':
            send_to_telegram("Введите новое значение активности (true/false):", chat_id)
        else:
            current_value = product.get(field, '')
            send_to_telegram(f"Текущее значение: {current_value}\nВведите новое значение:", chat_id)
    
    elif state['step'] == 'value':
        field = state['field']
        product = next((p for p in products if p['id'] == state['product_id']), None)
        
        if not product:
            send_to_telegram("❌ Продукт не найден", chat_id)
            del user_states[chat_id]
            return
        
        try:
            if field == 'price':
                product[field] = int(message_text)
            elif field == 'active':
                product[field] = message_text.lower() == 'true'
            else:
                product[field] = message_text
            
            save_products(products)
            send_to_telegram(f"✅ Поле '{field}' успешно обновлено!", chat_id)
            del user_states[chat_id]
            
        except ValueError:
            send_to_telegram("❌ Неверный формат значения. Попробуйте снова:", chat_id)

def telegram_long_polling():
    """Long polling для получения обновлений от Telegram"""
    global stop_polling
    offset = 0
    
    while not stop_polling:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {
                'timeout': 30,
                'offset': offset
            }
            
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 200:
                data = response.json()
                if data['ok'] and data['result']:
                    for update in data['result']:
                        offset = update['update_id'] + 1
                        
                        # Обрабатываем текстовые сообщения
                        if 'message' in update and 'text' in update['message']:
                            handle_message(update)
            
        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.ConnectionError:
            logging.warning("Ошибка соединения с Telegram API")
            time.sleep(5)
        except Exception as e:
            logging.error(f"Ошибка в long polling: {e}")
            time.sleep(5)

def handle_message(update):
    """Обработка текстовых сообщений"""
    message = update.get('message', {})
    chat_id = message['chat']['id']
    message_text = message.get('text', '')
    
    # Проверяем права доступа
    if str(chat_id) not in ADMIN_CHAT_IDS:
        send_to_telegram("❌ У вас нет прав для выполнения этой команды", chat_id)
        return
    
    # Обработка команд
    if message_text.startswith('/'):
        if message_text == '/start':
            send_help_message(chat_id)
        
        elif message_text == '/help':
            send_help_message(chat_id)
        
        elif message_text == '/list':
            send_products_list(chat_id)
        
        elif message_text == '/add':
            user_states[chat_id] = {'adding_product': {'step': 'name', 'data': {}}}
            send_to_telegram("Введите название продукта:", chat_id)
        
        elif message_text.startswith('/edit'):
            try:
                parts = message_text.split()
                if len(parts) < 2:
                    send_to_telegram("❌ Укажите ID продукта: /edit [ID]", chat_id)
                    return
                
                product_id = int(parts[1])
                handle_product_edit(chat_id, product_id, "")
            except ValueError:
                send_to_telegram("❌ Неверный формат ID. Используйте: /edit [ID]", chat_id)
        
        elif message_text.startswith('/delete'):
            try:
                parts = message_text.split()
                if len(parts) < 2:
                    send_to_telegram("❌ Укажите ID продукта: /delete [ID]", chat_id)
                    return
                
                product_id = int(parts[1])
                product = next((p for p in products if p['id'] == product_id), None)
                
                if product:
                    products[:] = [p for p in products if p['id'] != product_id]
                    save_products(products)
                    send_to_telegram(f"✅ Продукт '{product['name']}' успешно удален!", chat_id)
                    send_products_list(chat_id)
                else:
                    send_to_telegram("❌ Продукт не найден", chat_id)
            except ValueError:
                send_to_telegram("❌ Неверный формат ID. Используйте: /delete [ID]", chat_id)

        elif message_text.startswith('/stats'):
            try:
                parts = message_text.split()
                time_period = parts[1] if len(parts) > 1 else 'all'
                
                if time_period not in ['today', 'week', 'month', 'all']:
                    send_to_telegram("❌ Неверный период. Используйте: /stats today/week/month/all", chat_id)
                    return
                
                stats = get_order_stats(time_period)
                if stats:
                    message = format_stats_message(stats, time_period)
                    send_to_telegram(message, chat_id)
                else:
                    send_to_telegram("❌ Ошибка получения статистики", chat_id)
                    
            except Exception as e:
                logging.error(f"Ошибка обработки статистики: {e}")
                send_to_telegram("❌ Ошибка при получении статистики", chat_id)
        
        else:
            send_to_telegram("❌ Неизвестная команда. Используйте /help для списка команд", chat_id)
        return
    
    # Обрабатываем состояние добавления продукта
    if chat_id in user_states and 'adding_product' in user_states[chat_id]:
        handle_product_addition(chat_id, message_text)
    
    # Обрабатываем состояние редактирования продукта
    elif chat_id in user_states and 'editing_product' in user_states[chat_id]:
        state = user_states[chat_id]['editing_product']
        handle_product_edit(chat_id, state['product_id'], message_text)

# Загружаем продукты при старте
products = load_products()

def init_orders_db():
    """Инициализация базы данных заказов"""
    try:
        conn = sqlite3.connect(ORDERS_DB)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                customer_address TEXT NOT NULL,
                delivery_date TEXT NOT NULL,
                delivery_time TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                subtotal INTEGER NOT NULL,
                delivery_fee INTEGER NOT NULL,
                total INTEGER NOT NULL,
                comment TEXT,
                items TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logging.info("База данных заказов инициализирована")
    except Exception as e:
        logging.error(f"Ошибка инициализации БД заказов: {e}")

def save_order_to_db(order_data):
    """Сохранение заказа в базу данных"""
    try:
        conn = sqlite3.connect(ORDERS_DB)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO orders 
            (customer_name, customer_phone, customer_address, delivery_date, delivery_time, 
             payment_method, subtotal, delivery_fee, total, comment, items)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_data['customer']['name'],
            order_data['customer']['phone'],
            order_data['customer']['address'],
            order_data['delivery']['date'],
            order_data['delivery']['time'],
            order_data['payment'],
            order_data['totals']['subtotal'],
            order_data['totals']['delivery'],
            order_data['totals']['total'],
            order_data.get('comment', ''),
            json.dumps(order_data['items'])
        ))
        
        conn.commit()
        conn.close()
        logging.info(f"Заказ от {order_data['customer']['name']} сохранен в БД")
        return True
    except Exception as e:
        logging.error(f"Ошибка сохранения заказа в БД: {e}")
        return False

def get_order_stats(time_period='all'):
    """Получение статистики заказов"""
    try:
        conn = sqlite3.connect(ORDERS_DB)
        cursor = conn.cursor()
        
        # Определяем условие времени в зависимости от периода
        time_conditions = {
            'today': "DATE(created_at) = DATE('now')",
            'week': "created_at >= DATE('now', '-7 days')",
            'month': "created_at >= DATE('now', '-30 days')",
            'all': "1=1"
        }
        
        condition = time_conditions.get(time_period, '1=1')
        
        # Общая статистика
        cursor.execute(f'''
            SELECT 
                COUNT(*) as total_orders,
                SUM(total) as total_revenue,
                AVG(total) as avg_order_value,
                COUNT(DISTINCT customer_phone) as unique_customers
            FROM orders 
            WHERE {condition}
        ''')
        
        stats = cursor.fetchone()
        
        # Статистика по дням (для графика)
        cursor.execute(f'''
            SELECT 
                DATE(created_at) as order_date,
                COUNT(*) as orders_count,
                SUM(total) as daily_revenue
            FROM orders 
            WHERE {condition}
            GROUP BY DATE(created_at)
            ORDER BY order_date
        ''')
        
        daily_stats = cursor.fetchall()
        
        # Популярные товары
        cursor.execute(f'''
            SELECT 
                json_extract(value, '$.name') as product_name,
                SUM(json_extract(value, '$.quantity')) as total_quantity,
                SUM(json_extract(value, '$.quantity') * json_extract(value, '$.price')) as total_revenue
            FROM orders, json_each(items)
            WHERE {condition}
            GROUP BY product_name
            ORDER BY total_quantity DESC
            LIMIT 10
        ''')
        
        popular_products = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_orders': stats[0] or 0,
            'total_revenue': stats[1] or 0,
            'avg_order_value': stats[2] or 0,
            'unique_customers': stats[3] or 0,
            'daily_stats': daily_stats,
            'popular_products': popular_products
        }
        
    except Exception as e:
        logging.error(f"Ошибка получения статистики: {e}")
        return None

def format_stats_message(stats, time_period):
    """Форматирование сообщения со статистикой"""
    period_names = {
        'today': 'сегодня',
        'week': 'за неделю',
        'month': 'за месяц',
        'all': 'за все время'
    }
    
    period_name = period_names.get(time_period, 'за все время')
    
    message = f"📊 <b>СТАТИСТИКА ЗАКАЗОВ ({period_name})</b>\n\n"
    
    message += f"📦 <b>Всего заказов:</b> {stats['total_orders']}\n"
    message += f"💰 <b>Общая выручка:</b> {stats['total_revenue']} ₽\n"
    message += f"📈 <b>Средний чек:</b> {stats['avg_order_value']:.0f} ₽\n"
    message += f"👥 <b>Уникальных клиентов:</b> {stats['unique_customers']}\n\n"
    
    # Популярные товары
    if stats['popular_products']:
        message += "🏆 <b>Популярные товары:</b>\n"
        for i, (name, quantity, revenue) in enumerate(stats['popular_products'][:5], 1):
            message += f"{i}. {name} - {quantity} шт. ({revenue} ₽)\n"
        message += "\n"
    
    # Ежедневная статистика (последние 7 дней)
    if stats['daily_stats'] and len(stats['daily_stats']) > 1:
        message += "📅 <b>Последние дни:</b>\n"
        for date, count, revenue in stats['daily_stats'][-7:]:
            message += f"• {date}: {count} зак. ({revenue} ₽)\n"
    
    message += f"\n💡 Используйте /stats today/week/month/all для фильтрации"
    
    return message

@app.route('/api/order', methods=['POST'])
def receive_order():
    try:
        order_data = request.get_json()
        
        if not order_data:
            return jsonify({'error': 'No data provided'}), 400
        
        logging.info(f"Получен новый заказ от {order_data['customer']['name']}")
        
        # Сохраняем заказ в базу данных
        save_order_to_db(order_data)
        
        # Форматируем сообщение
        message = format_order_message(order_data)
        
        # Отправляем асинхронно (не блокируем ответ)
        send_to_telegram_async(message)
        
        # Немедленно возвращаем ответ клиенту
        return jsonify({
            'message': 'Order received successfully',
            'status': 'success'
        }), 200
            
    except Exception as e:
        logging.error(f"Ошибка обработки заказа: {e}")
        return jsonify({
            'error': 'Internal server error',
            'status': 'error'
        }), 500

@app.route('/api/bot-check', methods=['GET'])
def check_bot():
    """Проверка доступности бота"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            bot_info = response.json()
            return jsonify({
                'status': 'success',
                'bot_username': bot_info['result']['username'],
                'bot_name': bot_info['result']['first_name']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'Bot API returned status code: {response.status_code}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Bot check failed: {str(e)}'
        }), 500

@app.route('/api/products', methods=['GET'])
def get_products():
    """Получение списка активных продуктов"""
    try:
        active_products = [p for p in products if p.get('active', True)]
        return jsonify(active_products), 200
    except Exception as e:
        logging.error(f"Ошибка получения продуктов: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/products', methods=['GET'])
def get_all_products():
    """Получение всех продуктов (для администрирования)"""
    try:
        return jsonify(products), 200
    except Exception as e:
        logging.error(f"Ошибка получения всех продуктов: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/products', methods=['POST'])
def add_product():
    """Добавление нового продукта"""
    try:
        new_product = request.get_json()
        if not new_product:
            return jsonify({'error': 'No data provided'}), 400
        
        # Генерируем ID
        new_id = max([p['id'] for p in products], default=0) + 1
        new_product['id'] = new_id
        new_product['active'] = new_product.get('active', True)
        
        products.append(new_product)
        
        if save_products(products):
            return jsonify({'message': 'Product added successfully', 'product': new_product}), 201
        else:
            return jsonify({'error': 'Failed to save product'}), 500
            
    except Exception as e:
        logging.error(f"Ошибка добавления продукта: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Обновление продукта"""
    try:
        updated_data = request.get_json()
        if not updated_data:
            return jsonify({'error': 'No data provided'}), 400
        
        product_index = next((i for i, p in enumerate(products) if p['id'] == product_id), None)
        
        if product_index is None:
            return jsonify({'error': 'Product not found'}), 404
        
        # Сохраняем ID и обновляем остальные поля
        updated_data['id'] = product_id
        products[product_index] = {**products[product_index], **updated_data}
        
        if save_products(products):
            return jsonify({'message': 'Product updated successfully', 'product': products[product_index]}), 200
        else:
            return jsonify({'error': 'Failed to save product'}), 500
            
    except Exception as e:
        logging.error(f"Ошибка обновления продукта: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Удаление продукта"""
    try:
        global products
        products[:] = [p for p in products if p['id'] != product_id]
        
        if save_products(products):
            return jsonify({'message': 'Product deleted successfully'}), 200
        else:
            return jsonify({'error': 'Failed to save products'}), 500
            
    except Exception as e:
        logging.error(f"Ошибка удаления продукта: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/check', methods=['GET'])
def check_api():
    return jsonify({
        'message': 'API is working!',
        'status': 'success'
    }), 200

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    # Проверяем доступность бота при запуске
    bot_available = check_bot_availability()
    # инициализация базы данных
    init_orders_db()
    
    if bot_available:
        logging.info("✅ Бот готов к работе")
        # Отправляем приветственное сообщение администраторам
        for admin_id in ADMIN_CHAT_IDS:
            send_to_telegram_async("🤖 Бот запущен и готов к работе!", admin_id)
            send_help_message(admin_id)
        
        # Запускаем long polling в отдельном потоке
        polling_thread = threading.Thread(target=telegram_long_polling, daemon=True)
        polling_thread.start()
        logging.info("🚀 Long polling запущен")
    else:
        logging.warning("⚠️  Бот недоступен. Проверьте токен и интернет-соединение")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        logging.info("🛑 Остановка сервера...")
        stop_polling = True
