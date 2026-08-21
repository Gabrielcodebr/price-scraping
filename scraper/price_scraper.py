from .driver_utils import HumanBehaviorMixin
from .matching import MatchingMixin
from .sites.kabum import KabumMixin
from .sites.amazon import AmazonMixin


class PriceScraper(HumanBehaviorMixin, MatchingMixin, KabumMixin, AmazonMixin):
    """
    Web scraper para buscar preços em Kabum e Amazon com comportamento humanizado.

    A implementação está dividida em mixins (mesma classe final, só organizada em
    arquivos separados por responsabilidade):
      - HumanBehaviorMixin (driver_utils.py): setup do Chrome, mouse/digitação/scroll
        humanizados, e helpers genéricos de espera/parsing de página.
      - MatchingMixin (matching.py): validação de que um produto encontrado é o
        componente buscado (tokens, capacidades, variantes) + fallback via Groq.
      - KabumMixin (sites/kabum.py): tudo específico da busca na Kabum.
      - AmazonMixin (sites/amazon.py): tudo específico da busca na Amazon.
    """

    def __init__(self):
        self.driver = None
        self._llm_blocked_until = 0
        self._last_llm_call = 0
        # [FIX/MONITORING 15/08] Controla se já visitamos a home da Amazon nesta sessão de
        # driver (ver warm_up_amazon). Mitigação para o padrão observado em produção de
        # bloqueio ("Algo deu errado") nos primeiros componentes logo após o Chrome subir.
        self._amazon_warmed_up = False
        self.setup_driver()

    def scrape_component(self, component):
        """
        Busca preços de um componente em ambos os sites.

        [MONITORING/FIX] Retorna um dict com o status/dados/meta de cada site, sempre
        presentes (nunca um dict vazio ou None), para que update_component_prices possa
        decidir com precisão o que fazer em cada caso (found/not_found/error).
        """
        component_id = component['id']
        component_name = component['name']

        print(f"\n{'=' * 60}")
        print(f"Processando: {component_name} (ID: {component_id})")
        print(f"{'=' * 60}")

        kabum_status, kabum_data, kabum_meta = self.search_kabum(component)

        self.human_delay(5, 8)

        amazon_status, amazon_data, amazon_meta = self.search_amazon(component)

        results = {
            "kabum": {"status": kabum_status, "data": kabum_data, "meta": kabum_meta},
            "amazon": {"status": amazon_status, "data": amazon_data, "meta": amazon_meta},
        }

        print(f"\n--- Resumo: {component_name} ---")

        if kabum_status == "found":
            print(f"Kabum: R$ {kabum_data['preco']:.2f}")
        elif kabum_status == "not_found":
            print("Kabum: Nao encontrado")
        else:
            print(f"Kabum: Erro tecnico ({kabum_meta.get('error_type')}) — preco anterior mantido")

        if amazon_status == "found":
            shipped = amazon_data.get('shipped_by_store')
            shipped_label = {True: "(Amazon)", False: "(Externo)", None: "(indefinido)"}.get(shipped, "")
            print(f"Amazon: R$ {amazon_data['preco']:.2f} {shipped_label}")
        elif amazon_status == "not_found":
            print("Amazon: Nao encontrado")
        else:
            print(f"Amazon: Erro tecnico ({amazon_meta.get('error_type')}) — preco anterior mantido")

        valid_prices = []
        if kabum_status == "found":
            valid_prices.append(('kabum', kabum_data['preco']))
        if amazon_status == "found":
            valid_prices.append(('amazon', amazon_data['preco']))

        if valid_prices:
            best_site, best_price = min(valid_prices, key=lambda x: x[1])
            print(f"Melhor preco (nesta run): {best_site.upper()} - R$ {best_price:.2f}")
        else:
            print("Nenhum preco encontrado nesta run")

        print(f"{'=' * 60}\n")

        return results

    def close(self):
        """Fecha o driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
