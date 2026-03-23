# 🛒 Price Scraper - Kabum & Amazon

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Selenium](https://img.shields.io/badge/Selenium-4.35.0-green.svg)](https://www.selenium.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-CC%20BY--ND%204.0-lightgrey.svg)](LICENSE)

> **Scraper automatizado e inteligente** para monitorar preços de componentes de PC nas principais lojas brasileiras (Kabum e Amazon BR).

## 📖 Sobre

Este scraper foi desenvolvido para automatizar a busca e comparação de preços de componentes de hardware (placas de vídeo, processadores, SSDs, memórias RAM, etc.) nas principais lojas online do Brasil.

**Diferenciais:**
- ✅ **Validação inteligente de produtos** - Evita variantes indesejadas (ex: não confunde RTX 5060 com RTX 5060 Ti)
- ✅ **Validação de capacidade e geração** - Garante 1TB é 1TB, DDR4 não é DDR5
- ✅ **Filtro de vendedor** - Aceita apenas produtos vendidos pela própria loja (KaBuM! ou Amazon)
- ✅ **LLM como fallback** - Usa Groq (Llama-3.3-70b) quando o matching automático falha
- ✅ **Scroll progressivo** - Carrega TODOS os produtos da página para encontrar o melhor preço
- ✅ **Comportamento humanizado** - Simula digitação e movimentos de mouse para evitar detecção
- ✅ **Anti-bot protection** - Múltiplos user-agents, delays aleatórios, scripts anti-detecção

---

## ✨ Features

### 🎯 Validação Inteligente
- **Detecta variantes de produto**: Diferencia 7600X de 7600X3D, RTX 5060 de RTX 5060 Ti
- **Valida capacidade de armazenamento**: Garante que a busca por "1TB" retorna exatamente 1TB
- **Valida geração de RAM**: Distingue DDR4 de DDR5 mesmo quando o modelo é genérico (ex: "Vengeance")
- **Filtra produtos indesejados**: Rejeita kits, PCs completos, acessórios
- **Normalização de códigos**: Encontra produtos com hífens (ex: RM-WA-FB-ARGB)

### 🤖 LLM Fallback (Groq)
- Quando o matching automático não encontra nenhum produto válido, consulta o **Llama-3.3-70b** via Groq API
- Avalia os 3 candidatos mais baratos e confirma se são o mesmo produto
- Rate limiter proativo (2s entre chamadas, cooldown de 60s após erro 429)
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
- **Logging detalhado**: Mostra Top 3 preços encontrados, produtos rejeitados/aceitos

### 🔒 Segurança
- **Comportamento humanizado**: Simula usuário real
- **Delays aleatórios**: Evita padrões de bot
- **Rotação de User-Agents**: Dificulta detecção
- **Scripts anti-detecção**: Remove propriedades de webdriver

---

## 🛠 Tecnologias

- **Python 3.9+** - Linguagem principal
- **Selenium 4.35.0** - Automação de navegador
- **webdriver-manager** - Gerenciamento automático do ChromeDriver
- **Chrome/ChromeDriver** - Browser headless
- **Supabase** - Banco de dados (PostgreSQL)
- **Groq API (Llama-3.3-70b)** - LLM fallback para validação de produtos
- **Docker** - Containerização

---

## 📦 Pré-requisitos

### Para rodar localmente:
- Python 3.9 ou superior
- Google Chrome instalado
- Conta no Supabase (ou outro banco PostgreSQL)
- Chave de API do Groq (opcional, mas recomendada para melhor matching)

### Para rodar com Docker:
- Docker
- Docker Compose

---

## 🚀 Instalação

### 🐳 Opção 1: Docker (Recomendado)

1. **Clone o repositório:**
```bash
git clone https://github.com/Gabrielcodebr/price-scraping.git
cd price-scraping
```

2. **Configure as variáveis de ambiente:**
```bash
cp .env.example .env
# Edite o .env com suas credenciais
```

3. **Build e execute:**
```bash
docker-compose up --build
```

**Comandos úteis:**
```bash
# Executar em background
docker-compose up -d

# Ver logs em tempo real
docker-compose logs -f

# Parar container
docker-compose down

# Rebuild (após mudanças no código)
docker-compose up --build

# Executar uma única vez e remover container
docker-compose run --rm selenium-scraper
```

### 🐍 Opção 2: Local

**Crie um ambiente virtual:**
```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**Instale as dependências:**
```bash
pip install -r requirements.txt
```

---

## ⚙️ Variáveis de Ambiente

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-anon

# Opcional — habilita fallback LLM para matching de produtos difíceis
GROQ_API_KEY=sua-chave-groq
```

---

## 🗄️ Schema do Banco de Dados

O scraper atualiza o campo `best_price` na tabela `components` do Supabase:

```sql
-- Preços (populado pelo scraper)
best_price JSONB DEFAULT '{
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
    "shipped_by_store": null
  },
  "amazon": {
    "url": null,
    "found": false,
    "price": null,
    "shipped_by_store": null
  },
  "updated_at": null
}'
```

O campo `shipped_by_store` indica se o produto é vendido e entregue pela própria loja (`true`), por um vendedor externo (`false`), ou se não foi possível determinar (`null`).

---

## 🎮 Como Usar

### Execução Básica

O scraper busca **todos** os componentes cadastrados na tabela `components`, ordena pelos mais antigos (ou nunca atualizados) e atualiza os preços automaticamente:

```bash
# Docker
docker-compose up

# Local
python selenium-scraper.py
```

### Logs de Execução

O scraper fornece logs detalhados em tempo real:

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
Melhor preco: KABUM - R$ 1497.00
============================================================
```

---

## 🔍 Como Funciona

### 1. Validação de Produtos

O scraper usa um sistema de **validação inteligente** para garantir que encontra o produto exato:

#### ✅ Aceita:
- **Variações de marketing**: "Gaming", "OC", "RGB", "Black Edition"
- **Mesmo modelo**: "RTX 5060" aceita "GeForce RTX 5060 Gaming OC"

#### ❌ Rejeita:
- **Variantes diferentes**: "RTX 5060" **NÃO** aceita "RTX 5060 Ti"
- **Capacidades diferentes**: "1TB" **NÃO** aceita "512GB" ou "2TB"
- **Gerações de RAM diferentes**: "DDR4" **NÃO** aceita "DDR5"
- **Kits/PCs completos**: Rejeita "Desktop", "Kit Upgrade", "Combo"
- **Acessórios**: Rejeita "Bracket", "Adaptador", "Extensor"

### 2. Sistema de Tokens

O scraper extrai **tokens-chave** dos nomes dos produtos:

```python
"AMD Ryzen 5 7600X Gaming OC" → ['7600x']
"AMD Ryzen 5 7600X3D Gaming" → ['7600x3d', 'x3d']
```

Ignora palavras genéricas:
```python
GENERIC_WORDS = ['gaming', 'oc', 'edition', 'rgb', 'black', ...]
```

Detecta variantes importantes:
```python
VARIANT_SUFFIXES = ['xt', 'ti', 'super', 'kf', 'x3d', '3d', ...]
```

### 3. Validação de Capacidade e Geração

Para SSDs, HDs e memórias RAM:

```python
Busca: "XPG S70 Blade 1TB"
✅ Aceita: "XPG GAMMIX S70 Blade 1TB NVMe"
❌ Rejeita: "XPG GAMMIX S70 Blade 512GB NVMe"
❌ Rejeita: "XPG GAMMIX S70 Blade 2TB NVMe"

Busca: "Corsair Vengeance DDR4"
✅ Aceita: "Corsair Vengeance 16GB DDR4 3200MHz"
❌ Rejeita: "Corsair Vengeance 16GB DDR5 5200MHz"
```

### 4. LLM Fallback (Groq)

Quando o matching automático retorna 0 produtos válidos, o scraper consulta o Llama-3.3-70b:

```
[KABUM] Matching normal: 0 resultados. Tentando LLM nos 3 candidatos mais baratos...
[LLM] 'ASUS TUF Gaming RX 7600 XT OC 16GB...' → SIM (match=True)
```

Produtos rejeitados por keyword (`kit`, `laptop`, etc.) **nunca** são enviados ao LLM.

### 5. Filtro de Vendedor

- **Kabum**: Clica no checkbox "KaBuM!" no filtro "Vendido por" antes de coletar produtos. Se o filtro não existir (sem estoque próprio), retorna `None`.
- **Amazon**: Após selecionar o mais barato, abre a página do produto e verifica o bloco de vendedor para confirmar se é `amazon.com.br`.

### 6. Scroll Progressivo

Muitos sites usam **lazy loading**. O scraper faz scroll progressivo para carregar TODOS os produtos:

```python
def progressive_scroll(self, max_scrolls=8):
    # Scroll até o final
    # Aguarda novos produtos carregarem
    # Repete até não haver mais produtos
    # Volta ao topo
```

Isso garante que encontramos o **melhor preço**, não apenas os primeiros resultados.

### 7. Comportamento Humanizado

Para evitar detecção como bot:

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

**Solução:** Certifique-se de que o Chrome está instalado:

```bash
# Verificar Chrome
google-chrome --version

# Ubuntu/Debian
sudo apt-get install google-chrome-stable

# Com Docker, isso é feito automaticamente
```

### Erro: "Nenhum produto encontrado"

**Possíveis causas:**

1. **Seletores CSS mudaram** - Sites atualizam frequentemente
   - Verifique os logs para ver quais seletores falharam
   - Atualize os `product_container_selectors` no código

2. **Produto realmente não existe**
   - Verifique manualmente no site
   - Ajuste o campo `model` no banco de dados

3. **Validação muito restritiva**
   - Verifique os logs: "Produtos validos: 0 | Rejeitados: 20"
   - Ajuste `VARIANT_SUFFIXES` ou `GENERIC_WORDS` se necessário

4. **Filtro KaBuM! sem estoque próprio**
   - Log: "Filtro 'KaBuM!' nao encontrado - sem estoque proprio nessa busca"
   - O produto existe na Kabum mas vendido por terceiros — resultado ignorado intencionalmente

### Erro: "Too many requests" / Bloqueado

**Solução:** Aumente os delays entre requisições:

```python
# No código, ajuste:
self.human_delay(5, 8)  # Aumentar para (10, 15)

# Entre componentes:
delay = random.uniform(8, 15)  # Aumentar para (15, 30)
```

### LLM não está sendo usado

**Verifique:** A variável `GROQ_API_KEY` está configurada no `.env`? O LLM só é ativado quando a chave está presente e o matching automático falha.

### Container Docker reinicia continuamente

**Solução:** Verifique os logs:

```bash
docker-compose logs -f

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
