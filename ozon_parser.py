"""
Парсер Ozon с использованием undetected-chromedriver
для обхода блокировки по IP и fingerprint.
"""
try:
    import undetected_chromedriver as uc
    HAS_UC = True
except ImportError:
    HAS_UC = False
    print("[WARN] undetected-chromedriver не установлен. Установите: pip install undetected-chromedriver")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import random


class OzonParser:

    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None

    def _find_chrome_binary(self):
        """Поиск Chrome binary (включая Chrome for Testing от Selenium)"""
        import glob
        import os

        # 1. Стандартные пути
        standard_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ]
        for p in standard_paths:
            if os.path.exists(p):
                return p

        # 2. Chrome for Testing (установленный Selenium Manager)
        selenium_cache = os.path.join(os.path.expanduser('~'), '.cache', 'selenium', 'chrome')
        if os.path.exists(selenium_cache):
            # Ищем самый свежий chrome.exe
            results = glob.glob(os.path.join(selenium_cache, '**', 'chrome.exe'), recursive=True)
            if results:
                # Берём последнюю версию (сортировка по пути)
                results.sort(reverse=True)
                return results[0]

        # 3. undetected-chromedriver своя функция
        try:
            found = uc.find_chrome_executable()
            if found:
                return found
        except Exception:
            pass

        return None

    def _init_driver(self):

        print("[INFO] Запускаем браузер (Ozon)...")

        chrome_binary = self._find_chrome_binary()
        if chrome_binary:
            print(f"[INFO] Chrome найден: {chrome_binary}")

        if HAS_UC:
            # undetected-chromedriver — основной способ обхода блокировки
            print("[INFO] Используем undetected-chromedriver для обхода защиты")
            options = uc.ChromeOptions()

            if self.headless:
                options.add_argument('--headless=new')

            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-infobars')

            # Указываем путь к Chrome явно
            if chrome_binary:
                options.binary_location = chrome_binary

            self.driver = uc.Chrome(options=options, version_main=None)
        else:
            # Fallback на обычный Selenium с anti-detection
            print("[WARN] Fallback на обычный Selenium (может быть заблокирован)")
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

            try:
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'
                })
            except Exception:
                pass

        self.driver.set_window_size(1366, 768)
        print("[OK] Браузер запущен!")

    def _check_and_wait_captcha(self):
        """Проверка и ручное решение капчи Ozon"""
        captcha_selectors = [
            'iframe[src*="captcha"]',
            'div[class*="captcha"]',
            'div[class*="Captcha"]',
            '[class*="recaptcha"]',
            '[id*="recaptcha"]',
            'div[id*="captcha"]',
            '[class*="robot"]',
            '[class*="Robot"]',
            'div[class*="BlockedPage"]',
            'div[class*="blocked"]',
        ]

        # Также проверяем по тексту страницы
        try:
            page_text = self.driver.page_source.lower()
            if any(word in page_text for word in ['заблокирован', 'blocked', 'доступ ограничен', 'подтвердите']):
                # Возможно заблокировано
                if 'ozon.ru/search' not in self.driver.current_url:
                    print("\n" + "!" * 60)
                    print("ВОЗМОЖНА БЛОКИРОВКА (Ozon)!")
                    print("Проверьте браузер. Если нужна капча — решите её.")
                    print("Ожидание до 120 секунд...")
                    print("!" * 60 + "\n")

                    for i in range(120):
                        time.sleep(1)
                        try:
                            current_url = self.driver.current_url
                            if 'search' in current_url:
                                print("[OK] Блокировка пройдена!")
                                time.sleep(2)
                                return True
                        except Exception:
                            pass

                        if i % 10 == 0 and i > 0:
                            print(f"[WAIT] Ожидание... {120 - i} сек осталось")

                    print("[WARN] Таймаут ожидания")
                    return False
        except Exception:
            pass

        for selector in captcha_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print("\n" + "!" * 60)
                    print("ОБНАРУЖЕНА КАПЧА (Ozon)!")
                    print("Пожалуйста, решите капчу в открытом браузере.")
                    print("Ожидание до 120 секунд...")
                    print("!" * 60 + "\n")

                    for i in range(120):
                        time.sleep(1)

                        # Проверяем, появились ли товары
                        items = self.driver.find_elements(By.CSS_SELECTOR,
                            'div[class*="widget-search-result-container"], '
                            '[data-widget="searchResultsV2"]'
                        )
                        if items:
                            print("[OK] Капча решена! Продолжаем...")
                            return True

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
        """Случайная задержка"""
        delay = random.uniform(min_sec, max_sec)
        print(f"[WAIT] Пауза {delay:.1f} сек...")
        time.sleep(delay)

    def _human_scroll(self):
        """Имитация скролла как у человека"""
        total_height = self.driver.execute_script("return document.body.scrollHeight")
        current = 0
        while current < total_height * 0.7:
            step = random.randint(200, 500)
            current += step
            self.driver.execute_script(f"window.scrollTo(0, {current});")
            time.sleep(random.uniform(0.3, 1.0))

    def search_products(self, query, max_results=3,
                        price_min=None, price_max=None, **kwargs):
        """
        Поиск товаров на Ozon.
        price_min / price_max: целые числа (рубли)
        """
        if not self.driver:
            self._init_driver()

        results = []

        try:
            print(f"\n[INFO] Поиск на Ozon: '{query}'")

            # Строим URL с фильтрами
            params = f'text={query.replace(" ", "+")}&from_search=true'
            if price_min and price_max:
                params += f'&currency_price={price_min}%3B{price_max}'
            elif price_min:
                params += f'&currency_price={price_min}%3B'
            elif price_max:
                params += f'&currency_price=%3B{price_max}'

            search_url = f'https://www.ozon.ru/search/?{params}'
            print(f"[INFO] URL: {search_url}")

            # Сначала заходим на главную
            print("[INFO] Заходим на главную Ozon...")
            self.driver.get('https://www.ozon.ru/')
            self._random_delay(4, 7)

            if not self._check_and_wait_captcha():
                print("[ERROR] Не удалось пройти блокировку на главной")
                return results

            self._human_scroll()
            self._random_delay(2, 4)

            # Переходим к поиску
            print("[INFO] Переходим к поиску...")
            self.driver.get(search_url)
            self._random_delay(5, 9)

            if not self._check_and_wait_captcha():
                print("[ERROR] Не удалось пройти блокировку")
                return results

            # Скролл для загрузки товаров
            self._human_scroll()
            time.sleep(2)

            print("[INFO] Ищем товары через JavaScript...")

            # Debug: покажем что есть на странице
            debug_info = self.driver.execute_script("""
                var links = document.querySelectorAll('a[href*="/product/"]');
                var tiles = document.querySelectorAll('[data-widget="tile"], [data-widget="searchResultsV2"] .tile, .tile-root, .widget-search-result-container');
                var allAnchors = document.querySelectorAll('a');
                return {
                    product_links: links.length,
                    tiles: tiles.length,
                    total_anchors: allAnchors.length,
                    body_text_preview: (document.body.innerText || '').substring(0, 500)
                };
            """)
            print(f"[DEBUG] product_links={debug_info['product_links']}, tiles={debug_info['tiles']}, total_anchors={debug_info['total_anchors']}")
            print(f"[DEBUG] page preview: {debug_info['body_text_preview'][:300]}")

            # Универсальный подход: берём все ссылки /product/ и извлекаем из контекста
            products_js = self.driver.execute_script("""
                var results = [];
                var seenHrefs = new Set();
                
                var links = document.querySelectorAll('a[href*="/product/"]');
                
                for (var i = 0; i < links.length; i++) {
                    var a = links[i];
                    var href = a.href.split('?')[0];
                    
                    if (seenHrefs.has(href)) continue;
                    if (!href.includes('/product/')) continue;
                    seenHrefs.add(href);
                    
                    // Поднимаемся до карточки
                    var card = a;
                    for (var j = 0; j < 10; j++) {
                        if (!card.parentElement) break;
                        card = card.parentElement;
                        if (card.offsetWidth > 150 && card.offsetHeight > 200) break;
                    }
                    
                    var cardText = card.innerText || '';
                    var lines = cardText.split('\\n').map(function(l) { return l.trim(); }).filter(function(l) { return l.length > 0; });
                    
                    var title = '';
                    var price = '';
                    var rating = '';
                    var possibleTitles = [];
                    
                    for (var k = 0; k < lines.length; k++) {
                        var line = lines[k];
                        
                        // Цена: содержит ₽
                        if (!price && /\\d/.test(line) && line.includes('₽')) {
                            price = line;
                            continue;
                        }
                        
                        // Рейтинг: начинается с цифры.цифра
                        if (!rating && /^\\d\\.\\d/.test(line) && line.length < 30) {
                            var rMatch = line.match(/^(\\d\\.\\d)(\\d*)/);
                            if (rMatch) {
                                rating = rMatch[1];
                                if (rMatch[2]) {
                                    rating += ' (' + rMatch[2] + ' отзывов)';
                                }
                            }
                            continue;
                        }
                        
                        // Игнорируем технические слова и промо
                        if (line.includes('₽') || /^\\d+$/.test(line) || /^(Вау|Хит|Скидк|Акци|Распродаж|Выгодн|Супер|Топ|Бестселлер|Новинк|Популярн|Express|В корзину|Смотреть|Остал|\\d+\\s+шт|Доставк|Завтра|Сегодня|Ozon|Лучшая|Мгновен)/i.test(line)) {
                            continue;
                        }
                        
                        // Оставшиеся строки собираем как кандидатов на название
                        if (line.length > 5) {
                            possibleTitles.push(line);
                        }
                    }
                    
                    // Выбираем самую длинную строку (вероятнее всего это название товара)
                    if (possibleTitles.length > 0) {
                        possibleTitles.sort(function(a, b) { return b.length - a.length; });
                        title = possibleTitles[0];
                    }
                    
                    // Fallback: aria-label
                    if (!title || title.length < 5) {
                        title = a.getAttribute('aria-label') || a.title || '';
                    }
                    
                    if (title && title.length > 5) {
                        results.push({
                            title: title.substring(0, 200),
                            price: price || 'Цена не указана',
                            url: href,
                            rating: rating,
                            description: cardText.replace(/\n+/g, ' ').trim()
                        });
                    }
                    
                    if (results.length >= Math.max(100, arguments[0] * 5)) break;
                }
                
                return results;
            """, max_results)

            print(f"[INFO] JS извлёк {len(products_js)} товаров")

            if not products_js:
                # Стратегия 2: Fallback через page source
                print("[INFO] Пробуем извлечь из page source...")
                products_js = self._extract_from_page_source()

            query_words = [w.lower() for w in query.split() if w.strip()]

            for item in products_js:
                title = item.get('title', '')
                if not title:
                    continue

                # Убрана строгая фильтрация по названию,
                # так как встроенный поиск Ozon работает хорошо,
                # а строгий фильтр часто отсекает валидные результаты.

                # Дедупликация
                if any(r['title'] == title for r in results):
                    continue

                product = {
                    'title': title,
                    'price': item.get('price', 'Цена не указана'),
                    'url': item.get('url', '#'),
                    'rating': item.get('rating', ''),
                    'location': 'Ozon',
                    'date': '',
                    'description': '',
                }

                results.append(product)
                print(f"[OK] {len(results)}. {product['title'][:50]}  |  {product['price']}")

                if len(results) >= max_results:
                    break

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()

        print(f"[ИТОГО] Найдено: {len(results)}")
        return results

    def _extract_from_page_source(self):
        """Извлечение данных из JSON в page source (Ozon SSR)"""
        import re, json
        products = []
        try:
            source = self.driver.page_source
            # Ozon встраивает JSON данные в __NEXT_DATA__ или window.__NUXT__
            match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', source)
            if match:
                data = json.loads(match.group(1))
                # Пробуем найти товары в JSON структуре
                items = self._find_products_in_json(data)
                for item in items:
                    if item.get('title'):
                        products.append(item)
        except Exception as e:
            print(f"[WARN] Не удалось извлечь из page source: {e}")
        return products

    def _find_products_in_json(self, data, depth=0):
        """Рекурсивный поиск товаров в JSON"""
        products = []
        if depth > 10:
            return products

        if isinstance(data, dict):
            # Проверяем, содержит ли dict данные о товаре
            if 'title' in data and 'price' in data:
                products.append({
                    'title': str(data.get('title', '')),
                    'price': str(data.get('price', 'Цена не указана')),
                    'url': data.get('action', {}).get('link', '#') if isinstance(data.get('action'), dict) else '#',
                    'rating': str(data.get('rating', '')),
                })
            for v in data.values():
                products.extend(self._find_products_in_json(v, depth + 1))
        elif isinstance(data, list):
            for item in data:
                products.extend(self._find_products_in_json(item, depth + 1))

        return products

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

    def __del__(self):
        """Подавляем ошибку очистки uc.Chrome на Windows"""
        try:
            self.close()
        except Exception:
            pass


if __name__ == '__main__':
    print("=" * 60)
    print("ТЕСТ: Парсер Ozon (undetected-chromedriver)")
    print("=" * 60)

    with OzonParser(headless=False) as parser:
        results = parser.search_products('Nike Jordan', max_results=3)

        print("\n" + "=" * 60)
        for i, p in enumerate(results, 1):
            print(f"{i}. {p['title']}")
            print(f"    {p['price']}")
            print(f"    {p['rating']}")
            print(f"    {p['url']}")
            print()

    input("Enter для выхода...")
