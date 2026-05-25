// ============================================================
// SISTEMA DE LEADS - Google Apps Script
// Fontes: Google Maps | LinkedIn (Apify) | Instagram (Apify)
// Enriquecimento: Hunter.io
// E-mail: Brevo | WhatsApp: Evolution API
// ============================================================

// ──────────────────────────────────────────────
// 1. UTILITÁRIOS
// ──────────────────────────────────────────────

function getConfig() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Config');
  const data = sheet.getDataRange().getValues();
  const cfg = {};
  data.forEach(row => { if (row[0]) cfg[row[0]] = row[1]; });
  return cfg;
}

function getLeadsSheet() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Leads');
}

function getLogSheet() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Log');
}

function log(mensagem, status) {
  const sheet = getLogSheet();
  sheet.appendRow([new Date(), mensagem, status || 'INFO']);
}

function normalizarTelefone(tel) {
  if (!tel) return '';
  const limpo = String(tel).replace(/\D/g, '');
  // Adiciona 55 (Brasil) se não tiver
  if (limpo.length === 11 && limpo.startsWith('0')) return '55' + limpo.slice(1);
  if (limpo.length === 11) return '55' + limpo;
  if (limpo.length === 10) return '55' + limpo;
  if (limpo.startsWith('55')) return limpo;
  return limpo;
}


// ──────────────────────────────────────────────
// 2. BUSCA DE LEADS — GOOGLE MAPS (Places API)
// ──────────────────────────────────────────────

function buscarLeadsGoogleMaps() {
  const cfg = getConfig();
  const sheet = getLeadsSheet();
  const ui = SpreadsheetApp.getUi();

  const respNicho = ui.prompt('Google Maps — Nicho', 'Qual tipo de negócio? (ex: agência de marketing, salão de beleza)', ui.ButtonSet.OK_CANCEL);
  if (respNicho.getSelectedButton() !== ui.Button.OK) return;

  const respCidade = ui.prompt('Google Maps — Cidade', 'Qual cidade/região? (ex: São Paulo SP, Curitiba PR)', ui.ButtonSet.OK_CANCEL);
  if (respCidade.getSelectedButton() !== ui.Button.OK) return;

  const query = encodeURIComponent(`${respNicho.getResponseText()} ${respCidade.getResponseText()}`);
  const url = `https://maps.googleapis.com/maps/api/place/textsearch/json?query=${query}&language=pt-BR&key=${cfg.GOOGLE_PLACES_API_KEY}`;

  try {
    const res = UrlFetchApp.fetch(url);
    const data = JSON.parse(res.getContentText());

    if (data.status !== 'OK') {
      ui.alert(`Erro na API: ${data.status}\n${data.error_message || ''}`);
      return;
    }

    let adicionados = 0;
    data.results.forEach(lugar => {
      const detalhes = buscarDetalhesPlace(lugar.place_id, cfg.GOOGLE_PLACES_API_KEY);
      const linha = [
        new Date(),
        'Google Maps',
        lugar.name || '',
        detalhes.website || '',
        detalhes.formatted_phone_number || '',
        '',  // email (enriquecer depois)
        lugar.formatted_address || '',
        lugar.rating || '',
        lugar.user_ratings_total || '',
        'Novo',
        '',  // enviado email
        '',  // enviado WhatsApp
        lugar.place_id
      ];
      sheet.appendRow(linha);
      adicionados++;
      Utilities.sleep(200); // evita rate limit
    });

    log(`Google Maps: ${adicionados} leads adicionados — "${respNicho.getResponseText()} ${respCidade.getResponseText()}"`, 'SUCESSO');
    ui.alert(`✅ ${adicionados} leads adicionados da busca no Google Maps!`);

  } catch (e) {
    log(`Erro Google Maps: ${e.message}`, 'ERRO');
    ui.alert(`Erro: ${e.message}`);
  }
}

function buscarDetalhesPlace(placeId, apiKey) {
  const campos = 'formatted_phone_number,website,formatted_address';
  const url = `https://maps.googleapis.com/maps/api/place/details/json?place_id=${placeId}&fields=${campos}&key=${apiKey}`;
  try {
    const res = UrlFetchApp.fetch(url);
    const data = JSON.parse(res.getContentText());
    return data.result || {};
  } catch (e) {
    return {};
  }
}


