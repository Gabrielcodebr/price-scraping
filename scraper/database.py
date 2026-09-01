import time

from .config import (
    supabase,
    PRICE_CHANGE_ALERT_PCT,
    STORE_MISMATCH_ALERT_PCT,
    NOT_FOUND_STREAK_THRESHOLD,
    DISCONTINUED_STREAK_THRESHOLD,
)
from .alerts import create_alert, upsert_streak_alert, resolve_streak_alert_if_open

# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------


def update_component_prices(component, results):
    """
    Atualiza preços do componente no Supabase, com base no status found/not_found/error
    retornado por cada site nesta run, e dispara os alertas de monitoramento cabíveis.

    [MONITORING/FIX] Esta é a correção central pedida: antes, QUALQUER falha (erro,
    timeout, exceção) resetava best_price inteiro pra null, apagando o último preço bom
    mesmo quando a causa era um problema transitório. Agora:
      - "found"     -> atualiza preço/url/found normalmente, zera o streak de misses.
      - "not_found" -> reseta found/preço/url daquele site (comportamento visível ao app
                       continua igual ao de hoje) e incrementa o streak de misses.
      - "error"     -> NÃO mexe em nada do preço/url/found/misses daquele site. A run
                       falhou tecnicamente, não o produto sumiu.
    """
    component_id = component['id']
    previous = component.get('best_price') or {}
    prev_kabum = previous.get('kabum') or {}
    prev_amazon = previous.get('amazon') or {}
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if not results:
        # Defensivo: nunca deveria acontecer (main() sempre monta um results bem-formado),
        # mas se acontecer, trata como erro nos dois sites — não mexe em nada.
        results = {
            "kabum": {"status": "error", "data": None, "meta": {"error_type": "missing_results"}},
            "amazon": {"status": "error", "data": None, "meta": {"error_type": "missing_results"}},
        }

    new_best_price = {
        "best": {"url": None, "price": None, "store": None, "shipped_by_store": None},
        "kabum": dict(prev_kabum) if prev_kabum else {"url": None, "found": False, "price": None, "shipped_by_store": None},
        "amazon": dict(prev_amazon) if prev_amazon else {"url": None, "found": False, "price": None, "shipped_by_store": None},
        "updated_at": timestamp,
    }
    # Garante presença das chaves de streak mesmo em best_price antigos (pré-migração)
    for site_key in ("kabum", "amazon"):
        new_best_price[site_key].setdefault("consecutive_misses", 0)
        new_best_price[site_key].setdefault("last_found_at", None)

    site_prices_this_run = {}

    for site in ("kabum", "amazon"):
        site_result = results.get(site) or {"status": "error", "data": None, "meta": {}}
        status = site_result.get("status", "error")
        data = site_result.get("data")
        site_state = new_best_price[site]
        previous_price = site_state.get("price")

        if status == "found" and data:
            new_price = data["preco"]
            site_state["found"] = True
            site_state["price"] = new_price
            site_state["url"] = data.get("url")
            site_state["shipped_by_store"] = data.get("shipped_by_store")
            site_state["consecutive_misses"] = 0
            site_state["last_found_at"] = timestamp
            site_prices_this_run[site] = {"price": new_price, "produto": data.get("produto")}

            # Alerta de variação de preço vs a última leitura conhecida daquele site
            if previous_price is not None and previous_price > 0:
                pct_change = ((new_price - previous_price) / previous_price) * 100
                if abs(pct_change) >= PRICE_CHANGE_ALERT_PCT:
                    alert_type = "price_spike" if pct_change > 0 else "price_drop"
                    create_alert(component_id, alert_type, site, {
                        "preco_anterior": previous_price,
                        "preco_novo": new_price,
                        "variacao_pct": round(pct_change, 1),
                        "produto": data.get("produto"),
                        "url": data.get("url"),
                    })

            # Voltou a achar — resolve eventual alerta de streak aberto nesse site
            resolve_streak_alert_if_open(component_id, "not_found_streak", site)

        elif status == "not_found":
            site_state["found"] = False
            site_state["price"] = None
            site_state["url"] = None
            site_state["shipped_by_store"] = None
            site_state["consecutive_misses"] = (site_state.get("consecutive_misses") or 0) + 1
            # last_found_at permanece com o valor anterior — não mexe

            if site_state["consecutive_misses"] >= NOT_FOUND_STREAK_THRESHOLD:
                upsert_streak_alert(component_id, "not_found_streak", site, {
                    "consecutive_misses": site_state["consecutive_misses"],
                    "last_found_at": site_state.get("last_found_at"),
                })

        else:
            # status == "error" — não mexe em preço/url/found/misses daquele site.
            pass

    # Alerta de possível descontinuado — misses altos nos DOIS sites ao mesmo tempo.
    # Exige os dois simultâneos porque um miss isolado de um site costuma ser problema
    # de matching daquele site específico, não o produto ter saído de linha de verdade.
    kabum_misses = new_best_price["kabum"].get("consecutive_misses") or 0
    amazon_misses = new_best_price["amazon"].get("consecutive_misses") or 0
    if kabum_misses >= DISCONTINUED_STREAK_THRESHOLD and amazon_misses >= DISCONTINUED_STREAK_THRESHOLD:
        upsert_streak_alert(component_id, "possible_discontinued", None, {
            "kabum_consecutive_misses": kabum_misses,
            "amazon_consecutive_misses": amazon_misses,
        })
    else:
        resolve_streak_alert_if_open(component_id, "possible_discontinued", None)

    # Alerta de divergência entre lojas na MESMA run — sinal de possível erro de matching
    # (ex: um site pegou a versão 8GB e o outro a versão 12GB do mesmo modelo de GPU).
    if "kabum" in site_prices_this_run and "amazon" in site_prices_this_run:
        k_price = site_prices_this_run["kabum"]["price"]
        a_price = site_prices_this_run["amazon"]["price"]
        menor = min(k_price, a_price)
        if menor > 0:
            pct_diff = abs(k_price - a_price) / menor * 100
            if pct_diff >= STORE_MISMATCH_ALERT_PCT:
                create_alert(component_id, "store_mismatch", None, {
                    "preco_kabum": k_price,
                    "preco_amazon": a_price,
                    "variacao_pct": round(pct_diff, 1),
                    "produto_kabum": site_prices_this_run["kabum"]["produto"],
                    "produto_amazon": site_prices_this_run["amazon"]["produto"],
                })

    # Determinar melhor preço entre os encontrados nesta consolidação
    candidates = []
    for site in ("kabum", "amazon"):
        if new_best_price[site]["found"] and new_best_price[site]["price"]:
            candidates.append((site, new_best_price[site]["price"]))

    if candidates:
        best_site, best_price = min(candidates, key=lambda x: x[1])
        new_best_price["best"] = {
            "url": new_best_price[best_site]["url"],
            "price": best_price,
            "store": best_site,
            "shipped_by_store": new_best_price[best_site]["shipped_by_store"],
        }

    try:
        response = supabase.table("components").update({
            "best_price": new_best_price
        }).eq("id", component_id).execute()

        if response.data:
            return True
        else:
            print(f"ERRO: Falha ao atualizar componente {component_id} no banco")
            return False

    except Exception as e:
        print(f"ERRO CRITICO: Falha ao atualizar Supabase - {e}")
        return False


