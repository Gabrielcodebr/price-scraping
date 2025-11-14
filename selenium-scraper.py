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

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Inicializar cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class HumanBehaviorScraper:
    def __init__(self):
        self.driver = None
        try:
            self.setup_driver()
        except Exception as e:
            print(f"❌ Erro no construtor do HumanBehaviorScraper: {e}")
            self.driver = None
    
    def setup_driver(self):
        """Configura Chrome para parecer mais humano"""
        try:
            chrome_options = Options()
            
            # COMENTAR esta linha para VER o navegador
            # chrome_options.add_argument("--headless=new")
            
            # Configurações essenciais
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Configurações para parecer um usuário real
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # User agent realista
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            ]
            chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            # Usar webdriver-manager
            service = Service(ChromeDriverManager().install())
            
            # Inicializar driver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Scripts para esconder automação
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ Driver Chrome configurado")
            return True
        
        except Exception as e:
            print(f"❌ Erro crítico ao configurar driver: {e}")
            print("⚠️  Verifique se o Chrome está instalado")
            self.driver = None
            return False
    
    def wait_for_page_load(self, timeout=30):
        """Espera até que a página esteja completamente carregada"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            print("✅ Página carregada completamente")
            return True
        except TimeoutException:
            print("❌ Timeout esperando página carregar")
            return False
    
    def human_mouse_movement(self, element):
        """Movimento de mouse mais humano"""
        try:
            actions = ActionChains(self.driver)
            # Movimento em curva até o elemento
            actions.move_to_element_with_offset(element, 
                                              random.randint(-5, 5), 
                                              random.randint(-5, 5))
            actions.perform()
            time.sleep(random.uniform(0.1, 0.3))
            return True
        except:
            return False
    
    def human_typing(self, element, text, clear_first=True):
        """Digitação bem humanizada"""
        try:
            # Mover mouse para o elemento primeiro
            self.human_mouse_movement(element)
            
            # Clicar no elemento
            element.click()
            time.sleep(random.uniform(0.2, 0.5))
            
            # Limpar campo se necessário
            if clear_first:
                element.clear()
                time.sleep(random.uniform(0.1, 0.3))
            
            # Digitar caracter por caracter com delays variados
            for i, char in enumerate(text):
                element.send_keys(char)
                
                # Delays mais realistas
                if char == ' ':
                    delay = random.uniform(0.1, 0.3)  # Espaço mais rápido
                elif i > 0 and text[i-1] == ' ':
                    delay = random.uniform(0.05, 0.15)  # Primeira letra após espaço
                else:
                    delay = random.uniform(0.08, 0.2)  # Delay normal
                
                # Ocasionalmente pausar como se estivesse pensando
                if random.random() < 0.1:  # 10% chance
                    delay += random.uniform(0.3, 0.8)
                
                time.sleep(delay)
            
            return True
            
        except Exception as e:
            print(f"      ❌ Erro na digitação: {e}")
            return False
    
    def human_delay(self, min_sec=1, max_sec=3):
        """Delays mais humanizados com variação"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def scroll_randomly(self):
        """Scroll aleatório para parecer mais humano"""
        try:
            # Às vezes scrollar um pouco
            if random.random() < 0.3:  # 30% chance
                scroll_amount = random.randint(100, 400)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                time.sleep(random.uniform(0.5, 1.5))
        except:
            pass
    
    def clean_price_text(self, text):
        """Limpa texto de preço de forma mais robusta para formato brasileiro"""
        if not text:
            return 0.0
            
        try:
            print(f"      🧹 Limpando preço: '{text}'")
            
            # Remove tudo exceto números, vírgula e ponto
            price_clean = re.sub(r'[^\d,.]', '', text)
            
            if not price_clean:
                return 0.0
            
            # Se não há vírgula nem ponto, é um número inteiro
            if ',' not in price_clean and '.' not in price_clean:
                result = float(price_clean)
                print(f"      ✅ Preço limpo (inteiro): {result:.2f}")
                
                # Validar se o preço é razoável (acima de R$ 20,00)
                if result < 20.0:
                    print(f"      ⚠️ Preço muito baixo (R$ {result:.2f}), considerando inválido")
                    return 0.0
                    
                return result
            
            # Lógica para formatos brasileiros
            # Se há vírgula e ponto, provavelmente é formato brasileiro: 1.234,56
            if ',' in price_clean and '.' in price_clean:
                # Verifica se a vírgula está depois do ponto (formato brasileiro)
                if price_clean.rindex(',') > price_clean.rindex('.'):
                    # Formato: 1.234,56 (brasileiro) - remove pontos, substitui vírgula por ponto
                    price_clean = price_clean.replace('.', '').replace(',', '.')
                else:
                    # Formato: 1,234.56 (americano) - remove vírgulas
                    price_clean = price_clean.replace(',', '')
            elif ',' in price_clean:
                # Se só tem vírgula, verifica se é decimal ou milhar
                parts = price_clean.split(',')
                if len(parts) == 2 and len(parts[1]) == 2:
                    # Provavelmente formato brasileiro: 1234,56
                    price_clean = price_clean.replace(',', '.')
                else:
                    # Provavelmente formato europeu: 1,234 - remove vírgulas
                    price_clean = price_clean.replace(',', '')
            # Se só tem ponto, verifica se é decimal ou milhar
            elif '.' in price_clean:
                parts = price_clean.split('.')
                # Se a parte depois do ponto tem 2 dígitos, pode ser decimal
                if len(parts) > 1 and len(parts[-1]) == 2:
                    # Provavelmente formato americano: 1234.56 - já está correto
                    pass
                else:
                    # Provavelmente formato brasileiro: 1.234 - remove pontos
                    price_clean = price_clean.replace('.', '')
            
            result = float(price_clean)
            print(f"      ✅ Preço limpo: {result:.2f}")
            
            # Validar se o preço é razoável (acima de R$ 20,00)
            if result < 20.0:
                print(f"      ⚠️ Preço muito baixo (R$ {result:.2f}), considerando inválido")
                return 0.0
                
            return result
            
        except (ValueError, AttributeError) as e:
            print(f"      ❌ Erro ao limpar preço '{text}': {e}")
            return 0.0
    
    def try_find_element_safe(self, selectors, timeout=5, parent_element=None):
        """Tenta encontrar elemento com múltiplos seletores"""
        search_root = parent_element if parent_element else self.driver
        
        for i, selector in enumerate(selectors):
            try:
                print(f"      🔍 Tentando seletor {i+1}/{len(selectors)}: {selector}")
                
                if parent_element:
                    element = search_root.find_element(By.CSS_SELECTOR, selector)
                else:
                    element = WebDriverWait(search_root, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                
                if element and element.is_displayed():
                    print(f"      ✅ Elemento encontrado!")
                    return element
                    
            except (TimeoutException, NoSuchElementException):
                print(f"      ❌ Seletor falhou")
                continue
        
        print(f"      ❌ Nenhum seletor funcionou")
        return None
    
    def close_popups(self):
        """Tenta fechar popups que possam aparecer"""
        try:
            # Tentar fechar popups comuns
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
                            print("✅ Popup fechado")
                            time.sleep(1)
                            break
                except:
                    continue
        except Exception as e:
            print(f"      ⚠️ Não foi possível fechar popups: {e}")
    
    def apply_kabum_seller_filter(self):
        """Aplica filtro 'Vendido por Kabum' de forma humanizada"""
        try:
            print("🔍 Procurando filtro 'Vendido por Kabum'...")
            
            # Aguardar um pouco para garantir que filtros carregaram
            self.human_delay(2, 3)
            
            # Seletores para o checkbox do filtro Kabum
            filter_selectors = [
                "input[type='checkbox'][value*='kabum']",
                "input[type='checkbox'][name*='kabum_product']",
                "[data-filter*='kabum'] input[type='checkbox']",
                "input[type='checkbox']#kabum_product",
            ]
            
            checkbox = None
            for selector in filter_selectors:
                try:
                    checkbox = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if checkbox:
                        break
                except:
                    continue
            
            if not checkbox:
                print("⚠️ Filtro 'Vendido por Kabum' não encontrado, tentando por label...")
                # Tentar encontrar pelo label
                try:
                    labels = self.driver.find_elements(By.TAG_NAME, "label")
                    for label in labels:
                        if "kabum" in label.text.lower() and "vendido" not in label.text.lower():
                            # Encontrou o label, tentar clicar nele
                            self.human_mouse_movement(label)
                            self.human_delay(0.3, 0.7)
                            label.click()
                            print("✅ Filtro aplicado via label")
                            self.human_delay(3, 4)
                            return True
                except:
                    pass
                
                print("❌ Não foi possível encontrar filtro 'Vendido por Kabum'")
                return False
            
            # Verificar se já está marcado
            if checkbox.is_selected():
                print("✅ Filtro já está aplicado")
                return True
            
            # Aplicar comportamento humano antes de clicar
            print("🖱️ Aplicando filtro de forma humanizada...")
            self.scroll_randomly()
            
            # NOVO: Re-encontrar o checkbox antes de clicar (evita stale element)
            try:
                # Esperar um pouco antes de clicar
                self.human_delay(0.5, 1.0)
                
                # Re-localizar o checkbox usando JavaScript (mais confiável)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                time.sleep(0.5)
                
                # Clicar usando JavaScript (mais confiável que .click())
                self.driver.execute_script("arguments[0].click();", checkbox)
                print("✅ Filtro 'Vendido por Kabum' aplicado")
                
            except Exception as e:
                print(f"⚠️ Erro ao clicar (tentando método alternativo): {e}")
                # Tentar clicar normalmente como fallback
                try:
                    checkbox.click()
                    print("✅ Filtro aplicado (método alternativo)")
                except:
                    print("❌ Falha ao aplicar filtro")
                    return False
            
            # Aguardar resultados atualizarem
            print("⏳ Aguardando resultados filtrarem...")
            self.human_delay(3, 4)
            
            # Esperar página atualizar
            self.wait_for_page_load(timeout=10)
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao aplicar filtro: {e}")
            return False
    
    def get_product_url_from_container(self, container):
        """Extrai URL do produto de um container"""
        try:
            # Seletores para links de produtos
            link_selectors = [
                "a.productLink",
                "a[href*='/produto/']",
                ".nameCard a",
                "a.sc-kpDqfm"
            ]
            
            for selector in link_selectors:
                try:
                    link = container.find_element(By.CSS_SELECTOR, selector)
                    url = link.get_attribute('href')
                    if url:
                        return url
                except:
                    continue
            
            return None
        except:
            return None
    
    def check_amazon_shipping(self, product_url):
        """Verifica se produto é enviado pela Amazon abrindo página individual"""
        try:
            print(f"🔍 Verificando envio do produto...")
            print(f"   🔗 URL: {product_url}")
            
            # Abrir página do produto
            self.driver.get(product_url)
            print("   ⏳ Aguardando página carregar...")
            self.human_delay(3, 5)
            
            if not self.wait_for_page_load():
                print("   ⚠️ Página do produto não carregou")
                return False
            
            print(f"   ✅ Página carregada: {self.driver.current_url}")
            
            # Fechar possíveis popups
            self.close_popups()
            
            # NOVO: Fazer scroll para garantir que tudo carregou
            self.driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1)
            
            # Procurar por "Enviado por"
            print("   🔍 Procurando informações de envio...")
            
            # Tentar encontrar TODO o texto da página primeiro
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                print(f"   📄 Texto da página contém 'enviado'? {'enviado' in body_text}")
                print(f"   📄 Texto da página contém 'amazon'? {'amazon' in body_text}")
            except:
                pass
            
            shipped_by_amazon = False
            
            # Estratégia 1: Buscar por seletores específicos
            shipping_selectors = [
                "#tabular-buybox",
                "#tabular-buybox-truncate-0",
                ".tabular-buybox-text",
                "[data-feature-name='shipsFromSoldBy']",
                ".offer-display-feature-text",
                "#merchant-info",
                ".offer-display-feature-text-message"
            ]
            
            for selector in shipping_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    print(f"   🔍 Seletor '{selector}': encontrou {len(elements)} elementos")
                    
                    for element in elements:
                        if element.is_displayed():
                            text = element.text.lower()
                            print(f"      📝 Texto encontrado: '{text[:100]}'")
                            
                            # Procurar por "enviado por" e verificar se é Amazon
                            if "enviado por" in text or "ships from" in text:
                                print(f"      ✅ Encontrou 'enviado por'!")
                                if "amazon" in text:
                                    shipped_by_amazon = True
                                    print("      ✅✅ ENVIADO PELA AMAZON!")
                                    return True
                                else:
                                    print("      ⚠️ Enviado por terceiro")
                                    return False
                except Exception as e:
                    print(f"      ❌ Erro no seletor '{selector}': {e}")
                    continue
            
            # Estratégia 2: Procurar em todo o HTML
            print("   🔍 Estratégia 2: Buscando no HTML completo...")
            try:
                page_source = self.driver.page_source.lower()
                
                if "enviado por amazon" in page_source or "ships from amazon" in page_source:
                    shipped_by_amazon = True
                    print("      ✅ Enviado pela Amazon (detectado no HTML)")
                    return True
                elif "enviado por" in page_source or "ships from" in page_source:
                    print("      ⚠️ Encontrou 'enviado por' mas não é Amazon")
                    return False
                else:
                    print("      ❌ Não encontrou informação de envio")
                    return False
            except Exception as e:
                print(f"      ❌ Erro na busca no HTML: {e}")
            
            return shipped_by_amazon
            
        except Exception as e:
            print(f"      ❌ Erro ao verificar envio: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_kabum_search(self, produto, marca=None):
        """Teste específico para Kabum - encontra o produto mais barato vendido pela Kabum"""
        print(f"\n🟦 TESTANDO KABUM: '{produto}'")
        if marca:
            print(f"🔍 Com marca: '{marca}'")
        print("=" * 50)
        
        try:
            # 1. Navegar para página inicial
            print("📡 Navegando para Kabum...")
            self.driver.get("https://www.kabum.com.br/")
            
            # Esperar página carregar completamente
            if not self.wait_for_page_load():
                print("❌ Página não carregou corretamente, tentando recarregar...")
                self.driver.refresh()
                if not self.wait_for_page_load():
                    print("❌ Falha ao carregar página após recarregar")
                    return None
            
            # Fazer scroll para ativar elementos
            self.scroll_randomly()
            
            # 2. Encontrar campo de busca
            print("🔍 Procurando campo de busca...")
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
                print("❌ Campo de busca não encontrado no Kabum")
                return None
            
            print("✅ Campo de busca encontrado!")
            
            # 3. Preparar termo de busca com marca se disponível
            search_term = f"{marca} {produto}" if marca and marca.lower() not in produto.lower() else produto
            print(f"🔍 Termo de busca: '{search_term}'")
            
            # 4. Digitar termo de busca
            print(f"⌨️  Digitando: '{search_term}'")
            if not self.human_typing(search_element, search_term):
                print("❌ Erro ao digitar no campo")
                return None
            
            # 5. Pressionar Enter
            print("🚀 Executando busca...")
            self.human_delay(0.5, 1.5)
            search_element.send_keys(Keys.ENTER)
            
            # 6. Aguardar resultados carregarem
            print("⏳ Aguardando resultados...")
            self.human_delay(4, 7)
            
            # Esperar página de resultados carregar
            if not self.wait_for_page_load():
                print("⚠️ Página de resultados pode não ter carregado completamente")
            
            # Fazer scroll para garantir que produtos carregaram
            self.scroll_randomly()
            
            # 7. Aplicar filtro "Vendido por Kabum"
            if not self.apply_kabum_seller_filter():
                print("⚠️ Não foi possível aplicar filtro, continuando sem filtro...")
            
            # 8. Procurar todos os produtos na página
            print("🎯 Procurando produtos...")
            
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
                        print(f"✅ Encontrados {len(product_containers)} produtos")
                        break
                except:
                    continue
            
            if not product_containers:
                print("❌ Nenhum produto encontrado")
                return None
            
            # 9. Coletar todos os produtos válidos com seus preços
            print("🔍 Coletando produtos e preços...")
            valid_products = []
            
            for container in product_containers:
                try:
                    # Obter o nome do produto
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
                    
                    # Verificar se é um componente individual (não começa com "PC")
                    if not product_name.lower().startswith(('pc ', 'computador ', 'notebook ', 'laptop ')):
                        # Verificar se contém a palavra do produto que estamos buscando
                        search_words = search_term.lower().split()
                        product_name_lower = product_name.lower()
                        
                        # Verificar se todas as palavras da busca estão no nome do produto
                        if all(word in product_name_lower for word in search_words):
                            # Procurar preço
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
                                    # Obter URL do produto
                                    product_url = self.get_product_url_from_container(container)
                                    
                                    valid_products.append({
                                        "name": product_name,
                                        "price": price_value,
                                        "price_text": price_text,
                                        "url": product_url,
                                        "element": container
                                    })
                                    print(f"✅ Produto válido: {product_name} - R$ {price_value:.2f}")
                    
                except Exception as e:
                    print(f"⚠️ Erro ao analisar produto: {e}")
                    continue
            
            if not valid_products:
                print("❌ Nenhum produto válido encontrado")
                return None
            
            # 10. Encontrar o produto mais barato
            valid_products.sort(key=lambda x: x["price"])
            cheapest_product = valid_products[0]
            
            product_name = cheapest_product["name"]
            price_value = cheapest_product["price"]
            price_text = cheapest_product["price_text"]
            product_url = cheapest_product["url"] or self.driver.current_url
            
            print(f"📦 Produto mais barato: {product_name}")
            print(f"💰 Preço: R$ {price_value:.2f}")
            print(f"🔗 URL: {product_url}")
            
            result = {
                "site": "Kabum",
                "produto": product_name,
                "preco": price_value,
                "preco_texto": price_text,
                "url": product_url,
                "shipped_by_store": True,  # Sempre True pois filtro foi aplicado
                "status": "sucesso"
            }
            
            print(f"🎉 KABUM RESULTADO:")
            print(f"   📦 Produto: {product_name}")
            print(f"   💰 Preço: R$ {price_value:.2f}")
            print(f"   🌐 URL: {product_url}")
            print(f"   ✅ Vendido e enviado por Kabum")
            
            return result
            
        except Exception as e:
            print(f"❌ ERRO NO KABUM: {e}")
            return None
    
    def test_amazon_search(self, produto, marca=None):
        """Teste específico para Amazon - encontra o produto mais barato e verifica envio"""
        print(f"\n🟧 TESTANDO AMAZON: '{produto}'")
        if marca:
            print(f"🔍 Com marca: '{marca}'")
        print("=" * 50)
        
        try:
            # 1. Navegar para página de busca da Amazon
            print("📡 Navegando para Amazon...")
            search_term = f"{marca} {produto}" if marca and marca.lower() not in produto.lower() else produto
            search_url = f"https://www.amazon.com.br/s?k={search_term.replace(' ', '+')}&i=computers"
            self.driver.get(search_url)
            
            # Esperar página carregar completamente
            if not self.wait_for_page_load():
                print("❌ Página não carregou corretamente, tentando recarregar...")
                self.driver.refresh()
                if not self.wait_for_page_load():
                    print("❌ Falha ao carregar página após recarregar")
                    return None
            
            # Fechar possíveis popups
            self.close_popups()
            
            # 2. Aguardar resultados carregarem
            print("⏳ Aguardando resultados...")
            self.human_delay(4, 7)
            
            # Esperar página de resultados carregar
            if not self.wait_for_page_load():
                print("⚠️ Página de resultados pode não ter carregado completamente")
            
            # Fazer scroll para garantir que produtos carregaram
            self.scroll_randomly()
            
            # 3. Procurar produtos
            print("🎯 Procurando produtos...")
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
                print("❌ Nenhum produto encontrado")
                return None
            
            print(f"✅ Encontrados {len(product_elements)} produtos")
            
            # 4. Coletar todos os produtos válidos com seus preços
            print("🔍 Coletando produtos e preços...")
            valid_products = []
            
            for product in product_elements[:20]:  # Verificar apenas os primeiros 20 produtos
                try:
                    # Verificar se é um componente individual (não PC pré-montado)
                    product_name = ""
                    name_selectors = [
                        "h2 a span",
                        ".a-size-medium.a-color-base.a-text-normal",
                        "h2 .a-text-normal",
                        ".a-size-base-plus.a-color-base.a-text-normal"
                    ]
                    
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
                    
                    # Verificar se não é um PC pré-montado
                    is_prebuilt = any(word in product_name.lower() for word in [
                        "pc", "computador", "completo", "kit", "combo", "gamer", "notebook", "laptop"
                    ])
                    
                    # Verificar se o produto corresponde ao termo de busca
                    search_words = search_term.lower().split()
                    product_name_lower = product_name.lower()
                    matches_search = all(word in product_name_lower for word in search_words)
                    
                    # Se for um componente individual e corresponde à busca
                    if not is_prebuilt and matches_search:
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
                            # Estratégia 2: Métodos alternativos
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
                        
                        # Se encontrou preço válido, extrair URL do produto
                        if price_value > 0:
                            print(f"      💰 Preço encontrado: R$ {price_value:.2f}")
                            print(f"      📦 Nome: {product_name}")
                            
                            product_url = None
                            
                            # Tentar múltiplos seletores para o link
                            link_selectors = [
                                "h2 a",
                                "a.a-link-normal",
                                ".a-link-normal.s-no-outline",
                                "a[href*='/dp/']",
                                ".s-image"
                            ]
                            
                            for link_selector in link_selectors:
                                try:
                                    link_element = product.find_element(By.CSS_SELECTOR, link_selector)
                                    product_url = link_element.get_attribute('href')
                                    if product_url and '/dp/' in product_url:
                                        print(f"      ✅ URL encontrada com '{link_selector}': {product_url[:80]}...")
                                        break
                                except:
                                    continue
                            
                            if not product_url:
                                print(f"      ❌ Nenhuma URL encontrada para este produto")
                                print(f"      🔍 HTML do card: {product.get_attribute('outerHTML')[:200]}...")
                            
                            if product_url:
                                valid_products.append({
                                    "name": product_name,
                                    "price": price_value,
                                    "price_text": price_text,
                                    "url": product_url,
                                    "element": product
                                })
                                print(f"✅ Produto válido COMPLETO: {product_name} - R$ {price_value:.2f}")
                            else:
                                print(f"⚠️ Produto descartado (sem URL): {product_name}")
                    
                except Exception as e:
                    continue
            
            if not valid_products:
                print("❌ Nenhum produto válido encontrado")
                return None
            
            # 5. Encontrar o produto mais barato
            valid_products.sort(key=lambda x: x["price"])
            cheapest_product = valid_products[0]
            
            product_name = cheapest_product["name"]
            price_value = cheapest_product["price"]
            price_text = cheapest_product["price_text"]
            product_url = cheapest_product["url"]
            
            print(f"📦 Produto mais barato: {product_name}")
            print(f"💰 Preço: R$ {price_value:.2f}")
            print(f"🔗 URL: {product_url}")
            
            # 6. Verificar quem envia o produto
            print("\n🔍 Verificando informações de envio...")
            shipped_by_amazon = self.check_amazon_shipping(product_url)
            
            result = {
                "site": "Amazon",
                "produto": product_name,
                "preco": price_value,
                "preco_texto": price_text,
                "url": product_url,
                "shipped_by_store": shipped_by_amazon,
                "status": "sucesso"
            }
            
            print(f"🎉 AMAZON RESULTADO:")
            print(f"   📦 Produto: {product_name}")
            print(f"   💰 Preço: R$ {price_value:.2f}")
            print(f"   🌐 URL: {product_url}")
            if shipped_by_amazon:
                print(f"   ✅ Enviado pela Amazon")
            else:
                print(f"   ⚠️ Envio Externo")
            
            return result
            
        except Exception as e:
            print(f"❌ ERRO NA AMAZON: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def test_product(self, component):
        """Testa busca de um produto em ambos os sites"""
        produto = component['name']
        marca = component.get('brand')
        
        print(f"\n{'='*60}")
        print(f"🧪 TESTANDO PRODUTO: {produto}")
        if marca:
            print(f"🏷️  MARCA: {marca}")
        print(f"{'='*60}")
        
        results = {}
        
        # Testar Kabum
        kabum_result = self.test_kabum_search(produto, marca)
        if kabum_result:
            results['kabum'] = kabum_result
        
        # Delay entre sites
        print(f"\n⏸️  Pausa entre sites...")
        self.human_delay(5, 8)
        
        # Testar Amazon
        amazon_result = self.test_amazon_search(produto, marca)
        if amazon_result:
            results['amazon'] = amazon_result
        
        # Resumo do produto
        print(f"\n📋 RESUMO PARA '{produto}':")
        print("-" * 40)
        
        if 'kabum' in results and results['kabum']['preco']:
            print(f"🟦 Kabum: R$ {results['kabum']['preco']:.2f} (Vendido por Kabum)")
        else:
            print("🟦 Kabum: ❌ Não encontrado")
            
        if 'amazon' in results and results['amazon']['preco']:
            shipping_status = "Enviado pela Amazon" if results['amazon']['shipped_by_store'] else "Envio Externo"
            print(f"🟧 Amazon: R$ {results['amazon']['preco']:.2f} ({shipping_status})")
        else:
            print("🟧 Amazon: ❌ Não encontrado")
        
        # Melhor preço
        valid_prices = []
        if 'kabum' in results and results['kabum']['preco']:
            valid_prices.append(('Kabum', results['kabum']['preco']))
        if 'amazon' in results and results['amazon']['preco']:
            valid_prices.append(('Amazon', results['amazon']['preco']))
        
        if valid_prices:
            best_site, best_price = min(valid_prices, key=lambda x: x[1])
            print(f"🏆 MELHOR: {best_site} - R$ {best_price:.2f}")
        else:
            print("💔 Nenhum preço válido encontrado")
        
        return results
    
    def close(self):
        """Fecha o driver"""
        if self.driver:
            try:
                self.driver.quit()
                print("\n✅ Navegador fechado")
            except:
                pass

def main():
    print("🔧 INICIANDO SCRAPER COM SUPABASE")
    
    # Inicializar o scraper
    try:
        scraper = HumanBehaviorScraper()
    except Exception as e:
        print(f"❌ Erro ao inicializar o scraper: {e}")
        return

    # Verificar se o driver foi inicializado corretamente
    if not scraper.driver:
        print("❌ Falha crítica: Driver do Chrome não foi inicializado")
        print("⚠️  Possíveis causas:")
        print("   - Problemas de permissão no Docker")
        print("   - Chrome/ChromeDriver não instalado corretamente")
        print("   - Incompatibilidade de versões")
        return

    print("Este modo busca componentes no Supabase e atualiza os preços")
    
    # Buscar componentes do Supabase (SEM LIMITE)
    try:
        response = supabase.table("components").select("*").execute()
        components = response.data
        
        if not components:
            print("❌ Nenhum componente encontrado no Supabase")
            return
        
        print(f"📦 Encontrados {len(components)} componentes no Supabase")
        
        for component in components:
            component_id = component['id']
            component_name = component['name']
            component_brand = component.get('brand')
            print(f"\n🔍 Processando componente: {component_name} (ID: {component_id})")
            if component_brand:
                print(f"🏷️  Marca: {component_brand}")
            
            # Testar o produto nas lojas
            results = scraper.test_product(component)
            
            # Preparar dados para atualização
            best_price_data = component.get('best_price', {})
            if not best_price_data:
                best_price_data = {
                    "best": {"url": None, "price": None, "store": None, "shipped_by_store": None},
                    "kabum": {"url": None, "found": False, "price": None, "shipped_by_store": None},
                    "amazon": {"url": None, "found": False, "price": None, "shipped_by_store": None},
                    "updated_at": None
                }
            
            # Preencher com os resultados
            if 'kabum' in results and results['kabum']['preco']:
                best_price_data['kabum'] = {
                    "url": results['kabum']['url'],
                    "found": True,
                    "price": results['kabum']['preco'],
                    "shipped_by_store": results['kabum']['shipped_by_store']
                }
            
            if 'amazon' in results and results['amazon']['preco']:
                best_price_data['amazon'] = {
                    "url": results['amazon']['url'],
                    "found": True,
                    "price": results['amazon']['preco'],
                    "shipped_by_store": results['amazon']['shipped_by_store']
                }
            
            # Determinar o melhor preço
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
                    "store": best_store,
                    "shipped_by_store": results[best_store]['shipped_by_store']
                }
            
            # Atualizar data de atualização
            best_price_data['updated_at'] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            
            # Atualizar o componente no Supabase
            try:
                update_response = supabase.table("components").update({
                    "best_price": best_price_data
                }).eq("id", component_id).execute()
                
                if update_response.data:
                    print(f"✅ Componente {component_name} atualizado com sucesso!")
                else:
                    print(f"❌ Falha ao atualizar componente {component_name}")
            except Exception as e:
                print(f"❌ Erro ao atualizar componente no Supabase: {e}")
            
            # Delay entre componentes
            if component != components[-1]:
                delay = random.uniform(8, 15)
                print(f"\n⏳ Pausa de {delay:.1f}s antes do próximo componente...")
                time.sleep(delay)
        
        scraper.close()
        
    except Exception as e:
        print(f"❌ Erro ao buscar componentes do Supabase: {e}")

if __name__ == "__main__":
    main()