from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random


class AvitoParserStealth:

    CITY_URLS = {
        'kazan': 'https://www.avito.ru/kazan',
        'казань': 'https://www.avito.ru/kazan',
        'moskva': 'https://www.avito.ru/moskva',
        'москва': 'https://www.avito.ru/moskva',
        'spb': 'https://www.avito.ru/sankt-peterburg',
        'санкт-петербург': 'https://www.avito.ru/sankt-peterburg',
        'rossiya': 'https://www.avito.ru/rossiya',
        'россия': 'https://www.avito.ru/rossiya',
    }

    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None

    def _init_driver(self):

        print("[INFO] Запускаем браузер...")

        options = Options()

        if self.headless:
            options.add_argument('--headless=new')

        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=options)
        self.driver.set_window_size(1366, 768)

        try:
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'
            })
        except Exception:
            pass

        print("[OK] Браузер запущен!")

    def _check_and_wait_captcha(self):
        captcha_selectors = [
            'iframe[src*="captcha"]',
            'div[class*="captcha"]',
            'div[class*="Captcha"]',
            '#checkbox-captcha',
            'form[action*="captcha"]',
            '[class*="firewall"]',
            '[class*="Firewall"]',
        ]

        for selector in captcha_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print("\n" + "!" * 60)
                    print("ОБНАРУЖЕНА КАПЧА!")
                    print("Пожалуйста, решите капчу в открытом браузере.")
                    print("Ожидание до 120 секунд...")
                    print("!" * 60 + "\n")

                    # Ждём пока капча исчезнет (макс 120 сек)
                    for i in range(120):
                        time.sleep(1)

                        items = self.driver.find_elements(By.CSS_SELECTOR, '[data-marker="item"]')
                        if items:
                            print("[OK] Капча решена! Продолжаем...")
                            return True

                        # Проверяем, исчезла ли капча
                        still_captcha = False
                        for sel in captcha_selectors:
                            if self.driver.find_elements(By.CSS_SELECTOR, sel):
                                still_captcha = True
                                break

                        if not still_captcha:
                            print("[OK] Капча решена! Продолжаем...")
                            time.sleep(2)
                            return True

                        if i % 10 == 0 and i > 0:
                            print(f"[WAIT] Ожидание... {120 - i} сек осталось")

                    print("[WARN] Таймаут ожидания капчи")
                    return False
            except Exception:
                continue

        return True  # Капчи нет

    def _random_delay(self, min_sec=3, max_sec=7):
        """Случайная задержка (увеличенная)"""
        delay = random.uniform(min_sec, max_sec)
        print(f"[WAIT] Пауза {delay:.1f} сек...")
        time.sleep(delay)

    def search_products(self, query, max_results=3, city='kazan',
                        price_min=None, price_max=None, condition=None):
        """
        Поиск товаров на Авито.
        condition: 'new' — новые, 'used' — б/у, None — все
        price_min / price_max: целые числа (рубли)
        """
        if not self.driver:
            self._init_driver()

        results = []

        try:
            print(f"\n[INFO] Поиск: '{query}' | Город: {city}")

            base_url = self.CITY_URLS.get(city.lower(), 'https://www.avito.ru/kazan')

            # Строим URL с фильтрами
            params = f'q={query.replace(" ", "+")}'
            params += '&s=104'  # сортировка: сначала новые объявления

            if price_min:
                params += f'&pmin={price_min}'
            if price_max:
                params += f'&pmax={price_max}'
            if condition == 'new':
                params += '&f%5B%5D=ASgBAgICAkSUA3Reu5AB'  # Авито-фильтр "новое"
            elif condition == 'used':
                params += '&f%5B%5D=ASgBAgICAkSUA3Reu5AD'  # Авито-фильтр "б/у"

            search_url = f'{base_url}?{params}'
            print(f"[INFO] URL: {search_url}")

            # Сначала заходим на главную (как обычный пользователь)
            self.driver.get('https://www.avito.ru/')
            self._random_delay(3, 5)

            # Проверяем капчу на главной
            self._check_and_wait_captcha()

            # Теперь переходим к поиску
            self.driver.get(search_url)
            self._random_delay(4, 7)

            # Проверяем капчу на странице поиска
            if not self._check_and_wait_captcha():
                print("[ERROR] Не удалось пройти капчу")
                return results

            # Скролл как человек
            for scroll_pos in [200, 400, 600]:
                self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
                time.sleep(random.uniform(0.5, 1.5))

            print("[INFO] Ищем объявления...")
            items = self.driver.find_elements(By.CSS_SELECTOR, '[data-marker="item"]')
            print(f"[INFO] Найдено на странице: {len(items)}")

            # Берём больше, чтобы после фильтрации осталось достаточно
            items_to_parse = items[:max(max_results * 5, 30)]

            # Слова из запроса для фильтрации (все должны присутствовать в названии)
            query_words = [w.lower() for w in query.split() if len(w) > 1]

            for idx, item in enumerate(items_to_parse, 1):
                try:
                    product = self._parse_item(item, idx)
                    if not product:
                        continue

                    # Фильтруем по словам запроса
                    title_lower = product['title'].lower()
                    if not all(word in title_lower for word in query_words):
                        print(f"[SKIP] Не релевантно: {product['title'][:50]}")
                        continue

                    results.append(product)
                    print(f"[OK] {len(results)}. {product['title'][:50]}  |  {product['price']}")

                    # Достаточно результатов
                    if len(results) >= max_results:
                        break

                except Exception as e:
                    print(f"[SKIP] Ошибка товар {idx}: {e}")
                    continue

                time.sleep(random.uniform(0.3, 0.7))

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()

        print(f"[ИТОГО] Релевантных: {len(results)}")
        return results

    def _parse_item(self, item, idx):
        """Парсинг одного объявления"""
        product = {}

        # Название
        try:
            title = item.find_element(By.CSS_SELECTOR, '[itemprop="name"]')
            product['title'] = title.text.strip()
        except Exception:
            try:
                title = item.find_element(By.CSS_SELECTOR, '[data-marker="item-title"]')
                product['title'] = title.text.strip()
            except Exception:
                return None

        if not product['title']:
            return None

        # Цена
        try:
            price = item.find_element(By.CSS_SELECTOR, '[itemprop="price"]')
            content = price.get_attribute('content')
            product['price'] = f"{content} ₽" if content else price.text.strip()
        except Exception:
            try:
                price = item.find_element(By.CSS_SELECTOR, '[data-marker="item-price"]')
                product['price'] = price.text.strip()
            except Exception:
                product['price'] = 'Цена не указана'

        # Ссылка
        try:
            link = item.find_element(By.CSS_SELECTOR, '[data-marker="item-title"]')
            product['url'] = link.get_attribute('href') or '#'
        except Exception:
            product['url'] = '#'

        # Местоположение — пробуем несколько селекторов
        product['location'] = ''
        location_selectors = [
            '[data-marker="item-address"]',
            '[class*="geo-address"]',
            '[class*="GeoAddress"]',
            '[class*="geo-root"]',
            '[class*="location"]',
            '[class*="Location"]',
            '[data-marker="item-address"] span',
            'p[data-marker="item-address"]',
        ]
        for sel in location_selectors:
            try:
                loc = item.find_element(By.CSS_SELECTOR, sel)
                text = loc.text.strip()
                if text:
                    product['location'] = text
                    break
            except Exception:
                continue

        # Если ничего не нашли — пытаемся найти любой элемент с текстом города
        if not product['location']:
            try:
                # Ищем все span/p внутри объявления, проверяем на города
                all_spans = item.find_elements(By.TAG_NAME, 'p')
                for span in all_spans:
                    text = span.text.strip()
                    # Типичные признаки адреса: содержит "ул.", "р-н", город, метро
                    if any(word in text.lower() for word in ['ул.', 'р-н', 'район', 'метро', 'пр.', 'пр-кт']):
                        product['location'] = text
                        break
            except Exception:
                pass

        if not product['location']:
            product['location'] = 'Не указано'

        # Дата
        try:
            date = item.find_element(By.CSS_SELECTOR, '[data-marker="item-date"]')
            product['date'] = date.text.strip()
        except Exception:
            product['date'] = ''

        # Собираем ВЕСЬ текст объявления для поиска по описанию
        try:
            full_text = item.text.strip()
            # Убираем цену и название из описания, если нужно, но для поиска лучше оставить всё
            product['description'] = " ".join(full_text.split())
        except Exception:
            product['description'] = ''

        # Рейтинг
        try:
            rating = item.find_element(By.CSS_SELECTOR, '[data-marker="seller-info/rating"]')
            product['rating'] = rating.text.strip()
        except Exception:
            try:
                rating = item.find_element(By.CSS_SELECTOR, '[class*="rating"]')
                product['rating'] = rating.text.strip()
            except Exception:
                product['rating'] = ''

        return product

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == '__main__':
    print("=" * 60)
    print("ТЕСТ: Парсер Авито (с обработкой капчи)")
    print("=" * 60)

    with AvitoParserStealth(headless=False) as parser:
        results = parser.search_products('Nike Jordan', max_results=3, city='kazan')

        print("\n" + "=" * 60)
        for i, p in enumerate(results, 1):
            print(f"{i}. {p['title']}")
            print(f"    {p['price']}")
            print(f"    {p['location']}")
            print(f"    {p['url']}")
            print()

    input("Enter для выхода...")
