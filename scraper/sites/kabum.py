import random
import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from ..matching_rules import EXCLUSION_KEYWORDS

# [FEATURE 01/09] Quantos candidatos extras (além do mais barato) cada site manda pra
# price_scraper.py combinar. O corte final pros "5 no total" (Kabum + Amazon combinados)
# acontece lá, não aqui — 5 por site é o máximo que qualquer site sozinho poderia
# precisar contribuir pro combinado (se TODOS os 5 mais baratos vierem de um único site).
# Mesma constante existe em sites/amazon.py; se um dia sair do lugar, considerar mover
# pra config.py pra não haver risco dos dois valores divergirem.
ALT_PRICES_PER_SITE = 5


class KabumMixin:
    """Mixin de PriceScraper: busca e extração de preços na Kabum."""

    # -------------------------------------------------------------------------
    # KABUM helpers
    # -------------------------------------------------------------------------

    def click_kabum_filter(self):
        """
        Tenta clicar no checkbox 'KaBuM!' no filtro 'Vendido por'.

        [MONITORING/FIX] Retorna um de três estados em vez de um bool, para distinguir
        "não tem estoque próprio nessa busca" (miss legítimo de negócio) de "falha
        técnica ao tentar aplicar o filtro" (erro transitório que não deve contar como
        miss nem resetar preço). A lógica de clique/scroll/timing em si NÃO foi alterada.

        Retorna:
            "applied"   -> filtro encontrado e aplicado (ou já estava aplicado)
            "not_found" -> checkbox 'KaBuM!' não existe nessa busca (sem estoque próprio)
            "error"     -> falha técnica ao tentar aplicar o filtro
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
                return "not_found"

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
                return "error"

            if already_checked:
                print("[KABUM] Filtro 'KaBuM!' ja estava selecionado")
                return "applied"

            # Buscar referência fresca imediatamente antes de clicar
            labels_fresh = self.driver.find_elements(By.CSS_SELECTOR, "label")
            if target_index >= len(labels_fresh):
                print("[KABUM] Filtro sumiu apos scroll")
                return "error"

            checkbox = labels_fresh[target_index].find_element(By.CSS_SELECTOR, "input")

            # Clique humanizado via ActionChains
            actions = ActionChains(self.driver)
            actions.move_to_element(checkbox)
            actions.pause(random.uniform(0.1, 0.3))
            actions.click()
            actions.perform()

            print("[KABUM] Filtro 'KaBuM!' aplicado")
            return "applied"

        except Exception as e:
            print(f"[KABUM] Falha ao aplicar filtro: {e}")
            return "error"

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
    # MAIN SEARCH METHOD
    # -------------------------------------------------------------------------

    def search_kabum(self, component):
        """
        Busca produto na Kabum.
        Aplica filtro 'KaBuM!' (só aceita itens vendidos pela própria Kabum).
        Retorna o mais barato com URL direta do produto.

        [MONITORING/FIX] Retorna uma tupla (status, result, meta) em vez de só o result.
        status ∈ {"found", "not_found", "error"}:
          - "found"     -> result contém os dados do produto (como antes).
          - "not_found" -> a busca rodou normalmente mas não passou nenhum candidato no
                           matching (ou não há estoque próprio da Kabum pra esse item).
                           É um miss "de negócio", conta para o streak de not-found.
          - "error"     -> falha técnica (página não carregou, exceção, timeout de
                           carregamento). NÃO conta como miss e NÃO deve resetar o
                           preço salvo — só reflete que essa tentativa específica falhou.
        meta é um dict com detalhes técnicos (error_type, uso do fallback LLM) usados
        só para as métricas de saúde da run, sem afetar a lógica de matching em si.

        [FEATURE 01/09] meta também carrega "extra_candidates": lista de até
        ALT_PRICES_PER_SITE produtos validados (mesmas regras de matching do cheapest),
        vindos direto da listagem já raspada — sem nenhuma navegação extra. Usado por
        price_scraper.py pra montar os "preços alternativos" combinados com a Amazon.
        Sempre presente (lista vazia quando não há found ou não sobrou candidato extra).
        """
        produto = component['name']
        marca = component.get('brand')
        modelo = component.get('model')
        categoria = component.get('category')
        especificacoes = component.get('specifications')

        print(f"\n[KABUM] Buscando: {produto}")
        if modelo:
            print(f"[KABUM] Modelo para validacao: {modelo}")

        meta = {"error_type": None, "llm_used": False, "llm_confirmed": False, "extra_candidates": []}

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
                    meta["error_type"] = "page_load"
                    return "error", None, meta

            # DEBUG: verificar URL final
            print(f"[KABUM DEBUG] URL apos busca: {self.driver.current_url}")

            self.human_delay(3, 5)

            # Scroll inicial para garantir que filtros e produtos carregaram
            print("[KABUM] Scroll inicial...")
            self.progressive_scroll(max_scrolls=3)

            # Aplicar filtro KaBuM! — sem filtro, não aceitamos nenhum item
            filter_status = self.click_kabum_filter()
            if filter_status == "error":
                meta["error_type"] = "filter_error"
                return "error", None, meta
            if filter_status == "not_found":
                # Sem estoque próprio da Kabum pra essa busca — miss legítimo, não erro.
                return "not_found", None, meta

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
                    return "not_found", None, meta
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
                # Nenhum candidato bruto foi listado — provável instabilidade de página/
                # seletor quebrado, não um "sem estoque" confirmado. Tratado como erro
                # técnico pra não resetar o preço salvo à toa.
                meta["error_type"] = "no_candidates"
                return "error", None, meta

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

            # 2ª passagem: filtrar por matching — sem Groq
            valid_products = []
            rejected_candidates = []

            for c in all_candidates:
                product_name = c["name"]
                if modelo:
                    if self.is_exact_product_match(product_name, modelo, marca, search_name=produto,
                                                    category=categoria, specifications=especificacoes):
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

            # Fallback Groq: só se matching normal falhou completamente
            # Produtos excluídos por keyword (kit, laptop, etc.) nunca vão ao Groq
            if not valid_products and rejected_candidates and modelo:
                groq_candidates = [
                    c for c in rejected_candidates
                    if not any(kw in c["name"].lower() for kw in EXCLUSION_KEYWORDS)
                ]
                groq_candidates.sort(key=lambda x: x["price"])
                if groq_candidates:
                    meta["llm_used"] = True
                    print(f"[KABUM] Matching normal: 0 resultados. Tentando LLM nos {min(3, len(groq_candidates))} candidatos mais baratos...")
                    for c in groq_candidates[:3]:
                        if self.ask_groq_is_match(c["name"], produto, modelo):
                            valid_products.append(c)
                            meta["llm_confirmed"] = True
                            break

            print(f"[KABUM] Produtos validos: {len(valid_products)} | Rejeitados: {len(rejected_candidates)}")

            if not valid_products:
                print("[KABUM] Produto nao encontrado")
                return "not_found", None, meta

            valid_products.sort(key=lambda x: x["price"])
            cheapest = valid_products[0]

            print(f"[KABUM] Top 3 precos encontrados:")
            for i, p in enumerate(valid_products[:3], 1):
                print(f"  {i}. R$ {p['price']:.2f} - {p['name'][:60]}...")

            # [FEATURE 01/09] Candidatos extras: próximos mais baratos depois do cheapest,
            # já validados pelo mesmo is_exact_product_match (ou já confirmados via Groq,
            # se cheapest veio do fallback — nesse caso normalmente não sobra mais nenhum,
            # já que o Groq para no primeiro confirmado). Nenhuma navegação extra: os dados
            # (nome/preço/url) já estavam em `all_candidates`, só filtramos e fatiamos.
            # shipped_by_store fica True pros extras também — o filtro "KaBuM!" já garante
            # que são vendidos pela própria Kabum, sem precisar abrir a página de cada um.
            extra = valid_products[1:1 + ALT_PRICES_PER_SITE]
            meta["extra_candidates"] = [
                {
                    "site": "kabum",
                    "produto": p["name"],
                    "preco": p["price"],
                    "url": p.get("url"),
                    "shipped_by_store": True,
                }
                for p in extra
            ]
            if meta["extra_candidates"]:
                print(f"[KABUM] Candidatos extras capturados: {len(meta['extra_candidates'])}")

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

            return "found", result, meta

        except Exception as e:
            print(f"ERRO CRITICO: Kabum - {e}")
            meta["error_type"] = "exception"
            return "error", None, meta