// ──────────────────────────────────────────────
// 3. BUSCA DE LEADS — LINKEDIN (via Apify)
// ──────────────────────────────────────────────

function buscarLeadsLinkedIn() {
  const cfg = getConfig();
  const sheet = getLeadsSheet();
  const ui = SpreadsheetApp.getUi();

  const respCargo = ui.prompt('LinkedIn — Cargo', 'Qual cargo buscar? (ex: CEO, Diretor de Marketing, Gerente Comercial)', ui.ButtonSet.OK_CANCEL);
  if (respCargo.getSelectedButton() !== ui.Button.OK) return;

  const respSetor = ui.prompt('LinkedIn — Setor', 'Qual setor/empresa? (ex: Marketing Digital, E-commerce, Saúde)', ui.ButtonSet.OK_CANCEL);
  if (respSetor.getSelectedButton() !== ui.Button.OK) return;

  // Apify: LinkedIn Profile Scraper (ativo gratuito com limite)
  const apifyUrl = `https://api.apify.com/v2/acts/curious_coder~linkedin-people-profile-scraper/runs?token=${cfg.APIFY_API_TOKEN}`;

  const payload = {
    searchQueries: [`${respCargo.getResponseText()} ${respSetor.getResponseText()} Brasil`],
    maxResults: 20,
    proxyConfiguration: { useApifyProxy: true }
  };

  try {
    const res = UrlFetchApp.fetch(apifyUrl, {
      method: 'POST',
      contentType: 'application/json',
      payload: JSON.stringify(payload)
    });

    const run = JSON.parse(res.getContentText());
    const runId = run.data.id;

    ui.alert(`Busca iniciada no Apify (ID: ${runId})\nAguarde ~2 minutos e clique em "Importar Resultados Apify".`);

    // Salva o runId para importar depois
    const configSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Config');
    const linhas = configSheet.getDataRange().getValues();
    for (let i = 0; i < linhas.length; i++) {
      if (linhas[i][0] === 'ULTIMO_RUN_APIFY') {
        configSheet.getRange(i + 1, 2).setValue(runId);
        return;
      }
    }
    configSheet.appendRow(['ULTIMO_RUN_APIFY', runId]);

  } catch (e) {
    log(`Erro LinkedIn Apify: ${e.message}`, 'ERRO');
    ui.alert(`Erro: ${e.message}`);
  }
}

function importarResultadosApify() {
  const cfg = getConfig();
  const sheet = getLeadsSheet();
  const ui = SpreadsheetApp.getUi();

  const runId = cfg.ULTIMO_RUN_APIFY;
  if (!runId) { ui.alert('Nenhuma busca Apify pendente.'); return; }

  const url = `https://api.apify.com/v2/actor-runs/${runId}/dataset/items?token=${cfg.APIFY_API_TOKEN}&format=json`;

  try {
    const res = UrlFetchApp.fetch(url);
    const items = JSON.parse(res.getContentText());

    if (!items.length) {
      ui.alert('Ainda sem resultados. Aguarde mais um pouco e tente novamente.');
      return;
    }

    let adicionados = 0;
    items.forEach(p => {
      sheet.appendRow([
        new Date(),
        'LinkedIn',
        (p.firstName || '') + ' ' + (p.lastName || ''),
        p.companyWebsite || p.currentCompanyUrl || '',
        p.phoneNumber || '',
        p.email || '',
        p.location || '',
        '',
        '',
        'Novo',
        '',
        '',
        p.profileUrl || ''
      ]);
      adicionados++;
    });

    log(`LinkedIn Apify: ${adicionados} leads importados`, 'SUCESSO');
    ui.alert(`✅ ${adicionados} leads do LinkedIn importados!`);

  } catch (e) {
    log(`Erro importar Apify: ${e.message}`, 'ERRO');
    ui.alert(`Erro: ${e.message}`);
  }
}


// ──────────────────────────────────────────────
// 4. BUSCA DE LEADS — INSTAGRAM (via Apify)
// ──────────────────────────────────────────────

