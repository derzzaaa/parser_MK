"""
Flask веб-приложение для поиска товаров на маркетплейсах
Поддержка: Авито, Яндекс Маркет, Ozon, Wildberries
"""
from flask import Flask, render_template, request, jsonify, send_file
from avito_parser_stealth import AvitoParserStealth as AvitoParser
from yandex_market_parser import YandexMarketParser
from ozon_parser import OzonParser
from wildberries_parser import WildberriesParser
from excel_export import save_results_to_excel, get_excel_path, get_row_count
import threading
import os

app = Flask(__name__)

# Глобальные парсеры
avito_parser = None
yandex_parser = None
ozon_parser = None
wb_parser = None
avito_lock = threading.Lock()
yandex_lock = threading.Lock()
ozon_lock = threading.Lock()
wb_lock = threading.Lock()

# Маппинг city id -> название города (для Авито)
CITY_NAMES = {
    'kazan': 'Казань',
    'moskva': 'Москва',
    'spb': 'Санкт-Петербург',
    'rossiya': 'Вся Россия'
}

MARKETPLACE_NAMES = {
    'avito': 'Авито',
    'yandex': 'Яндекс Маркет',
    'ozon': 'Ozon',
    'wb': 'Wildberries',
}


def get_avito_parser():
    global avito_parser
    with avito_lock:
        if avito_parser is None:
            avito_parser = AvitoParser(headless=False)
        return avito_parser


def get_yandex_parser():
    global yandex_parser
    with yandex_lock:
        if yandex_parser is None:
            yandex_parser = YandexMarketParser(headless=False)
        return yandex_parser


def get_ozon_parser():
    global ozon_parser
    with ozon_lock:
        if ozon_parser is None:
            ozon_parser = OzonParser(headless=False)
        return ozon_parser


def get_wb_parser():
    global wb_parser
    with wb_lock:
        if wb_parser is None:
            wb_parser = WildberriesParser(headless=False)
        return wb_parser


@app.route('/')
def index():
    row_count = get_row_count()
    return render_template('index.html', row_count=row_count)


@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = int(data.get('max_results', 3))
        city = data.get('city', 'kazan')
        marketplace = data.get('marketplace', 'avito')

        price_min = data.get('price_min') or None
        price_max = data.get('price_max') or None
        condition = data.get('condition') or None  # 'new', 'used' или None

        if not query:
            return jsonify({'error': 'Введите поисковый запрос'}), 400

        if max_results < 1 or max_results > 20:
            max_results = 3

        price_min_int = int(price_min) if price_min else None
        price_max_int = int(price_max) if price_max else None

        # Выбираем парсер по маркетплейсу
        if marketplace == 'yandex':
            parser = get_yandex_parser()
            results = parser.search_products(
                query,
                max_results=max_results,
                price_min=price_min_int,
                price_max=price_max_int,
            )
        elif marketplace == 'ozon':
            parser = get_ozon_parser()
            results = parser.search_products(
                query,
                max_results=max_results,
                price_min=price_min_int,
                price_max=price_max_int,
            )
        elif marketplace == 'wb':
            parser = get_wb_parser()
            results = parser.search_products(
                query,
                max_results=max_results,
                price_min=price_min_int,
                price_max=price_max_int,
            )
        else:
            # Авито (по умолчанию)
            parser = get_avito_parser()
            results = parser.search_products(
                query,
                max_results=max_results,
                city=city,
                price_min=price_min_int,
                price_max=price_max_int,
                condition=condition
            )

        # Сохраняем в Excel
        marketplace_name = MARKETPLACE_NAMES.get(marketplace, 'Авито')
        city_name = CITY_NAMES.get(city, 'Казань')
        if results:
            save_results_to_excel(results, city_name, marketplace=marketplace_name, brand=query)

        return jsonify({
            'success': True,
            'query': query,
            'marketplace': marketplace,
            'count': len(results),
            'results': results,
            'saved_to_excel': len(results) > 0,
            'total_records': get_row_count()
        })

    except Exception as e:
        import traceback
        print(f"Ошибка в /search: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/download_excel')
def download_excel():
    """Скачать Excel файл с результатами"""
    excel_path = get_excel_path()
    if os.path.exists(excel_path):
        return send_file(
            excel_path,
            as_attachment=True,
            download_name='avito_prices.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        return jsonify({'error': 'Файл не найден. Сначала выполните поиск.'}), 404


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'records': get_row_count()})


@app.teardown_appcontext
def cleanup(error=None):
    global avito_parser, yandex_parser, ozon_parser, wb_parser
    for p in [avito_parser, yandex_parser, ozon_parser, wb_parser]:
        if p:
            try:
                p.close()
            except Exception:
                pass
    avito_parser = None
    yandex_parser = None
    ozon_parser = None
    wb_parser = None


if __name__ == '__main__':
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    finally:
        for p in [avito_parser, yandex_parser, ozon_parser, wb_parser]:
            if p:
                p.close()
