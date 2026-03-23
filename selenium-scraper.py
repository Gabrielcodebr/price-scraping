import os
import time
import random
import re
import requests
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

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Palavras que indicam que não é o produto puro (kits, acessórios, PCs completos)
# REMOVIDOS intencionalmente: 'suporte', 'cooler', 'ventoinha', 'base', 'case', 'gabinete'
# pois aparecem em descrições técnicas legítimas (ex: "sem cooler", "suporte a PCIe",
# "base clock") e 'gabinete'/'case' são categorias de produto válidas.
#
# [FIX Bug#1/#4] 'computador' e 'desktop' foram substituídos por frases específicas
# para evitar rejeitar descrições legítimas como "caixa de computador ATX" ou
# "processador de desktop Core i7".
#
# [FIX Bug#6] 'pc ' removido — era genérico demais e rejeitava gabinetes legítimos cujos
# títulos contêm "Capa para PC", "Capa PC" ou "PC Case" (descrição do tipo de produto).
# Substituído por frases específicas de PCs completos. Os demais casos (completo, kit, combo
# workstation, etc.) já cobrem os sistemas montados que precisam ser filtrados.
EXCLUSION_KEYWORDS = [
    'completo', 'combo', 'notebook', 'laptop',
    'workstation', 'all-in-one', 'torre', 'cpu completo',
    'bracket', 'shield', 'parafuso', 'adaptador', 'extensor', 'acessorio',
    # 'cabo' removido — PSUs frequentemente mencionam "com cabo 12V-2x6" no título Amazon,
    # causando falsos negativos. Acessórios de cabo puro são rejeitados pelo token matching.
    # 'kit' mantido intencionalmente — usuário seleciona UM pente de RAM por vez,
    # então kits de 2+ pentes (2x8GB, 2x16GB etc.) são inválidos para o caso de uso.
    # 'kit gamer/pc/computador' ficam como reforço para kits de PC completo.
    'kit', 'kit gamer', 'kit pc', 'kit computador',
    # [FIX Bug#8] 'desktop gamer' removido — bloqueava RAM com "Memória Desktop Gamer" no título
    # PCs completos já são cobertos por 'computador gamer', 'pc gamer', 'desktop completo' etc.
    # Frases específicas para PCs completos (substituem 'pc ' e os genéricos 'computador'/'desktop')
    'mini pc', 'barebone pc',
    'pc gamer', 'pc completo', 'pc montado', 'pc computador',
    'pc intel', 'pc amd', 'pc core', 'pc ryzen',
    'computador completo', 'computador gamer', 'computador montado',
    'computador intel', 'computador amd', 'computador core', 'computador ryzen',
    'desktop completo', 'desktop montado',
    'desktop intel', 'desktop amd', 'desktop core', 'desktop ryzen',
]