function buscarLeadsInstagram() {
  const cfg = getConfig();
  const ui = SpreadsheetApp.getUi();

  const respHashtag = ui.prompt('Instagram — Hashtag', 'Qual hashtag buscar? (ex: marketingdigital, ecommercebrasil)', ui.ButtonSet.OK_CANCEL);
  if (respHashtag.getSelectedButton() !== ui.Button.OK) return;

  const hashtag = respHashtag.getResponseText().replace('#', '');

  // Apify: Instagram Hashtag Scraper
  const apifyUrl = `https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/runs?token=${cfg.APIFY_API_TOKEN}`;

  const payload = {
    hashtags: [hashtag],
    resultsLimit: 30,
    proxyConfiguration: { useApifyProxy: true }
  };

  try {
    const res = UrlFetchApp.fetch(apifyUrl, {
      method: 'POST',
      contentType: 'application/json',
      payload: JSON.stringify(payload)
    });

    const run = JSON.parse(res.getContentText());
    ui.alert(`Busca Instagram iniciada (hashtag: #${hashtag})\nID: ${run.data.id}\nAguarde e importe os resultados.`);

    const configSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Config');
    const linhas = configSheet.getDataRange().getValues();
    for (let i = 0; i < linhas.length; i++) {
      if (linhas[i][0] === 'ULTIMO_RUN_APIFY') {
        configSheet.getRange(i + 1, 2).setValue(run.data.id);
        return;
      }
    }
    configSheet.appendRow(['ULTIMO_RUN_APIFY', run.data.id]);

  } catch (e) {
    log(`Erro Instagram Apify: ${e.message}`, 'ERRO');
    ui.alert(`Erro: ${e.message}`);
  }
}


// ──────────────────────────────────────────────
// 5. ENRIQUECIMENTO DE E-MAIL (Hunter.io)
// ──────────────────────────────────────────────

function enriquecerEmails() {
  const cfg = getConfig();
  const sheet = getLeadsSheet();
  const dados = sheet.getDataRange().getValues();
  const ui = SpreadsheetApp.getUi();

  let enriquecidos = 0;

  for (let i = 1; i < dados.length; i++) {
    const email = dados[i][5];
    const website = dados[i][3];
    const nome = dados[i][2];

    // Pula se já tem email
    if (email && email.includes('@')) continue;
    // Pula se não tem website
    if (!website) continue;

    try {
      const dominio = extrairDominio(website);
      if (!dominio) continue;

      // Tenta domain search primeiro
      const urlDomain = `https://api.hunter.io/v2/domain-search?domain=${dominio}&api_key=${cfg.HUNTER_API_KEY}&limit=1`;
      const resDomain = UrlFetchApp.fetch(urlDomain);
      const dataDomain = JSON.parse(resDomain.getContentText());

      let emailEncontrado = '';

      if (dataDomain.data && dataDomain.data.emails && dataDomain.data.emails.length > 0) {
        emailEncontrado = dataDomain.data.emails[0].value;
      }

      // Se tem nome, tenta email finder
      if (!emailEncontrado && nome) {
        const partes = nome.trim().split(' ');
        const firstName = partes[0] || '';
        const lastName = partes[partes.length - 1] || '';
        const urlFinder = `https://api.hunter.io/v2/email-finder?domain=${dominio}&first_name=${firstName}&last_name=${lastName}&api_key=${cfg.HUNTER_API_KEY}`;
        const resFinder = UrlFetchApp.fetch(urlFinder);
        const dataFinder = JSON.parse(resFinder.getContentText());
        if (dataFinder.data && dataFinder.data.email) {
          emailEncontrado = dataFinder.data.email;
        }
      }

      if (emailEncontrado) {
        sheet.getRange(i + 1, 6).setValue(emailEncontrado);
        enriquecidos++;
      }

      Utilities.sleep(300); // respeita rate limit Hunter.io

    } catch (e) {
      log(`Erro enriquecer linha ${i + 1}: ${e.message}`, 'AVISO');
    }
  }

  log(`Hunter.io: ${enriquecidos} emails enriquecidos`, 'SUCESSO');
  ui.alert(`✅ ${enriquecidos} emails encontrados e preenchidos!`);
}

