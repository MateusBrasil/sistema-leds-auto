# Plano de Escala V2 — Sistema de Prospecção VV TRAFFIC DATA

> Documento consolidado para transformar o sistema actual (Google Sheets + Apps Script) numa máquina automatizada de prospecção + CRM, com o utilizador a indicar apenas **nicho + cidade** e receber leads enriquecidos, qualificados, contactados em multi-canal e em pipeline.

**Data:** 22/05/2026
**Operador:** VV TRAFFIC DATA (Portugal)
**Email remetente:** wtrafficdataeu@gmail.com
**Stack actual:** Google Sheets + Apps Script + Google Places + Apify + Hunter.io + Brevo + Z-API
**Objectivo:** 50 → 500 leads/dia, 100% automatizado, em 3 meses

---

## Sumário Executivo (TL;DR)

O sistema actual funciona mas está **plafonado**: cada parte está acoplada ao Apps Script (limite 6 min/execução), o WhatsApp depende de Z-API trial, falta follow-up automático, falta IA para qualificação/personalização e falta dashboard.

A solução **não é reescrever** — é **adicionar camadas**:

1. **Manter** o Sheets como CRM operacional (já está estruturado, fácil de operar).
2. **Adicionar n8n** (auto-hospedado grátis no Railway/Render) como orquestrador central — substitui o que o Apps Script faz pesado.
3. **Adicionar fontes** (Páginas Amarelas PT, racius.com, einforma.pt, Facebook Pages, Google Search) via Apify actors públicos.
4. **Adicionar IA grátis** (Gemini 2.0 Flash + Groq Llama 3.3) para qualificar leads (score 0-100), personalizar mensagens por negócio, e gerar follow-ups.
5. **Adicionar Evolution API self-hosted** (free, ilimitado) para substituir Z-API trial.
6. **Adicionar Looker Studio** (grátis, conecta ao Sheets) para o dashboard.
7. **Adicionar SPF/DKIM/DMARC** no domínio (sem isto, 60% dos emails vão para spam).

**Custo total estimado da nova stack:** 0–30€/mês no início, 50–150€/mês a 500 leads/dia.

---

## 1. Auditoria do Sistema Actual

### O que funciona bem
| Componente | Estado | Comentário |
|---|---|---|
| Google Places API | OK | Retorna nome, telefone, website, morada, rating, place_id |
| Hunter.io enrichment | OK | Domain-search + email-finder em sequência |
| Brevo (email) | OK | 300/dia free é suficiente para começar |
| Apify (LinkedIn/Instagram) | OK | Mas asyncrono — precisa de "Importar Resultados" manual |
| Estrutura Sheets | OK | 13 colunas, status, marcação de envios |
| Logs | OK | Aba `Log` regista tudo |

### Gaps críticos a corrigir
| # | Gap | Impacto | Prioridade |
|---|---|---|---|
| 1 | Z-API é trial 7 dias | WhatsApp pára em 7 dias | 🔴 Crítica |
| 2 | Sem SPF/DKIM/DMARC | 50–70% dos emails vão para spam | 🔴 Crítica |
| 3 | Sem follow-up automático | 80% das conversões acontecem no 2º–3º contacto | 🔴 Crítica |
| 4 | Apps Script limite 6 min | Scrapers pesados (Páginas Amarelas, etc.) não cabem | 🟠 Alta |
| 5 | Sem dedup cross-source | Mesma empresa entra como lead 2-3x | 🟠 Alta |
| 6 | Sem dashboard | Não sabes taxa de resposta, conversão, ROI por nicho | 🟠 Alta |
| 7 | Sem verificação email pré-envio | Bounce rate alto → blacklisting do remetente | 🟠 Alta |
| 8 | 1 aba `Leads` só | Sem separação por etapa de funil | 🟡 Média |
| 9 | Sem IA para qualificação | Tratas leads bons e maus igual | 🟡 Média |
| 10 | Sem rotação de números WhatsApp | Risco de banimento a >80 msg/dia | 🟡 Média |
| 11 | Sem opt-out automático (RGPD) | Risco legal | 🟡 Média |
| 12 | Apify free $5/mês | Insuficiente para 500/dia | 🟡 Média |

