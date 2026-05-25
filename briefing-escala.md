# Briefing Estratégico: Escalar o Sistema de Captação de Leads

**Agência de Tráfego Pago | Portugal | Maio 2026**

---

## Visão Geral do Sistema Actual

O sistema construído é funcional e já cobre o essencial: captação, enriquecimento, contacto e acompanhamento. O próximo passo não é substituir o que existe — é **amplificar, automatizar e sistematizar** cada parte do funil para passar de 50 para 500+ leads/dia com o mínimo de esforço manual.

---

## 1. Escalar o Volume de Leads: Mais Fontes e Automações

### Fontes Actuais vs. Fontes a Adicionar

| Fonte | Estado | Volume Estimado | Custo |
|---|---|---|---|
| Google Maps (Places API) | Activo | 50–200/dia | Baixo |
| LinkedIn (Apify) | Activo | 30–100/dia | Médio |
| Instagram (Apify) | Activo | 50–150/dia | Médio |
| Google Search Scraping | A adicionar | 100–300/dia | Baixo |
| Facebook Pages | A adicionar | 100–200/dia | Baixo |
| Páginas Amarelas PT | A adicionar | 200–500/dia | Gratuito |
| Registos .pt (DNS) | A adicionar | Ilimitado | Gratuito |
| Listagens sectoriais (ex: AHRESP, ACAP) | A adicionar | Nicho específico | Gratuito |

### Acções Concretas para Escalar Fontes

- **Páginas Amarelas PT**: usar o Apify com o actor `yellow-pages-scraper`. Contém negócios com telefone, morada e por vezes e-mail directamente.
- **Google Search**: pesquisar `"restaurante" + "Lisboa" site:facebook.com` para encontrar páginas de negócios locais.
- **Facebook Pages**: o Apify tem actores para scraping de páginas públicas do Facebook.
- **Registos de empresas**: o portal `racius.com` e o `einforma.pt` têm listagens públicas de empresas com contactos.
- **Associações sectoriais**: AHRESP, ACAP, Ordem dos Médicos, etc. Muitas publicam listas de associados com contactos.

### Automação da Captação

- Criar um **trigger diário no Google Apps Script** (às 07h00) que dispara automaticamente a pesquisa por nicho + cidade.
- Rodar por **rotação de cidades**: semana 1 Lisboa, semana 2 Porto, semana 3 Braga, semana 4 Coimbra.
- Criar uma sheet de configuração com a lista de nichos e cidades — o script lê e executa automaticamente.

---

## 2. Melhorar a Taxa de Resposta no WhatsApp e E-mail

### WhatsApp: O Que Funciona Melhor

**Timing**
- Melhor hora: **terça a quinta, entre as 09h30–11h30** ou **14h00–16h00**
- Evitar segundas-feiras e sextas-feiras à tarde

**Variações de Mensagem a Testar (A/B)**

Versão B — Âncora de credibilidade:
```
Olá {{nome}}! Andei a analisar negócios do sector de {{nicho}} 
aqui em {{cidade}} e reparei numa coisa no vosso caso que me 
chamou atenção. Já ajudei outros negócios locais com situação 
parecida a crescer de forma consistente. 
Tens 10 minutos esta semana para uma conversa rápida?
```

Versão C — Ultra-curta:
```
Oi {{nome}}! Vi uma oportunidade no vosso negócio 
que acho que vais querer saber. Posso partilhar?
```

**Personalização que aumenta resposta**
- Mencionar o nome do negócio: `"reparei numa coisa no {{nome_negocio}} que..."`
- Mencionar a cidade específica: `"negócios aqui em {{cidade}}"`
- Se tiveres a morada, mencionar o bairro: `"aqui no Chiado"` em vez de `"em Lisboa"`

### E-mail: Boas Práticas

**Assuntos a testar**

| Assunto | Tipo |
|---|---|
| `{{nome}}, reparei numa coisa no vosso negócio` | Curiosidade pessoal |
| `Uma oportunidade que a maioria em {{cidade}} ainda não viu` | Exclusividade |
| `10 minutos que podem mudar o mês de {{nome_negocio}}` | Valor + urgência |
| `Pergunta rápida sobre {{nome_negocio}}` | Ultra-simples |

**Configurações técnicas essenciais**
- Configurar **SPF, DKIM e DMARC** no domínio — sem isto, os e-mails vão para spam
- Usar um **subdomínio para envio** (ex: `outreach@mail.tuaagencia.pt`)
- Manter taxa de bounce abaixo de 2%
- Não enviar mais de 100 e-mails/dia por conta nova — fazer warm-up gradual

---

## 3. Estratégia de Follow-Up: O Que Fazer Quando Não Respondem

### Sequência de Follow-Up Recomendada

