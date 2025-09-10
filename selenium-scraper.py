import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
import urllib.parse
import random

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import chromedriver_autoinstaller

def setup_selenium_driver():
    """Configurar driver do Selenium com Chrome"""
    try:
        # Instala o ChromeDriver automaticamente
        chromedriver_autoinstaller.install()
        
        # Configurações do Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Roda sem interface gráfica
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # User agent para parecer com navegador real
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Outras configurações anti-detecção
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=chrome_options)
        
        # Remove propriedades que identificam automação
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        print(f"Erro ao configurar Selenium: {e}")
        return None

def setup_supabase():
    """Configurar conexão com Supabase"""
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise Exception("Credenciais do Supabase não encontradas no .env")
    
    return create_client(supabase_url, supabase_key)

def get_components(supabase, limit=5):
    """Buscar componentes da tabela (limitado para teste)"""
    try:
        response = supabase.table("components").select("id, name, category").limit(limit).execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar componentes: {e}")
        return []

def search_kabum_selenium(driver, product_name):
    """Buscar preço no Kabum usando Selenium"""
    print(f"  >>> Buscando no Kabum: {product_name}")
    
    try:
        # URL de busca do Kabum
        search_query = urllib.parse.quote(product_name)
        search_url = f"https://www.kabum.com.br/busca?query={search_query}"
        print(f"    URL de busca KabumTeste: {search_url}")
        
        driver.get(search_url)
        
        # Aguardar carregamento da página
        wait = WebDriverWait(driver, 10)
        
        # Aguardar produtos carregarem
        time.sleep(3)
        
        # Tentar encontrar produtos com diferentes seletores
        product_selectors = [
            'article[data-testid="product-card"]',
            '.productCard',
            '[data-testid="product-card"]',
            '.sc-kEqXSa',
            '.listingCard'
        ]
        
        products = []
        for selector in product_selectors:
            try:
                products = driver.find_elements(By.CSS_SELECTOR, selector)
                if products:
                    print(f"    Encontrados {len(products)} produtos com seletor: {selector}")
                    break
            except:
                continue
        
        if not products:
            print("    Nenhum produto encontrado no Kabum")
            return {'price': None, 'url': None, 'found': False}
        
        # Tentar extrair preço do primeiro produto
        for i, product in enumerate(products[:3]):  # Primeiros 3 produtos
            try:
                # Diferentes seletores para preço
                price_selectors = [
                    '[data-testid="price-value"]',
                    '.priceCard',
                    '.oldPriceCard',
                    '.sc-dcJsrY',
                    '[class*="price"]'
                ]
                
                price_element = None
                for price_selector in price_selectors:
                    try:
                        price_element = product.find_element(By.CSS_SELECTOR, price_selector)
                        break
                    except:
                        continue
                
                if price_element:
                    price_text = price_element.text.strip()
                    print(f"    Preço bruto encontrado: {price_text}")
                    
                    # Extrair valor numérico
                    price_clean = ''.join(c for c in price_text if c.isdigit() or c in '.,')
                    price_clean = price_clean.replace(',', '.')
                    
                    if price_clean:
                        try:
                            price_value = float(price_clean)
                            if price_value > 0:
                                # Tentar pegar link do produto
                                try:
                                    link_element = product.find_element(By.TAG_NAME, 'a')
                                    product_url = link_element.get_attribute('href')
                                except:
                                    product_url = search_url
                                
                                print(f"    Kabum - Preço encontrado: R$ {price_value:.2f}")
                                return {
                                    'price': price_value,
                                    'url': product_url,
                                    'found': True
                                }
                        except ValueError:
                            continue
            except Exception as e:
                print(f"    Erro ao processar produto {i+1}: {e}")
                continue
        
        print("    Kabum - Preço não encontrado")
        return {'price': None, 'url': None, 'found': False}
        
    except Exception as e:
        print(f"    Erro geral no Kabum: {e}")
        return {'price': None, 'url': None, 'found': False}

