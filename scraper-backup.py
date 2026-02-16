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
EXCLUSION_KEYWORDS = [
    'pc ', 'computador', 'completo', 'kit', 'combo', 'notebook', 'laptop',
    'desktop', 'workstation', 'all-in-one', 'torre', 'cpu completo',
    'suporte', 'bracket', 'shield', 'parafuso', 'cabo', 'adaptador', 'extensor',
    'acessorio', 'cooler', 'ventoinha', 'base', 'case', 'gabinete'
]

# Sufixos que indicam PRODUTO DIFERENTE (não podem aparecer se não estão no modelo buscado)
VARIANT_SUFFIXES = [
    'xt', 'ti', 'super', 'kf', 'f', 'ultra', 'max', 'pro',
    'plus', 'boost', 'overclocked', 'turbo', 'extreme', 'premium',
    'x3d', '3d', 's', 'g'  # Adicionados para Ryzen X3D e outras variantes
]

# Palavras genéricas que podem aparecer sem problema (são apenas marketing)
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
    'nitro', 'pulse', 'red', 'devil', 'v2', 'v1', 'ex', 'lx', 'lpx'
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
            
            # Configurações para Docker
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--remote-debugging-port=9222")
            
            # Anti-detecção
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins-discovery")
            
            # User agent aleatório
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
            
            # Scripts anti-detecção
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
                elif i > 0 and text[i-1] == ' ':
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
                # Scroll até o final da página
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.5, 2.5))
                
                # Verificar se a altura mudou (novos produtos carregaram)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                
                if new_height == last_height:
                    scrolls_without_change += 1
                    # Se não mudou em 2 scrolls consecutivos, provavelmente carregou tudo
                    if scrolls_without_change >= 2:
                        break
                else:
                    scrolls_without_change = 0
                    last_height = new_height
                
                # Scroll um pouco para trás (comportamento humano)
                if random.random() < 0.3:
                    self.driver.execute_script("window.scrollBy(0, -200);")
                    time.sleep(random.uniform(0.3, 0.7))
            
            # Scroll de volta ao topo
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
        """
        Extrai capacidade de armazenamento do texto.
        Retorna valor normalizado em GB para comparação.
        
        Exemplos:
        - "1TB" → 1024
        - "512GB" → 512
        - "2 tb" → 2048
        """
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Procurar padrões como "1tb", "512gb", "2 tb", etc
        # Aceita espaço opcional entre número e unidade
        match = re.search(r'(\d+)\s*(tb|gb)', text_lower)
        
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            # Normalizar tudo para GB
            if unit == 'tb':
                return value * 1024  # converter TB para GB
            return value  # já está em GB
        
        return None
    
    def extract_key_tokens(self, text):
        """
        Extrai tokens-chave de um texto (números e códigos alfanuméricos importantes).
        Retorna tokens normalizados (lowercase, sem hífens/underscores).
        """
        if not text:
            return []
        
        # Normalizar: lowercase
        text_lower = text.lower()
        
        # Separar por espaços, hífens, underscores
        # Mas manter hífens em códigos alfanuméricos específicos (ex: RM-WA-FB-ARGB)
        tokens = re.split(r'[\s]+', text_lower)
        
        key_tokens = []
        for token in tokens:
            # Remover hífens/underscores do token para normalização
            normalized_token = token.replace('-', '').replace('_', '')
            
            # Ignorar tokens vazios
            if not normalized_token:
                continue
            
            # Ignorar palavras genéricas
            if normalized_token in GENERIC_WORDS:
                continue
            
            # Manter tokens que:
            # - Contêm números (ex: "9070", "13600k", "32gb", "3200mhz")
            # - São códigos curtos importantes (ex: "xt", "ti", "kf", "x3d")
            # - São códigos alfanuméricos com hífens (ex: "rmwafbargb" de "RM-WA-FB-ARGB")
            if re.search(r'\d', normalized_token):
                key_tokens.append(normalized_token)
            elif normalized_token in VARIANT_SUFFIXES:
                # Sufixos de variante são importantes!
                key_tokens.append(normalized_token)
            elif len(normalized_token) >= 6 and re.search(r'[a-z]+[0-9]+|[0-9]+[a-z]+', normalized_token):
                # Códigos alfanuméricos mistos (letras e números)
                key_tokens.append(normalized_token)
        
        return key_tokens
    
    def is_exact_product_match(self, product_name, search_model, search_brand=None):
        """
        Valida se o produto encontrado corresponde exatamente ao modelo buscado.
        
        Lógica:
        1. Verifica palavras de exclusão (kits, acessórios, PCs completos)
        2. Extrai tokens-chave do modelo buscado e do produto
        3. TODOS os tokens do modelo buscado devem estar no produto
        4. O produto NÃO pode ter tokens de variante que não estão no modelo buscado
        5. Valida capacidade de armazenamento (GB/TB) se presente
        
        Exemplos:
        - Busca "RX 9070" → Aceita "Radeon RX 9070 Gaming OC"
        - Busca "RX 9070" → REJEITA "RX 9070 XT" (tem token extra "xt")
        - Busca "7600X" → REJEITA "7600X3D" (tem token extra "x3d")
        - Busca "Barracuda 1TB" → REJEITA "Barracuda 500GB" (capacidade diferente)
        """
        if not product_name or not search_model:
            return False
        
        product_name_lower = product_name.lower()
        
        # 1. Verificar palavras de exclusão (kits, acessórios, PCs completos)
        for keyword in EXCLUSION_KEYWORDS:
            if keyword in product_name_lower:
                return False
        
        # 2. Extrair tokens-chave
        search_tokens = self.extract_key_tokens(search_model)
        product_tokens = self.extract_key_tokens(product_name)
        
        # Se não há tokens de busca, fazer validação simples por substring
        if not search_tokens:
            return search_model.lower() in product_name_lower
        
        # 3. TODOS os tokens de busca devem estar no produto
        # Normalizar para comparação (remover hífens)
        product_name_normalized = product_name_lower.replace('-', '').replace('_', '')
        
        for token in search_tokens:
            if token not in product_name_normalized:
                return False
        
        # 4. Verificar se há tokens de variante extras no produto
        # Exemplo: buscar "7600x" não pode aceitar produto com "x3d" se "x3d" não está na busca
        search_variants = [t for t in search_tokens if t in VARIANT_SUFFIXES]
        product_variants = [t for t in product_tokens if t in VARIANT_SUFFIXES]
        
        # Se o produto tem variantes que não estão na busca, rejeitar
        for variant in product_variants:
            if variant not in search_variants:
                return False
        
        # 5. Verificar tokens numéricos extras
        # Exemplo: buscar "9070" não pode aceitar produto com "9070xt" como um token único
        search_numeric = [t for t in search_tokens if re.search(r'\d', t)]
        product_numeric = [t for t in product_tokens if re.search(r'\d', t)]
        
        # Para cada token numérico da busca, verificar se está presente no produto
        for search_num in search_numeric:
            # Verificar se existe um token no produto que seja similar mas diferente
            # Ex: busca "9070" mas produto tem "9070xt"
            found_match = False
            for prod_num in product_numeric:
                if search_num == prod_num:
                    found_match = True
                    break
                # Se o produto tem um token que COMEÇA com o número buscado mas tem sufixo
                # Ex: busca "9070", produto tem "9070xt"
                if prod_num.startswith(search_num) and len(prod_num) > len(search_num):
                    # Verificar se o sufixo é uma variante importante
                    suffix = prod_num[len(search_num):]
                    if suffix in VARIANT_SUFFIXES:
                        # É uma variante diferente! Rejeitar
                        return False
            
            if not found_match:
                # O token numérico não foi encontrado exatamente
                # Pode estar combinado com texto. Verificar no nome normalizado.
                if search_num not in product_name_normalized:
                    return False
                
                # NOVO: Verificar se o número está grudado com variante no meio do texto
                # Ex: busca "9070" mas produto tem "rx9070xt" ou "rtx5060ti"
                for variant in VARIANT_SUFFIXES:
                    # Procurar padrões onde número está grudado com variante
                    pattern = search_num + variant
                    if pattern in product_name_normalized:
                        # Verificar se essa variante NÃO está na busca original
                        if variant not in [t for t in search_tokens if t in VARIANT_SUFFIXES]:
                            # Número grudado com variante que não está na busca!
                            return False
        
        # 6. VALIDAÇÃO DE CAPACIDADE DE ARMAZENAMENTO
        # Se a busca menciona capacidade (ex: "1TB"), o produto DEVE ter a mesma capacidade
        search_capacity = self.extract_storage_capacity(search_model)
        product_capacity = self.extract_storage_capacity(product_name)
        
        if search_capacity is not None:
            # Se a busca tem capacidade especificada, o produto DEVE ter exatamente a mesma
            if product_capacity is None or product_capacity != search_capacity:
                return False
        
        # 7. Se tem marca, verificar se está presente
        if search_brand:
            if search_brand.lower() not in product_name_lower:
                return False
        
        return True
    
    def search_kabum(self, component):
        """Busca produto na Kabum e retorna o mais barato que corresponde exatamente"""
        produto = component['name']
        marca = component.get('brand')
        modelo = component.get('model')
        
        print(f"\n[KABUM] Buscando: {produto}")
        if modelo:
            print(f"[KABUM] Modelo para validacao: {modelo}")
        
        try:
            # Navegar para Kabum
            self.driver.get("https://www.kabum.com.br/")
            
            if not self.wait_for_page_load():
                self.driver.refresh()
                if not self.wait_for_page_load():
                    print("ERRO: Kabum nao carregou")
                    return None
            
            # Encontrar campo de busca
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
            
            # Preparar termo de busca
            search_term = f"{marca} {produto}" if marca and marca.lower() not in produto.lower() else produto
            
            # Digitar e buscar
            if not self.human_typing(search_element, search_term):
                print("ERRO: Falha ao digitar na Kabum")
                return None
            
            self.human_delay(0.5, 1.5)
            search_element.send_keys(Keys.ENTER)
            
            # Aguardar resultados
            self.human_delay(4, 7)
            
            if not self.wait_for_page_load():
                pass
            
            # SCROLL PROGRESSIVO para carregar TODOS os produtos
            print("[KABUM] Fazendo scroll progressivo...")
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
            
            # Coletar produtos válidos
            valid_products = []
            rejected_count = 0
            
            for container in product_containers:
                try:
                    # Obter nome do produto
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
                    
                    # Validar se é o produto exato usando o modelo
                    if modelo and not self.is_exact_product_match(product_name, modelo, marca):
                        rejected_count += 1
                        continue
                    
                    # Se não tem modelo, validar por nome completo
                    if not modelo:
                        search_words = search_term.lower().split()
                        product_name_lower = product_name.lower()
                        
                        if not all(word in product_name_lower for word in search_words):
                            rejected_count += 1
                            continue
                        
                        # Verificar palavras de exclusão
                        if any(keyword in product_name_lower for keyword in EXCLUSION_KEYWORDS):
                            rejected_count += 1
                            continue
                    
                    # Buscar preço
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
                            valid_products.append({
                                "name": product_name,
                                "price": price_value,
                                "price_text": price_text,
                                "element": container
                            })
                
                except Exception as e:
                    continue
            
            print(f"[KABUM] Produtos validos: {len(valid_products)} | Rejeitados: {rejected_count}")
            
            if not valid_products:
                print("[KABUM] Produto nao encontrado")
                return None
            
            # Retornar o mais barato
            valid_products.sort(key=lambda x: x["price"])
            cheapest = valid_products[0]
            
            # Mostrar top 3 para debug
            print(f"[KABUM] Top 3 precos encontrados:")
            for i, p in enumerate(valid_products[:3], 1):
                print(f"  {i}. R$ {p['price']:.2f} - {p['name'][:60]}...")
            
            result = {
                "site": "Kabum",
                "produto": cheapest["name"],
                "preco": cheapest["price"],
                "preco_texto": cheapest["price_text"],
                "url": self.driver.current_url,
                "status": "sucesso"
            }
            
            print(f"[KABUM] SELECIONADO: {cheapest['name']} - R$ {cheapest['price']:.2f}")
            
            return result
            
        except Exception as e:
            print(f"ERRO CRITICO: Kabum - {e}")
            return None
    
    def search_amazon(self, component):
        """Busca produto na Amazon e retorna o mais barato que corresponde exatamente"""
        produto = component['name']
        marca = component.get('brand')
        modelo = component.get('model')
        
        print(f"\n[AMAZON] Buscando: {produto}")
        if modelo:
            print(f"[AMAZON] Modelo para validacao: {modelo}")
        
        try:
            # Navegar diretamente para busca
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
            
            if not self.wait_for_page_load():
                pass
            
            # SCROLL PROGRESSIVO para carregar TODOS os produtos
            print("[AMAZON] Fazendo scroll progressivo...")
            self.progressive_scroll(max_scrolls=6)
            
            # Buscar produtos
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
            
            # Coletar produtos válidos
            valid_products = []
            rejected_count = 0
            
            for product in product_elements[:40]:  # Verificar mais produtos
                try:
                    # Obter nome
                    name_selectors = [
                        "h2 a span",
                        ".a-size-medium.a-color-base.a-text-normal",
                        "h2 .a-text-normal",
                        ".a-size-base-plus.a-color-base.a-text-normal"
                    ]
                    
                    product_name = ""
                    for selector in name_selectors:
                        try:
                            name_element = product.find_element(By.CSS_SELECTOR, selector)
                            product_name = name_element.text
                            if product_name:
                                break
                        except:
                            continue
                    
                    if not product_name:
                        continue
                    
                    # Validar se é o produto exato
                    if modelo and not self.is_exact_product_match(product_name, modelo, marca):
                        rejected_count += 1
                        continue
                    
                    # Se não tem modelo, validar por nome completo
                    if not modelo:
                        search_words = search_term.lower().split()
                        product_name_lower = product_name.lower()
                        
                        if not all(word in product_name_lower for word in search_words):
                            rejected_count += 1
                            continue
                        
                        # Verificar palavras de exclusão
                        if any(keyword in product_name_lower for keyword in EXCLUSION_KEYWORDS):
                            rejected_count += 1
                            continue
                    
                    # Extrair preço
                    price_value = 0
                    price_text = ""
                    
                    # Estratégia 1: Estrutura específica da Amazon
                    try:
                        price_whole = product.find_element(By.CSS_SELECTOR, ".a-price-whole").text.strip()
                        try:
                            price_decimal = product.find_element(By.CSS_SELECTOR, ".a-price-fraction").text.strip()
                        except:
                            try:
                                price_decimal_elem = product.find_element(By.CSS_SELECTOR, ".a-price-decimal")
                                if price_decimal_elem.text.strip() == ",":
                                    price_html = product.get_attribute("innerHTML")
                                    decimal_match = re.search(r'<span class="a-price-decimal">,</span>\s*<span[^>]*>(\d+)</span>', price_html)
                                    if decimal_match:
                                        price_decimal = decimal_match.group(1)
                                    else:
                                        price_decimal = "00"
                                else:
                                    price_decimal = price_decimal_elem.text.strip()
                            except:
                                price_decimal = "00"
                        
                        price_text = f"{price_whole},{price_decimal}"
                        price_value = self.clean_price_text(price_text)
                    except:
                        # Estratégia 2: Seletores alternativos
                        price_selectors = [
                            ".a-price[data-a-size='xl'] .a-offscreen",
                            ".a-price .a-offscreen",
                            ".a-price-whole",
                            "[data-a-size='xl'] .a-price-whole",
                            ".a-price .a-price-whole",
                            ".a-price[data-a-size='l']",
                            ".a-price[data-a-size='m']",
                        ]
                        
                        for selector in price_selectors:
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
                            "element": product
                        })
                
                except Exception as e:
                    continue
            
            print(f"[AMAZON] Produtos validos: {len(valid_products)} | Rejeitados: {rejected_count}")
            
            if not valid_products:
                print("[AMAZON] Produto nao encontrado")
                return None
            
            # Retornar o mais barato
            valid_products.sort(key=lambda x: x["price"])
            cheapest = valid_products[0]
            
            # Mostrar top 3 para debug
            print(f"[AMAZON] Top 3 precos encontrados:")
            for i, p in enumerate(valid_products[:3], 1):
                print(f"  {i}. R$ {p['price']:.2f} - {p['name'][:60]}...")
            
            result = {
                "site": "Amazon",
                "produto": cheapest["name"],
                "preco": cheapest["price"],
                "preco_texto": cheapest["price_text"],
                "url": self.driver.current_url,
                "status": "sucesso"
            }
            
            print(f"[AMAZON] SELECIONADO: {cheapest['name']} - R$ {cheapest['price']:.2f}")
            
            return result
            
        except Exception as e:
            print(f"ERRO CRITICO: Amazon - {e}")
            return None
    
    def scrape_component(self, component):
        """Busca preços de um componente em ambos os sites"""
        component_id = component['id']
        component_name = component['name']
        
        print(f"\n{'='*60}")
        print(f"Processando: {component_name} (ID: {component_id})")
        print(f"{'='*60}")
        
        results = {}
        
        # Buscar na Kabum
        kabum_result = self.search_kabum(component)
        if kabum_result:
            results['kabum'] = kabum_result
        
        # Delay entre sites
        self.human_delay(5, 8)
        
        # Buscar na Amazon
        amazon_result = self.search_amazon(component)
        if amazon_result:
            results['amazon'] = amazon_result
        
        # Exibir resumo
        print(f"\n--- Resumo: {component_name} ---")
        
        if 'kabum' in results and results['kabum']['preco']:
            print(f"Kabum: R$ {results['kabum']['preco']:.2f}")
        else:
            print("Kabum: Nao encontrado")
            
        if 'amazon' in results and results['amazon']['preco']:
            print(f"Amazon: R$ {results['amazon']['preco']:.2f}")
        else:
            print("Amazon: Nao encontrado")
        
        # Determinar melhor preço
        valid_prices = []
        if 'kabum' in results and results['kabum']['preco']:
            valid_prices.append(('kabum', results['kabum']['preco']))
        if 'amazon' in results and results['amazon']['preco']:
            valid_prices.append(('amazon', results['amazon']['preco']))
        
        if valid_prices:
            best_site, best_price = min(valid_prices, key=lambda x: x[1])
            print(f"Melhor preco: {best_site.upper()} - R$ {best_price:.2f}")
        else:
            print("Nenhum preco valido encontrado")
        
        print(f"{'='*60}\n")
        
        return results
    
    def close(self):
        """Fecha o driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


def update_component_prices(component_id, results):
    """Atualiza preços do componente no Supabase"""
    try:
        # Estrutura base do best_price
        best_price_data = {
            "best": {"url": None, "price": None, "store": None},
            "kabum": {"url": None, "found": False, "price": None},
            "amazon": {"url": None, "found": False, "price": None},
            "updated_at": None
        }
        
        # Preencher com resultados
        if 'kabum' in results and results['kabum']['preco']:
            best_price_data['kabum'] = {
                "url": results['kabum']['url'],
                "found": True,
                "price": results['kabum']['preco']
            }
        
        if 'amazon' in results and results['amazon']['preco']:
            best_price_data['amazon'] = {
                "url": results['amazon']['url'],
                "found": True,
                "price": results['amazon']['preco']
            }
        
        # Determinar melhor preço
        valid_prices = []
        if 'kabum' in results and results['kabum']['preco']:
            valid_prices.append(('kabum', results['kabum']['preco']))
        if 'amazon' in results and results['amazon']['preco']:
            valid_prices.append(('amazon', results['amazon']['preco']))
        
        if valid_prices:
            best_store, best_price = min(valid_prices, key=lambda x: x[1])
            best_price_data['best'] = {
                "url": results[best_store]['url'],
                "price": best_price,
                "store": best_store
            }
        
        # Timestamp de atualização
        best_price_data['updated_at'] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Atualizar no Supabase
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


def main():
    print("="*60)
    print("Price Scraper - Kabum & Amazon")
    print("="*60)
    
    # Inicializar scraper
    scraper = PriceScraper()
    
    if not scraper.driver:
        print("ERRO CRITICO: Driver nao inicializado")
        print("Verifique instalacao do Chrome/ChromeDriver")
        return
    
    # Buscar componentes no Supabase
    try:
        response = supabase.table("components").select("*").execute()
        components = response.data
        
        if not components:
            print("Nenhum componente encontrado no banco")
            return
        
        print(f"\nTotal de componentes: {len(components)}\n")
        
        # Processar cada componente
        for i, component in enumerate(components, 1):
            print(f"\n[{i}/{len(components)}]")
            
            results = scraper.scrape_component(component)
            
            # Atualizar no banco
            if results:
                update_component_prices(component['id'], results)
            
            # Delay entre componentes
            if component != components[-1]:
                delay = random.uniform(8, 15)
                print(f"Aguardando {delay:.1f}s...\n")
                time.sleep(delay)
        
        print("\n" + "="*60)
        print("Scraping concluido")
        print("="*60)
        
    except Exception as e:
        print(f"ERRO CRITICO: Falha ao buscar componentes - {e}")
    
    finally:
        scraper.close()


if __name__ == "__main__":
    main()