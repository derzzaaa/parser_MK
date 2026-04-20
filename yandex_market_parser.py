from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random


class YandexMarketParser:

    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None

    def _init_driver(self):

        print("[INFO] Запускаем браузер (Яндекс Маркет)...")

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
        """Проверка и ручное решение капчи Яндекса (SmartCaptcha)"""
        captcha_selectors = [
            'iframe[src*="captcha"]',
            'div[class*="captcha"]',
            'div[class*="Captcha"]',
            'div[class*="CheckboxCaptcha"]',
            'form[action*="checkcaptcha"]',
            '[class*="smartcaptcha"]',
            '[class*="SmartCaptcha"]',
            'div[class*="AdvancedCaptcha"]',
            '[id*="checkbox-captcha"]',
        ]

        for selector in captcha_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print("\n" + "!" * 60)
                    print("ОБНАРУЖЕНА КАПЧА (Яндекс)!")
                    print("Пожалуйста, решите капчу в открытом браузере.")
                    print("Ожидание до 120 секунд...")
                    print("!" * 60 + "\n")

                    for i in range(120):
                        time.sleep(1)

                        # Проверяем, появились ли товары
                        items = self.driver.find_elements(By.CSS_SELECTOR,
                            '[data-auto="snippet-card"], [data-autotest-id="product-snippet"], '
                            '[data-zone-name="snippetList"] article, [data-baobab-name="snippet"]'
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

    def search_products(self, query, max_results=3,
                        price_min=None, price_max=None, **kwargs):
        """
        Поиск товаров на Яндекс Маркете.
        price_min / price_max: целые числа (рубли)
        """
        if not self.driver:
            self._init_driver()

        results = []

        try:
            print(f"\n[INFO] Поиск на Яндекс Маркете: '{query}'")

            # Строим URL
            params = f'text={query.replace(" ", "+")}'
            if price_min:
                params += f'&pricefrom={price_min}'
            if price_max:
                params += f'&priceto={price_max}'

            search_url = f'https://market.yandex.ru/search?{params}'
            print(f"[INFO] URL: {search_url}")

            # Сначала заходим на главную
            self.driver.get('https://market.yandex.ru/')
            self._random_delay(3, 5)

            self._check_and_wait_captcha()

            # Переходим к поиску
            self.driver.get(search_url)
            self._random_delay(4, 8)

            if not self._check_and_wait_captcha():
                print("[ERROR] Не удалось пройти капчу")
                return results

            # Скролл как человек
            for scroll_pos in [300, 600, 900, 1200]:
                self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
                time.sleep(random.uniform(0.5, 1.5))

            print("[INFO] Ищем товары...")

            # Несколько вариантов селекторов карточек (Яндекс часто меняет вёрстку)
            item_selectors = [
                '[data-auto="snippet-card"]',
                '[data-autotest-id="product-snippet"]',
                'article[data-auto="searchOrganic"]',
                '[data-baobab-name="snippet"]',
                '[data-zone-name="snippetList"] article',
                'div[data-apiary-widget-name*="SearchSnippet"]',
                'main article',
            ]

            items = []
            for sel in item_selectors:
                items = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if items:
                    print(f"[INFO] Селектор: {sel} → {len(items)} карточек")
                    break

            if not items:
                # Последняя попытка — ищем все article
                items = self.driver.find_elements(By.TAG_NAME, 'article')
                print(f"[INFO] Fallback (article): {len(items)} карточек")

            print(f"[INFO] Найдено на странице: {len(items)}")

            items_to_parse = items[:max(max_results * 3, 20)]

            query_words = [w.lower() for w in query.split() if len(w) > 1]

            for idx, item in enumerate(items_to_parse, 1):
                try:
                    product = self._parse_item(item, idx)
                    if not product:
                        continue

                    # Фильтрация по релевантности
                    title_lower = product['title'].lower()
                    if query_words and not any(word in title_lower for word in query_words):
                        print(f"[SKIP] Не релевантно: {product['title'][:50]}")
                        continue

                    results.append(product)
                    print(f"[OK] {len(results)}. {product['title'][:50]}  |  {product['price']}")

                    if len(results) >= max_results:
                        break

                except Exception as e:
                    print(f"[SKIP] Ошибка товар {idx}: {e}")
                    continue

                time.sleep(random.uniform(0.2, 0.5))

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()

        print(f"[ИТОГО] Найдено: {len(results)}")
        return results

    def _parse_item(self, item, idx):
        """Парсинг одной карточки Яндекс Маркета"""
        product = {}

        # Название
        title_selectors = [
            '[data-auto="snippet-title"]',
            '[data-auto="snippet-title-header"]',
            '[data-autotest-id="product-snippet-title"]',
            'h3[data-zone-name="title"] a',
            'h3 a span',
            'a[title]',
            'h3',
        ]

        for sel in title_selectors:
            try:
                el = item.find_element(By.CSS_SELECTOR, sel)
                text = el.text.strip()
                if text and len(text) > 3:
                    product['title'] = text
                    break
            except Exception:
                continue

        if not product.get('title'):
            # Fallback: ищем любой длинный текст в ссылке
            try:
                links = item.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    title_attr = link.get_attribute('title')
                    if title_attr and len(title_attr) > 5:
                        product['title'] = title_attr
                        break
                    text = link.text.strip()
                    if text and len(text) > 10:
                        product['title'] = text
                        break
            except Exception:
                pass

        if not product.get('title'):
            return None

        # Цена
        price_selectors = [
            '[data-auto="snippet-price-current"]',
            '[data-auto="price-value"]',
            '[data-auto="mainPrice"] span',
            '[data-autotest-id="product-snippet-price"]',
            'span[data-auto="snippet-price"]',
            '[class*="price"]',
        ]

        product['price'] = 'Цена не указана'
        for sel in price_selectors:
            try:
                el = item.find_element(By.CSS_SELECTOR, sel)
                text = el.text.strip()
                if text and any(c.isdigit() for c in text):
                    product['price'] = text
                    break
            except Exception:
                continue

        # Ссылка
        product['url'] = '#'
        try:
            link_selectors = [
                '[data-auto="snippet-title"] a',
                '[data-auto="snippet-title-header"] a',
                'h3 a',
                'a[href*="/product/"]',
                'a[href*="/offer/"]',
                'a',
            ]
            for sel in link_selectors:
                try:
                    el = item.find_element(By.CSS_SELECTOR, sel)
                    href = el.get_attribute('href')
                    if href and ('market.yandex' in href or href.startswith('/')):
                        if href.startswith('/'):
                            href = 'https://market.yandex.ru' + href
                        product['url'] = href
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Рейтинг
        product['rating'] = ''
        rating_selectors = [
            '[data-auto="rating-badge-value"]',
            '[data-auto="snippet-rating"]',
            '[aria-label*="рейтинг"]',
            '[class*="rating"]',
        ]
        for sel in rating_selectors:
            try:
                el = item.find_element(By.CSS_SELECTOR, sel)
                text = el.text.strip() or el.get_attribute('aria-label') or ''
                if text:
                    product['rating'] = text
                    break
            except Exception:
                continue

        # Доп. поля для совместимости
        product['location'] = 'Яндекс Маркет'
        product['date'] = ''
        
        # Собираем ВЕСЬ текст карточки для поиска по описанию
        try:
            full_text = item.text.strip()
            product['description'] = " ".join(full_text.split())
        except Exception:
            product['description'] = ''

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
    print("ТЕСТ: Парсер Яндекс Маркет (с обработкой капчи)")
    print("=" * 60)

    with YandexMarketParser(headless=False) as parser:
        results = parser.search_products('Nike Jordan', max_results=3)

        print("\n" + "=" * 60)
        for i, p in enumerate(results, 1):
            print(f"{i}. {p['title']}")
            print(f"    {p['price']}")
            print(f"    {p['rating']}")
            print(f"    {p['url']}")
            print()

    input("Enter для выхода...")