function extrairDominio(url) {
  try {
    const limpo = url.replace(/https?:\/\//i, '').replace(/www\./i, '').split('/')[0].split('?')[0];
    return limpo;
  } catch (e) {
    return '';
  }
}


// ──────────────────────────────────────────────
// 6. DISPARO DE E-MAIL (Brevo API)
// ──────────────────────────────────────────────

function dispararEmails() {
  const cfg = getConfig();
  const sheet = getLeadsSheet();
  const dados = sheet.getDataRange().getValues();
  const ui = SpreadsheetApp.getUi();

  const respAssunto = ui.prompt('E-mail — Assunto', 'Qual o assunto do e-mail?', ui.ButtonSet.OK_CANCEL);
  if (respAssunto.getSelectedButton() !== ui.Button.OK) return;

  const respCorpo = ui.prompt('E-mail — Corpo', 'Cole o texto do e-mail.\nUse {{nome}} para personalizar o nome do lead.', ui.ButtonSet.OK_CANCEL);
  if (respAssunto.getSelectedButton() !== ui.Button.OK) return;

  const assunto = respAssunto.getResponseText();
  const corpoTemplate = respCorpo.getResponseText();

  let enviados = 0;
  let erros = 0;

  for (let i = 1; i < dados.length; i++) {
    const nome = dados[i][2];
    const email = dados[i][5];
    const jaEnviou = dados[i][10]; // coluna K

    if (!email || !email.includes('@')) continue;
    if (jaEnviou === 'Enviado') continue;

    const corpo = corpoTemplate.replace(/\{\{nome\}\}/gi, nome.split(' ')[0] || nome);

    const payload = {
      sender: { name: cfg.EMAIL_FROM_NAME, email: cfg.EMAIL_FROM },
      to: [{ email: email, name: nome }],
      subject: assunto,
      htmlContent: `<p>${corpo.replace(/\n/g, '<br>')}</p>`
    };

    try {
      const res = UrlFetchApp.fetch('https://api.brevo.com/v3/smtp/email', {
        method: 'POST',
        headers: {
          'api-key': cfg.BREVO_API_KEY,
          'Content-Type': 'application/json'
        },
        payload: JSON.stringify(payload)
      });

      if (res.getResponseCode() === 201) {
        sheet.getRange(i + 1, 11).setValue('Enviado');
        sheet.getRange(i + 1, 11).setBackground('#d4edda');
        enviados++;
      } else {
        erros++;
        log(`Email falhou para ${email}: ${res.getContentText()}`, 'ERRO');
      }

    } catch (e) {
      erros++;
      log(`Erro email ${email}: ${e.message}`, 'ERRO');
    }

    Utilities.sleep(500);
  }

  log(`Brevo: ${enviados} emails enviados, ${erros} erros`, 'SUCESSO');
  ui.alert(`✅ ${enviados} emails enviados!\n❌ ${erros} erros (veja a aba Log)`);
}


// ──────────────────────────────────────────────
// 7. DISPARO DE WHATSAPP (Evolution API)
// ──────────────────────────────────────────────

function dispararWhatsApp() {
  const cfg = getConfig();
  const sheet = getLeadsSheet();
  const dados = sheet.getDataRange().getValues();
  const ui = SpreadsheetApp.getUi();

  const respMsg = ui.prompt('WhatsApp — Mensagem', 'Digite a mensagem.\nUse {{nome}} para personalizar.', ui.ButtonSet.OK_CANCEL);
  if (respMsg.getSelectedButton() !== ui.Button.OK) return;

  const msgTemplate = respMsg.getResponseText();
  let enviados = 0;
  let erros = 0;

  // Z-API: https://api.z-api.io/instances/{instanceId}/token/{token}/send-text
  const instanceId = cfg.EVOLUTION_INSTANCE;
  const token = cfg.EVOLUTION_API_KEY;
  const zApiUrl = `https://api.z-api.io/instances/${instanceId}/token/${token}/send-text`;

  for (let i = 1; i < dados.length; i++) {
    const nome = dados[i][2];
    const telefoneRaw = dados[i][4];
    const jaEnviou = dados[i][11]; // coluna L

    if (!telefoneRaw) continue;
    if (jaEnviou === 'Enviado') continue;

    const telefone = normalizarTelefone(telefoneRaw);
    if (telefone.length < 12) continue; // número inválido

    const mensagem = msgTemplate.replace(/\{\{nome\}\}/gi, nome.split(' ')[0] || nome);

    // Z-API usa "phone" e "message" no body
    const payload = {
      phone: telefone,
      message: mensagem
    };

    try {
      const res = UrlFetchApp.fetch(zApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'client-token': cfg.EVOLUTION_API_URL // campo extra de segurança do Z-API (opcional)
        },
        payload: JSON.stringify(payload)
      });

      const code = res.getResponseCode();
      if (code === 200 || code === 201) {
        sheet.getRange(i + 1, 12).setValue('Enviado');
        sheet.getRange(i + 1, 12).setBackground('#d4edda');
        enviados++;
      } else {
        erros++;
        log(`WhatsApp falhou ${telefone}: ${res.getContentText()}`, 'ERRO');
      }

    } catch (e) {
      erros++;
      log(`Erro WhatsApp ${telefone}: ${e.message}`, 'ERRO');
    }

    Utilities.sleep(1500); // 1.5s entre mensagens para evitar bloqueio
  }

  log(`Z-API: ${enviados} WhatsApp enviados, ${erros} erros`, 'SUCESSO');
  ui.alert(`✅ ${enviados} mensagens WhatsApp enviadas!\n❌ ${erros} erros (veja a aba Log)`);
}


