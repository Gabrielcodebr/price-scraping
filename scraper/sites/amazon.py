import random
import re
import time

from selenium.webdriver.common.by import By

from ..matching_rules import EXCLUSION_KEYWORDS


class AmazonMixin:
    """Mixin de PriceScraper: busca e extração de preços na Amazon."""

    # -------------------------------------------------------------------------
    # AMAZON helpers
    # -------------------------------------------------------------------------

    def warm_up_amazon(self):
        """
        [FIX/MITIGACAO 15/08] Visita a home da Amazon UMA VEZ por sessão de driver, antes
        da primeira busca, para estabelecer cookies/sessão básica antes de bater direto
        numa URL de busca profunda (https://www.amazon.com.br/s?k=...).

        Motivação: em runs reais foi observado que a Amazon retorna a página de erro
        "Algo deu errado" (título da página) nas primeiras buscas logo após o Chrome
        subir, normalizando depois de alguns componentes processados — em uma run por
        ~2-3 componentes, em outra por 10. Isso sugere algum tipo de checagem de
        reputação/sessão mais rígida no início.

        IMPORTANTE: isso é uma mitigação, não uma correção confirmada. O critério de
        bloqueio da Amazon é opaco e não foi possível validar contra o site real neste
        ambiente. Se o padrão persistir mesmo com o aquecimento, o problema é outra
        coisa (IP/datacenter, fingerprint do Chrome headless, etc.) e precisa de
        investigação adicional.
        """
        if self._amazon_warmed_up:
            return
        try:
            print("[AMAZON] Aquecendo sessao (visita inicial a home)...")
            self.driver.get("https://www.amazon.com.br")
            self.wait_for_page_load(timeout=20)
            self.human_delay(3, 5)
            self.close_popups()
            self.progressive_scroll(max_scrolls=2)
            self.human_delay(1, 2)
        except Exception as e:
            print(f"[AMAZON] Falha no aquecimento (nao critico, seguindo): {e}")
        finally:
            # Marca como aquecido mesmo se falhar, pra não tentar de novo a cada componente
            # e perder tempo — é best-effort, uma tentativa por sessão já é o suficiente.
            self._amazon_warmed_up = True

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
    # MAIN SEARCH METHOD
    # -------------------------------------------------------------------------

    def search_amazon(self, component):
        """
        Busca produto na Amazon.
        Entra na página do mais barato para pegar URL direta e verificar vendedor.

        [MONITORING/FIX] Mesma mudança de contrato de retorno que search_kabum:
        retorna (status, result, meta) com status ∈ {"found", "not_found", "error"}.
        CAPTCHA e falha de carregamento são tratados como "error" (não conta como miss,
        não reseta preço). Zero candidatos brutos na página também é tratado como "error"
        por segurança (pode ser instabilidade/seletor quebrado, não necessariamente "sem
        estoque"). "not_found" só é usado quando a busca rodou normalmente e o matching
        (incluindo fallback LLM) não confirmou nenhum candidato.

        [FIX 15/08] Antes de qualquer busca, garante que a sessão já foi "aquecida" com
        uma visita à home (warm_up_amazon, roda só uma vez por driver). Além disso, a
        página "Algo deu errado" (bloqueio observado em produção, especialmente nos
        primeiros componentes da run) agora é detectada explicitamente pelo título e
        tratada com retry com espera maior, em vez de cair direto em "zero candidatos"
        na primeira tentativa. O error_type fica marcado como "amazon_error_page" nesses
        casos, separado de "no_candidates"/"captcha", para facilitar diagnóstico futuro
        nas métricas de run_health.
        """
        produto = component['name']
        marca = component.get('brand')
        modelo = component.get('model')
        categoria = component.get('category')
        especificacoes = component.get('specifications')

        print(f"\n[AMAZON] Buscando: {produto}")
        if modelo:
            print(f"[AMAZON] Modelo para validacao: {modelo}")

        meta = {"error_type": None, "llm_used": False, "llm_confirmed": False}

        self.warm_up_amazon()

        try:
            search_term = f"{marca} {produto}" if marca and marca.lower() not in produto.lower() else produto

            # DEBUG: verificar termo de busca
            print(f"[AMAZON DEBUG] component['name']: '{produto}'")
            print(f"[AMAZON DEBUG] brand: '{marca}'")
            print(f"[AMAZON DEBUG] search_term final: '{search_term}'")

            search_url = f"https://www.amazon.com.br/s?k={search_term.replace(' ', '+')}&i=computers"

            # DEBUG: verificar URL construída
            print(f"[AMAZON DEBUG] URL: {search_url}")

            # [FIX 15/08] Loop de retry específico para a página de erro "Algo deu errado".
            # Antes, uma única tentativa (com no máximo um refresh se o load falhasse) e,
            # se a página "carregasse" mas fosse a de erro, o código seguia adiante,
            # não achava produtos e reportava "no_candidates" — misturando esse padrão de
            # bloqueio com outras causas de zero-candidatos no mesmo contador.
            max_load_attempts = 3
            page_ready = False

            for attempt in range(1, max_load_attempts + 1):
                self.driver.get(search_url)

                if not self.wait_for_page_load():
                    self.driver.refresh()
                    self.wait_for_page_load()

                self.close_popups()
                self.human_delay(4, 7)
                self.wait_for_page_load()

                current_title = self.driver.title
                current_title_lower = current_title.lower()

                if "algo deu errado" in current_title_lower:
                    meta["error_type"] = "amazon_error_page"
                    if attempt < max_load_attempts:
                        wait_extra = random.uniform(15, 25)
                        print(f"[AMAZON] Pagina de erro detectada (tentativa {attempt}/{max_load_attempts}) — aguardando {wait_extra:.0f}s e tentando novamente")
                        time.sleep(wait_extra)
                        continue
                    else:
                        print(f"[AMAZON] Pagina de erro persistente apos {max_load_attempts} tentativas. Titulo: {current_title}")
                        return "error", None, meta

                page_ready = True
                break

            if not page_ready:
                # Segurança: não deveria chegar aqui (o loop sempre retorna ou marca
                # page_ready), mas se chegar, trata como erro técnico sem mexer no preço.
                meta["error_type"] = meta["error_type"] or "unknown_load_failure"
                return "error", None, meta

            print("[AMAZON] Fazendo scroll progressivo...")
            self.progressive_scroll(max_scrolls=10)

            # Detectar CAPTCHA antes de tentar encontrar produtos
            page_title = self.driver.title.lower()
            if "robot" in page_title or "captcha" in page_title or "verification" in page_title:
                print(f"[AMAZON] CAPTCHA detectado! Titulo: {self.driver.title}")
                meta["error_type"] = "captcha"
                return "error", None, meta
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
                # Nenhum candidato bruto foi listado — provável instabilidade de página/
                # seletor quebrado, não um "sem estoque" confirmado. Tratado como erro
                # técnico pra não resetar o preço salvo à toa.
                meta["error_type"] = "no_candidates"
                return "error", None, meta

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

            # Fallback groq: só se matching normal falhou completamente
            # Produtos excluídos por keyword (kit, laptop, etc.) nunca vão ao Groq
            if not valid_products and rejected_candidates and modelo:
                groq_candidates = [
                    c for c in rejected_candidates
                    if not any(kw in c["name"].lower() for kw in EXCLUSION_KEYWORDS)
                ]
                groq_candidates.sort(key=lambda x: x["price"])
                if groq_candidates:
                    meta["llm_used"] = True
                    print(f"[AMAZON] Matching normal: 0 resultados. Tentando LLM nos {min(3, len(groq_candidates))} candidatos mais baratos...")
                    for c in groq_candidates[:3]:
                        if self.ask_groq_is_match(c["name"], produto, modelo):
                            valid_products.append(c)
                            meta["llm_confirmed"] = True
                            break

            print(f"[AMAZON] Produtos validos: {len(valid_products)} | Rejeitados: {len(rejected_candidates)}")

            if not valid_products:
                print("[AMAZON] Produto nao encontrado")
                return "not_found", None, meta

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

            return "found", result, meta

        except Exception as e:
            print(f"ERRO CRITICO: Amazon - {e}")
            meta["error_type"] = "exception"
            return "error", None, meta