### Bug específico já detectado
No `Codigo.gs`, função `dispararWhatsApp` linha ~285:
```js
const clientToken = cfg.EVOLUTION_API_URL; // B7 = Client-Token
```
A variável `EVOLUTION_API_URL` está a guardar o Client-Token do Z-API, o que é confuso. **Renomear** para `ZAPI_CLIENT_TOKEN` quando migrarmos para Evolution self-hosted real.

---

## 2. Arquitectura Alvo (V2)

```
┌─────────────────────────────────────────────────────────────────┐
│  TU: indicas só Nicho + Cidade (numa célula da Config sheet)    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  n8n (orquestrador) — auto-hospedado free em Railway/Render     │
│  cron diário 07:00 → executa pipeline completo                  │
└──────────┬─────────────────┬─────────────┬──────────────────────┘
           │                 │             │
           ▼                 ▼             ▼
┌──────────────────┐ ┌────────────────┐ ┌──────────────────┐
│ FONTES (8)       │ │ ENRICHMENT     │ │ IA (free tier)   │
│ • Google Places  │ │ • Hunter.io    │ │ • Gemini 2.0     │
│ • LinkedIn       │ │ • Apollo.io    │ │ • Groq Llama 3.3 │
│ • Instagram      │ │ • ZeroBounce   │ │ • Score 0-100    │
│ • PáginasAmarelas│ │ • Clearbit     │ │ • Personalização │
│ • racius.com     │ │ • Snov.io      │ │ • Qualificação   │
│ • einforma.pt    │ └────────────────┘ └──────────────────┘
│ • Facebook Pages │
│ • Google Search  │
└──────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Google Sheets (CRM operacional) — 9 abas (kanban funnel)       │
│  Config | Leads_Novos | Em_Contacto | Follow_Up | Reunião       │
│  Proposta | Clientes | Arquivo | Blacklist                       │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────┐  ┌────────────────────────────┐
│ DISPARO MULTI-CANAL          │  │ DASHBOARD (Looker Studio)  │
│ • Brevo (email) + SPF/DKIM   │  │ • Leads/dia por fonte      │
│ • Evolution API self-hosted  │  │ • Taxa de resposta         │
│ • Instagram DM (Phantom)     │  │ • Funil de conversão       │
│ • LinkedIn DM (Phantom)      │  │ • ROI por nicho/cidade     │
└──────────────────────────────┘  └────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Sequência de follow-up (D0, D2, D4, D7, D10) automática        │
│  Trigger no n8n a verificar status diariamente                   │
└─────────────────────────────────────────────────────────────────┘
```

### Princípios da arquitectura
1. **Sheets é o single source of truth** — todo o estado vive lá. n8n só lê/escreve.
2. **n8n é o cérebro** — Apps Script reduz-se ao menu da planilha (UX humana) e à inicialização.
3. **APIs separadas, falhas isoladas** — se o Brevo cai, o WhatsApp continua. Se o LinkedIn falha, o Maps continua.
4. **Free tiers primeiro, pago só quando dor justifica** — Gemini Flash 1M tokens/dia grátis aguenta 5000 leads/dia de personalização.

---

## 3. Novas Fontes de Leads (de 3 para 8)

### 3.1 Páginas Amarelas Portugal
- **Actor Apify:** `epctex/paginas-amarelas-scraper` (≈ $1.50 por 1000 resultados)
- **Output:** nome, telefone, morada, categoria, distrito
- **Free alternativa:** scraper Python custom usando `requests` + `BeautifulSoup` no n8n (HTTP Request node)
- **Volume estimado:** 200–500/dia

### 3.2 racius.com (registo empresas PT)
- **URL pattern:** `https://www.racius.com/<distrito>/<concelho>/<actividade>/`
- **Não há actor oficial — fazer scraper custom em n8n**
- **Free, ilimitado**
- **Output:** nome empresa, NIPC, morada, CAE, gerentes
- **Volume estimado:** 100–300/dia

