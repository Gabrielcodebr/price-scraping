# Price Scraper - Kabum & Amazon

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Selenium](https://img.shields.io/badge/Selenium-4.35.0-green.svg)](https://www.selenium.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-CC%20BY--ND%204.0-lightgrey.svg)](LICENSE)

> **Scraper automatizado e inteligente** para monitorar preços de componentes de PC nas principais lojas brasileiras (Kabum e Amazon BR).

## Sobre

Este scraper busca e compara preços de componentes de hardware (placas de vídeo,
processadores, SSDs, memórias RAM, etc.) na Kabum e na Amazon BR, roda automaticamente
via GitHub Actions a cada 2 dias, e alimenta a tabela `components` do Supabase que o
app React Native consome.

**Diferenciais:**
- ✅ **Validação inteligente de produtos** - Evita variantes indesejadas (ex: não confunde RTX 5060 com RTX 5060 Ti)
- ✅ **Validação de capacidade e geração** - Garante que 1TB é 1TB, DDR4 não é DDR5
- ✅ **Filtro de vendedor** - Aceita apenas produtos vendidos pela própria loja (KaBuM! ou Amazon)
- ✅ **LLM como fallback** - Usa Groq (OpenAI/GPT-OSS-120b) quando o matching automático falha
- ✅ **Scroll progressivo** - Carrega TODOS os produtos da página para encontrar o melhor preço
- ✅ **Comportamento humanizado** - Simula digitação e movimentos de mouse para evitar detecção
- ✅ **Monitoramento e alertas** - Detecta variação brusca de preço, produto sumindo, ou run com muitos erros técnicos (ver seção [Monitoramento e Alertas](#-monitoramento-e-alertas))

---

## 📁 Estrutura do projeto

O código está dividido em módulos por responsabilidade — pensado tanto pra facilitar
manutenção quanto pra ajudar uma LLM a localizar rápido o trecho relevante:

```
selenium-scraper.py        # entry point — só chama scraper.main.main()
scraper/
  config.py                # .env, cliente Supabase, chave da Groq, constantes de alerta/tempo
  matching_rules.py        # listas de palavras/sufixos usadas para validar produtos
  driver_utils.py          # setup do Chrome + comportamento humanizado (mouse, digitação, scroll)
  matching.py              # decide se um produto encontrado é o componente buscado
  sites/
    kabum.py               # busca e extração de preços específicas da Kabum
    amazon.py              # busca e extração de preços específicas da Amazon
  price_scraper.py         # classe PriceScraper — junta tudo acima em um scraper só
  alerts.py                # cria/atualiza/resolve alertas na tabela scraper_alerts
  database.py              # grava o resultado da run na tabela components
  main.py                  # loop principal: percorre componentes, watchdog, limites de tempo
```

`PriceScraper` é uma classe só, mas seus métodos estão espalhados nesses arquivos via
**mixins** (`HumanBehaviorMixin`, `MatchingMixin`, `KabumMixin`, `AmazonMixin`) — em tempo
de execução não há diferença nenhuma pra um arquivo único: `self.driver`,
`self.search_kabum(...)` etc. continuam acessíveis de qualquer método.

**Guia rápido — onde mexer:**

| Se você quer mexer em... | Vá em... |
|---|---|
| Regra que rejeita "kit", "notebook", PCs completos, etc. | `matching_rules.py` (`EXCLUSION_KEYWORDS`) |
| Regra de sufixo de variante (XT, Ti, Super...) | `matching_rules.py` (`VARIANT_SUFFIXES`) |
| Lógica que decide se um produto encontrado é o mesmo buscado | `matching.py` (`is_exact_product_match`) |
| Prompt ou comportamento do fallback via Groq/LLM | `matching.py` (`ask_groq_is_match`) |
| Delays humanizados, scroll, digitação, setup do Chrome | `driver_utils.py` |
| Filtro "KaBuM!", seletores de produto/preço da Kabum | `sites/kabum.py` |
| Retry de "Algo deu errado", CAPTCHA, seletores da Amazon | `sites/amazon.py` |
| Thresholds de alerta (% de variação de preço, streak de miss) | `config.py` |
| Quando um alerta é criado/resolvido | `alerts.py` |
| Como o preço é salvo no Supabase (found/not_found/error) | `database.py` |
| Tempo máximo de run, timeout por componente, loop principal | `main.py` |

---

## ✨ Features

### 🎯 Validação Inteligente
- **Detecta variantes de produto**: Diferencia 7600X de 7600X3D, RTX 5060 de RTX 5060 Ti
- **Valida capacidade de armazenamento**: Garante que a busca por "1TB" retorna exatamente 1TB
- **Valida VRAM de GPU**: Diferencia RTX 3060 8GB de RTX 3060 12GB (não são o mesmo produto)
- **Valida geração de RAM**: Distingue DDR4 de DDR5 mesmo quando o modelo é genérico (ex: "Vengeance")
- **Filtra produtos indesejados**: Rejeita kits, PCs completos, acessórios
- **Normalização de códigos**: Encontra produtos com hífens (ex: RM-WA-FB-ARGB)

### 🤖 LLM Fallback (Groq)
- Quando o matching automático não encontra nenhum produto válido, consulta o **OpenAI/GPT-OSS-120b** via Groq API
- Avalia os 3 candidatos mais baratos e confirma se são o mesmo produto
- Rate limiter proativo (2.5s entre chamadas, cooldown de 60s após erro 429)
- Fallback desabilitado automaticamente se `GROQ_API_KEY` não estiver configurada

### 🏪 Filtro de Vendedor
- **Kabum**: Aplica o filtro "Vendido por KaBuM!" antes de coletar resultados — rejeita vendedores terceiros
- **Amazon**: Entra na página de cada produto para verificar se é vendido e enviado pela Amazon
- O campo `shipped_by_store` é salvo no banco para cada loja

### 🚀 Performance
- **Scroll progressivo**: Carrega todos os produtos (lazy loading)
- **Busca sequencial**: Kabum → Amazon, com delay humanizado entre as buscas
- **Priorização por data**: Componentes nunca atualizados ou mais antigos são processados primeiro
- **Limite de runtime**: Para após 5h de execução (margem para o timeout de 6h do GitHub Actions)
- **Watchdog por componente**: Aborta e segue em frente se um único componente passar de 5min
- **Logging detalhado**: Mostra Top 3 preços encontrados, produtos rejeitados/aceitos

### 🔔 Monitoramento e alertas
- Distingue **erro técnico** (página não carregou, CAPTCHA, timeout) de **produto não encontrado**
  de verdade — erro técnico nunca apaga o preço já salvo, só um "not found" real reseta
- Alerta de variação brusca de preço (`price_spike` / `price_drop`)
- Alerta de divergência de preço entre Kabum e Amazon na mesma run (`store_mismatch`)
- Alerta de produto sumindo de um site (`not_found_streak`) ou dos dois ao mesmo tempo,
  sinalizando possível descontinuação (`possible_discontinued`)
- Snapshot de saúde de cada run (`run_health`) — % de CAPTCHA, % de erro técnico, se a run
  foi cortada por tempo, taxa de confirmação do fallback LLM
- Detalhes completos na seção [Monitoramento e Alertas](#-monitoramento-e-alertas)

### 🔒 Segurança / Anti-detecção
- **Comportamento humanizado**: Simula usuário real
- **Delays aleatórios**: Evita padrões de bot
- **Rotação de User-Agents**: Dificulta detecção
- **Scripts anti-detecção**: Remove propriedades de webdriver
- **Aquecimento de sessão na Amazon**: Visita a home antes da primeira busca pra reduzir bloqueios no início da run

---

## 🛠 Tecnologias

- **Python 3.9+** - Linguagem principal
- **Selenium 4.35.0** - Automação de navegador
- **webdriver-manager** - Gerenciamento automático do ChromeDriver (usado só localmente — no Docker o chromedriver já vem pré-instalado na imagem)
- **Chrome/ChromeDriver** - Browser headless
- **Supabase** - Banco de dados (PostgreSQL)
- **Groq API (OpenAI/GPT-OSS-120b)** - LLM fallback para validação de produtos
- **Docker** - Containerização

---

## 📦 Pré-requisitos

### Para rodar localmente:
- Python 3.11 ou 3.12 (evite 3.14 — pacotes como `pydantic_core`, dependência do Supabase, podem não ter wheel pré-compilada ainda e falhar ao compilar via Rust)
- Google Chrome instalado
- Conta no Supabase (ou outro banco PostgreSQL)
- Chave de API do Groq (opcional, mas recomendada para melhor matching)

### Para rodar com Docker:
- Docker
- Docker Compose (opcional, só para desenvolvimento local)

---

## 🚀 Instalação

### 🐳 Opção 1: Docker Compose (desenvolvimento local)

O projeto tem um `docker-compose.dev.yml` — **uso exclusivo de desenvolvimento local**,
com bind mount do código pra hot-reload. Em produção o scraper roda via GitHub Actions,
que builda a imagem direto do `Dockerfile` (ver `.github/workflows/scraper.yml`), sem
Docker Compose.

1. **Clone o repositório:**
```bash
git clone https://github.com/Gabrielcodebr/price-scraping.git
cd price-scraping
```

2. **Crie o arquivo `.env` na raiz** com suas credenciais (não há `.env.example` no repo — veja as variáveis necessárias em [Variáveis de Ambiente](#️-variáveis-de-ambiente)).

3. **Build e execute:**
```bash
docker compose -f docker-compose.dev.yml up --build
```
(Se seu Docker usa a CLI antiga, o comando equivalente é `docker-compose -f docker-compose.dev.yml up --build`.)

**Comandos úteis:**
```bash
# Executar em background
docker compose -f docker-compose.dev.yml up -d

# Ver logs em tempo real
docker compose -f docker-compose.dev.yml logs -f

# Parar container
docker compose -f docker-compose.dev.yml down

# Rebuild (após mudanças no código)
docker compose -f docker-compose.dev.yml up --build
```

### 🐳 Opção 2: Docker "puro" (igual à produção)

Reproduz exatamente o que o GitHub Actions faz:
```bash
docker build -t price-scraper .
docker run --env-file .env price-scraper
```

### 🐍 Opção 3: Local (sem Docker)

**Crie um ambiente virtual (Python 3.11 ou 3.12):**
```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows (git bash)
source venv/Scripts/activate
```

**Instale as dependências:**
```bash
pip install -r requirements.txt
```

**Execute:**
```bash
python selenium-scraper.py
```

---

## ⚙️ Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com:

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-anon

# Opcional — habilita fallback LLM para matching de produtos difíceis
GROQ_API_KEY=sua-chave-groq
```

No Docker (produção via GitHub Actions), `CHROME_DRIVER_PATH` já vem fixado no
`Dockerfile` (`/usr/local/bin/chromedriver`) — não precisa ser configurado manualmente.

---

## 🗄️ Schema do Banco de Dados

### Tabela `components`

O scraper atualiza o campo `best_price`:

```jsonc
best_price: {
  "best": {
    "url": null,
    "price": null,
    "store": null,
    "shipped_by_store": null
  },
  "kabum": {
    "url": null,
    "found": false,
    "price": null,
    "shipped_by_store": null,
    "consecutive_misses": 0,   // usado para os alertas de not_found_streak
    "last_found_at": null      // timestamp da última vez que foi encontrado
  },
  "amazon": {
    "url": null,
    "found": false,
    "price": null,
    "shipped_by_store": null,
    "consecutive_misses": 0,
    "last_found_at": null
  },
  "updated_at": null
}
```

O campo `shipped_by_store` indica se o produto é vendido e entregue pela própria loja
(`true`), por um vendedor externo (`false`), ou se não foi possível determinar (`null`).

### Tabela `scraper_alerts`

Populada por `alerts.py` (ver seção abaixo). Cada linha tem `component_id` (nulo para
alertas gerais como `run_health`), `type`, `site`, `details` (JSON), `resolved`,
`resolved_at` e `expires_at`.

---

## 🔔 Monitoramento e Alertas

Cada tentativa de busca (Kabum ou Amazon) retorna um de três status, e essa distinção é
o que evita que uma falha técnica passageira apague um preço bom salvo anteriormente:

| Status | Significa | O que acontece no banco |
|---|---|---|
| `found` | Produto localizado e validado | Atualiza preço/URL, zera o streak de misses |
| `not_found` | Busca rodou normal, mas nada passou na validação (miss de negócio) | Reseta preço/URL daquele site, incrementa o streak de misses |
| `error` | Falha técnica (CAPTCHA, timeout, página não carregou) | **Não mexe em nada** — preço salvo anteriormente é preservado |

A partir disso, `alerts.py` dispara (thresholds configuráveis em `config.py`):

- **`price_spike` / `price_drop`** — preço variou 80%+ em relação à última leitura do mesmo site
- **`store_mismatch`** — Kabum e Amazon divergem em 80%+ na mesma run (possível erro de matching, ex: pegou capacidades diferentes em cada loja)
- **`not_found_streak`** — 4+ misses consecutivos em um site (produto pode estar sumindo de lá)
- **`possible_discontinued`** — 8+ misses consecutivos nos **dois** sites ao mesmo tempo
- **`run_health`** — snapshot registrado ao fim de toda run (mesmo as saudáveis), com % de CAPTCHA/erro técnico, se foi cortada por tempo, e taxa de confirmação do fallback LLM

Alertas de streak (`not_found_streak`, `possible_discontinued`) são atualizados em vez de
duplicados enquanto a condição persistir, e resolvidos automaticamente quando o produto
volta a ser encontrado. Alertas pontuais (preço, mismatch) expiram sozinhos após 14 dias;
`run_health` expira em 30 dias.

---

## 🎮 Como Usar

O scraper busca **todos** os componentes cadastrados na tabela `components`, ordena pelos
mais antigos (ou nunca atualizados) e atualiza os preços automaticamente:

```bash
# Docker Compose (dev)
docker compose -f docker-compose.dev.yml up

# Docker puro
docker run --env-file .env price-scraper

# Local
python selenium-scraper.py
```

### Logs de Execução

```
============================================================
Processando: AMD Ryzen 5 7600X (ID: abc-123)
============================================================

[KABUM] Buscando: AMD Ryzen 5 7600X
[KABUM] Modelo para validacao: Ryzen 5 7600X
[KABUM] Filtro 'KaBuM!' aplicado
[KABUM] Scroll apos filtro...
[KABUM] Total de produtos na pagina: 16
[KABUM] Produtos validos: 1 | Rejeitados: 15
[KABUM] Top 3 precos encontrados:
  1. R$ 1497.00 - Processador AMD Ryzen 5 7600X, 5.3GHz...
[KABUM] SELECIONADO: Processador AMD Ryzen 5 7600X - R$ 1497.00

[AMAZON] Buscando: AMD Ryzen 5 7600X
[AMAZON] Total de produtos na pagina: 24
[AMAZON] Produtos validos: 1 | Rejeitados: 22
[AMAZON] Vendedor: Vendido e enviado pela Amazon
[AMAZON] SELECIONADO: AMD Ryzen 5 7600X - R$ 1599.00

--- Resumo: AMD Ryzen 5 7600X ---
Kabum: R$ 1497.00
Amazon: R$ 1599.00 (Amazon)
Melhor preco (nesta run): KABUM - R$ 1497.00
============================================================
```

---

## 🔍 Como Funciona

### 1. Validação de Produtos (`matching.py` + `matching_rules.py`)

#### ✅ Aceita:
- **Variações de marketing**: "Gaming", "OC", "RGB", "Black Edition"
- **Mesmo modelo**: "RTX 5060" aceita "GeForce RTX 5060 Gaming OC"

#### ❌ Rejeita:
- **Variantes diferentes**: "RTX 5060" **NÃO** aceita "RTX 5060 Ti"
- **Capacidades diferentes**: "1TB" **NÃO** aceita "512GB" ou "2TB"
- **VRAM diferente (GPU)**: "RTX 3060 12GB" **NÃO** aceita "RTX 3060 8GB"
- **Gerações de RAM diferentes**: "DDR4" **NÃO** aceita "DDR5"
- **Kits/PCs completos**: Rejeita "Desktop", "Kit Upgrade", "Combo"
- **Acessórios**: Rejeita "Bracket", "Adaptador", "Extensor", e itens que só citam o modelo buscado após "para" (ex: "Antena WiFi **para** MSI MAG Z890 Tomahawk")

### 2. Sistema de Tokens

```python
"AMD Ryzen 5 7600X Gaming OC" → ['7600x']
"AMD Ryzen 5 7600X3D Gaming" → ['7600x3d', 'x3d']
```

Ignora palavras genéricas (`GENERIC_WORDS`) e detecta sufixos de variante importantes
(`VARIANT_SUFFIXES`) — ambos em `matching_rules.py`.

### 3. Validação de Capacidade e Geração

```python
Busca: "XPG S70 Blade 1TB"
✅ Aceita: "XPG GAMMIX S70 Blade 1TB NVMe"
❌ Rejeita: "XPG GAMMIX S70 Blade 512GB NVMe"

Busca: "Corsair Vengeance DDR4"
✅ Aceita: "Corsair Vengeance 16GB DDR4 3200MHz"
❌ Rejeita: "Corsair Vengeance 16GB DDR5 5200MHz"
```

### 4. LLM Fallback (Groq)

Quando o matching automático retorna 0 produtos válidos:

```
[KABUM] Matching normal: 0 resultados. Tentando LLM nos 3 candidatos mais baratos...
[LLM] 'ASUS TUF Gaming RX 7600 XT OC 16GB...' → SIM (match=True)
```

Produtos rejeitados por keyword (`kit`, `laptop`, etc.) **nunca** são enviados ao LLM.

### 5. Filtro de Vendedor

- **Kabum** (`sites/kabum.py`): Clica no checkbox "KaBuM!" no filtro "Vendido por" antes de coletar produtos. Se o filtro não existir, é tratado como "sem estoque próprio" (`not_found`), diferente de uma falha técnica ao aplicá-lo (`error`).
- **Amazon** (`sites/amazon.py`): Após selecionar o mais barato, abre a página do produto e verifica o bloco de vendedor para confirmar se é `amazon.com.br`.

### 6. Scroll Progressivo

```python
def progressive_scroll(self, max_scrolls=8):
    # Scroll até o final
    # Aguarda novos produtos carregarem
    # Repete até não haver mais produtos
    # Volta ao topo
```

### 7. Comportamento Humanizado (`driver_utils.py`)

```python
# Digitação humanizada (com delays variáveis)
def human_typing(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.08, 0.2))

# Movimentos de mouse naturais
def human_mouse_movement(element):
    actions.move_to_element_with_offset(element,
        random.randint(-5, 5),
        random.randint(-5, 5))
```

---

## 🐛 Troubleshooting

### Erro: "Driver não inicializado"

Certifique-se de que o Chrome está instalado (local) — com Docker isso é automático:
```bash
google-chrome --version
```

### `ModuleNotFoundError` ao instalar dependências / falha ao compilar `pydantic_core`

Geralmente é versão de Python incompatível. Use Python 3.11 ou 3.12 no venv local
(o Docker/produção já roda em 3.9 e não tem esse problema).

### Erro: "Nenhum produto encontrado"

**Possíveis causas:**

1. **Seletores CSS mudaram** - Sites atualizam frequentemente
   - Verifique os logs para ver quais seletores falharam
   - Atualize os seletores em `sites/kabum.py` ou `sites/amazon.py`

2. **Produto realmente não existe**
   - Verifique manualmente no site
   - Ajuste o campo `model` no banco de dados

3. **Validação muito restritiva**
   - Verifique os logs: "Produtos validos: 0 | Rejeitados: 20"
   - Ajuste `VARIANT_SUFFIXES` ou `GENERIC_WORDS` em `matching_rules.py`

4. **Filtro KaBuM! sem estoque próprio**
   - Log: "Filtro 'KaBuM!' nao encontrado - sem estoque proprio nessa busca"
   - Resultado ignorado intencionalmente (`not_found`, não `error`)

### Erro: "Too many requests" / Bloqueado / página "Algo deu errado" (Amazon)

O scraper já tenta mitigar isso sozinho (aquecimento de sessão + retry com espera maior
em `sites/amazon.py`). Se persistir, aumente os delays em `driver_utils.py`
(`human_delay`) e em `main.py` (delay entre componentes).

### LLM não está sendo usado

Verifique se `GROQ_API_KEY` está no `.env`. O LLM só é ativado quando a chave está
presente **e** o matching automático falha completamente.

### Container Docker reinicia continuamente

```bash
docker compose -f docker-compose.dev.yml logs -f

# Se for problema de permissões:
sudo chown -R 1000:1000 .
```

---

## 🙏 Agradecimentos

- [Selenium](https://www.selenium.dev/) - Framework de automação
- [Supabase](https://supabase.com/) - Backend as a Service
- [webdriver-manager](https://github.com/SergeyPirogov/webdriver_manager) - Gerenciamento automático do ChromeDriver
- [Groq](https://groq.com/) - Inferência LLM para fallback de matching

---

<div align="center">

**⭐ Se este projeto foi útil, deixe uma estrela!**

</div>