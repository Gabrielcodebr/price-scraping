import os
import requests
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from bs4 import BeautifulSoup
import urllib.parse

def setup_supabase():
    """Configurar conexão com Supabase"""
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise Exception("Credenciais do Supabase não encontradas no .env")
    
    return create_client(supabase_url, supabase_key)

def get_components(supabase):
    """Buscar todos os componentes da tabela"""
    try:
        response = supabase.table("components").select("id, name, category").execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar componentes: {e}")
        return []

def search_kabum(product_name):
    """Buscar preço no Kabum"""
    print(f"  >>> Buscando no Kabum: {product_name}")
    
    try:
        # URL de busca do Kabum
        search_url = f"https://www.kabum.com.br/busca?query={urllib.parse.quote(product_name)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Procurar pelo primeiro produto na página de resultados
            # Kabum usa classes específicas para produtos
            product_cards = soup.find_all('article', class_='productCard')
            
            if not product_cards:
                product_cards = soup.find_all('div', class_='sc-fFeiMQ')
            
            for card in product_cards[:3]:  # Verificar primeiros 3 resultados
                try:
                    # Buscar preço
                    price_element = card.find('span', class_='priceCard') or \
                                  card.find('span', class_='oldPriceCard') or \
                                  card.find('div', class_='priceCard')
                    
                    if price_element:
                        price_text = price_element.get_text().strip()
                        # Extrair só os números
                        price = ''.join(filter(lambda x: x.isdigit() or x == '.', price_text.replace(',', '.')))
                        
                        if price and float(price) > 0:
                            # Buscar link do produto
                            link_element = card.find('a', href=True)
                            product_url = f"https://www.kabum.com.br{link_element['href']}" if link_element else search_url
                            
                            return {
                                'price': float(price),
                                'url': product_url,
                                'found': True
                            }
                except Exception as e:
                    continue
            
            return {'price': None, 'url': None, 'found': False}
            
        else:
            print(f"    Kabum retornou status: {response.status_code}")
            return {'price': None, 'url': None, 'found': False}
            
    except Exception as e:
        print(f"    Erro no Kabum: {e}")
        return {'price': None, 'url': None, 'found': False}

def search_pichau(product_name):
    """Buscar preço na Pichau"""
    print(f"  >>> Buscando na Pichau: {product_name}")
    
    try:
        # URL de busca da Pichau
        search_url = f"https://www.pichau.com.br/buscar?q={urllib.parse.quote(product_name)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Procurar pelo primeiro produto na página de resultados
            product_cards = soup.find_all('div', class_='MuiGrid-item') or \
                          soup.find_all('article') or \
                          soup.find_all('div', {'data-cy': 'list-product'})
            
            for card in product_cards[:3]:  # Verificar primeiros 3 resultados
                try:
                    # Buscar preço - Pichau pode usar várias classes
                    price_element = card.find('div', class_='jss') or \
                                  card.find('span', string=lambda text: text and 'R$' in text) or \
                                  card.find('div', string=lambda text: text and 'R$' in text)
                    
                    if price_element:
                        price_text = price_element.get_text().strip()
                        # Extrair só os números
                        price = ''.join(filter(lambda x: x.isdigit() or x == '.', price_text.replace(',', '.')))
                        
                        if price and float(price) > 0:
                            # Buscar link do produto
                            link_element = card.find('a', href=True)
                            product_url = f"https://www.pichau.com.br{link_element['href']}" if link_element else search_url
                            
                            return {
                                'price': float(price),
                                'url': product_url,
                                'found': True
                            }
                except Exception as e:
                    continue
            
            return {'price': None, 'url': None, 'found': False}
            
        else:
            print(f"    Pichau retornou status: {response.status_code}")
            return {'price': None, 'url': None, 'found': False}
            
    except Exception as e:
        print(f"    Erro na Pichau: {e}")
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
    
    # Encontrar o menor preço
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

def scrape_prices():
    """Função principal do scraper"""
    print("=== INICIANDO SCRAPER DE PREÇOS ===")
    print(f"Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Configurar Supabase
        supabase = setup_supabase()
        print(">>> Conectado ao Supabase")
        
        # Buscar componentes
        components = get_components(supabase)
        print(f">>> Encontrados {len(components)} componentes")
        
        if not components:
            print(">>> Nenhum componente encontrado. Finalizando.")
            return
        
        success_count = 0
        error_count = 0
        
        for i, component in enumerate(components, 1):
            print(f"\n[{i}/{len(components)}] Processando: {component['name']}")
            
            try:
                # Buscar nos dois sites
                kabum_result = search_kabum(component['name'])
                time.sleep(2)  # Delay entre requisições
                
                pichau_result = search_pichau(component['name'])
                time.sleep(2)  # Delay entre requisições
                
                # Encontrar melhor preço
                best_result = find_best_price(kabum_result, pichau_result)
                
                # Mostrar resultados
                print(f"    Kabum: {'R$ %.2f' % kabum_result['price'] if kabum_result['found'] else 'Não encontrado'}")
                print(f"    Pichau: {'R$ %.2f' % pichau_result['price'] if pichau_result['found'] else 'Não encontrado'}")
                
                if best_result['price']:
                    print(f"    >>> MELHOR: R$ {best_result['price']:.2f} ({best_result['store'].upper()})")
                else:
                    print(f"    >>> Não encontrado em nenhum site")
                
                # Atualizar banco de dados
                if update_component_price(supabase, component['id'], kabum_result, pichau_result, best_result):
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                print(f"    Erro ao processar {component['name']}: {e}")
                error_count += 1
        
        print(f"\n=== SCRAPER FINALIZADO ===")
        print(f"Sucessos: {success_count}")
        print(f"Erros: {error_count}")
        print(f"Total: {len(components)}")
        
    except Exception as e:
        print(f"Erro geral no scraper: {e}")

if __name__ == "__main__":
    scrape_prices()