### 3.3 einforma.pt
- **Similar ao racius mas tem mais info financeira**
- **Free com limites; tier pago dá CSV bulk**

### 3.4 Google Search Scraper (gold mine)
- **Actor Apify:** `apify/google-search-scraper` ou `serper.dev` (1000 queries/mês grátis)
- **Queries úteis:**
  - `"<nicho>" + "<cidade>" site:facebook.com`
  - `"<nicho>" + "<cidade>" "telefone"`
  - `"<nicho>" + "<cidade>" "@gmail.com" OR "@hotmail.com"`
- **Volume estimado:** 100–300/dia

### 3.5 Facebook Pages
- **Actor Apify:** `apify/facebook-pages-scraper`
- **Output:** nome página, telefone, website, email (quando público), morada, número de likes
- **Volume estimado:** 100–200/dia

### 3.6 Listagens sectoriais (gold para nichos específicos)
| Nicho | Fonte |
|---|---|
| Hotelaria/restauração | AHRESP.pt — lista de associados |
| Concessionários auto | ACAP.pt |
| Médicos/clínicas | Ordem dos Médicos (pesquisa pública) |
| Advogados | Ordem dos Advogados |
| Imobiliárias | APEMIP |
| Estética/beleza | ANEPE |

### 3.7 LinkedIn Sales Navigator (escala B2B)
- **Actor Apify:** `curious_coder/linkedin-profile-scraper` (já estás a usar)
- **Upgrade:** `dev_fusion/linkedin-jobs-scraper` para encontrar empresas que estão a contratar (sinal forte de crescimento)

### 3.8 Instagram (escala B2C)
- **Já tens hashtag scraper.** Adicionar:
  - `apify/instagram-profile-scraper` — perfis comerciais
  - `apify/instagram-location-scraper` — negócios geolocalizados

---

## 4. IA Gratuita para Qualificação e Personalização

### 4.1 Gemini 2.0 Flash (Google AI Studio)
- **Grátis:** 1M tokens/dia, 15 req/min
- **Uso 1 — Qualificação (score 0-100):**
  ```
  Input: nome empresa + website + rating Google + nº reviews + categoria
  Output: JSON { score: 87, motivo: "alta facturação prevista, baixa concorrência digital, dependente de tráfego local" }
  ```
- **Uso 2 — Personalização da 1ª mensagem:**
  ```
  Input: nome empresa + nicho + dados do website (scraped)
  Output: 1 frase de abertura específica daquele negócio
  Exemplo: "vi que o vosso menu tem destaque para o brunch ao fim-de-semana — reparei numa coisa no vosso anúncio que pode estar a custar-vos reservas"
  ```
- **Uso 3 — Classificação de respostas:**
  Quando alguém responde no WhatsApp/email, IA classifica:
  - `interessado` → mover para `Em_Contacto`
  - `pediu_remover` → mover para `Blacklist`
  - `irrelevante` → ignorar e continuar sequência

### 4.2 Groq + Llama 3.3 70B
- **Grátis:** 14.400 req/dia
- **Vantagem:** velocidade absurda (300+ tokens/s) — útil para personalizar 500 mensagens em segundos
- **Caso de uso:** batch processing nocturno

### 4.3 Integração no n8n
Já existem nodes oficiais para:
- `n8n-nodes-base.googleGemini`
- HTTP Request → Groq API

---

## 5. Pipeline CRM no Sheets (de 1 aba para 9)

Estrutura recomendada (substitui a aba `Leads` actual):

