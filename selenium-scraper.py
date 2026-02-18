import os
import time
import random
import re
from supabase import create_client, Client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from dotenv import load_dotenv
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Palavras que indicam que não é o produto puro (kits, acessórios, PCs completos)
# REMOVIDOS intencionalmente: 'suporte', 'cooler', 'ventoinha', 'base', 'case', 'gabinete'
# pois aparecem em descrições técnicas legítimas (ex: "sem cooler", "suporte a PCIe",
# "base clock") e 'gabinete'/'case' são categorias de produto válidas.
EXCLUSION_KEYWORDS = [
    'pc ', 'computador', 'completo', 'kit', 'combo', 'notebook', 'laptop',
    'desktop', 'workstation', 'all-in-one', 'torre', 'cpu completo',
    'bracket', 'shield', 'parafuso', 'cabo', 'adaptador', 'extensor', 'acessorio'
]

# Sufixos que indicam PRODUTO DIFERENTE (não podem aparecer se não estão no modelo buscado)
VARIANT_SUFFIXES = [
    'xt', 'ti', 'super', 'kf', 'f', 'ultra', 'max', 'pro',
    'plus', 'boost', 'overclocked', 'turbo', 'extreme', 'premium',
    'x3d', '3d', 's', 'g', 'x'  # 'x' adicionado para cobrir 7600X, 5800X, etc.
]

# Palavras genéricas que podem aparecer sem problema (são apenas marketing/descrição)
GENERIC_WORDS = [
    'radeon', 'geforce', 'ryzen', 'core', 'intel', 'amd', 'nvidia',
    'processador', 'processor', 'cpu', 'gpu', 'ssd', 'hdd', 'memoria',
    'memory', 'ram', 'placa', 'video', 'mae', 'motherboard', 'fonte',
    'power', 'supply', 'psu', 'gaming', 'oc', 'edition', 'overclock',
    'series', 'tri', 'dual', 'fan', 'fans', 'ventilador', 'refrigeracao',
    'western', 'digital', 'kingston', 'corsair', 'crucial', 'samsung',
    'seagate', 'wd', 'xpg', 'adata', 'sandisk', 'gskill', 'msi',
    'asus', 'gigabyte', 'asrock', 'evga', 'nzxt', 'fractal', 'design',
    'cooler', 'master', 'rise', 'mode', 'com', 'with', 'de', 'da', 'do',
    'para', 'e', 'and', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for',
    'black', 'white', 'rgb', 'argb', 'led', 'custom', 'windforce', 'phantom',
    'strix', 'tuf', 'rog', 'aorus', 'ventus', 'eagle', 'armor', 'twin', 'frozr',
    'nitro', 'pulse', 'red', 'devil', 'v2', 'v1', 'ex', 'lx', 'lpx',
    # Palavras descritivas portuguesas comuns que não fazem parte de nomes de modelo
    'preto', 'preta', 'branco', 'branca', 'sem', 'ate', 'max', 'turbo',
    'cache', 'nucleos', 'nucleo', 'geracao', 'interno', 'interna',
    'chipset', 'socket', 'suporte', 'compativel', 'alta', 'alto',
    'velocidade', 'leitura', 'gravacao', 'desempenho', 'gamer',
    'cooler', 'ventoinha', 'base', 'gabinete', 'case', 'torre'
]


