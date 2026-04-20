"""
Парсер Wildberries через Selenium (обход ограничений API).
Аналогичный подход как у Авито — Selenium + anti-detection.
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import time
import random
import re


class WildberriesParser:

    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None

    def _init_driver(self):

        print("[INFO] Запускаем браузер (Wildberries)...")

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
        """Проверка и ручное решение капчи Wildberries"""
        captcha_selectors = [
            'iframe[src*="captcha"]',
            'div[class*="captcha"]',
            'div[class*="Captcha"]',
            '[class*="recaptcha"]',
            '[id*="recaptcha"]',
            '[class*="robot"]',
            'div[class*="blocked"]',
        ]

        for selector in captcha_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print("\n" + "!" * 60)
                    print("ОБНАРУЖЕНА КАПЧА (Wildberries)!")
                    print("Пожалуйста, решите капчу в открытом браузере.")
                    print("Ожидание до 120 секунд...")
                    print("!" * 60 + "\n")

                    for i in range(120):
                        time.sleep(1)

                        # Проверяем, появились ли товары
                        items = self.driver.find_elements(By.CSS_SELECTOR,
                            '.product-card, [class*="product-card"], .j-card-item'
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
        Поиск товаров на Wildberries.
        price_min / price_max: целые числа (рубли)
        """
        if not self.driver:
            self._init_driver()

        results = []

        try:
            print(f"\n[INFO] Поиск на Wildberries: '{query}'")

            # Строим URL
            search_query = query.replace(' ', '+')
            search_url = f'https://www.wildberries.ru/catalog/0/search.aspx?search={search_query}'

            # Добавляем фильтры по цене
            if price_min:
                search_url += f'&priceU={int(price_min) * 100}'
            if price_max:
                if price_min:
                    search_url = search_url.replace(f'priceU={int(price_min) * 100}',
                                                     f'priceU={int(price_min) * 100}%3B{int(price_max) * 100}')
                else:
                    search_url += f'&priceU=0%3B{int(price_max) * 100}'

            print(f"[INFO] URL: {search_url}")

            # Сначала заходим на главную
            self.driver.get('https://www.wildberries.ru/')
            self._random_delay(3, 5)

            self._check_and_wait_captcha()

            # Переходим к поиску
            self.driver.get(search_url)
            self._random_delay(4, 7)

            if not self._check_and_wait_captcha():
                print("[ERROR] Не удалось пройти капчу")
                return results

            # Скролл для загрузки товаров
            for scroll_pos in [300, 600, 900, 1200, 1500]:
                self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
                time.sleep(random.uniform(0.5, 1.5))

            # Дополнительная пауза для подгрузки
            time.sleep(2)

            print("[INFO] Ищем товары...")

            # Селекторы карточек WB
            item_selectors = [
                '.product-card',
                '[class*="product-card"]',
                '.j-card-item',
                'article.product-card',
                '[data-nm-id]',
                '.product-card-list .product-card',
            ]

            items = []
            for sel in item_selectors:
                items = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if items:
                    print(f"[INFO] Селектор: {sel} → {len(items)} карточек")
                    break

            if not items:
                # Fallback — ищем ссылки на товары
                items = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/catalog/"][class*="product"]')
                print(f"[INFO] Fallback (product links): {len(items)}")

            print(f"[INFO] Найдено на странице: {len(items)}")

            items_to_parse = items[:max(max_results * 5, 50)]

            query_words = [w.lower() for w in query.split() if w.strip()]

            for idx, item in enumerate(items_to_parse, 1):
                try:
                    product = self._parse_item(item, idx)
                    if not product:
                        continue

                    # Строгая фильтрация: ДОЛЖНЫ присутствовать ВСЕ слова из запроса
                    title_lower = product['title'].lower()
                    # Убираем лишние символы для точного соответствия
                    import string
                    title_clean = title_lower.translate(str.maketrans('', '', string.punctuation))
                    
                    if query_words and not all(word in title_clean for word in query_words):
                        print(f"[SKIP] Неточные слова: {product['title'][:50]}")
                        continue

                    # Дедупликация
                    if any(r['title'] == product['title'] for r in results):
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
        """Парсинг одной карточки Wildberries"""
        product = {}

        # Название
        title_selectors = [
            '.product-card__name',
            '[class*="product-card__name"]',
            'span.goods-name',
            '[class*="goods-name"]',
            '.product-card__brand-wrap + span',
            '[class*="product-card"] span[class*="name"]',
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

        # Бренд (WB часто показывает бренд отдельно)
        brand = ''
        brand_selectors = [
            '.product-card__brand',
            '[class*="product-card__brand"]',
            'span.brand-name',
            '[class*="brand-name"]',
        ]
        for sel in brand_selectors:
            try:
                el = item.find_element(By.CSS_SELECTOR, sel)
                text = el.text.strip().rstrip(' /')
                if text:
                    brand = text
                    break
            except Exception:
                continue

        if not product.get('title'):
            # Fallback: берём весь текст элемента
            try:
                text = item.text.strip()
                if text:
                    lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 3]
                    # Пропускаем цену и рейтинг
                    for line in lines:
                        if not re.match(r'^[\d\s₽%]+$', line) and '⭐' not in line:
                            product['title'] = line[:200]
                            break
            except Exception:
                pass

        if not product.get('title'):
            return None

        # Добавляем бренд к названию
        if brand and brand.lower() not in product['title'].lower():
            product['title'] = f"{brand} {product['title']}"

        # Цена
        product['price'] = 'Цена не указана'
        price_selectors = [
            '.price__lower-price',
            '[class*="lower-price"]',
            'ins.price__lower-price',
            '.product-card__price [class*="lower"]',
            '[class*="price"] ins',
            '.price-block__final-price',
        ]

        for sel in price_selectors:
            try:
                el = item.find_element(By.CSS_SELECTOR, sel)
                text = el.text.strip()
                if text and any(c.isdigit() for c in text):
                    product['price'] = text
                    break
            except Exception:
                continue

        if product['price'] == 'Цена не указана':
            # Fallback — ищем цену в тексте
            try:
                all_text = item.text or ''
                price_match = re.search(r'(\d[\d\s]*\d)\s*₽', all_text)
                if price_match:
                    product['price'] = price_match.group(0).strip()
            except Exception:
                pass

        # Ссылка
        product['url'] = '#'
        try:
            link_selectors = [
                'a[href*="/catalog/"]',
                'a.product-card__link',
                '[class*="product-card__link"]',
                'a',
            ]
            for sel in link_selectors:
                try:
                    el = item.find_element(By.CSS_SELECTOR, sel)
                    href = el.get_attribute('href')
                    if href and ('wildberries.ru' in href or href.startswith('/')):
                        if href.startswith('/'):
                            href = 'https://www.wildberries.ru' + href
                        product['url'] = href
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Рейтинг
        product['rating'] = ''
        try:
            rating_selectors = [
                '.address-rate-mini',
                '[class*="star-rating"]',
                '.product-card__rating',
                '[class*="rating"]',
            ]
            for sel in rating_selectors:
                try:
                    el = item.find_element(By.CSS_SELECTOR, sel)
                    text = el.text.strip()
                    if text:
                        product['rating'] = text
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Доп. поля для совместимости
        product['location'] = 'Wildberries'
        product['date'] = ''
        
        # Собираем ВЕСЬ текст карточки для поиска по описанию
        try:
            full_text = item.text.strip()
            # Убираем переносы строк для компактности в поиске
            product['description'] = " ".join(full_text.split())
        except Exception:
            product['description'] = brand

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
    print("ТЕСТ: Парсер Wildberries (Selenium)")
    print("=" * 60)

    with WildberriesParser(headless=False) as parser:
        results = parser.search_products('Nike', max_results=5)

        print("\n" + "=" * 60)
        for i, p in enumerate(results, 1):
            print(f"{i}. {p['title']}")
            print(f"    {p['price']}")
            print(f"    {p['rating']}")
            print(f"    {p['url']}")
            print()

    input("Enter для выхода...")
