import time

from .config import (
    supabase,
    ALLOWED_ALERT_TYPES,
    ALERT_DEFAULT_EXPIRY_DAYS,
    RUN_HEALTH_EXPIRY_DAYS,
    RUN_HEALTH_FAILURE_PCT,
)

# ---------------------------------------------------------------------------
# ALERTAS (scraper_alerts)
# ---------------------------------------------------------------------------
# [MONITORING] Helpers isolados do restante do scraping — só lidam com criar/atualizar/
# resolver linhas em scraper_alerts. Nunca deletam nem descontinuam nada sozinhos; só
# sinalizam para revisão manual no painel admin.


def create_alert(component_id, alert_type, site, details, expires_days=ALERT_DEFAULT_EXPIRY_DAYS):
    """Cria um novo alerta pontual (preço, mismatch entre lojas, etc)."""
    if alert_type not in ALLOWED_ALERT_TYPES:
        print(f"[ALERT] Tipo invalido ignorado: {alert_type}")
        return None
    try:
        expires_at = None
        if expires_days:
            expires_at = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(time.time() + expires_days * 86400)
            )
        payload = {
            "component_id": component_id,
            "type": alert_type,
            "site": site,
            "details": details,
            "expires_at": expires_at,
        }
        response = supabase.table("scraper_alerts").insert(payload).execute()
        print(f"[ALERT] Criado: {alert_type} | site={site} | component={component_id}")
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"[ALERT] Falha ao criar alerta: {e}")
        return None


def get_open_alert(component_id, alert_type, site):
    """Busca um alerta não resolvido existente para (component_id, type, site)."""
    try:
        query = (
            supabase.table("scraper_alerts")
            .select("*")
            .eq("type", alert_type)
            .eq("resolved", False)
        )
        if component_id is None:
            query = query.is_("component_id", "null")
        else:
            query = query.eq("component_id", component_id)
        if site is None:
            query = query.is_("site", "null")
        else:
            query = query.eq("site", site)
        response = query.limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"[ALERT] Falha ao buscar alerta aberto: {e}")
        return None


def upsert_streak_alert(component_id, alert_type, site, details, expires_days=ALERT_DEFAULT_EXPIRY_DAYS):
    """
    Cria um alerta de streak (not_found_streak / possible_discontinued) ou, se já existir
    um aberto para o mesmo (component_id, type, site), só atualiza os detalhes — evita
    spam de alertas duplicados a cada run enquanto a condição persistir.
    """
    existing = get_open_alert(component_id, alert_type, site)
    if existing:
        try:
            expires_at = None
            if expires_days:
                expires_at = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(time.time() + expires_days * 86400)
                )
            supabase.table("scraper_alerts").update({
                "details": details,
                "expires_at": expires_at,
            }).eq("id", existing["id"]).execute()
        except Exception as e:
            print(f"[ALERT] Falha ao atualizar alerta existente: {e}")
        return existing["id"]
    else:
        created = create_alert(component_id, alert_type, site, details, expires_days)
        return created["id"] if created else None


def resolve_streak_alert_if_open(component_id, alert_type, site):
    """Marca como resolvido um alerta de streak quando a condição que o gerou já passou."""
    existing = get_open_alert(component_id, alert_type, site)
    if existing:
        try:
            resolved_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            supabase.table("scraper_alerts").update({
                "resolved": True,
                "resolved_at": resolved_ts,
            }).eq("id", existing["id"]).execute()
            print(f"[ALERT] Resolvido automaticamente: {alert_type} | site={site} | component={component_id}")
        except Exception as e:
            print(f"[ALERT] Falha ao resolver alerta: {e}")


def record_run_health(stats):
    """
    [MONITORING] Registra um snapshot de saúde da run atual. Sempre grava (mesmo em runs
    saudáveis), pra dar histórico contínuo no painel admin; runs saudáveis já nascem
    resolved=True (não poluem a lista de "precisa de atenção"), runs problemáticas ficam
    resolved=False até alguém revisar.

    [FIX 15/08] Adicionado amazon_error_page_pct (páginas "Algo deu errado" da Amazon,
    tipicamente vistas no início da run) como sinal separado de amazon_error_pct genérico,
    pra dar visibilidade específica desse padrão de bloqueio no aquecimento do driver.
    Ele também entra no cálculo de "problematic", no mesmo espírito do captcha_pct.
    """
    total = stats["total_attempted"] or 1
    captcha_pct = (stats["amazon_captcha_count"] / total) * 100
    amazon_error_page_pct = (stats["amazon_error_page_count"] / total) * 100
    kabum_error_pct = (stats["kabum_error_count"] / total) * 100
    amazon_error_pct = (stats["amazon_error_count"] / total) * 100

    problematic = (
        captcha_pct >= RUN_HEALTH_FAILURE_PCT
        or amazon_error_page_pct >= RUN_HEALTH_FAILURE_PCT
        or kabum_error_pct >= RUN_HEALTH_FAILURE_PCT
        or amazon_error_pct >= RUN_HEALTH_FAILURE_PCT
        or stats["cut_short_by_time_limit"]
    )

    llm_confirm_rate = None
    if stats["llm_fallback_attempts"] > 0:
        llm_confirm_rate = round(
            (stats["llm_fallback_confirmed"] / stats["llm_fallback_attempts"]) * 100, 1
        )

    details = {
        "total_componentes_tentados": stats["total_attempted"],
        "componentes_pendentes_por_tempo": stats["deferred_count"],
        "run_cortada_por_tempo": stats["cut_short_by_time_limit"],
        "amazon_captcha_pct": round(captcha_pct, 1),
        "amazon_error_page_pct": round(amazon_error_page_pct, 1),
        "kabum_error_pct": round(kabum_error_pct, 1),
        "amazon_error_pct": round(amazon_error_pct, 1),
        "llm_fallback_attempts": stats["llm_fallback_attempts"],
        "llm_fallback_confirm_rate_pct": llm_confirm_rate,
        "duracao_minutos": round(stats["elapsed_minutes"], 1),
    }

    try:
        expires_at = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + RUN_HEALTH_EXPIRY_DAYS * 86400)
        )
        resolved = not problematic
        supabase.table("scraper_alerts").insert({
            "component_id": None,
            "type": "run_health",
            "site": None,
            "details": details,
            "resolved": resolved,
            "resolved_at": None if problematic else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "expires_at": expires_at,
        }).execute()
        print(f"[RUN HEALTH] Registrado (problematico={problematic}): {details}")
    except Exception as e:
        print(f"[RUN HEALTH] Falha ao registrar: {e}")
