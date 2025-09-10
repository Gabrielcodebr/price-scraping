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
    "RTX 4060",
    "Ryzen 5 5600X", 
    "WD Blue 1TB",
    "Corsair 16GB DDR4",
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
        """Limpa texto de preço de forma mais robusta"""
        if not text:
            return 0.0
            
        try:
            print(f"      🧹 Limpando preço: '{text}'")
            
            # Remove tudo exceto números, vírgula e ponto
            price_clean = re.sub(r'[^\d,.]', '', text)
            
            if not price_clean:
                return 0.0
            
            # Lógica para diferentes formatos brasileiros
            if ',' in price_clean and '.' in price_clean:
                # Formato: 1.234,56 (brasileiro)
                if price_clean.rindex(',') > price_clean.rindex('.'):
                    price_clean = price_clean.replace('.', '').replace(',', '.')
                # Formato: 1,234.56 (americano - raro no Brasil)
                else:
                    price_clean = price_clean.replace(',', '')
            elif ',' in price_clean:
                # Formato: 1234,56
                price_clean = price_clean.replace(',', '.')
            # Se só tem ponto, assume formato: 1234.56
            
            result = float(price_clean)
            print(f"      ✅ Preço limpo: {result:.2f}")
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
    
    def test_kabum_search(self, produto):
        """Teste específico para Kabum"""
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
                "#input-busca",
                "input[data-testid='input-busca']",
                "input[placeholder*='Busque']",
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
            
            # 6. Procurar primeiro produto
            print("🎯 Procurando produtos...")
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
            
            name_element = self.try_find_element_safe(name_selectors, timeout=8)
            
            if not name_element:
                print("❌ Nenhum produto encontrado")
                return None
            
            product_name = name_element.text.strip()
            print(f"📦 Produto encontrado: {product_name}")
            
            # 7. Procurar preço
            print("💰 Procurando preço...")
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
            
            price_element = self.try_find_element_safe(price_selectors, timeout=5)
            
            if not price_element:
                print("❌ Preço não encontrado")
                return {
                    "site": "Kabum",
                    "produto": product_name,
                    "preco": None,
                    "url": self.driver.current_url,
                    "status": "produto_sem_preco"
                }
            
            price_text = price_element.text.strip()
            price_value = self.clean_price_text(price_text)
            
            result = {
                "site": "Kabum",
                "produto": product_name,
                "preco": price_value if price_value > 0 else None,
                "preco_texto": price_text,
                "url": self.driver.current_url,
                "status": "sucesso" if price_value > 0 else "preco_invalido"
            }
            
            print(f"🎉 KABUM RESULTADO:")
            print(f"   📦 Produto: {product_name}")
            print(f"   💰 Preço: R$ {price_value:.2f}" if price_value > 0 else "   ❌ Preço inválido")
            print(f"   🌐 URL: {self.driver.current_url}")
            
            return result
            
        except Exception as e:
            print(f"❌ ERRO NO KABUM: {e}")
            return None
    
    def test_pichau_search(self, produto):
        """Teste específico para Pichau"""
        print(f"\n🟨 TESTANDO PICHAU: '{produto}'")
        print("=" * 50)
        
        try:
            # 1. Navegar para página inicial
            print("📡 Navegando para Pichau...")
            self.driver.get("https://www.pichau.com.br/")
            self.human_delay(3, 5)
            
            # Verificar se não está em manutenção
            page_text = self.driver.page_source.lower()
            if any(word in page_text for word in ["manutenção", "maintenance", "temporariamente"]):
                print("⚠️ Site está em manutenção")
                return None
            
            self.scroll_randomly()
            
            # 2. Encontrar campo de busca
            print("🔍 Procurando campo de busca...")
            search_selectors = [
                "input[name='search']",
                "#search",
                "input[placeholder*='Buscar']",
                "input[placeholder*='buscar']",
                "[data-testid='search-input']",
                ".search-input",
                "input[type='search']"
            ]
            
            search_element = self.try_find_element_safe(search_selectors, timeout=10)
            
            if not search_element:
                print("❌ Campo de busca não encontrado na Pichau")
                return None
            
            print("✅ Campo de busca encontrado!")
            
            # 3. Digitar termo de busca
            print(f"⌨️  Digitando: '{produto}'")
            if not self.human_typing(search_element, produto):
                print("❌ Erro ao digitar no campo")
                return None
            
            # 4. Executar busca
            print("🚀 Executando busca...")
            self.human_delay(0.5, 1.5)
            search_element.send_keys(Keys.ENTER)
            
            # 5. Aguardar resultados
            print("⏳ Aguardando resultados...")
            self.human_delay(4, 7)
            
            self.scroll_randomly()
            
            # 8. Debug: verificar se há produtos na página
            print("🔍 DEBUG: Verificando se há produtos na página...")
            try:
                # Contar diferentes tipos de elementos que podem indicar produtos
                product_indicators = [
                    (".product", "divs com classe product"),
                    ("[data-testid*='product']", "elementos com data-testid product"),
                    (".card", "cards"),
                    (".item", "items"),
                    ("h1,h2,h3,h4", "títulos"),
                    ("img", "imagens"),
                    (".price,.preco", "elementos de preço")
                ]
                
                for selector, desc in product_indicators:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        print(f"   {desc}: {len(elements)} encontrados")
                    except:
                        print(f"   {desc}: erro ao contar")
                        
            except Exception as e:
                print(f"   Erro no debug: {e}")
            
            # 9. Procurar primeiro produto com mais seletores
            print("🎯 Procurando produtos...")
            name_selectors = [
                # Seletores específicos conhecidos
                "h2.mui-ulfya8-product_info_title-noMarginBottom",
                ".product-name",
                "h2[class*='product']",
                ".MuiTypography-h6",
                "[data-cy='product-name']",
                "h2[class*='title']",
                ".product-title",
                ".MuiTypography-root",
                # Seletores mais genéricos
                "h1", "h2", "h3",
                ".card h2", ".card h3", ".card h4",
                ".item h2", ".item h3", ".item h4",
                "[class*='name']",
                "[class*='title']",
                "[class*='produto']"
            ]
            
            name_element = self.try_find_element_safe(name_selectors, timeout=8)
            
            if not name_element:
                print("❌ Nenhum produto encontrado")
                return None
            
            product_name = name_element.text.strip()
            print(f"📦 Produto encontrado: {product_name}")
            
            # 7. Procurar preço
            print("💰 Procurando preço...")
            price_selectors = [
                "div.mui-12athy2-price_vista",
                ".price-vista",
                "[data-cy='price']",
                ".price",
                "div[class*='price']",
                ".priceMain",
                ".bestPrice",
                ".MuiTypography-h5"
            ]
            
            price_element = self.try_find_element_safe(price_selectors, timeout=5)
            
            if not price_element:
                print("❌ Preço não encontrado")
                return {
                    "site": "Pichau",
                    "produto": product_name,
                    "preco": None,
                    "url": self.driver.current_url,
                    "status": "produto_sem_preco"
                }
            
            price_text = price_element.text.strip()
            price_value = self.clean_price_text(price_text)
            
            result = {
                "site": "Pichau",
                "produto": product_name,
                "preco": price_value if price_value > 0 else None,
                "preco_texto": price_text,
                "url": self.driver.current_url,
                "status": "sucesso" if price_value > 0 else "preco_invalido"
            }
            
            print(f"🎉 PICHAU RESULTADO:")
            print(f"   📦 Produto: {product_name}")
            print(f"   💰 Preço: R$ {price_value:.2f}" if price_value > 0 else "   ❌ Preço inválido")
            print(f"   🌐 URL: {self.driver.current_url}")
            
            return result
            
        except Exception as e:
            print(f"❌ ERRO NA PICHAU: {e}")
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
        
        # Testar Pichau
        pichau_result = self.test_pichau_search(produto)
        if pichau_result:
            results['pichau'] = pichau_result
        
        # Resumo do produto
        print(f"\n📋 RESUMO PARA '{produto}':")
        print("-" * 40)
        
        if 'kabum' in results and results['kabum']['preco']:
            print(f"🟦 Kabum: R$ {results['kabum']['preco']:.2f}")
        else:
            print("🟦 Kabum: ❌ Não encontrado")
            
        if 'pichau' in results and results['pichau']['preco']:
            print(f"🟨 Pichau: R$ {results['pichau']['preco']:.2f}")
        else:
            print("🟨 Pichau: ❌ Não encontrado")
        
        # Melhor preço
        valid_prices = []
        if 'kabum' in results and results['kabum']['preco']:
            valid_prices.append(('Kabum', results['kabum']['preco']))
        if 'pichau' in results and results['pichau']['preco']:
            valid_prices.append(('Pichau', results['pichau']['preco']))
        
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
        pichau_sucessos = 0
        total_produtos = len(all_results)
        
        for produto, results in all_results.items():
            print(f"\n📦 {produto}:")
            
            if 'kabum' in results and results['kabum'].get('preco'):
                print(f"   🟦 Kabum: ✅ R$ {results['kabum']['preco']:.2f}")
                kabum_sucessos += 1
            else:
                print(f"   🟦 Kabum: ❌ Falhou")
            
            if 'pichau' in results and results['pichau'].get('preco'):
                print(f"   🟨 Pichau: ✅ R$ {results['pichau']['preco']:.2f}")
                pichau_sucessos += 1
            else:
                print(f"   🟨 Pichau: ❌ Falhou")
        
        print(f"\n🎯 ESTATÍSTICAS:")
        print(f"   Kabum: {kabum_sucessos}/{total_produtos} ({kabum_sucessos/total_produtos*100:.1f}%)")
        print(f"   Pichau: {pichau_sucessos}/{total_produtos} ({pichau_sucessos/total_produtos*100:.1f}%)")
        print(f"   Total de buscas bem-sucedidas: {kabum_sucessos + pichau_sucessos}/{total_produtos * 2}")
        
        if kabum_sucessos + pichau_sucessos >= total_produtos:
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