import os
import re
import random
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


class HumanBehaviorMixin:
    """
    Mixin de PriceScraper: configuração do Chrome (setup_driver) e simulação de
    comportamento humano (mouse, digitação, delays, scroll), além de helpers genéricos
    de espera/parsing de página que não são específicos de nenhum site (Kabum/Amazon).
    """

    def setup_driver(self):
        """Configura Chrome com comportamento humanizado"""
        try:
            chrome_options = Options()

            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--remote-debugging-port=9222")

            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins-discovery")

            user_agents = [
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            ]
            chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")

            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")

            chromedriver_path = os.environ.get("CHROME_DRIVER_PATH", "/usr/local/bin/chromedriver")
            if os.path.exists(chromedriver_path):
                service = Service(chromedriver_path)
            else:
                service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            self.driver.set_page_load_timeout(45)
            self.driver.set_script_timeout(30)

            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']})")

            return True

        except Exception as e:
            print(f"ERRO CRITICO: Falha ao configurar driver - {e}")
            self.driver = None
            return False

    def wait_for_page_load(self, timeout=30):
        """Espera página carregar completamente"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            return False

    def human_mouse_movement(self, element):
        """Simula movimento natural de mouse"""
        try:
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(element,
                                                random.randint(-5, 5),
                                                random.randint(-5, 5))
            actions.perform()
            time.sleep(random.uniform(0.1, 0.3))
            return True
        except:
            return False

    def human_typing(self, element, text, clear_first=True):
        """Simula digitação humanizada"""
        try:
            self.human_mouse_movement(element)
            element.click()
            time.sleep(random.uniform(0.2, 0.5))

            if clear_first:
                element.clear()
                time.sleep(random.uniform(0.1, 0.3))

            for i, char in enumerate(text):
                element.send_keys(char)

                if char == ' ':
                    delay = random.uniform(0.1, 0.3)
                elif i > 0 and text[i - 1] == ' ':
                    delay = random.uniform(0.05, 0.15)
                else:
                    delay = random.uniform(0.08, 0.2)

                if random.random() < 0.1:
                    delay += random.uniform(0.3, 0.8)

                time.sleep(delay)

            return True

        except Exception as e:
            print(f"ERRO: Falha na digitacao - {e}")
            return False

    def human_delay(self, min_sec=1, max_sec=3):
        """Delay humanizado"""
        time.sleep(random.uniform(min_sec, max_sec))

    def progressive_scroll(self, max_scrolls=8):
        """Scroll progressivo para carregar todos os produtos (lazy loading)"""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scrolls_without_change = 0

            for i in range(max_scrolls):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.5, 2.5))

                new_height = self.driver.execute_script("return document.body.scrollHeight")

                if new_height == last_height:
                    scrolls_without_change += 1
                    if scrolls_without_change >= 2:
                        break
                else:
                    scrolls_without_change = 0
                    last_height = new_height

                if random.random() < 0.3:
                    self.driver.execute_script("window.scrollBy(0, -200);")
                    time.sleep(random.uniform(0.3, 0.7))

            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(0.5, 1.0))

        except Exception as e:
            print(f"ERRO: Falha no scroll progressivo - {e}")

    def clean_price_text(self, text):
        """Extrai valor numérico de texto de preço"""
        if not text:
            return 0.0

        try:
            price_clean = re.sub(r'[^\d,.]', '', text)

            if not price_clean:
                return 0.0

            if ',' not in price_clean and '.' not in price_clean:
                result = float(price_clean)
                return result if result >= 20.0 else 0.0

            if ',' in price_clean and '.' in price_clean:
                if price_clean.rindex(',') > price_clean.rindex('.'):
                    price_clean = price_clean.replace('.', '').replace(',', '.')
                else:
                    price_clean = price_clean.replace(',', '')
            elif ',' in price_clean:
                parts = price_clean.split(',')
                if len(parts) == 2 and len(parts[1]) == 2:
                    price_clean = price_clean.replace(',', '.')
                else:
                    price_clean = price_clean.replace(',', '')
            elif '.' in price_clean:
                parts = price_clean.split('.')
                if len(parts) > 1 and len(parts[-1]) == 2:
                    pass
                else:
                    price_clean = price_clean.replace('.', '')

            result = float(price_clean)
            return result if result >= 20.0 else 0.0

        except (ValueError, AttributeError):
            return 0.0

    def try_find_element_safe(self, selectors, timeout=5, parent_element=None):
        """Tenta encontrar elemento com múltiplos seletores"""
        search_root = parent_element if parent_element else self.driver

        for selector in selectors:
            try:
                if parent_element:
                    element = search_root.find_element(By.CSS_SELECTOR, selector)
                else:
                    element = WebDriverWait(search_root, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )

                if element and element.is_displayed():
                    return element

            except (TimeoutException, NoSuchElementException):
                continue

        return None

    def close_popups(self):
        """Fecha popups que aparecem nas páginas"""
        try:
            close_selectors = [
                "button[aria-label*='fechar']",
                "button[aria-label*='close']",
                ".close-button",
                ".modal-close",
                ".btn-close",
                "#onesignal-slidedown-cancel-button"
            ]

            for selector in close_selectors:
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in close_buttons:
                        if button.is_displayed():
                            button.click()
                            time.sleep(1)
                            break
                except:
                    continue
        except:
            pass