# Sufixos que indicam PRODUTO DIFERENTE (não podem aparecer se não estão no modelo buscado)
VARIANT_SUFFIXES = [
    'xt', 'ti', 'super', 'kf', 'f', 'ultra', 'max', 'pro',
    'plus', 'boost', 'overclocked', 'turbo', 'extreme', 'premium',
    'x3d', '3d', 's', 'g', 'x',  # 'x' adicionado para cobrir 7600X, 5800X, etc.
    'i',  # 'i' para distinguir HX1200 de HX1200i (versão com monitoramento digital iCUE)
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

# [FIX Bug#5] Fabricantes de chip — seus produtos são vendidos por terceiros
# (ASUS, MSI, Gigabyte, ZOTAC, etc.), então o nome da marca quase nunca aparece
# no título do produto. Pular brand check para esses fabricantes.
CHIP_MANUFACTURERS = {'nvidia', 'amd', 'intel'}


class PriceScraper:
    """Web scraper para buscar preços em Kabum e Amazon com comportamento humanizado"""

    def __init__(self):
        self.driver = None
        self._llm_blocked_until = 0
        self._last_llm_call = 0
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

    def ask_gemini_is_match(self, product_name, component_name, model):
        """
        Usa Groq (llama-3.3-70b-versatile) como segunda opinião quando is_exact_product_match rejeita.
        Retorna True se o LLM confirma que é o mesmo produto, False caso contrário
        ou em caso de erro.
        Free tier Groq: 30 RPM, 1.000 RPD — muito mais generoso que Gemini (20 RPD).
        """
        if not GROQ_API_KEY:
            return False

        # Cooldown de segurança após 429 (60s)
        if time.time() < self._llm_blocked_until:
            remaining = int(self._llm_blocked_until - time.time())
            print(f"[LLM] Cooldown ativo — {remaining}s restantes")
            return False

        # Rate limiter proativo: intervalo mínimo de 2s entre chamadas (~30 RPM)
        if self._last_llm_call > 0:
            elapsed = time.time() - self._last_llm_call
            if elapsed < 2:
                wait = 2 - elapsed
                print(f"[LLM] Rate limiter — aguardando {wait:.1f}s")
                time.sleep(wait)

        prompt = (
            f'Você é especialista em hardware de computador. '
            f'Decida se estes dois itens são EXATAMENTE o mesmo produto.\n\n'
            f'Produto buscado: "{component_name}" (modelo: {model})\n'
            f'Produto encontrado na loja: "{product_name}"\n\n'
            f'REGRAS OBRIGATÓRIAS — responda NÃO se qualquer uma for verdade:\n'
            f'- As marcas são diferentes (ex: XPG vs C3Tech, Corsair vs Redragon)\n'
            f'- O modelo é diferente (ex: Pylon vs Kyber, Core Reactor vs PS-G850)\n'
            f'- É apenas um produto similar da mesma categoria (ex: outra fonte 550W)\n\n'
            f'Responda APENAS com SIM ou NÃO, sem mais texto.\n'
            f'SIM = definitivamente o mesmo produto, com nome abreviado ou variante\n'
            f'NÃO = produto diferente, marca diferente, ou modelo diferente'
        )

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 5,
            "temperature": 0,
        }

        self._last_llm_call = time.time()

        try:
            response = requests.post(url, json=body, headers=headers, timeout=10)

            if response.status_code == 429:
                self._llm_blocked_until = time.time() + 60
                print(f"[LLM] Rate limit (429) — cooldown de 60s ativado")
                return False

            response.raise_for_status()

            answer = (
                response.json()
                ["choices"][0]["message"]["content"]
                .strip()
                .upper()
            )
            result = answer.startswith("SIM")
            print(f"[LLM] '{product_name[:60]}' → {answer} (match={result})")
            return result

        except Exception as e:
            print(f"[LLM] Erro na validacao: {e}")
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

    def extract_ddr_type(self, text):
        """Extrai tipo DDR do texto (ddr3, ddr4, ddr5). Usado para evitar confundir gerações."""
        if not text:
            return None
        match = re.search(r'\bddr(\d)\b', text.lower())
        return f"ddr{match.group(1)}" if match else None

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
            # [FIX Bug#2] Remover TODOS os caracteres não-alfanuméricos (não apenas - e _).
            # Evita que pontuação residual (vírgulas, barras de SKU como "SA400S37/240G")
            # crie tokens sujos que causam falsos positivos na checagem de variantes.
            normalized_token = re.sub(r'[^a-z0-9]', '', token)

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

    def is_exact_product_match(self, product_name, search_model, search_brand=None, search_name=None):
        """
        Valida se o produto encontrado corresponde exatamente ao modelo buscado.

        Args:
            product_name: Nome do produto encontrado na loja.
            search_model: Modelo sendo buscado (campo 'model' do componente).
            search_brand: Marca do componente (campo 'brand').
            search_name: Nome completo do componente (campo 'name'), usado como
                         fallback para extrair capacidade de armazenamento quando
                         o model não contém essa informação (Bug#3).
        """
        if not product_name or not search_model:
            return False

        product_name_lower = product_name.lower()

        for keyword in EXCLUSION_KEYWORDS:
            if keyword in product_name_lower:
                print(f"  [MATCH] REJEITADO (exclusion '{keyword}'): {product_name[:80]}")
                return False

        search_tokens = self.extract_key_tokens(search_model)
        product_tokens = self.extract_key_tokens(product_name)

        if not search_tokens:
            return search_model.lower() in product_name_lower

        # [FIX Bug#11] Rejeitar acessórios de compatibilidade: produtos onde TODOS os tokens
        # do modelo buscado aparecem apenas após "para " no título (seção de lista de
        # compatibilidade), e não antes. Evita casos como:
        #   "Antena WiFi para MSI MAG Z890 Tomahawk"
        #   "Módulo TPM 2.0 para Gigabyte H610M H DDR4"
        #   "Cabo PCIE para Corsair HX1200"
        if ' para ' in product_name_lower:
            first_para_idx = product_name_lower.index(' para ')
            tokens_before_para = self.extract_key_tokens(product_name_lower[:first_para_idx])
            if not any(t in tokens_before_para for t in search_tokens):
                print(f"  [MATCH] REJEITADO (tokens só após 'para' - acessório): {product_name[:80]}")
                return False

        product_name_normalized = product_name_lower.replace('-', '').replace('_', '')

        for token in search_tokens:
            if token not in product_name_normalized:
                print(f"  [MATCH] REJEITADO (token '{token}' ausente): {product_name[:80]}")
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
                    print(f"  [MATCH] REJEITADO (variante '{num}+{variant}'): {product_name[:80]}")
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
                        print(f"  [MATCH] REJEITADO (variante numerica '{prod_num}' != '{search_num}'): {product_name[:80]}")
                        return False

            if not found_match:
                if search_num not in product_name_normalized:
                    print(f"  [MATCH] REJEITADO (num '{search_num}' ausente): {product_name[:80]}")
                    return False

                # [FIX Bug#2] Usar word boundary (\b) em vez de substring simples (`in`).
                # Evita que códigos de peça como "SA400S37" sejam interpretados como
                # variante "A400S" do modelo "A400".
                for variant in VARIANT_SUFFIXES:
                    variant_pattern = re.compile(
                        r'\b' + re.escape(search_num) + re.escape(variant) + r'\b'
                    )
                    if variant_pattern.search(product_name_normalized):
                        if variant not in [t for t in search_tokens if t in VARIANT_SUFFIXES]:
                            print(f"  [MATCH] REJEITADO (variante word-boundary '{search_num}+{variant}'): {product_name[:80]}")
                            return False

        # [FIX Bug#3] Extrair capacidade também do nome completo do componente (search_name)
        # quando o model não contém essa informação. Ex: model="870 EVO", name="Samsung 870 EVO 1TB"
        search_capacity = self.extract_storage_capacity(search_model)
        if search_capacity is None and search_name:
            search_capacity = self.extract_storage_capacity(search_name)
        product_capacity = self.extract_storage_capacity(product_name)

        if search_capacity is not None:
            if product_capacity is None or product_capacity != search_capacity:
                print(f"  [MATCH] REJEITADO (capacidade {search_capacity}GB != {product_capacity}GB): {product_name[:80]}")
                return False

        # [FIX Bug#10] Checar geração DDR quando o modelo é genérico (ex: "Vengeance", "Fury Beast").
        # Sem isso, DDR4 e DDR5 do mesmo produto ficam intercambiáveis no matching.
        # Só rejeita quando AMBOS têm DDR explícito e são diferentes.
        search_ddr = self.extract_ddr_type(search_model)
        if search_ddr is None and search_name:
            search_ddr = self.extract_ddr_type(search_name)
        product_ddr = self.extract_ddr_type(product_name)
        if search_ddr is not None and product_ddr is not None and search_ddr != product_ddr:
            print(f"  [MATCH] REJEITADO (tipo {search_ddr.upper()} != {product_ddr.upper()}): {product_name[:80]}")
            return False

        # [FIX Bug#5] Pular brand check para fabricantes de chip (NVIDIA, AMD, Intel).
        # Seus produtos são vendidos por terceiros (ASUS, MSI, Gigabyte, ZOTAC etc.)
        # e o nome da marca quase nunca aparece no título do produto na loja.
        if search_brand:
            if search_brand.lower() not in CHIP_MANUFACTURERS:
                if search_brand.lower() not in product_name_lower:
                    print(f"  [MATCH] REJEITADO (marca '{search_brand}' ausente): {product_name[:80]}")
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
            # Usa 'label' genérico (sem classe) para resistir a mudanças de styled-components
            target_index = self.driver.execute_script("""
                var labels = document.querySelectorAll('label');
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
                var labels = document.querySelectorAll('label');
                var label = labels[arguments[0]];
                if (label) label.scrollIntoView({block: 'center', behavior: 'smooth'});
            """, target_index)

            # Aguardar scroll terminar e página estabilizar
            time.sleep(random.uniform(0.6, 1.0))

            # Verificar se já está marcado via JS (sem guardar referência)
            already_checked = self.driver.execute_script("""
                var labels = document.querySelectorAll('label');
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
            labels_fresh = self.driver.find_elements(By.CSS_SELECTOR, "label")
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
            # Se o container já é o próprio <a> (fallback de links diretos)
            if container.tag_name.lower() == "a":
                href = container.get_attribute("href")
                if href and "kabum.com.br" in href:
                    return href
            # Caso o container seja um card wrapper com link filho
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
            search_term = f"{marca} {produto}" if marca and marca.lower() not in produto.lower() else produto

            # DEBUG: verificar termo de busca
            print(f"[KABUM DEBUG] component['name']: '{produto}'")
            print(f"[KABUM DEBUG] brand: '{marca}'")
            print(f"[KABUM DEBUG] search_term final: '{search_term}'")

            # Navegar diretamente pela URL de busca (evita inconsistência do autocomplete)
            search_url = f"https://www.kabum.com.br/busca/{search_term.replace(' ', '-')}"
            self.driver.get(search_url)

            if not self.wait_for_page_load():
                self.driver.refresh()
                if not self.wait_for_page_load():
                    print("ERRO: Kabum nao carregou")
                    return None

            # DEBUG: verificar URL final
            print(f"[KABUM DEBUG] URL apos busca: {self.driver.current_url}")

            self.human_delay(3, 5)

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
                        d.find_elements(By.CSS_SELECTOR, ".productCard, [data-testid='product-card'], [class*='productCard'], [class*='ProductCard'], a[href*='/produto/']")
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
            self.progressive_scroll(max_scrolls=12)  # Aumentado de 8 para 12

            # Buscar containers de produtos
            product_container_selectors = [
                ".productCard",
                "[data-testid='product-card']",
                "[class*='productCard']",
                "[class*='ProductCard']",
                "[class*='product-card']",
                "article",
                "[class*='CardProduct']",
                "[class*='ItemProduct']",
                "[class*='ProductItem']",
            ]

            product_containers = []
            for selector in product_container_selectors:
                try:
                    containers = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if containers:
                        product_containers = containers
                        print(f"[KABUM] Seletor usado: {selector}")
                        break
                except:
                    continue

            # Fallback: extrai nome + preço via JS em um único call (evita race condition
            # com o re-render do React: se o DOM mudar entre o JS e o .text do Selenium,
            # os dados já estariam perdidos numa abordagem em dois passos).
            # Retorna lista de dicts {href, name, price} em vez de WebElements.
            kabum_js_data = []
            if not product_containers:
                try:
                    if self.driver:
                        kabum_js_data = self.driver.execute_script("""
                            var results = [];
                            var seen = {};
                            var links = document.querySelectorAll('a[href*="/produto/"]');
                            for (var i = 0; i < links.length; i++) {
                                var link = links[i];
                                var href = link.href || '';
                                if (!/\\/produto\\/\\d+/.test(href)) continue;
                                if (seen[href]) continue;
                                seen[href] = true;

                                // Novo layout Kabum: o <a> em si É o card completo (tem preco dentro).
                                // Layout antigo: o <a> é filho de um card wrapper.
                                var card;
                                var linkText = (link.innerText || '').trim();
                                if (linkText.length > 30 && linkText.length < 3000 && /R\\$/.test(linkText)) {
                                    card = link;
                                } else {
                                    card = link.parentElement;
                                    for (var j = 0; j < 8 && card && card !== document.body; j++) {
                                        var t = (card.innerText || '').trim();
                                        if (t.length > 30 && t.length < 3000 && /R\\$/.test(t)) break;
                                        card = card.parentElement;
                                    }
                                    if (!card || card === document.body) card = link;
                                }

                                // 1. CSS selector direto para o nome (span com line-clamp é o título do produto)
                                var name = '';
                                var nameEl = card.querySelector('span[class*="line-clamp"]');
                                if (nameEl) {
                                    name = nameEl.textContent.trim();
                                }

                                // 2. Fallback: parsear linhas do innerText filtrando labels de UI
                                // l.length >= 10: filtra "SELO:" (5), sr-only "Avaliação " (10 c/ nbsp → 9 c/ trim)
                                // regex: filtra "Avaliação 5.0 de 5.0" e outros labels conhecidos
                                if (!name || name.length < 5) {
                                    var text = (card.innerText || '').trim();
                                    var lines = text.split('\\n')
                                        .map(function(l){ return l.trim(); })
                                        .filter(function(l){
                                            return l.length >= 10 &&
                                                   /[a-zA-Z]/.test(l) &&
                                                   !/^R\\$/.test(l) &&
                                                   !/^(SELO|Avalia|Estrela|Frete|Parcel|Gr[aá]tis|Comprar|Adicionar|Ver mais|Estoque)/i.test(l);
                                        });
                                    name = lines.length > 0 ? lines[0] : '';
                                }

                                if (!name) continue;

                                var cardText = (card.innerText || '').trim();
                                var pm = cardText.match(/R\\$\\s*[\\d\\.]+,[\\d]{2}/);
                                var price = pm ? pm[0] : '';
                                if (price) results.push({href: href, name: name, price: price});
                            }
                            return results;
                        """) or []
                    if kabum_js_data:
                        print(f"[KABUM] Seletor fallback: a[href*='/produto/'] — {len(kabum_js_data)} containers")
                except Exception:
                    kabum_js_data = []

            if not product_containers and not kabum_js_data:
                page_title = self.driver.title
                print(f"[KABUM] Titulo da pagina: {page_title}")
                print("ERRO: Nenhum produto encontrado na Kabum")
                return None

            total = len(product_containers) if product_containers else len(kabum_js_data)
            print(f"[KABUM] Total de produtos na pagina: {total}")

            # 1ª passagem: coletar todos os candidatos com nome e preço
            all_candidates = []

            # Caminho A: dados pré-extraídos pelo JS fallback (nome+preço já em string)
            for item in kabum_js_data:
                product_name = (item.get('name') or '').strip()
                price_text = (item.get('price') or '').strip()
                if not product_name or not price_text:
                    continue
                price_value = self.clean_price_text(price_text)
                if price_value > 0:
                    all_candidates.append({
                        "name": product_name,
                        "price": price_value,
                        "price_text": price_text,
                        "url": item.get('href'),
                    })
                else:
                    print(f"[KABUM DEBUG] Preco nao encontrado para: {product_name[:60]}")

            # Caminho B: containers WebElement (seletores primários funcionaram)
            for container in product_containers:
                try:
                    name_selectors = [
                        ".nameCard",
                        "span.nameCard",
                        "[data-testid='product-name']",
                        "[class*='nameCard']",
                        "[class*='productName']",
                        "[class*='ProductName']",
                        ".productName",
                        "a[href*='/produto/'] span",
                        "a[href*='/produto/']",
                        "h2 span",
                        "h3 span",
                    ]

                    name_element = None
                    for selector in name_selectors:
                        try:
                            name_element = container.find_element(By.CSS_SELECTOR, selector)
                            if name_element and name_element.text.strip():
                                break
                        except:
                            continue

                    if not name_element:
                        raw_text = container.text.strip().split('\n')[0]
                        if raw_text:
                            product_name = raw_text
                        else:
                            continue
                    else:
                        product_name = name_element.text.strip()

                    if not product_name:
                        continue

                    price_selectors = [
                        ".priceCard",
                        "span.priceCard",
                        "[data-testid='price']",
                        "[class*='priceCard']",
                        "[class*='finalPrice']",
                        "[class*='bestPrice']",
                        "[class*='Price']",
                        ".finalPrice",
                        ".price",
                        ".priceMain",
                        ".bestPrice",
                    ]

                    price_element = None
                    for selector in price_selectors:
                        try:
                            price_element = container.find_element(By.CSS_SELECTOR, selector)
                            if price_element:
                                break
                        except:
                            continue

                    price_text = ""
                    price_value = 0

                    if price_element:
                        price_text = price_element.text.strip()
                        price_value = self.clean_price_text(price_text)

                    # Fallback: extrair preço do texto bruto do container via regex
                    if price_value == 0:
                        raw_text = container.text
                        price_match = re.search(r'R\$\s*[\d\.]+,\d{2}', raw_text)
                        if price_match:
                            price_text = price_match.group(0)
                            price_value = self.clean_price_text(price_text)

                    if price_value > 0:
                        product_url = self.get_kabum_product_url(container)
                        all_candidates.append({
                            "name": product_name,
                            "price": price_value,
                            "price_text": price_text,
                            "url": product_url,
                        })
                    else:
                        print(f"[KABUM DEBUG] Preco nao encontrado para: {product_name[:60]}")

                except Exception:
                    continue

            # 2ª passagem: filtrar por matching — sem Gemini
            valid_products = []
            rejected_candidates = []

            for c in all_candidates:
                product_name = c["name"]
                if modelo:
                    if self.is_exact_product_match(product_name, modelo, marca, search_name=produto):
                        valid_products.append(c)
                    else:
                        rejected_candidates.append(c)
                else:
                    search_words = search_term.lower().split()
                    product_name_lower = product_name.lower()
                    if (all(word in product_name_lower for word in search_words)
                            and not any(kw in product_name_lower for kw in EXCLUSION_KEYWORDS)):
                        valid_products.append(c)
                    else:
                        rejected_candidates.append(c)

            # Fallback Gemini: só se matching normal falhou completamente
            # Produtos excluídos por keyword (kit, laptop, etc.) nunca vão ao Gemini
            if not valid_products and rejected_candidates and modelo:
                gemini_candidates = [
                    c for c in rejected_candidates
                    if not any(kw in c["name"].lower() for kw in EXCLUSION_KEYWORDS)
                ]
                gemini_candidates.sort(key=lambda x: x["price"])
                if gemini_candidates:
                    print(f"[KABUM] Matching normal: 0 resultados. Tentando LLM nos {min(3, len(gemini_candidates))} candidatos mais baratos...")
                    for c in gemini_candidates[:3]:
                        if self.ask_gemini_is_match(c["name"], produto, modelo):
                            valid_products.append(c)
                            break

            print(f"[KABUM] Produtos validos: {len(valid_products)} | Rejeitados: {len(rejected_candidates)}")

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

            # DEBUG: verificar termo de busca
            print(f"[AMAZON DEBUG] component['name']: '{produto}'")
            print(f"[AMAZON DEBUG] brand: '{marca}'")
            print(f"[AMAZON DEBUG] search_term final: '{search_term}'")

            search_url = f"https://www.amazon.com.br/s?k={search_term.replace(' ', '+')}&i=computers"

            # DEBUG: verificar URL construída
            print(f"[AMAZON DEBUG] URL: {search_url}")

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
            self.progressive_scroll(max_scrolls=10)

            # Detectar CAPTCHA antes de tentar encontrar produtos
            page_title = self.driver.title.lower()
            if "robot" in page_title or "captcha" in page_title or "verification" in page_title:
                print(f"[AMAZON] CAPTCHA detectado! Titulo: {self.driver.title}")
                return None
            print(f"[AMAZON] Titulo da pagina: {self.driver.title}")

            product_selectors = [
                "[data-component-type='s-search-result']",
                "[data-asin]",
                ".s-result-item[data-asin]",
                ".s-result-item",
                ".s-card-container",
                ".sg-col-inner"
            ]

            product_elements = []
            for selector in product_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    # Ignorar elementos sem data-asin quando possível (evita containers vazios)
                    if elements:
                        real = [e for e in elements if e.get_attribute("data-asin")]
                        product_elements = real if real else elements
                        print(f"[AMAZON] Seletor usado: {selector} ({len(product_elements)} elementos)")
                        break
                except:
                    continue

            if not product_elements:
                print(f"[AMAZON] Titulo da pagina: {self.driver.title}")
                print("ERRO: Nenhum produto encontrado na Amazon")
                return None

            print(f"[AMAZON] Total de produtos na pagina: {len(product_elements)}")

            # 1ª passagem: coletar todos os candidatos com nome e preço
            all_candidates = []

            for product in product_elements[:60]:
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
                        all_candidates.append({
                            "name": product_name,
                            "price": price_value,
                            "price_text": price_text,
                            "link": product_link,
                        })

                except Exception:
                    continue

            # 2ª passagem: filtrar por matching — sem Gemini
            valid_products = []
            rejected_candidates = []

            for c in all_candidates:
                product_name = c["name"]
                if modelo:
                    if self.is_exact_product_match(product_name, modelo, marca, search_name=produto):
                        valid_products.append(c)
                    else:
                        rejected_candidates.append(c)
                else:
                    search_words = search_term.lower().split()
                    product_name_lower = product_name.lower()
                    if (all(word in product_name_lower for word in search_words)
                            and not any(kw in product_name_lower for kw in EXCLUSION_KEYWORDS)):
                        valid_products.append(c)
                    else:
                        rejected_candidates.append(c)

            # Fallback Gemini: só se matching normal falhou completamente
            # Produtos excluídos por keyword (kit, laptop, etc.) nunca vão ao Gemini
            if not valid_products and rejected_candidates and modelo:
                gemini_candidates = [
                    c for c in rejected_candidates
                    if not any(kw in c["name"].lower() for kw in EXCLUSION_KEYWORDS)
                ]
                gemini_candidates.sort(key=lambda x: x["price"])
                if gemini_candidates:
                    print(f"[AMAZON] Matching normal: 0 resultados. Tentando LLM nos {min(3, len(gemini_candidates))} candidatos mais baratos...")
                    for c in gemini_candidates[:3]:
                        if self.ask_gemini_is_match(c["name"], produto, modelo):
                            valid_products.append(c)
                            break

            print(f"[AMAZON] Produtos validos: {len(valid_products)} | Rejeitados: {len(rejected_candidates)}")

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

MAX_RUNTIME_MINUTES = 300  # Para dentro de 5h, deixando 1h de margem pro timeout de 6h do GitHub Actions


def main():
    print("=" * 60)
    print("Price Scraper - Kabum & Amazon")
    print("=" * 60)

    scraper = PriceScraper()

    if not scraper.driver:
        print("ERRO CRITICO: Driver nao inicializado")
        print("Verifique instalacao do Chrome/ChromeDriver")
        return

    start_time = time.time()

    try:
        # Ordena pelos mais antigos primeiro — nunca atualizados (null) têm prioridade máxima
        response = (
            supabase.table("components")
            .select("*")
            .order("best_price->>updated_at", desc=False, nullsfirst=True)
            .execute()
        )
        components = response.data

        if not components:
            print("Nenhum componente encontrado no banco")
            return

        print(f"\nTotal de componentes: {len(components)}\n")

        for i, component in enumerate(components, 1):
            elapsed = (time.time() - start_time) / 60
            remaining = MAX_RUNTIME_MINUTES - elapsed

            if remaining < 5:
                print(f"\n⏰ Limite de tempo atingido ({elapsed:.0f}min). Processados {i - 1}/{len(components)} componentes.")
                print("Os componentes restantes serao priorizados na proxima execucao.")
                break

            print(f"\n[{i}/{len(components)}] | Tempo decorrido: {elapsed:.0f}min | Restante: {remaining:.0f}min")

            results = scraper.scrape_component(component)

            # Sempre atualiza — com resultados ou resetando
            update_component_prices(component['id'], results)

            if i < len(components):
                delay = random.uniform(8, 15)
                print(f"Aguardando {delay:.1f}s...\n")
                time.sleep(delay)

        else:
            print("\n" + "=" * 60)
            print("Scraping concluido")
            print("=" * 60)

    except Exception as e:
        print(f"ERRO CRITICO: Falha ao buscar componentes - {e}")

    finally:
        scraper.close()


if __name__ == "__main__":
    main()