class PriceScraper:
    """Web scraper para buscar preços em Kabum e Amazon com comportamento humanizado"""

    def __init__(self):
        self.driver = None
        self.setup_driver()

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

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

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

    def extract_storage_capacity(self, text):
        """Extrai capacidade de armazenamento do texto. Retorna valor normalizado em GB."""
        if not text:
            return None

        text_lower = text.lower()
        match = re.search(r'(\d+)\s*(tb|gb)', text_lower)

        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if unit == 'tb':
                return value * 1024
            return value

        return None

    def extract_key_tokens(self, text):
        """Extrai tokens-chave de um texto (números e códigos alfanuméricos importantes)."""
        if not text:
            return []

        text_lower = text.lower()
        tokens = re.split(r'[\s]+', text_lower)

        key_tokens = []
        for token in tokens:
            normalized_token = token.replace('-', '').replace('_', '')

            if not normalized_token:
                continue

            # Ignorar tokens muito curtos (1 char) e palavras genéricas
            if len(normalized_token) < 2:
                continue

            if normalized_token in GENERIC_WORDS:
                continue

            # Manter qualquer token que não seja genérico:
            # - com dígitos: "9070", "265k", "32gb"
            # - sufixos de variante: "xt", "ti", "kf"
            # - tokens curtos significativos: "ii", "wifi", "ax", "itx", "atx"
            # - códigos alfanuméricos longos: "b550mplus", "rmwafbargb"
            key_tokens.append(normalized_token)

        return key_tokens

    def is_exact_product_match(self, product_name, search_model, search_brand=None):
        """Valida se o produto encontrado corresponde exatamente ao modelo buscado."""
        if not product_name or not search_model:
            return False

        product_name_lower = product_name.lower()

        for keyword in EXCLUSION_KEYWORDS:
            if keyword in product_name_lower:
                return False

        search_tokens = self.extract_key_tokens(search_model)
        product_tokens = self.extract_key_tokens(product_name)

        if not search_tokens:
            return search_model.lower() in product_name_lower

        product_name_normalized = product_name_lower.replace('-', '').replace('_', '')

        for token in search_tokens:
            if token not in product_name_normalized:
                return False

        search_variants = [t for t in search_tokens if t in VARIANT_SUFFIXES]

        # Verificar variantes apenas quando aparecem ADJACENTES a tokens numéricos do modelo.
        # Ex: rejeita "7600 xt" mas aceita "7600, 5.1GHz Max Turbo" (Max não é variante do modelo)
        search_numeric_for_variants = [t for t in search_tokens if re.search(r'\d', t)]

        for variant in VARIANT_SUFFIXES:
            if variant in search_variants:
                continue  # Variante faz parte da busca, ok

            # Verificar se a variante aparece colada ou logo após algum número do modelo
            for num in search_numeric_for_variants:
                # Padrões: "7600xt", "7600 xt", "7600-xt"
                pattern = re.compile(r'\b' + re.escape(num) + r'[\s\-]?' + re.escape(variant) + r'\b')
                if pattern.search(product_name_normalized):
                    return False

        search_numeric = [t for t in search_tokens if re.search(r'\d', t)]
        product_numeric = [t for t in product_tokens if re.search(r'\d', t)]

        for search_num in search_numeric:
            found_match = False
            for prod_num in product_numeric:
                if search_num == prod_num:
                    found_match = True
                    break
                if prod_num.startswith(search_num) and len(prod_num) > len(search_num):
                    suffix = prod_num[len(search_num):]
                    if suffix in VARIANT_SUFFIXES:
                        return False

            if not found_match:
                if search_num not in product_name_normalized:
                    return False

                for variant in VARIANT_SUFFIXES:
                    pattern = search_num + variant
                    if pattern in product_name_normalized:
                        if variant not in [t for t in search_tokens if t in VARIANT_SUFFIXES]:
                            return False

        search_capacity = self.extract_storage_capacity(search_model)
        product_capacity = self.extract_storage_capacity(product_name)

        if search_capacity is not None:
            if product_capacity is None or product_capacity != search_capacity:
                return False

        if search_brand:
            if search_brand.lower() not in product_name_lower:
                return False

        return True

    # -------------------------------------------------------------------------
    # KABUM helpers
    # -------------------------------------------------------------------------

    def click_kabum_filter(self):
        """
        Tenta clicar no checkbox 'KaBuM!' no filtro 'Vendido por'.
        Retorna True se encontrou e clicou, False se não encontrou.
        - JS usado apenas para scroll (evita ElementClickIntercepted por elemento coberto)
        - ActionChains para o clique real (preserva comportamento humanizado)
        - Índice usado em vez de referência Python (evita StaleElementReference)
        """
        try:
            # Encontrar índice da label pelo texto via JS — sem referência Python
            target_index = self.driver.execute_script("""
                var labels = document.querySelectorAll('label.filterOption');
                for (var i = 0; i < labels.length; i++) {
                    if (labels[i].textContent.toLowerCase().indexOf('kabum') !== -1) {
                        return i;
                    }
                }
                return -1;
            """)

            if target_index == -1:
                print("[KABUM] Filtro 'KaBuM!' nao encontrado - sem estoque proprio nessa busca")
                return False

            # Scroll via JS para o centro da tela — evita que fique atrás do header
            self.driver.execute_script("""
                var labels = document.querySelectorAll('label.filterOption');
                var label = labels[arguments[0]];
                if (label) label.scrollIntoView({block: 'center', behavior: 'smooth'});
            """, target_index)

            # Aguardar scroll terminar e página estabilizar
            time.sleep(random.uniform(0.6, 1.0))

            # Verificar se já está marcado via JS (sem guardar referência)
            already_checked = self.driver.execute_script("""
                var labels = document.querySelectorAll('label.filterOption');
                var label = labels[arguments[0]];
                if (!label) return null;
                var input = label.querySelector('input');
                return input ? input.checked : null;
            """, target_index)

            if already_checked is None:
                print("[KABUM] Filtro sumiu apos scroll")
                return False

            if already_checked:
                print("[KABUM] Filtro 'KaBuM!' ja estava selecionado")
                return True

            # Buscar referência fresca imediatamente antes de clicar
            labels_fresh = self.driver.find_elements(By.CSS_SELECTOR, "label.filterOption")
            if target_index >= len(labels_fresh):
                print("[KABUM] Filtro sumiu apos scroll")
                return False

            checkbox = labels_fresh[target_index].find_element(By.CSS_SELECTOR, "input")

            # Clique humanizado via ActionChains
            actions = ActionChains(self.driver)
            actions.move_to_element(checkbox)
            actions.pause(random.uniform(0.1, 0.3))
            actions.click()
            actions.perform()

            print("[KABUM] Filtro 'KaBuM!' aplicado")
            return True

        except Exception as e:
            print(f"[KABUM] Falha ao aplicar filtro: {e}")
            return False

    def get_kabum_product_url(self, container):
        """Extrai a URL direta do produto Kabum a partir do card."""
        try:
            link = container.find_element(By.CSS_SELECTOR, "a")
            href = link.get_attribute("href")
            if href and "kabum.com.br" in href:
                return href
        except:
            pass
        return None

    # -------------------------------------------------------------------------
    # AMAZON helpers
    # -------------------------------------------------------------------------

    def check_amazon_shipped_by_amazon(self):
        """
        Verifica na página do produto Amazon se é vendido e enviado pela Amazon.
        Retorna True  → Amazon vende e envia
                False → Vendedor/envio externo
                None  → Não foi possível determinar
        """
        try:
            self.wait_for_page_load(timeout=15)
            self.human_delay(2, 3)

            amazon_indicators = [
                "amazon.com.br",
                "vendido pela amazon",
                "enviado pela amazon",
                "vendido e enviado por amazon",
            ]
            third_party_indicators = [
                "loja parceira",
                "vendedor parceiro",
            ]

            info_selectors = [
                "#merchant-info",
                "#tabular-buybox",
                "#buybox",
                "#buyBoxAccordion",
                "#shipsFromSoldBy_feature_div",
                "#price_feature_div",
                ".a-section.a-spacing-small.a-padding-small",
            ]

            for selector in info_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.lower()
                        if not text:
                            continue
                        if any(ind in text for ind in amazon_indicators):
                            return True
                        if any(ind in text for ind in third_party_indicators):
                            return False
                except:
                    continue

            # Fallback: busca no corpo completo da página
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "vendido e enviado por amazon" in page_text:
                    return True
                if "vendido por amazon" in page_text and "enviado por amazon" in page_text:
                    return True
                if any(ind in page_text for ind in third_party_indicators):
                    return False
            except:
                pass

            return None

        except Exception as e:
            print(f"[AMAZON] Falha ao verificar vendedor: {e}")
            return None

    # -------------------------------------------------------------------------
    # MAIN SEARCH METHODS
    # -------------------------------------------------------------------------

    def search_kabum(self, component):
        """
        Busca produto na Kabum.
        Aplica filtro 'KaBuM!' (só aceita itens vendidos pela própria Kabum).
        Retorna o mais barato com URL direta do produto.
        """
        produto = component['name']
        marca = component.get('brand')
        modelo = component.get('model')

        print(f"\n[KABUM] Buscando: {produto}")
        if modelo:
            print(f"[KABUM] Modelo para validacao: {modelo}")

        try:
            self.driver.get("https://www.kabum.com.br/")

            if not self.wait_for_page_load():
                self.driver.refresh()
                if not self.wait_for_page_load():
                    print("ERRO: Kabum nao carregou")
                    return None

            search_selectors = [
                "input[placeholder*='Busque']",
                "#input-busca",
                "input[data-testid='input-busca']",
                "input[placeholder*='buscar']",
                ".sc-fqkvVR input",
                "[data-cy='search-input']",
                "input.sc-fqkvVR"
            ]

            search_element = self.try_find_element_safe(search_selectors, timeout=10)

            if not search_element:
                print("ERRO: Campo de busca nao encontrado na Kabum")
                return None

            search_term = f"{marca} {produto}" if marca and marca.lower() not in produto.lower() else produto

            if not self.human_typing(search_element, search_term):
                print("ERRO: Falha ao digitar na Kabum")
                return None

            self.human_delay(0.5, 1.5)
            search_element.send_keys(Keys.ENTER)
            self.human_delay(4, 7)
            self.wait_for_page_load()

            # Scroll inicial para garantir que filtros e produtos carregaram
            print("[KABUM] Scroll inicial...")
            self.progressive_scroll(max_scrolls=3)

            # Aplicar filtro KaBuM! — sem filtro, não aceitamos nenhum item
            filter_applied = self.click_kabum_filter()
            if not filter_applied:
                return None

            # Aguardar recarregamento após filtro
            self.human_delay(3, 5)
            self.wait_for_page_load()

            # Esperar explicitamente pelos cards ou pela mensagem de vazio
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: (
                        d.find_elements(By.CSS_SELECTOR, ".productCard, [data-testid='product-card'], .sc-iCoHVE, .sc-dkrFOg")
                        or d.find_elements(By.CSS_SELECTOR, "[data-testid='empty-result'], .sc-empty-result, .emptyResult")
                    )
                )
            except TimeoutException:
                print("[KABUM] Timeout aguardando produtos apos filtro")

            # Verificar se ainda há produtos após filtro
            try:
                no_results = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[data-testid='empty-result'], .sc-empty-result, .emptyResult"
                )
                if no_results and any(el.is_displayed() for el in no_results):
                    print("[KABUM] Nenhum produto KaBuM! apos filtro")
                    return None
            except:
                pass

            # Scroll completo após filtro
            print("[KABUM] Scroll apos filtro...")
            self.progressive_scroll(max_scrolls=8)

            # Buscar containers de produtos
            product_container_selectors = [
                ".productCard",
                "[data-testid='product-card']",
                ".sc-iCoHVE",
                ".sc-dkrFOg"
            ]

            product_containers = []
            for selector in product_container_selectors:
                try:
                    containers = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if containers:
                        product_containers = containers
                        break
                except:
                    continue

            if not product_containers:
                print("ERRO: Nenhum produto encontrado na Kabum")
                return None

            print(f"[KABUM] Total de produtos na pagina: {len(product_containers)}")

            valid_products = []
            rejected_count = 0

            for container in product_containers:
                try:
                    name_selectors = [
                        ".nameCard",
                        "span.nameCard",
                        "[data-testid='product-name']",
                        ".sc-dcJsrY",
                        ".productName",
                        "a.productLink span",
                        ".sc-kpDqfm",
                        "h2.sc-dcJsrY"
                    ]

                    name_element = None
                    for selector in name_selectors:
                        try:
                            name_element = container.find_element(By.CSS_SELECTOR, selector)
                            if name_element:
                                break
                        except:
                            continue

                    if not name_element:
                        continue

                    product_name = name_element.text.strip()

                    if modelo and not self.is_exact_product_match(product_name, modelo, marca):
                        rejected_count += 1
                        # DEBUG: mostrar primeiros 3 produtos rejeitados
                        if rejected_count <= 3:
                            print(f"[KABUM DEBUG] Rejeitado #{rejected_count}: {product_name[:80]}")
                            search_tokens = self.extract_key_tokens(modelo)
                            product_normalized = product_name.lower().replace('-', '').replace('_', '')
                            print(f"  Tokens busca: {search_tokens}")
                            print(f"  Nome normalizado: {product_normalized[:100]}")
                        continue

                    if not modelo:
                        search_words = search_term.lower().split()
                        product_name_lower = product_name.lower()

                        if not all(word in product_name_lower for word in search_words):
                            rejected_count += 1
                            continue

                        if any(keyword in product_name_lower for keyword in EXCLUSION_KEYWORDS):
                            rejected_count += 1
                            continue

                    price_selectors = [
                        ".priceCard",
                        "span.priceCard",
                        "[data-testid='price']",
                        ".finalPrice",
                        ".sc-dcJsrY.fkuRgL",
                        ".price",
                        ".priceMain",
                        ".bestPrice",
                        ".sc-dlfnbm"
                    ]

                    price_element = None
                    for selector in price_selectors:
                        try:
                            price_element = container.find_element(By.CSS_SELECTOR, selector)
                            if price_element:
                                break
                        except:
                            continue

                    if price_element:
                        price_text = price_element.text.strip()
                        price_value = self.clean_price_text(price_text)

                        if price_value > 0:
                            product_url = self.get_kabum_product_url(container)
                            valid_products.append({
                                "name": product_name,
                                "price": price_value,
                                "price_text": price_text,
                                "url": product_url,
                            })

                except Exception:
                    continue

            print(f"[KABUM] Produtos validos: {len(valid_products)} | Rejeitados: {rejected_count}")

            if not valid_products:
                print("[KABUM] Produto nao encontrado")
                return None

            valid_products.sort(key=lambda x: x["price"])
            cheapest = valid_products[0]

            print(f"[KABUM] Top 3 precos encontrados:")
            for i, p in enumerate(valid_products[:3], 1):
                print(f"  {i}. R$ {p['price']:.2f} - {p['name'][:60]}...")

            direct_url = cheapest.get("url") or self.driver.current_url

            result = {
                "site": "Kabum",
                "produto": cheapest["name"],
                "preco": cheapest["price"],
                "preco_texto": cheapest["price_text"],
                # Filtro KaBuM! foi aplicado — tudo que passou é vendido e entregue pela Kabum
                "shipped_by_store": True,
                "url": direct_url,
                "status": "sucesso"
            }

            print(f"[KABUM] SELECIONADO: {cheapest['name']} - R$ {cheapest['price']:.2f}")
            print(f"[KABUM] URL: {direct_url}")

            return result

        except Exception as e:
            print(f"ERRO CRITICO: Kabum - {e}")
            return None

    def search_amazon(self, component):
        """
        Busca produto na Amazon.
        Entra na página do mais barato para pegar URL direta e verificar vendedor.
        """
        produto = component['name']
        marca = component.get('brand')
        modelo = component.get('model')

        print(f"\n[AMAZON] Buscando: {produto}")
        if modelo:
            print(f"[AMAZON] Modelo para validacao: {modelo}")

        try:
            search_term = f"{marca} {produto}" if marca and marca.lower() not in produto.lower() else produto
            search_url = f"https://www.amazon.com.br/s?k={search_term.replace(' ', '+')}&i=computers"
            self.driver.get(search_url)

            if not self.wait_for_page_load():
                self.driver.refresh()
                if not self.wait_for_page_load():
                    print("ERRO: Amazon nao carregou")
                    return None

            self.close_popups()
            self.human_delay(4, 7)
            self.wait_for_page_load()

            print("[AMAZON] Fazendo scroll progressivo...")
            self.progressive_scroll(max_scrolls=6)

            product_selectors = [
                "[data-component-type='s-search-result']",
                ".s-result-item",
                ".s-card-container",
                ".sg-col-inner"
            ]

            product_elements = []
            for selector in product_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        product_elements = elements
                        break
                except:
                    continue

            if not product_elements:
                print("ERRO: Nenhum produto encontrado na Amazon")
                return None

            print(f"[AMAZON] Total de produtos na pagina: {len(product_elements)}")

            valid_products = []
            rejected_count = 0

            for product in product_elements[:40]:
                try:
                    name_selectors = [
                        "h2 a span",
                        ".a-size-medium.a-color-base.a-text-normal",
                        "h2 .a-text-normal",
                        ".a-size-base-plus.a-color-base.a-text-normal"
                    ]

                    product_name = ""
                    product_link = None

                    for selector in name_selectors:
                        try:
                            name_element = product.find_element(By.CSS_SELECTOR, selector)
                            product_name = name_element.text
                            if product_name:
                                # Tentar pegar href do ancestral <a> ou do <a> dentro do h2
                                try:
                                    if name_element.tag_name == "a":
                                        product_link = name_element.get_attribute("href")
                                    else:
                                        parent_a = name_element.find_element(By.XPATH, "./ancestor::a")
                                        product_link = parent_a.get_attribute("href")
                                except:
                                    try:
                                        link_el = product.find_element(By.CSS_SELECTOR, "h2 a")
                                        product_link = link_el.get_attribute("href")
                                    except:
                                        pass
                                break
                        except:
                            continue

                    if not product_name:
                        continue

                    if modelo and not self.is_exact_product_match(product_name, modelo, marca):
                        rejected_count += 1
                        # DEBUG: mostrar primeiros 3 produtos rejeitados
                        if rejected_count <= 3:
                            print(f"[AMAZON DEBUG] Rejeitado #{rejected_count}: {product_name[:80]}")
                            search_tokens = self.extract_key_tokens(modelo)
                            product_normalized = product_name.lower().replace('-', '').replace('_', '')
                            print(f"  Tokens busca: {search_tokens}")
                            print(f"  Nome normalizado: {product_normalized[:100]}")
                        continue

                    if not modelo:
                        search_words = search_term.lower().split()
                        product_name_lower = product_name.lower()

                        if not all(word in product_name_lower for word in search_words):
                            rejected_count += 1
                            continue

                        if any(keyword in product_name_lower for keyword in EXCLUSION_KEYWORDS):
                            rejected_count += 1
                            continue

                    price_value = 0
                    price_text = ""

                    try:
                        price_whole = product.find_element(By.CSS_SELECTOR, ".a-price-whole").text.strip()
                        try:
                            price_decimal = product.find_element(By.CSS_SELECTOR, ".a-price-fraction").text.strip()
                        except:
                            try:
                                price_decimal_elem = product.find_element(By.CSS_SELECTOR, ".a-price-decimal")
                                if price_decimal_elem.text.strip() == ",":
                                    price_html = product.get_attribute("innerHTML")
                                    decimal_match = re.search(
                                        r'<span class="a-price-decimal">,</span>\s*<span[^>]*>(\d+)</span>',
                                        price_html
                                    )
                                    price_decimal = decimal_match.group(1) if decimal_match else "00"
                                else:
                                    price_decimal = price_decimal_elem.text.strip()
                            except:
                                price_decimal = "00"

                        price_text = f"{price_whole},{price_decimal}"
                        price_value = self.clean_price_text(price_text)
                    except:
                        price_selectors_fallback = [
                            ".a-price[data-a-size='xl'] .a-offscreen",
                            ".a-price .a-offscreen",
                            ".a-price-whole",
                            "[data-a-size='xl'] .a-price-whole",
                            ".a-price .a-price-whole",
                            ".a-price[data-a-size='l']",
                            ".a-price[data-a-size='m']",
                        ]

                        for selector in price_selectors_fallback:
                            try:
                                price_elements = product.find_elements(By.CSS_SELECTOR, selector)
                                for element in price_elements:
                                    candidate_text = element.text.strip()
                                    candidate_value = self.clean_price_text(candidate_text)
                                    if candidate_value > 0:
                                        price_text = candidate_text
                                        price_value = candidate_value
                                        break
                                if price_value > 0:
                                    break
                            except:
                                continue

                    if price_value > 0:
                        valid_products.append({
                            "name": product_name,
                            "price": price_value,
                            "price_text": price_text,
                            "link": product_link,
                        })

                except Exception:
                    continue

            print(f"[AMAZON] Produtos validos: {len(valid_products)} | Rejeitados: {rejected_count}")

            if not valid_products:
                print("[AMAZON] Produto nao encontrado")
                return None

            valid_products.sort(key=lambda x: x["price"])
            cheapest = valid_products[0]

            print(f"[AMAZON] Top 3 precos encontrados:")
            for i, p in enumerate(valid_products[:3], 1):
                print(f"  {i}. R$ {p['price']:.2f} - {p['name'][:60]}...")

            # Entrar na página do produto para pegar URL direta e verificar vendedor
            shipped_by_store = None
            direct_url = cheapest.get("link") or self.driver.current_url

            if cheapest.get("link"):
                try:
                    print("[AMAZON] Abrindo pagina do produto para verificar vendedor...")
                    self.driver.get(cheapest["link"])
                    self.wait_for_page_load()
                    self.human_delay(2, 4)

                    direct_url = self.driver.current_url
                    shipped_by_store = self.check_amazon_shipped_by_amazon()

                    status_map = {
                        True: "Vendido e enviado pela Amazon",
                        False: "Vendedor/envio externo",
                        None: "Nao foi possivel determinar"
                    }
                    print(f"[AMAZON] Vendedor: {status_map[shipped_by_store]}")

                except Exception as e:
                    print(f"[AMAZON] Falha ao verificar pagina do produto: {e}")
            else:
                print("[AMAZON] Link do produto nao encontrado, usando URL da busca")

            result = {
                "site": "Amazon",
                "produto": cheapest["name"],
                "preco": cheapest["price"],
                "preco_texto": cheapest["price_text"],
                "shipped_by_store": shipped_by_store,
                "url": direct_url,
                "status": "sucesso"
            }

            print(f"[AMAZON] SELECIONADO: {cheapest['name']} - R$ {cheapest['price']:.2f}")
            print(f"[AMAZON] URL: {direct_url}")

            return result

        except Exception as e:
            print(f"ERRO CRITICO: Amazon - {e}")
            return None

    def scrape_component(self, component):
        """Busca preços de um componente em ambos os sites"""
        component_id = component['id']
        component_name = component['name']

        print(f"\n{'=' * 60}")
        print(f"Processando: {component_name} (ID: {component_id})")
        print(f"{'=' * 60}")

        results = {}

        kabum_result = self.search_kabum(component)
        if kabum_result:
            results['kabum'] = kabum_result

        self.human_delay(5, 8)

        amazon_result = self.search_amazon(component)
        if amazon_result:
            results['amazon'] = amazon_result

        print(f"\n--- Resumo: {component_name} ---")

        if 'kabum' in results:
            print(f"Kabum: R$ {results['kabum']['preco']:.2f}")
        else:
            print("Kabum: Nao encontrado")

        if 'amazon' in results:
            shipped = results['amazon'].get('shipped_by_store')
            shipped_label = {True: "(Amazon)", False: "(Externo)", None: "(indefinido)"}.get(shipped, "")
            print(f"Amazon: R$ {results['amazon']['preco']:.2f} {shipped_label}")
        else:
            print("Amazon: Nao encontrado")

        valid_prices = []
        if 'kabum' in results:
            valid_prices.append(('kabum', results['kabum']['preco']))
        if 'amazon' in results:
            valid_prices.append(('amazon', results['amazon']['preco']))

        if valid_prices:
            best_site, best_price = min(valid_prices, key=lambda x: x[1])
            print(f"Melhor preco: {best_site.upper()} - R$ {best_price:.2f}")
        else:
            print("Nenhum preco valido encontrado")

        print(f"{'=' * 60}\n")

        return results

    def close(self):
        """Fecha o driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------

def update_component_prices(component_id, results):
    """
    Atualiza preços do componente no Supabase.
    Se results for vazio (nada encontrado), reseta best_price mantendo updated_at.
    """
    try:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Nada encontrado em nenhum site — reseta tudo
        if not results:
            reset_data = {
                "best": {"url": None, "price": None, "store": None, "shipped_by_store": None},
                "kabum": {"url": None, "found": False, "price": None, "shipped_by_store": None},
                "amazon": {"url": None, "found": False, "price": None, "shipped_by_store": None},
                "updated_at": timestamp
            }

            response = supabase.table("components").update({
                "best_price": reset_data
            }).eq("id", component_id).execute()

            if response.data:
                print(f"[DB] best_price resetado para componente {component_id}")
                return True
            else:
                print(f"ERRO: Falha ao resetar componente {component_id}")
                return False

        # Montar estrutura com os resultados encontrados
        best_price_data = {
            "best": {"url": None, "price": None, "store": None, "shipped_by_store": None},
            "kabum": {"url": None, "found": False, "price": None, "shipped_by_store": None},
            "amazon": {"url": None, "found": False, "price": None, "shipped_by_store": None},
            "updated_at": timestamp
        }

        if 'kabum' in results and results['kabum'].get('preco'):
            best_price_data['kabum'] = {
                "url": results['kabum'].get('url'),
                "found": True,
                "price": results['kabum']['preco'],
                "shipped_by_store": results['kabum'].get('shipped_by_store')
            }

        if 'amazon' in results and results['amazon'].get('preco'):
            best_price_data['amazon'] = {
                "url": results['amazon'].get('url'),
                "found": True,
                "price": results['amazon']['preco'],
                "shipped_by_store": results['amazon'].get('shipped_by_store')
            }

        # Determinar melhor preço
        valid_prices = []
        if best_price_data['kabum']['found']:
            valid_prices.append(('kabum', best_price_data['kabum']['price']))
        if best_price_data['amazon']['found']:
            valid_prices.append(('amazon', best_price_data['amazon']['price']))

        if valid_prices:
            best_store, best_price = min(valid_prices, key=lambda x: x[1])
            best_price_data['best'] = {
                "url": best_price_data[best_store]['url'],
                "price": best_price,
                "store": best_store,
                "shipped_by_store": best_price_data[best_store]['shipped_by_store']
            }

        response = supabase.table("components").update({
            "best_price": best_price_data
        }).eq("id", component_id).execute()

        if response.data:
            return True
        else:
            print(f"ERRO: Falha ao atualizar componente {component_id} no banco")
            return False

    except Exception as e:
        print(f"ERRO CRITICO: Falha ao atualizar Supabase - {e}")
        return False


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Price Scraper - Kabum & Amazon")
    print("=" * 60)

    scraper = PriceScraper()

    if not scraper.driver:
        print("ERRO CRITICO: Driver nao inicializado")
        print("Verifique instalacao do Chrome/ChromeDriver")
        return

    try:
        response = supabase.table("components").select("*").execute()
        components = response.data

        if not components:
            print("Nenhum componente encontrado no banco")
            return

        print(f"\nTotal de componentes: {len(components)}\n")

        for i, component in enumerate(components, 1):
            print(f"\n[{i}/{len(components)}]")

            results = scraper.scrape_component(component)

            # Sempre atualiza — com resultados ou resetando
            update_component_prices(component['id'], results)

            if component != components[-1]:
                delay = random.uniform(8, 15)
                print(f"Aguardando {delay:.1f}s...\n")
                time.sleep(delay)

        print("\n" + "=" * 60)
        print("Scraping concluido")
        print("=" * 60)

    except Exception as e:
        print(f"ERRO CRITICO: Falha ao buscar componentes - {e}")

    finally:
        scraper.close()


if __name__ == "__main__":
    main()