| Aba | Conteúdo | Trigger de saída |
|---|---|---|
| `Config` | Nichos, cidades, templates, chaves API, IA prompts | — |
| `Leads_Novos` | Captados ainda não contactados | Após 1ª mensagem → `Em_Contacto` |
| `Em_Contacto` | Receberam 1 mensagem | Após resposta → `Follow_Up` ou `Reunião` |
| `Follow_Up` | Em sequência de follow-up | Sequência D2/D4/D7/D10 automática |
| `Reunião_Agendada` | Aceitaram conversar | Após reunião → `Proposta` ou `Arquivo` |
| `Proposta_Enviada` | Em fase comercial | Após fecho → `Clientes` |
| `Clientes` | Convertidos | — |
| `Arquivo` | Sem resposta após sequência | — |
| `Blacklist` | Pediram para não contactar (RGPD) | — |

### Migração suave
Não apagar a aba `Leads` actual. Criar as novas abas e um script de **migração one-shot** que distribui os leads existentes pelas novas abas baseado na coluna `Status`.

### Novas colunas a adicionar
- `Score_IA` (0-100)
- `Etapa_Funil` (Novo / Contactado / Em Follow-up / Reunião / Cliente)
- `Data_Ultimo_Contacto`
- `Numero_Toques` (1, 2, 3...)
- `Personalizacao_IA` (frase gerada pela IA)
- `Hash_Dedup` (md5 de nome+telefone+website para evitar duplicados)

---

## 6. Follow-up Automático

### Sequência D0 → D10
| Dia | Canal | Conteúdo | Trigger |
|---|---|---|---|
| 0 | WhatsApp | Mensagem 1 (curiosidade, personalizada por IA) | Lead entra em `Leads_Novos` |
| 0 | Email | Reforço | +5 min após WhatsApp |
| 2 | WhatsApp | Follow-up leve | Cron n8n diário |
| 4 | Email | Follow-up com valor | Cron n8n diário |
| 7 | WhatsApp | "Última mensagem" + urgência | Cron n8n diário |
| 10 | Email | Breakup email | Cron n8n diário |

### Implementação técnica
- n8n workflow `daily_followup`:
  - Lê todos os leads em `Em_Contacto` + `Follow_Up`
  - Calcula `dias_desde_ultimo_contacto`
  - Aplica regra de etapa correspondente
  - Envia mensagem
  - Actualiza `Numero_Toques` e `Data_Ultimo_Contacto`
  - Se chegou ao Dia 10 sem resposta → move para `Arquivo`

### Detecção de resposta
- **Email (Brevo):** webhook do Brevo notifica n8n quando há reply
- **WhatsApp (Evolution):** webhook nativo da Evolution API notifica n8n
- IA classifica → workflow move o lead para a aba certa

---

## 7. Substituir Z-API por Evolution API Self-Hosted

### Por que mudar
- Z-API trial = 7 dias, depois pago (~50€/mês)
- Evolution = open-source, free, ilimitado, e tem webhooks nativos

### Como deployar (3 opções)

**Opção A — Railway (recomendada, sem cartão necessário no início)**
- Template oficial: https://railway.app/template/evolution-api
- Fork do repo: https://github.com/EvolutionAPI/evolution-api
- ~5€/mês após créditos free

**Opção B — Render (free tier limitado mas funcional)**
- Conta free, deploy do Docker image
- Limites de RAM podem causar disconnects → upgrade $7/mês

**Opção C — VPS (Hetzner / Contabo, 4€/mês)**
- Mais robusto, controlo total
- Usar docker-compose do repo oficial

### Migração código
Substituir no `Codigo.gs` a função `dispararWhatsApp` para usar a API real da Evolution (em vez do Z-API):

```js
const url = `${cfg.EVOLUTION_API_URL}/message/sendText/${cfg.EVOLUTION_INSTANCE}`;
const payload = {
  number: telefone,
  text: mensagem
};
const headers = {
  'apikey': cfg.EVOLUTION_API_KEY,
  'Content-Type': 'application/json'
};
```

---

## 8. Email Deliverability (SPF / DKIM / DMARC)

**Sem isto, 50-70% dos emails vão para spam — é o melhoramento mais barato e impactante.**