def search_pichau_selenium(driver, product_name):
    """Buscar preço na Pichau usando Selenium"""
    print(f"  >>> Buscando na Pichau: {product_name}")
    
    try:
        # URL de busca da Pichau
        search_query = urllib.parse.quote(product_name)
        search_url = f"https://www.pichau.com.br/buscar?q={search_query}"
        print(f"    URL de buscaPichauTeste: {search_url}")
        
        driver.get(search_url)
        
        # Aguardar carregamento
        time.sleep(4)
        
        # Tentar diferentes seletores para produtos
        product_selectors = [
            '[data-cy="list-product"]',
            '.MuiGrid-item',
            '.jss',
            '[class*="product"]',
            'article'
        ]
        
        products = []
        for selector in product_selectors:
            try:
                products = driver.find_elements(By.CSS_SELECTOR, selector)
                if products:
                    print(f"    Encontrados {len(products)} produtos com seletor: {selector}")
                    break
            except:
                continue
        
        if not products:
            print("    Nenhum produto encontrado na Pichau")
            return {'price': None, 'url': None, 'found': False}
        
        # Tentar extrair preço
        for i, product in enumerate(products[:3]):
            try:
                # Procurar por elementos que contenham "R$"
                price_elements = product.find_elements(By.XPATH, ".//*[contains(text(), 'R$')]")
                
                for price_element in price_elements:
                    price_text = price_element.text.strip()
                    if 'R$' in price_text:
                        print(f"    Preço bruto encontrado: {price_text}")
                        
                        # Extrair valor numérico
                        price_clean = price_text.replace('R$', '').strip()
                        price_clean = ''.join(c for c in price_clean if c.isdigit() or c in '.,')
                        price_clean = price_clean.replace(',', '.')
                        
                        if price_clean:
                            try:
                                price_value = float(price_clean)
                                if price_value > 0:
                                    # Tentar pegar link
                                    try:
                                        link_element = product.find_element(By.TAG_NAME, 'a')
                                        product_url = link_element.get_attribute('href')
                                    except:
                                        product_url = search_url
                                    
                                    print(f"    Pichau - Preço encontrado: R$ {price_value:.2f}")
                                    return {
                                        'price': price_value,
                                        'url': product_url,
                                        'found': True
                                    }
                            except ValueError:
                                continue
            except Exception as e:
                continue
        
        print("    Pichau - Preço não encontrado")
        return {'price': None, 'url': None, 'found': False}
        
    except Exception as e:
        print(f"    Erro geral na Pichau: {e}")
        return {'price': None, 'url': None, 'found': False}

def find_best_price(kabum_result, pichau_result):
    """Encontrar o melhor preço entre os dois sites"""
    prices = []
    
    if kabum_result['found'] and kabum_result['price']:
        prices.append({
            'price': kabum_result['price'],
            'store': 'kabum',
            'url': kabum_result['url']
        })
    
    if pichau_result['found'] and pichau_result['price']:
        prices.append({
            'price': pichau_result['price'],
            'store': 'pichau',
            'url': pichau_result['url']
        })
    
    if not prices:
        return {'price': None, 'store': None, 'url': None}
    
    best = min(prices, key=lambda x: x['price'])
    return best

def update_component_price(supabase, component_id, kabum_result, pichau_result, best_result):
    """Atualizar preços no banco de dados"""
    price_data = {
        'kabum': kabum_result,
        'pichau': pichau_result,
        'best': best_result,
        'updated_at': datetime.now().isoformat()
    }
    
    try:
        supabase.table("components").update({
            'best_price': price_data
        }).eq('id', component_id).execute()
        return True
    except Exception as e:
        print(f"    Erro ao atualizar banco: {e}")
        return False

def scrape_prices_selenium():
    """Função principal com Selenium"""
    print("=== SCRAPER COM SELENIUM ===")
    print(f"Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    driver = None
    try:
        # Configurar Selenium
        print(">>> Configurando Selenium...")
        driver = setup_selenium_driver()
        if not driver:
            print(">>> Erro: Não foi possível configurar o Selenium")
            return
        
        print(">>> Selenium configurado com sucesso")
        
        # Configurar Supabase
        supabase = setup_supabase()
        print(">>> Conectado ao Supabase")
        
        # Buscar componentes (limitado para teste)
        components = get_components(supabase, limit=3)  # Apenas 3 para testar
        print(f">>> Testando com {len(components)} componentes")
        
        if not components:
            print(">>> Nenhum componente encontrado")
            return
        
        success_count = 0
        error_count = 0
        
        for i, component in enumerate(components, 1):
            print(f"\n[{i}/{len(components)}] Processando: {component['name']}")
            
            try:
                # Buscar no Kabum
                kabum_result = search_kabum_selenium(driver, component['name'])
                
                # Delay entre buscas
                time.sleep(random.uniform(3, 6))
                
                # Buscar na Pichau
                pichau_result = search_pichau_selenium(driver, component['name'])
                
                # Delay entre buscas
                time.sleep(random.uniform(2, 4))
                
                # Encontrar melhor preço
                best_result = find_best_price(kabum_result, pichau_result)
                
                # Mostrar resultados
                if best_result['price']:
                    print(f"    >>> MELHOR PREÇO: R$ {best_result['price']:.2f} ({best_result['store'].upper()})")
                else:
                    print(f"    >>> Produto não encontrado em nenhum site")
                
                # Atualizar banco
                if update_component_price(supabase, component['id'], kabum_result, pichau_result, best_result):
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                print(f"    Erro ao processar {component['name']}: {e}")
                error_count += 1
        
        print(f"\n=== TESTE FINALIZADO ===")
        print(f"Sucessos: {success_count}")
        print(f"Erros: {error_count}")
        
    except Exception as e:
        print(f"Erro geral: {e}")
    
    finally:
        if driver:
            driver.quit()
            print(">>> Driver fechado")

if __name__ == "__main__":
    scrape_prices_selenium()