// ──────────────────────────────────────────────
// 8. INICIALIZAÇÃO DA PLANILHA
// ──────────────────────────────────────────────

function inicializarPlanilha() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Aba Leads
  let leads = ss.getSheetByName('Leads');
  if (!leads) leads = ss.insertSheet('Leads');
  if (leads.getLastRow() === 0) {
    const cabecalho = [
      'Data Adição', 'Fonte', 'Nome/Empresa', 'Website',
      'Telefone/WhatsApp', 'E-mail', 'Endereço/Localização',
      'Avaliação', 'Nº Avaliações', 'Status',
      'Email Enviado', 'WhatsApp Enviado', 'ID/URL Fonte'
    ];
    leads.appendRow(cabecalho);
    leads.getRange(1, 1, 1, cabecalho.length).setBackground('#4a90d9').setFontColor('#ffffff').setFontWeight('bold');
    leads.setFrozenRows(1);
  }

  // Aba Config
  let config = ss.getSheetByName('Config');
  if (!config) config = ss.insertSheet('Config');
  if (config.getLastRow() === 0) {
    const configData = [
      ['Chave', 'Valor'],
      ['GOOGLE_PLACES_API_KEY', ''],
      ['HUNTER_API_KEY', ''],
      ['BREVO_API_KEY', ''],
      ['EMAIL_FROM', ''],
      ['EMAIL_FROM_NAME', ''],
      ['EVOLUTION_API_URL', ''],
      ['EVOLUTION_API_KEY', ''],
      ['EVOLUTION_INSTANCE', ''],
      ['APIFY_API_TOKEN', ''],
      ['ULTIMO_RUN_APIFY', '']
    ];
    config.getRange(1, 1, configData.length, 2).setValues(configData);
    config.getRange(1, 1, 1, 2).setBackground('#4a90d9').setFontColor('#ffffff').setFontWeight('bold');
  }

  // Aba Log
  let logSheet = ss.getSheetByName('Log');
  if (!logSheet) logSheet = ss.insertSheet('Log');
  if (logSheet.getLastRow() === 0) {
    logSheet.appendRow(['Data/Hora', 'Mensagem', 'Status']);
    logSheet.getRange(1, 1, 1, 3).setBackground('#4a90d9').setFontColor('#ffffff').setFontWeight('bold');
    logSheet.setFrozenRows(1);
  }

  SpreadsheetApp.getUi().alert('✅ Planilha inicializada com sucesso!\n\nPreencha suas chaves de API na aba "Config" e comece a buscar leads.');
}


// ──────────────────────────────────────────────
// 9. MENU PERSONALIZADO
// ──────────────────────────────────────────────

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🎯 Sistema de Leads')
    .addItem('⚙️ Inicializar Planilha', 'inicializarPlanilha')
    .addSeparator()
    .addSubMenu(SpreadsheetApp.getUi().createMenu('🔍 Buscar Leads')
      .addItem('📍 Google Maps', 'buscarLeadsGoogleMaps')
      .addItem('💼 LinkedIn (iniciar)', 'buscarLeadsLinkedIn')
      .addItem('📸 Instagram (iniciar)', 'buscarLeadsInstagram')
      .addItem('📥 Importar Resultados (Apify)', 'importarResultadosApify'))
    .addSeparator()
    .addItem('✉️ Enriquecer E-mails (Hunter.io)', 'enriquecerEmails')
    .addSeparator()
    .addSubMenu(SpreadsheetApp.getUi().createMenu('🚀 Disparar')
      .addItem('📧 Enviar E-mails (Brevo)', 'dispararEmails')
      .addItem('💬 Enviar WhatsApp (Evolution API)', 'dispararWhatsApp'))
    .addToUi();
}
