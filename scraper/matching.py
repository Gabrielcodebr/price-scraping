import re
import time

import requests

from .config import GROQ_API_KEY
from .matching_rules import (
    EXCLUSION_KEYWORDS,
    VARIANT_SUFFIXES,
    GENERIC_WORDS,
    CHIP_MANUFACTURERS,
    KNOWN_STORAGE_CAPACITIES_GB,
    KNOWN_VRAM_CAPACITIES_GB,
    FULL_PC_LEADING_WORDS,
)


class MatchingMixin:
    """
    Mixin de PriceScraper: tudo relacionado a decidir se um produto encontrado na loja
    é de fato o componente buscado (extração de tokens/capacidades/variantes, validação
    principal em is_exact_product_match, e o fallback via LLM em ask_groq_is_match).
    """

    def ask_groq_is_match(self, product_name, component_name, model):
        """
        Usa Groq (openai/gpt-oss-120b) como segunda opinião quando is_exact_product_match rejeita.
        Retorna True se o LLM confirma que é o mesmo produto, False caso contrário
        ou em caso de erro.

        Free tier Groq p/ gpt-oss-120b: 30 RPM, 1.000 RPD, 8.000 TPM, 200.000 TPD.
        gpt-oss-120b é um modelo de raciocínio: reasoning_effort="low" mantém custo/latência
        baixos, e reasoning_format="hidden" garante que 'content' venha só com a resposta
        final (sem isso, o texto de raciocínio viria junto e quebraria o parsing de SIM/NÃO).
        Por consumir mais tokens por chamada que o modelo antigo (llama-3.3-70b-versatile,
        descontinuado pelo Groq em 16/08/2026), o TPM (8.000/min) tende a ser o limite mais
        provável de bater antes do RPM — daí o intervalo de 2.5s abaixo (era 2s).
        """
        if not GROQ_API_KEY:
            return False

        # Cooldown de segurança após 429 (60s)
        if time.time() < self._llm_blocked_until:
            remaining = int(self._llm_blocked_until - time.time())
            print(f"[LLM] Cooldown ativo — {remaining}s restantes")
            return False

        # Rate limiter proativo: intervalo mínimo de 2.5s entre chamadas.
        if self._last_llm_call > 0:
            elapsed = time.time() - self._last_llm_call
            if elapsed < 2.5:
                wait = 2.5 - elapsed
                print(f"[LLM] Rate limiter — aguardando {wait:.1f}s")
                time.sleep(wait)

        prompt = (
            f'Você é especialista em hardware de computador. '
            f'Decida se estes dois itens são EXATAMENTE o mesmo produto.\n\n'
            f'Produto buscado: "{component_name}" (modelo: {model})\n'
            f'Produto encontrado na loja: "{product_name}"\n\n'
            f'REGRAS OBRIGATÓRIAS — responda NÃO se qualquer uma for verdade:\n'
            f'- As marcas são diferentes (ex: XPG vs C3Tech, Corsair vs Redragon)\n'
            f'- O modelo é diferente (ex: Pylon vs Kyber, Core Reactor vs PS-G850)\n'
            f'- É apenas um produto similar da mesma categoria (ex: outra fonte 550W)\n\n'
            f'Responda APENAS com SIM ou NÃO, sem mais texto.\n'
            f'SIM = definitivamente o mesmo produto, com nome abreviado ou variante\n'
            f'NÃO = produto diferente, marca diferente, ou modelo diferente'
        )

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": 500,
            "temperature": 0,
            "reasoning_effort": "low",
            "reasoning_format": "hidden",
        }

        self._last_llm_call = time.time()

        try:
            response = requests.post(url, json=body, headers=headers, timeout=10)

            if response.status_code == 429:
                self._llm_blocked_until = time.time() + 60
                print(f"[LLM] Rate limit (429) — cooldown de 60s ativado")
                return False

            response.raise_for_status()

            answer = (
                response.json()
                ["choices"][0]["message"]["content"]
                .strip()
                .upper()
            )
            result = answer.startswith("SIM")
            print(f"[LLM] '{product_name[:60]}' → {answer} (match={result})")
            return result

        except Exception as e:
            print(f"[LLM] Erro na validacao: {e}")
            return False

    def extract_ddr_type(self, text):
        """Extrai tipo DDR do texto (ddr3, ddr4, ddr5). Usado para evitar confundir gerações."""
        if not text:
            return None
        match = re.search(r'\bddr(\d)\b', text.lower())
        return f"ddr{match.group(1)}" if match else None

    def extract_storage_capacity(self, text, extra_known_capacities=None):
        """
        Extrai capacidade de armazenamento (ou VRAM, via extra_known_capacities) do texto.
        Retorna valor normalizado em GB.

        extra_known_capacities: safelist adicional (set) para o fallback sem "B" final,
        usada por is_exact_product_match para GPUs (KNOWN_VRAM_CAPACITIES_GB), já que a
        safelist padrão (KNOWN_STORAGE_CAPACITIES_GB) foi pensada para SSD/HD e não cobre
        capacidades típicas de VRAM.
        """
        if not text:
            return None

        text_lower = text.lower()
        match = re.search(r'(\d+)\s*(tb|gb)', text_lower)

        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if unit == 'tb':
                return value * 1024
            return value

        # [FIX] Fallback para capacidade escrita sem o "B" final (ex: "SA400S37/480G").
        # Restrito à safelist KNOWN_STORAGE_CAPACITIES_GB (mais extra_known_capacities,
        # quando fornecida) pra não confundir com sufixos de modelo de CPU/GPU que também
        # terminam em G (ex: Ryzen "5700G") e não têm nada a ver com armazenamento.
        fallback_match = re.search(r'(\d+)\s*g\b', text_lower)
        if fallback_match:
            value = int(fallback_match.group(1))
            allowed_capacities = KNOWN_STORAGE_CAPACITIES_GB
            if extra_known_capacities:
                allowed_capacities = allowed_capacities | extra_known_capacities
            if value in allowed_capacities:
                return value

        return None

    def extract_gpu_vram(self, specifications):
        """
        [MONITORING/FIX] Extrai a VRAM de referência (em GB) do campo specifications.memory
        de um componente GPU (ex: "16GB GDDR6" -> 16). Usado só para categoria GPU, pois
        o model/name de uma GPU normalmente NÃO diz a capacidade (ex: "GeForce RTX 3060"
        não diz se é a versão 8GB ou 12GB — são produtos diferentes). Sem isso, o matching
        aceitava qualquer capacidade de VRAM como se fosse o mesmo produto.
        """
        if not specifications:
            return None
        memory_str = specifications.get('memory')
        if not memory_str:
            return None
        return self.extract_storage_capacity(memory_str)

    def extract_key_tokens(self, text):
        """Extrai tokens-chave de um texto (números e códigos alfanuméricos importantes)."""
        if not text:
            return []

        text_lower = text.lower()
        # [FIX] Separar tokens também por hífen, não só por espaço. Sem isso, algo como
        # "Core Ultra 7-265KF" virava um token só ("7265kf", hífen sem espaço ao redor
        # grudava o "7" com "265kf"), escondendo o sufixo "F" das checagens de variante
        # e deixando 265KF passar como se fosse o 265K buscado.
        tokens = re.split(r'[\s\-]+', text_lower)

        key_tokens = []
        for token in tokens:
            # [FIX Bug#2] Remover TODOS os caracteres não-alfanuméricos (não apenas - e _).
            # Evita que pontuação residual (vírgulas, barras de SKU como "SA400S37/240G")
            # crie tokens sujos que causam falsos positivos na checagem de variantes.
            normalized_token = re.sub(r'[^a-z0-9]', '', token)

            if not normalized_token:
                continue

            # Ignorar tokens muito curtos (1 char) e palavras genéricas
            if len(normalized_token) < 2:
                continue

            if normalized_token in GENERIC_WORDS:
                continue

            # Manter qualquer token que não seja genérico:
            # - com dígitos: "9070", "265k", "32gb"
            # - sufixos de variante: "xt", "ti", "kf"
            # - tokens curtos significativos: "ii", "wifi", "ax", "itx", "atx"
            # - códigos alfanuméricos longos: "b550mplus", "rmwafbargb"
            key_tokens.append(normalized_token)

        return key_tokens

    def is_exact_product_match(self, product_name, search_model, search_brand=None,
                                search_name=None, category=None, specifications=None):
        """
        Valida se o produto encontrado corresponde exatamente ao modelo buscado.

        Args:
            product_name: Nome do produto encontrado na loja.
            search_model: Modelo sendo buscado (campo 'model' do componente).
            search_brand: Marca do componente (campo 'brand').
            search_name: Nome completo do componente (campo 'name'), usado como
                         fallback para extrair capacidade de armazenamento quando
                         o model não contém essa informação (Bug#3).
            category: Categoria do componente (campo 'category'). Usado para ativar a
                      checagem de VRAM em GPUs e para pular a checagem de PC completo
                      em CASE (Bug#6).
            specifications: Dict de especificações do componente (campo 'specifications').
                             Usado para extrair a VRAM de referência em GPUs.
        """
        if not product_name or not search_model:
            return False

        product_name_lower = product_name.lower()

        for keyword in EXCLUSION_KEYWORDS:
            if keyword in product_name_lower:
                print(f"  [MATCH] REJEITADO (exclusion '{keyword}'): {product_name[:80]}")
                return False

        # [FIX 02/09] PC completo anunciado como "Computador/PC/Desktop <linha> - <specs
        # internas>" (ex: "Computador BluePC Pro X - Intel Core i5 12400F, 32GB DDR5...").
        # A marca/modelo do componente buscado não fica adjacente à palavra "Computador"/
        # "PC" no título (o nome da linha do PC fica no meio), então nenhuma frase de
        # EXCLUSION_KEYWORDS acima bate. Como nenhum componente avulso vendido nas lojas
        # tem título começando com essas palavras (sempre começam com marca/modelo próprio),
        # checar pela PRIMEIRA palavra do título resolve sem depender de adjacência.
        # Pulada inteira para category == 'CASE': gabinetes legitimamente têm títulos como
        # "PC Case ..." (Bug#6), e ali 'pc' não indica um sistema completo.
        if category != 'CASE':
            stripped = product_name_lower.strip()
            first_word = stripped.split(maxsplit=1)[0].rstrip(':.,-') if stripped else ''
            if first_word in FULL_PC_LEADING_WORDS:
                print(f"  [MATCH] REJEITADO (PC completo, titulo inicia com '{first_word}'): {product_name[:80]}")
                return False

        search_tokens = self.extract_key_tokens(search_model)
        product_tokens = self.extract_key_tokens(product_name)

        if not search_tokens:
            return search_model.lower() in product_name_lower

        # [FIX Bug#11] Rejeitar acessórios de compatibilidade: produtos onde TODOS os tokens
        # do modelo buscado aparecem apenas após "para " no título (seção de lista de
        # compatibilidade), e não antes. Evita casos como:
        #   "Antena WiFi para MSI MAG Z890 Tomahawk"
        #   "Módulo TPM 2.0 para Gigabyte H610M H DDR4"
        #   "Cabo PCIE para Corsair HX1200"
        if ' para ' in product_name_lower:
            first_para_idx = product_name_lower.index(' para ')
            tokens_before_para = self.extract_key_tokens(product_name_lower[:first_para_idx])

            # [FIX 01/09] Bug real observado em produção: buscando "MSI MAG Z890 TOMAHAWK
            # WIFI" (variante COM wifi da placa, "wifi" é token legítimo do modelo), passou
            # uma "Antena WiFi 7 ... para MSI MAG X870 ... Z890 ... TOMAHAWK ...". A checagem
            # original aceitava se QUALQUER token do modelo buscado aparecesse antes do
            # "para" — e "wifi" batia por coincidência (a antena é "WiFi", não a placa),
            # derrubando essa proteção mesmo o produto sendo claramente um acessório
            # genérico pra várias placas.
            #
            # Fix: priorizar tokens com dígito (ex: "z890") nessa checagem — são
            # identificadores de modelo muito mais confiáveis do que palavras descritivas
            # sem dígito ("wifi", "tomahawk", etc.), que podem aparecer à toa na descrição
            # do PRÓPRIO acessório. Só cai no fallback de checar todos os tokens se o
            # modelo buscado não tiver nenhum token numérico (ex: modelo só com nome,
            # tipo "Vengeance" sem código).
            search_tokens_with_digit = [t for t in search_tokens if re.search(r'\d', t)]
            tokens_to_check = search_tokens_with_digit if search_tokens_with_digit else search_tokens

            if not any(t in tokens_before_para for t in tokens_to_check):
                print(f"  [MATCH] REJEITADO (tokens só após 'para' - acessório): {product_name[:80]}")
                return False

        product_name_normalized = product_name_lower.replace('-', '').replace('_', '')

        for token in search_tokens:
            if token not in product_name_normalized:
                print(f"  [MATCH] REJEITADO (token '{token}' ausente): {product_name[:80]}")
                return False

        search_variants = [t for t in search_tokens if t in VARIANT_SUFFIXES]

        # Verificar variantes apenas quando aparecem ADJACENTES a tokens numéricos do modelo.
        # Ex: rejeita "7600 xt" mas aceita "7600, 5.1GHz Max Turbo" (Max não é variante do modelo)
        search_numeric_for_variants = [t for t in search_tokens if re.search(r'\d', t)]

        for variant in VARIANT_SUFFIXES:
            if variant in search_variants:
                continue  # Variante faz parte da busca, ok

            # Verificar se a variante aparece colada ou logo após algum número do modelo
            for num in search_numeric_for_variants:
                # Padrões: "7600xt", "7600 xt", "7600-xt"
                pattern = re.compile(r'\b' + re.escape(num) + r'[\s\-]?' + re.escape(variant) + r'\b')
                if pattern.search(product_name_normalized):
                    print(f"  [MATCH] REJEITADO (variante '{num}+{variant}'): {product_name[:80]}")
                    return False

        search_numeric = [t for t in search_tokens if re.search(r'\d', t)]
        product_numeric = [t for t in product_tokens if re.search(r'\d', t)]

        for search_num in search_numeric:
            found_match = False
            for prod_num in product_numeric:
                if search_num == prod_num:
                    found_match = True
                    break
                if prod_num.startswith(search_num) and len(prod_num) > len(search_num):
                    suffix = prod_num[len(search_num):]
                    if suffix in VARIANT_SUFFIXES:
                        # [FIX] Se o sufixo colado no número já é a variante buscada
                        # (ex: busca "9070 XT" e o anúncio escreve "9070XT" sem espaço),
                        # não é produto diferente — é o mesmo, só sem espaço no título.
                        if suffix in search_variants:
                            found_match = True
                            break
                        print(f"  [MATCH] REJEITADO (variante numerica '{prod_num}' != '{search_num}'): {product_name[:80]}")
                        return False

            if not found_match:
                if search_num not in product_name_normalized:
                    print(f"  [MATCH] REJEITADO (num '{search_num}' ausente): {product_name[:80]}")
                    return False

                # [FIX Bug#2] Usar word boundary (\b) em vez de substring simples (`in`).
                # Evita que códigos de peça como "SA400S37" sejam interpretados como
                # variante "A400S" do modelo "A400".
                for variant in VARIANT_SUFFIXES:
                    variant_pattern = re.compile(
                        r'\b' + re.escape(search_num) + re.escape(variant) + r'\b'
                    )
                    if variant_pattern.search(product_name_normalized):
                        if variant not in [t for t in search_tokens if t in VARIANT_SUFFIXES]:
                            print(f"  [MATCH] REJEITADO (variante word-boundary '{search_num}+{variant}'): {product_name[:80]}")
                            return False

        # [FIX Bug#3] Extrair capacidade também do nome completo do componente (search_name)
        # quando o model não contém essa informação. Ex: model="870 EVO", name="Samsung 870 EVO 1TB"
        search_capacity = self.extract_storage_capacity(search_model)
        if search_capacity is None and search_name:
            search_capacity = self.extract_storage_capacity(search_name)
        product_capacity = self.extract_storage_capacity(product_name)

        if search_capacity is not None:
            if product_capacity is None or product_capacity != search_capacity:
                print(f"  [MATCH] REJEITADO (capacidade {search_capacity}GB != {product_capacity}GB): {product_name[:80]}")
                return False

        # [MONITORING/FIX] Checagem de VRAM para GPUs: model/name normalmente não trazem a
        # capacidade (ex: "GeForce RTX 3060" não diz se é a versão 8GB ou 12GB), então a
        # capacidade de referência vem do campo specifications.memory cadastrado no
        # componente. Sem isso, uma RTX 3060 12GB e uma RTX 3060 8GB (produtos diferentes,
        # preços bem diferentes) eram tratadas como o mesmo match.
        if category == 'GPU' and specifications:
            vram_capacity = self.extract_gpu_vram(specifications)
            if vram_capacity is not None:
                # [FIX 15/08] Recalcula a capacidade do product_name aceitando também a
                # safelist de VRAM (KNOWN_VRAM_CAPACITIES_GB) no fallback sem "B" final.
                # O `product_capacity` calculado acima usa só a safelist de storage, que
                # não inclui valores típicos de VRAM (4, 6, 8, 10, 12...) — por isso títulos
                # como "RTX 5050 ... 8G" (sem o B) rejeitavam produtos válidos com
                # "VRAM 8GB != NoneGB".
                product_vram_capacity = self.extract_storage_capacity(
                    product_name, extra_known_capacities=KNOWN_VRAM_CAPACITIES_GB
                )
                if product_vram_capacity is None or product_vram_capacity != vram_capacity:
                    print(f"  [MATCH] REJEITADO (VRAM {vram_capacity}GB != {product_vram_capacity}GB): {product_name[:80]}")
                    return False

        # [FIX Bug#10] Checar geração DDR quando o modelo é genérico (ex: "Vengeance", "Fury Beast").
        # Sem isso, DDR4 e DDR5 do mesmo produto ficam intercambiáveis no matching.
        # Só rejeita quando AMBOS têm DDR explícito e são diferentes.
        search_ddr = self.extract_ddr_type(search_model)
        if search_ddr is None and search_name:
            search_ddr = self.extract_ddr_type(search_name)
        product_ddr = self.extract_ddr_type(product_name)
        if search_ddr is not None and product_ddr is not None and search_ddr != product_ddr:
            print(f"  [MATCH] REJEITADO (tipo {search_ddr.upper()} != {product_ddr.upper()}): {product_name[:80]}")
            return False

        # [FIX Bug#5] Pular brand check para fabricantes de chip (NVIDIA, AMD, Intel).
        # Seus produtos são vendidos por terceiros (ASUS, MSI, Gigabyte, ZOTAC etc.)
        # e o nome da marca quase nunca aparece no título do produto na loja.
        if search_brand:
            if search_brand.lower() not in CHIP_MANUFACTURERS:
                if search_brand.lower() not in product_name_lower:
                    print(f"  [MATCH] REJEITADO (marca '{search_brand}' ausente): {product_name[:80]}")
                    return False

        return True