### Setup completo (1 vez, ~30 min)
1. Comprar domínio próprio (ex: `vvtraffic.pt` na GoDaddy ou Cloudflare Registrar — 8-10€/ano)
2. Mudar `EMAIL_FROM` para `outreach@vvtraffic.pt` (subdomínio dedicado a outreach, não o domínio principal)
3. Adicionar registros DNS:
   - **SPF:** `v=spf1 include:spf.brevo.com -all`
   - **DKIM:** copiar do painel Brevo (Senders & IP → Authenticate Domain)
   - **DMARC:** `v=DMARC1; p=quarantine; rua=mailto:dmarc@vvtraffic.pt`
4. Validar em https://mxtoolbox.com/SuperTool.aspx
5. Warm-up: começar com 10 emails/dia, subir 10% por dia até 100/dia

### Verificação de emails antes de envio
- **ZeroBounce** (~0.008€/email)
- **NeverBounce** (similar)
- **Free alternativa:** validar sintaxe + MX record (já dá para evitar 80% dos bounces)

---

## 9. Anti-Bloqueio WhatsApp

| Risco | Mitigação |
|---|---|
| >80 msg/dia → ban Meta | Usar 2-3 números rotativos, max 50/dia por número |
| Mensagens iguais → spam flag | IA gera 5-10 variações para cada mensagem base |
| Sem warm-up → ban no dia 1 | Começar com 10 msg/dia, +5/dia por semana |
| Links na 1ª mensagem → ban | Nunca incluir URL antes da resposta do lead |
| Reports de utilizadores → ban | Sempre incluir "responde 'remover' para parar" |

### Multi-number rotation (avançado)
- Criar 3 instâncias Evolution
- n8n distribui round-robin
- Aba `Config` tem 3 colunas para 3 instâncias

---

## 10. Dashboard (Looker Studio — grátis)

Conectar o Looker Studio à Google Sheet (1 clique). Métricas a mostrar:

### Painel 1 — Volume
- Leads/dia (linha temporal)
- Leads por fonte (donut chart)
- Top 5 nichos por volume

### Painel 2 — Conversão
- Taxa de resposta (responderam ÷ contactados)
- Funil: Novos → Contactados → Responderam → Reunião → Cliente
- Tempo médio de cada etapa

### Painel 3 — ROI
- Custo por lead (Apify + Brevo + Evolution ÷ leads)
- Receita por nicho
- Lifetime value médio de cliente

---

## 11. Recursos GitHub e Frameworks Recomendados

### Repositórios para clonar/inspirar

