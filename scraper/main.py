import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout

from .config import supabase, MAX_RUNTIME_MINUTES, PER_COMPONENT_TIMEOUT_S
from .price_scraper import PriceScraper
from .database import update_component_prices
from .alerts import record_run_health

# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------


def _build_error_results(error_type):
    """
    [MONITORING/FIX] Monta um results bem-formado (ambos os sites como 'error') para os
    casos em que scrape_component nem chegou a rodar de verdade (watchdog timeout ou
    exceção inesperada no wrapper). Antes, esses casos viravam None e resetavam o
    best_price inteiro — agora são tratados como erro técnico, sem mexer no preço salvo.
    """
    meta = {"error_type": error_type, "llm_used": False, "llm_confirmed": False}
    return {
        "kabum": {"status": "error", "data": None, "meta": dict(meta)},
        "amazon": {"status": "error", "data": None, "meta": dict(meta)},
    }


def _accumulate_stats(stats, results):
    """
    [MONITORING] Acumula métricas de saúde da run a partir do results de um componente.

    [FIX 15/08] Passa a contar separadamente amazon_error_page_count (bloqueio "Algo deu
    errado"), antes misturado dentro de amazon_error_count genérico.
    """
    kabum = results.get("kabum") or {}
    amazon = results.get("amazon") or {}
    kabum_meta = kabum.get("meta") or {}
    amazon_meta = amazon.get("meta") or {}

    if kabum.get("status") == "error":
        stats["kabum_error_count"] += 1
    if amazon.get("status") == "error":
        stats["amazon_error_count"] += 1
    if amazon_meta.get("error_type") == "captcha":
        stats["amazon_captcha_count"] += 1
    if amazon_meta.get("error_type") == "amazon_error_page":
        stats["amazon_error_page_count"] += 1

    for meta in (kabum_meta, amazon_meta):
        if meta.get("llm_used"):
            stats["llm_fallback_attempts"] += 1
            if meta.get("llm_confirmed"):
                stats["llm_fallback_confirmed"] += 1


def main():
    print("=" * 60)
    print("Price Scraper - Kabum & Amazon")
    print("=" * 60)

    scraper = PriceScraper()

    if not scraper.driver:
        print("ERRO CRITICO: Driver nao inicializado")
        print("Verifique instalacao do Chrome/ChromeDriver")
        return

    start_time = time.time()

    # [MONITORING] Estatisticas da run inteira, usadas pra registrar o alerta run_health
    # no final (captcha, falhas tecnicas, cortes por tempo, taxa de confirmacao do LLM).
    # [FIX 15/08] amazon_error_page_count adicionado (ver _accumulate_stats/record_run_health).
    stats = {
        "total_attempted": 0,
        "kabum_error_count": 0,
        "amazon_error_count": 0,
        "amazon_captcha_count": 0,
        "amazon_error_page_count": 0,
        "llm_fallback_attempts": 0,
        "llm_fallback_confirmed": 0,
        "deferred_count": 0,
        "cut_short_by_time_limit": False,
        "elapsed_minutes": 0,
    }

    try:
        # Ordena pelos mais antigos primeiro — nunca atualizados (null) têm prioridade máxima
        response = (
            supabase.table("components")
            .select("*")
            .order("best_price->>updated_at", desc=False, nullsfirst=True)
            .execute()
        )
        components = response.data

        if not components:
            print("Nenhum componente encontrado no banco")
            return

        print(f"\nTotal de componentes: {len(components)}\n")

        for i, component in enumerate(components, 1):
            elapsed = (time.time() - start_time) / 60
            remaining = MAX_RUNTIME_MINUTES - elapsed

            if remaining < 5:
                stats["cut_short_by_time_limit"] = True
                stats["deferred_count"] = len(components) - (i - 1)
                print(f"\n⏰ Limite de tempo atingido ({elapsed:.0f}min). Processados {i - 1}/{len(components)} componentes.")
                print("Os componentes restantes serao priorizados na proxima execucao.")
                break

            print(f"\n[{i}/{len(components)}] | Tempo decorrido: {elapsed:.0f}min | Restante: {remaining:.0f}min")

            try:
                with ThreadPoolExecutor(max_workers=1) as ex:
                    results = ex.submit(scraper.scrape_component, component).result(
                        timeout=PER_COMPONENT_TIMEOUT_S
                    )
            except FutTimeout:
                print(f"[WATCHDOG] Componente {component.get('id')} excedeu {PER_COMPONENT_TIMEOUT_S}s — pulando")
                results = _build_error_results("watchdog_timeout")
            except Exception as e:
                print(f"[WATCHDOG] Erro inesperado em scrape_component: {e}")
                results = _build_error_results("unexpected_exception")

            stats["total_attempted"] += 1
            _accumulate_stats(stats, results)

            # Sempre atualiza — found/not_found/error tratados corretamente por site
            update_component_prices(component, results)

            if i < len(components):
                delay = random.uniform(8, 15)
                print(f"Aguardando {delay:.1f}s...\n")
                time.sleep(delay)

        else:
            print("\n" + "=" * 60)
            print("Scraping concluido")
            print("=" * 60)

    except Exception as e:
        print(f"ERRO CRITICO: Falha ao buscar componentes - {e}")

    finally:
        stats["elapsed_minutes"] = (time.time() - start_time) / 60
        if stats["total_attempted"] > 0:
            record_run_health(stats)
        scraper.close()