def update_component_alt_prices(component_id, alt_prices, kabum_status, amazon_status):
    """
    [FEATURE 01/09] Atualiza a tabela component_alt_prices com os preços alternativos
    (até 5, combinados Kabum+Amazon) capturados nesta run — direto da listagem, sem abrir
    página individual (ver extra_candidates em sites/kabum.py e sites/amazon.py, e a
    combinação em PriceScraper.scrape_component).

    É um SNAPSHOT, não histórico: o array inteiro é sobrescrito a cada run (por isso
    upsert simples, sem lógica de streak/alerta como em update_component_prices).

    IMPORTANTE — mesma cautela do fix central de update_component_prices: se os DOIS
    sites falharam tecnicamente nesta run (kabum_status == amazon_status == "error"),
    NÃO sobrescreve nada. alt_prices só é populado dentro de search_kabum/search_amazon
    no caminho "found" — se os dois deram erro técnico, um alt_prices vazio aqui não
    significa "não há mais opções de preço", significa "a run não conseguiu nem tentar".
    Sobrescrever com [] nesse cenário apagaria dados válidos de runs anteriores à toa,
    o mesmo problema que motivou reescrever update_component_prices. Nos demais casos
    (found/not_found, mesmo que só um dos dois sites tenha funcionado) o array É
    sobrescrito normalmente, inclusive quando fica vazio de propósito (matching rodou
    certinho mas não sobrou candidato extra além do principal).
    """
    if kabum_status == "error" and amazon_status == "error":
        print(f"[ALT_PRICES] Kabum e Amazon falharam tecnicamente — mantendo alt_prices anterior de {component_id}")
        return True  # não é falha da operação, é decisão de não mexer

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    try:
        response = supabase.table("component_alt_prices").upsert({
            "component_id": component_id,
            "alt_prices": alt_prices,
            "updated_at": timestamp,
        }, on_conflict="component_id").execute()

        if response.data:
            return True
        else:
            print(f"ERRO: Falha ao atualizar alt_prices do componente {component_id}")
            return False

    except Exception as e:
        print(f"ERRO CRITICO: Falha ao atualizar component_alt_prices - {e}")
        return False