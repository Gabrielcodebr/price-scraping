import os

from dotenv import load_dotenv
from supabase import create_client, Client
from supabase.client import ClientOptions

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(postgrest_client_timeout=30, storage_client_timeout=30),
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


# ---------------------------------------------------------------------------
# MONITORAMENTO / ALERTAS
# ---------------------------------------------------------------------------
# [MONITORING] Thresholds definidos junto com o usuário: 80% de variação de preço é um
# chute consciente ("raro um produto ficar tão mais caro/barato do uma run pra outra,
# mesmo em Black Friday") — serve como sinalizador para revisão manual, não como
# verdade absoluta.
PRICE_CHANGE_ALERT_PCT = 80          # variação % (preço novo vs preço salvo) no mesmo site
STORE_MISMATCH_ALERT_PCT = 80        # diferença % entre Kabum e Amazon na MESMA run
NOT_FOUND_STREAK_THRESHOLD = 4       # misses consecutivos em um site -> alerta "sumindo"
DISCONTINUED_STREAK_THRESHOLD = 8    # misses consecutivos nos DOIS sites -> possível descontinuado
RUN_HEALTH_FAILURE_PCT = 30          # % de erros técnicos (captcha/filtro) na run -> alerta de saúde
ALERT_DEFAULT_EXPIRY_DAYS = 14       # expiração padrão de alertas pontuais (preço/mismatch/streak)
RUN_HEALTH_EXPIRY_DAYS = 30          # run_health é registro histórico, expira mais devagar

ALLOWED_ALERT_TYPES = {
    "price_spike", "price_drop", "store_mismatch",
    "not_found_streak", "possible_discontinued", "run_health",
}


# ---------------------------------------------------------------------------
# LIMITES DE EXECUÇÃO (entry point)
# ---------------------------------------------------------------------------
MAX_RUNTIME_MINUTES = 300  # Para dentro de 5h, deixando 1h de margem pro timeout de 6h do GitHub Actions
PER_COMPONENT_TIMEOUT_S = 300  # Watchdog: aborta se um único componente passar de 5min