| Dia | Canal | Objectivo |
|---|---|---|
| Dia 0 | WhatsApp | Primeiro contacto — mensagem de curiosidade |
| Dia 0 | E-mail | Reforço do contacto |
| Dia 2 | WhatsApp | Follow-up leve — reactivar interesse |
| Dia 4 | E-mail | Follow-up com valor adicional |
| Dia 7 | WhatsApp | "Última mensagem" — criar urgência |
| Dia 10 | E-mail | E-mail de ruptura (breakup email) |

### Mensagens de Follow-Up para WhatsApp

**Dia 2:**
```
Oi {{nome}}, sou eu outra vez! Vi que não tiveste oportunidade 
de responder. Sem problema — é mesmo uma coisa pequena que quero 
partilhar, nada de vendas. Vale a pena 5 minutos?
```

**Dia 7:**
```
{{nome}}, vou fechar o contacto por aqui para não chatear. 
Mas antes de ir embora — a oportunidade que vi no {{nome_negocio}} 
ainda está em aberto. Se quiseres saber, é só responder aqui. 
Se não, tudo bem, boa sorte no negócio!
```

**Breakup E-mail (Dia 10):**
```
Assunto: Fecho de contacto — {{nome_negocio}}

Olá {{nome}}, tentei entrar em contacto algumas vezes mas percebo 
que estás ocupado/a. Vou deixar de contactar.

Se algum dia quiseres perceber como outros negócios em {{cidade}} 
estão a aumentar clientes sem depender de boca-a-boca, fica à 
vontade para me contactar.

Boa sorte!
```

> O breakup e-mail tem taxas de resposta surpreendentemente altas — as pessoas sentem que estão a perder algo.

---

## 4. Pipeline de Vendas na Planilha: Como Organizar

### Estrutura de Sheets Recomendada

| Sheet | Conteúdo |
|---|---|
| `Config` | Nichos, cidades, templates, credenciais de API |
| `Leads_Novos` | Leads captados ainda não contactados |
| `Em_Contacto` | Leads que receberam pelo menos uma mensagem |
| `Follow_Up` | Leads em sequência de follow-up activa |
| `Reunião_Agendada` | Leads que aceitaram conversar |
| `Proposta_Enviada` | Leads na fase comercial |
| `Clientes` | Convertidos |
| `Arquivo` | Leads sem resposta após sequência completa |
| `Blacklist` | Leads que pediram para não ser contactados |

### Painel de Controlo (Dashboard) — Métricas Essenciais

- Total de leads captados esta semana / mês
- Taxa de resposta (responderam ÷ contactados)
- Taxa de conversão para reunião (reuniões ÷ responderam)
- Taxa de fecho (clientes ÷ reuniões)
- Nicho com maior taxa de resposta
- Cidade com maior taxa de conversão
- Leads por fonte (Maps, LinkedIn, Instagram)

---

## 5. Segmentação por Nicho: Maximizar Conversão

### Nichos com Maior Potencial em Portugal

| Nicho | Potencial | Ticket Médio/mês | Razão |
|---|---|---|---|
| Clínicas dentárias | Alto | 800–2.000€ | Alta margem, concorrência digital baixa |
| Clínicas de estética / beleza | Alto | 500–1.500€ | Dependem de captação local constante |
| Ginásios e PT | Médio-Alto | 400–1.000€ | Fácil mostrar ROI |
| Imobiliárias independentes | Alto | 1.000–3.000€ | Alta margem por transacção |
| Oficinas auto / concessionários | Médio-Alto | 600–1.500€ | Menos saturados digitalmente |
| Escola de condução | Médio | 400–800€ | Procura constante |
| Advogados / solicitadores | Alto | 1.000–3.000€ | Alta margem |
| Hotéis boutique e alojamento local | Alto | 800–2.500€ | Dependem de reservas directas |

### Personalização da Mensagem por Nicho

- **Dentistas**: "reparei que o vosso agendamento online pode estar a perder marcações automáticas"
- **Estética**: "vi que o vosso Instagram tem boa presença mas pode estar a deixar clientes escapar"
- **Restaurantes**: "notei que o vosso negócio não aparece quando alguém procura {{nicho}} em {{cidade}} no Google"
- **Imobiliárias**: "vi que têm imóveis excelentes mas a visibilidade online pode estar a limitar os contactos directos"

---

## 6. Riscos a Evitar

### WhatsApp: Risco de Bloqueio

| Risco | Como Evitar |
|---|---|
| Número bloqueado pela Meta | Nunca enviar mais de 80–100 msg/dia por número |
| Número reportado | Personalizar sempre, nunca enviar igual a todos |
| Conta banida permanentemente | Usar número dedicado (não o pessoal) |
| Z-API instável | Verificar conexão diariamente |

