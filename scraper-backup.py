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

# Palavras que indicam que não é o produto puro
EXCLUSION_KEYWORDS = [
    'pc ', 'computador', 'completo', 'kit', 'combo', 'gamer', 'notebook', 'laptop',
    'suporte', 'bracket', 'shield', 'parafuso', 'cabo', 'adaptador', 'extensor',
    'acessorio', 'cooler', 'ventoinha', 'base', 'case', 'gabinete'
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
    
    def scroll_randomly(self):
        """Scroll aleatório para simular leitura"""
        try:
            if random.random() < 0.3:
                scroll_amount = random.randint(100, 400)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                time.sleep(random.uniform(0.5, 1.5))
        except:
            pass
    
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
    
    def normalize_model(self, model_text):
        """Normaliza texto do modelo para comparação"""
        if not model_text:
            return ""
        # Remove hífens, espaços extras e converte para minúsculas
        normalized = re.sub(r'[-\s]+', '', model_text.lower())
        return normalized
    
    def is_exact_product_match(self, product_name, search_model, search_brand=None):
        """
        Valida se o produto encontrado corresponde exatamente ao modelo buscado.
        Aceita variações pequenas mas rejeita acessórios e produtos similares.
        """
        if not product_name or not search_model:
            return False
        
        product_name_lower = product_name.lower()
        
        # Verificar palavras de exclusão
        for keyword in EXCLUSION_KEYWORDS:
            if keyword in product_name_lower:
                return False
        
        # Normalizar para comparação
        normalized_product = self.normalize_model(product_name)
        normalized_search = self.normalize_model(search_model)
        
        # O modelo normalizado deve estar presente no nome do produto
        if normalized_search not in normalized_product:
            return False
        
        # Se tem marca, verificar se está presente
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
        
        try:
            # Navegar para Kabum
            self.driver.get("https://www.kabum.com.br/")
            
            if not self.wait_for_page_load():
                self.driver.refresh()
                if not self.wait_for_page_load():
                    print("ERRO: Kabum nao carregou")
                    return None
            
            self.scroll_randomly()
            
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
            
            self.scroll_randomly()
            
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
            
            # Coletar produtos válidos
            valid_products = []
            
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
                        continue
                    
                    # Se não tem modelo, validar por nome completo
                    if not modelo:
                        search_words = search_term.lower().split()
                        product_name_lower = product_name.lower()
                        
                        if not all(word in product_name_lower for word in search_words):
                            continue
                        
                        # Verificar palavras de exclusão
                        if any(keyword in product_name_lower for keyword in EXCLUSION_KEYWORDS):
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
            
            if not valid_products:
                print("[KABUM] Produto nao encontrado")
                return None
            
            # Retornar o mais barato
            valid_products.sort(key=lambda x: x["price"])
            cheapest = valid_products[0]
            
            result = {
                "site": "Kabum",
                "produto": cheapest["name"],
                "preco": cheapest["price"],
                "preco_texto": cheapest["price_text"],
                "url": self.driver.current_url,
                "status": "sucesso"
            }
            
            print(f"[KABUM] Encontrado: {cheapest['name']} - R$ {cheapest['price']:.2f}")
            
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
            
            self.scroll_randomly()
            
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
            
            # Coletar produtos válidos
            valid_products = []
            
            for product in product_elements[:20]:
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
                        continue
                    
                    # Se não tem modelo, validar por nome completo
                    if not modelo:
                        search_words = search_term.lower().split()
                        product_name_lower = product_name.lower()
                        
                        if not all(word in product_name_lower for word in search_words):
                            continue
                        
                        # Verificar palavras de exclusão
                        if any(keyword in product_name_lower for keyword in EXCLUSION_KEYWORDS):
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
            
            if not valid_products:
                print("[AMAZON] Produto nao encontrado")
                return None
            
            # Retornar o mais barato
            valid_products.sort(key=lambda x: x["price"])
            cheapest = valid_products[0]
            
            result = {
                "site": "Amazon",
                "produto": cheapest["name"],
                "preco": cheapest["price"],
                "preco_texto": cheapest["price_text"],
                "url": self.driver.current_url,
                "status": "sucesso"
            }
            
            print(f"[AMAZON] Encontrado: {cheapest['name']} - R$ {cheapest['price']:.2f}")
            
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