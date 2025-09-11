import time
import random
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains

# Produtos para teste (use produtos reais que você sabe que existem)
produtos_teste = [
    "RX 7800 xt",
    "Processador Intel i5 12400F", 
    "ASUS B450M"
]

class HumanBehaviorScraper:
    def __init__(self):
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Configura Chrome para parecer mais humano"""
        try:
            chrome_options = Options()
            
            # Configurações para parecer um usuário real
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins-discovery") 
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            
            # User agent mais realista
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
            
            chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            # Desabilitar automação detectável
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Scripts para esconder automação
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']})")
            
            print("✅ Driver configurado para comportamento humano")
            
        except Exception as e:
            print(f"❌ Erro ao configurar driver: {e}")
            self.driver = None
    
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
    
    def test_kabum_search(self, produto):
        """Teste específico para Kabum - encontra o produto mais barato"""
        print(f"\n🟦 TESTANDO KABUM: '{produto}'")
        print("=" * 50)
        
        try:
            # 1. Navegar para página inicial
            print("📡 Navegando para Kabum...")
            self.driver.get("https://www.kabum.com.br/")
            self.human_delay(3, 5)
            
            # Fazer scroll para ativar elementos
            self.scroll_randomly()
            
            # 2. Encontrar campo de busca
            print("🔍 Procurando campo de busca...")
            search_selectors = [
                "input[placeholder*='Busque']",  # Primeiro o seletor que funcionou nos logs
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
            
            # 3. Digitar termo de busca
            print(f"⌨️  Digitando: '{produto}'")
            if not self.human_typing(search_element, produto):
                print("❌ Erro ao digitar no campo")
                return None
            
            # 4. Pressionar Enter ou clicar no botão
            print("🚀 Executando busca...")
            self.human_delay(0.5, 1.5)
            search_element.send_keys(Keys.ENTER)
            
            # 5. Aguardar resultados carregarem
            print("⏳ Aguardando resultados...")
            self.human_delay(4, 7)
            
            # Fazer scroll para garantir que produtos carregaram
            self.scroll_randomly()
            
            # 6. Procurar todos os produtos na página
            print("🎯 Procurando produtos...")
            
            # Primeiro, encontrar todos os produtos na página
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
            
            # 7. Coletar todos os produtos válidos com seus preços
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
                        search_words = produto.lower().split()
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
                                    valid_products.append({
                                        "name": product_name,
                                        "price": price_value,
                                        "price_text": price_text,
                                        "element": container
                                    })
                                    print(f"✅ Produto válido: {product_name} - R$ {price_value:.2f}")
                    
                except Exception as e:
                    print(f"⚠️ Erro ao analisar produto: {e}")
                    continue
            
            if not valid_products:
                print("❌ Nenhum produto válido encontrado")
                return None
            
            # 8. Encontrar o produto mais barato
            valid_products.sort(key=lambda x: x["price"])
            cheapest_product = valid_products[0]
            
            product_name = cheapest_product["name"]
            price_value = cheapest_product["price"]
            price_text = cheapest_product["price_text"]
            
            print(f"📦 Produto mais barato: {product_name}")
            print(f"💰 Preço: R$ {price_value:.2f}")
            
            result = {
                "site": "Kabum",
                "produto": product_name,
                "preco": price_value,
                "preco_texto": price_text,
                "url": self.driver.current_url,
                "status": "sucesso"
            }
            
            print(f"🎉 KABUM RESULTADO:")
            print(f"   📦 Produto: {product_name}")
            print(f"   💰 Preço: R$ {price_value:.2f}")
            print(f"   🌐 URL: {self.driver.current_url}")
            
            return result
            
        except Exception as e:
            print(f"❌ ERRO NO KABUM: {e}")
            return None
    
    def test_amazon_search(self, produto):
        """Teste específico para Amazon - encontra o produto mais barato"""
        print(f"\n🟧 TESTANDO AMAZON: '{produto}'")
        print("=" * 50)
        
        try:
            # 1. Navegar para página de busca da Amazon
            print("📡 Navegando para Amazon...")
            search_url = f"https://www.amazon.com.br/s?k={produto.replace(' ', '+')}&i=computers"
            self.driver.get(search_url)
            self.human_delay(3, 5)
            
            # Fechar possíveis popups
            self.close_popups()
            
            # 2. Aguardar resultados carregarem
            print("⏳ Aguardando resultados...")
            self.human_delay(4, 7)
            
            # Fazer scroll para garantir que produtos carregaram
            self.scroll_randomly()
            
            # 3. Procurar produtos - seletores para Amazon
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
                        "h2 a span",  # Nome do produto
                        ".a-size-medium.a-color-base.a-text-normal",  # Classe comum para nomes
                        "h2 .a-text-normal",  # Outro seletor para nomes
                        ".a-size-base-plus.a-color-base.a-text-normal"  # Nome do produto alternativo
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
                    
                    # Verificar se o produto corresponde exatamente ao termo de busca
                    search_words = produto.lower().split()
                    product_name_lower = product_name.lower()
                    
                    # Verificar se todas as palavras da busca estão no nome do produto
                    matches_search = all(word in product_name_lower for word in search_words)
                    
                    # Se for um componente individual e corresponde à busca, tentar extrair o preço
                    if not is_prebuilt and matches_search:
                        # Extrair preço usando a estrutura HTML fornecida
                        price_value = 0
                        price_text = ""
                        
                        # Estratégia 1: Extrair usando a estrutura específica fornecida
                        try:
                            price_whole = product.find_element(By.CSS_SELECTOR, ".a-price-whole").text.strip()
                            try:
                                # Tentar encontrar a parte decimal
                                price_decimal = product.find_element(By.CSS_SELECTOR, ".a-price-fraction").text.strip()
                            except:
                                # Se não encontrar .a-price-fraction, tentar .a-price-decimal
                                try:
                                    price_decimal_elem = product.find_element(By.CSS_SELECTOR, ".a-price-decimal")
                                    # Se é apenas a vírgula, procurar o valor decimal em outro lugar
                                    if price_decimal_elem.text.strip() == ",":
                                        # Procurar o valor decimal após a vírgula
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
                        except Exception as e:
                            print(f"      ⚠️ Erro na extração específica: {e}")
                            # Estratégia 2: Se não funcionar, tentar métodos alternativos
                            price_selectors = [
                                ".a-price[data-a-size='xl'] .a-offscreen",  # Preço com símbolo
                                ".a-price .a-offscreen",  # Preço com símbolo (alternativo)
                                ".a-price-whole",  # Parte inteira do preço
                                "[data-a-size='xl'] .a-price-whole",  # Preço em destaque
                                ".a-price .a-price-whole",  # Parte inteira do preço dentro de .a-price
                                ".a-price[data-a-size='l']",  # Preço grande
                                ".a-price[data-a-size='m']",  # Preço médio
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
                        
                        # Se encontrou um preço válido, adicionar à lista
                        if price_value > 0:
                            valid_products.append({
                                "name": product_name,
                                "price": price_value,
                                "price_text": price_text,
                                "element": product
                            })
                            print(f"✅ Produto válido: {product_name} - R$ {price_value:.2f}")
                    
                except Exception as e:
                    print(f"      ⚠️ Erro ao analisar produto: {e}")
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
            
            print(f"📦 Produto mais barato: {product_name}")
            print(f"💰 Preço: R$ {price_value:.2f}")
            
            result = {
                "site": "Amazon",
                "produto": product_name,
                "preco": price_value,
                "preco_texto": price_text,
                "url": self.driver.current_url,
                "status": "sucesso"
            }
            
            print(f"🎉 AMAZON RESULTADO:")
            print(f"   📦 Produto: {product_name}")
            print(f"   💰 Preço: R$ {price_value:.2f}")
            print(f"   🌐 URL: {self.driver.current_url}")
            
            return result
            
        except Exception as e:
            print(f"❌ ERRO NA AMAZON: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def test_product(self, produto):
        """Testa busca de um produto em ambos os sites"""
        print(f"\n{'='*60}")
        print(f"🧪 TESTANDO PRODUTO: {produto}")
        print(f"{'='*60}")
        
        results = {}
        
        # Testar Kabum
        kabum_result = self.test_kabum_search(produto)
        if kabum_result:
            results['kabum'] = kabum_result
        
        # Delay entre sites
        print(f"\n⏸️  Pausa entre sites...")
        self.human_delay(5, 8)
        
        # Testar Amazon
        amazon_result = self.test_amazon_search(produto)
        if amazon_result:
            results['amazon'] = amazon_result
        
        # Resumo do produto
        print(f"\n📋 RESUMO PARA '{produto}':")
        print("-" * 40)
        
        if 'kabum' in results and results['kabum']['preco']:
            print(f"🟦 Kabum: R$ {results['kabum']['preco']:.2f}")
        else:
            print("🟦 Kabum: ❌ Não encontrado")
            
        if 'amazon' in results and results['amazon']['preco']:
            print(f"🟧 Amazon: R$ {results['amazon']['preco']:.2f}")
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
    
    def run_tests(self, limit=2):
        """Executa testes com produtos limitados"""
        print("🧪 MODO TESTE - SCRAPER DE COMPONENTES")
        print("Vamos testar se conseguimos buscar e extrair preços corretamente")
        print(f"Testando {limit} produtos dos {len(produtos_teste)} disponíveis\n")
        
        if not self.driver:
            print("❌ Driver não foi configurado corretamente")
            return
        
        test_products = produtos_teste[:limit]
        all_results = {}
        
        try:
            for i, produto in enumerate(test_products, 1):
                print(f"\n🎯 TESTE {i}/{len(test_products)}")
                
                results = self.test_product(produto)
                all_results[produto] = results
                
                # Delay entre produtos (exceto no último)
                if i < len(test_products):
                    delay = random.uniform(8, 15)
                    print(f"\n⏳ Pausa de {delay:.1f}s antes do próximo produto...")
                    time.sleep(delay)
            
            # Relatório final
            self.print_final_report(all_results)
            
        except KeyboardInterrupt:
            print("\n⚠️ Teste interrompido pelo usuário")
        except Exception as e:
            print(f"\n❌ Erro durante teste: {e}")
        finally:
            self.close()
    
    def print_final_report(self, all_results):
        """Imprime relatório final dos testes"""
        print(f"\n{'='*60}")
        print("📊 RELATÓRIO FINAL DOS TESTES")
        print(f"{'='*60}")
        
        kabum_sucessos = 0
        amazon_sucessos = 0
        total_produtos = len(all_results)
        
        for produto, results in all_results.items():
            print(f"\n📦 {produto}:")
            
            if 'kabum' in results and results['kabum'].get('preco'):
                print(f"   🟦 Kabum: ✅ R$ {results['kabum']['preco']:.2f}")
                kabum_sucessos += 1
            else:
                print(f"   🟦 Kabum: ❌ Falhou")
            
            if 'amazon' in results and results['amazon'].get('preco'):
                print(f"   🟧 Amazon: ✅ R$ {results['amazon']['preco']:.2f}")
                amazon_sucessos += 1
            else:
                print(f"   🟧 Amazon: ❌ Falhou")
        
        print(f"\n🎯 ESTATÍSTICAS:")
        print(f"   Kabum: {kabum_sucessos}/{total_produtos} ({kabum_sucessos/total_produtos*100:.1f}%)")
        print(f"   Amazon: {amazon_sucessos}/{total_produtos} ({amazon_sucessos/total_produtos*100:.1f}%)")
        print(f"   Total de buscas bem-suedidas: {kabum_sucessos + amazon_sucessos}/{total_produtos * 2}")
        
        if kabum_sucessos + amazon_sucessos >= total_produtos:
            print("\n🎉 TESTE APROVADO! Scraper está funcionando bem.")
        else:
            print("\n⚠️ TESTE PARCIAL. Alguns sites podem precisar de ajustes nos seletores.")
    
    def close(self):
        """Fecha o driver"""
        if self.driver:
            try:
                self.driver.quit()
                print("\n✅ Navegador fechado")
            except:
                pass

def main():
    print("🔧 INICIANDO TESTES DO SCRAPER")
    print("Este modo testa se conseguimos buscar e extrair preços corretamente")
    print("Após os testes funcionarem, podemos integrar com o Supabase\n")
    
    scraper = HumanBehaviorScraper()
    
    # Testar com apenas 2 produtos primeiro
    scraper.run_tests(limit=2)

if __name__ == "__main__":
    main()