**Boas práticas anti-bloqueio**
- Usar número de telemóvel dedicado à prospecção
- Adicionar variações aleatórias nas mensagens
- Enviar de forma escalonada ao longo de 2–3 horas
- Nunca incluir links nas primeiras mensagens
- Ter um número de backup pronto

### RGPD: Conformidade Legal em Portugal

- Focar em **contactos de empresas** (B2B) — menos restritivo
- Incluir sempre linha de opt-out: "Se não quiseres receber mais mensagens, responde com 'remover'"
- Manter registo de opt-outs na sheet `Blacklist`
- Nunca comprar listas de e-mails

---

## 7. Próximos Passos: De 50 para 500 Leads/Dia

### Fase 1 — Optimização (Semanas 1–2)
- [ ] Configurar SPF, DKIM e DMARC no domínio de envio
- [ ] Criar trigger diário automático no Apps Script
- [ ] Adicionar coluna `Etapa_Followup` e lógica de follow-up automático
- [ ] Criar o Dashboard com métricas básicas
- [ ] Criar templates de mensagem por nicho
- [ ] Comprar número dedicado para prospecção via WhatsApp

### Fase 2 — Expansão de Fontes (Semanas 3–4)
- [ ] Adicionar Páginas Amarelas PT como fonte via Apify
- [ ] Adicionar Facebook Pages como fonte via Apify
- [ ] Configurar rotação automática de cidades
- [ ] Testar variações de mensagem (A/B)
- [ ] Implementar verificação de e-mails com ZeroBounce

### Fase 3 — Escala e Sistema (Mês 2)
- [ ] Contratar assistente virtual (VA) para qualificar leads
- [ ] Adicionar 2–3 nichos de alto ticket (dentistas, imobiliárias, advogados)
- [ ] Expandir para cidades secundárias (Setúbal, Faro, Évora, Aveiro, Funchal)
- [ ] Considerar segunda conta Brevo para duplicar volume (600/dia)

### Mapa de Escala

```
Semana 1–2:   50 leads/dia  →  Sistema optimizado e automatizado
Semana 3–4:  150 leads/dia  →  Novas fontes activas + rotação de cidades
Mês 2:       300 leads/dia  →  VA a qualificar + novos nichos
Mês 3:       500 leads/dia  →  Sistema completo, múltiplas fontes
```

---

## 8. Ferramentas Complementares

| Ferramenta | Função | Custo | Prioridade |
|---|---|---|---|
| **ZeroBounce** | Verificar e-mails antes de enviar | ~20€/mês | Alta |
| **Make (ex-Integromat)** | Automação entre ferramentas sem código | 9–16€/mês | Alta |
| **Clay** | Enriquecimento de leads em massa com IA | 149€/mês | Alta (escala) |
| **Apollo.io** | Base de dados B2B com e-mails verificados | 49€/mês | Alta |
| **Lemlist** | Sequências de e-mail com personalização avançada | 39€/mês | Média |
| **Phantombuster** | Automação de LinkedIn | 56€/mês | Média |
| **Google Looker Studio** | Dashboard visual conectado à Google Sheet | Grátis | Média |
| **Instantly.ai** | Warm-up automático de e-mail + envio em escala | 37€/mês | Média |

### A Ferramenta de Maior Impacto: Make (Integromat)

O Make permite ligar o Google Sheets ao Brevo, ao Z-API, ao Hunter.io e a qualquer outra ferramenta **sem escrever uma linha de código adicional**. Quando um lead entra na sheet, o Make pode automaticamente:

1. Verificar o e-mail no ZeroBounce
2. Enviar a mensagem de WhatsApp via Z-API
3. Agendar o e-mail no Brevo
4. Criar uma tarefa de follow-up para daqui a 2 dias
5. Notificar-te no telemóvel via Telegram quando alguém responde

---

## Resumo Executivo: As 5 Acções de Maior Impacto

Se só puderes fazer 5 coisas esta semana, faz estas:

1. **Configurar SPF/DKIM/DMARC** — sem isto, metade dos teus e-mails vão para spam
2. **Criar o trigger diário automático** — o sistema trabalha enquanto dormes
3. **Adicionar Páginas Amarelas PT como fonte** — duplica o volume sem custo adicional
4. **Implementar sequência de follow-up automático** — 80% das conversões acontecem no 2.º ou 3.º contacto
5. **Criar o Dashboard de métricas** — sem dados, não sabes o que está a funcionar

---

*Este briefing deve ser revisto mensalmente à medida que o sistema cresce.*
*Gerado em: 22/05/2026*
*Ficheiro: C:\Users\lfern\sistema-leads\briefing-escala.md*