| Repo | Função | Como usar |
|---|---|---|
| [`EvolutionAPI/evolution-api`](https://github.com/EvolutionAPI/evolution-api) | WhatsApp API self-hosted | Substituir Z-API |
| [`n8n-io/n8n`](https://github.com/n8n-io/n8n) | Orquestrador no-code | Deploy Railway, ligar a tudo |
| [`apify/apify-sdk-js`](https://github.com/apify/apify-sdk-js) | SDK para criar actors custom | Para racius.com / einforma.pt |
| [`Mailman-Suite/mailman`](https://github.com/mailman/mailman) | Lista de unsubscribes | Gestão RGPD |
| [`piyushtechsavy/python-lead-generator`](https://github.com/topics/lead-generation) | Scrapers Python | Exemplo de scraping com Selenium |
| [`scrapy/scrapy`](https://github.com/scrapy/scrapy) | Framework de scraping | Alternativa a Apify para auto-hospedagem |
| [`crewAIInc/crewAI`](https://github.com/crewAIInc/crewAI) | Multi-agentes IA | Agentes para qualificar/personalizar/responder |
| [`langgenius/dify`](https://github.com/langgenius/dify) | Plataforma LLM no-code | Backoffice de IA com UI |

### Frameworks de prospecção open-source
- **[OPES (Open Source Email System)](https://github.com/topics/email-marketing)** — alternativa a Brevo
- **[Mautic](https://github.com/mautic/mautic)** — marketing automation completo, free, auto-hospedável
- **[Listmonk](https://github.com/knadh/listmonk)** — newsletter & campaign manager rápido em Go
- **[Postal](https://github.com/postalserver/postal)** — servidor SMTP próprio (para sair do Brevo a partir de 10.000/dia)

### MCPs Claude que já tens disponíveis (relevantes)
| MCP | Uso para o projecto |
|---|---|
| `mcp__claude_ai_Vibe_Prospecting` | **Match the most relevant** — `enrich-business`, `enrich-prospects`, `fetch-businesses-events`, `match-business` |
| `mcp__claude_ai_ClickUp` | Para um CRM mais robusto que Sheets quando escalares |
| `mcp__claude_ai_Gmail` | Para responder aos leads sem sair do Claude |

### Agentes/Skills relevantes na tua instalação
| Skill | Uso |
|---|---|
| `traffic-masters` | Aconselhar campanhas Ads quando converteres leads em clientes |
| `copy-master` / `copy-squad` | Optimizar copy das mensagens (A/B testing inteligente) |
| `hormozi-squad` | Construir ofertas irresistíveis (Grand Slam Offer) para apresentar nas reuniões |
| `data-squad` | Construir o dashboard e modelo de retenção |
| `utils:n8n` | Skill que tens para construir workflows n8n |
| `cybersecurity` | Pentest do sistema antes de pôr em produção (chaves, RGPD) |

---

## 12. Roadmap em 3 Fases

### Fase 1 — Foundation (Semanas 1-2)

**Objectivo:** sistema robusto, sem bugs, sem perder leads.

- [ ] Migrar Z-API → Evolution API self-hosted (Railway template)
- [ ] Comprar domínio `vvtraffic.pt`
- [ ] Configurar SPF/DKIM/DMARC no Brevo
- [ ] Warm-up de email (10 → 100/dia em 2 semanas)
- [ ] Criar abas Kanban (`Leads_Novos`, `Em_Contacto`, `Follow_Up`, etc.)
- [ ] Migração one-shot dos leads existentes
- [ ] Adicionar coluna `Hash_Dedup` e função de deduplicação
- [ ] Validar emails antes do envio (sintaxe + MX, free)

**Outcome esperado:** 50–100 leads/dia, taxa de bounce <2%, WhatsApp estável.

---

### Fase 2 — Automação (Semanas 3-6)

**Objectivo:** o sistema roda sozinho, tu só vês o dashboard.

- [ ] Deploy n8n no Railway
- [ ] Workflow `daily_capture` (cron 07h00, rotação de cidades)
- [ ] Workflow `daily_followup` (cron 09h00, sequência D2/D4/D7/D10)
- [ ] Webhook Brevo → n8n (detectar respostas email)
- [ ] Webhook Evolution → n8n (detectar respostas WhatsApp)
- [ ] Integração Gemini 2.0 Flash (score + personalização)
- [ ] Adicionar Páginas Amarelas PT como fonte
- [ ] Adicionar Google Search Scraper como fonte
- [ ] Dashboard Looker Studio v1

**Outcome esperado:** 150–250 leads/dia, follow-up automático, taxa de resposta 5-8%.

---

### Fase 3 — Escala (Mês 2-3)

**Objectivo:** 500 leads/dia, multi-canal, multi-nicho.

- [ ] Adicionar racius.com, einforma.pt, Facebook Pages, listagens sectoriais
- [ ] Adicionar 2-3 nichos de alto ticket (clínicas dentárias, imobiliárias, advogados)
- [ ] Multi-number WhatsApp rotation (3 números)
- [ ] Contratar VA (assistente virtual) para qualificar respostas
- [ ] Migrar Brevo → Postal/Mautic (self-hosted) se passar dos 10.000 emails/mês
- [ ] Dashboard v2 com ROI por nicho/cidade
- [ ] A/B testing automático de copy (n8n + IA escolhe vencedor)
- [ ] Integração com Calendly (agendamento automático na resposta "sim")

**Outcome esperado:** 500 leads/dia, 5-10 reuniões/dia, 2-3 clientes novos/semana.

---

## 13. Custos Estimados

| Item | Fase 1 (50/dia) | Fase 2 (200/dia) | Fase 3 (500/dia) |
|---|---|---|---|
| Domínio `.pt` | 10€/ano | — | — |
| Google Places API | Free ($200 crédito) | Free | ~20€/mês |
| Hunter.io | Free (25/mês) | 49€/mês (1k/mês) | 99€/mês (5k/mês) |
| Brevo | Free (300/dia) | Free | 25€/mês (40k/mês) |
| Apify | Free ($5/mês) | 49€/mês ($49 crédito) | 99€/mês |
| Evolution self-hosted | Free (Railway) | 5€/mês (Railway) | 10€/mês (Hetzner) |
| n8n self-hosted | Free (Railway) | 5€/mês | 10€/mês |
| ZeroBounce | — | 20€/mês | 40€/mês |
| Looker Studio | Free | Free | Free |
| **TOTAL** | **~10€/mês** | **~130€/mês** | **~300€/mês** |

Considerando ticket médio de cliente 500–1.500€/mês e taxa de conversão 1-2% sobre leads, **o ROI esperado paga a stack ao 1º cliente**.

---

## 14. Compliance RGPD (Portugal/UE)

| Regra | Implementação |
|---|---|
| Base legal: interesse legítimo B2B | Só prospectar empresas, nunca particulares |
| Direito ao apagamento | Aba `Blacklist` + IA detecta "remover"/"para" |
| Informação clara | Cada mensagem termina com `responde "STOP" para não receber mais` |
| Registo de consentimentos | Aba `Log` regista tudo (data, IP, conteúdo) |
| DPO | Para escala, ter DPO externo (50-100€/mês) |
| Retenção dados | Auto-purge após 12 meses sem resposta |

**Nota:** B2B na UE é menos restritivo que B2C, mas o RGPD aplica-se. O modelo "soft opt-in" + opt-out fácil é geralmente aceite.

---

## 15. Próximos Passos Imediatos (Hoje/Amanhã)

Por ordem de impacto/esforço:

1. **(30 min, free)** Comprar `vvtraffic.pt` e configurar SPF/DKIM no Brevo
2. **(20 min, free)** Deploy Evolution API no Railway (template oficial)
3. **(15 min, free)** Criar conta Google AI Studio, copiar API key do Gemini
4. **(45 min, free)** Deploy n8n no Railway (template oficial)
5. **(1h, free)** Criar workflow n8n `daily_capture` que substitua a busca manual no Sheets
6. **(30 min, free)** Implementar deduplicação no `Codigo.gs` (coluna `Hash_Dedup`)

Tudo isto é **zero custo**, **executável esta semana**, e desbloqueia toda a Fase 1.

---

## 16. Como Tu Vais Usar Isto Quando Estiver Pronto

```
Tu, sexta à noite:
1. Abres a Sheet
2. Vais à aba Config
3. Escreves na linha "Nicho_Hoje": "clínica dentária"
4. Escreves na linha "Cidade_Hoje": "Lisboa"
5. Fechas a Sheet.

Sábado de manhã (07h00, n8n cron):
6. Sistema busca em 8 fontes em paralelo
7. Dedup, enriquece (Hunter), valida emails (ZeroBounce)
8. IA classifica score 0-100
9. IA gera 1 frase de personalização por lead
10. Filtra só leads com score >70 (configurável)
11. Envia WhatsApp + email com 2 min de diferença
12. Marca status, regista no Log

Domingo:
13. Cron de follow-up corre.
14. Quem respondeu → IA classifica → ClickUp/aba certa.

Tu, segunda de manhã:
15. Abres o dashboard Looker.
16. Vês: 47 leads novos, 8 responderam, 3 marcaram reunião.
17. Só falas com os 3.
```

---

*Plano gerado em 22/05/2026. Revisar mensalmente conforme o sistema escala.*
*Próximo checkpoint: fim da Fase 1 (≈ 5 de Junho).*
