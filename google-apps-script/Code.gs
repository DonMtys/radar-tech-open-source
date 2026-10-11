const RADAR_CONFIG = Object.freeze({
  githubTopics: ['ai-agent', 'developer-tools'],
  githubMinimumStars: 10,
  githubMaximumAgeDays: 14,
  newsMaximumAgeHours: 48,
  maximumDailyPosts: 48,
  minimumIntervalMinutes: 28,
  recentPostLimit: 60,
  seenUrlRetentionDays: 120,
  userAgent: 'RadarTechBot/1.0',
});

const TECH_TERMS = [
  'ai', 'agent', 'artificial intelligence', 'llm', 'model', 'openai', 'anthropic',
  'github', 'open source', 'software', 'developer', 'programming', 'python',
  'linux', 'security', 'cyber', 'database', 'duckdb', 'browser', 'cloud',
  'robot', 'chip', 'semiconductor', 'hardware', 'javascript', 'rust', 'api',
  'inteligência artificial', 'tecnologia', 'programação', 'código aberto',
];

/** Executado pelo gatilho a cada 30 minutos. Envia no máximo uma publicação. */
function runRadarBot() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) {
    console.log('Outra execução ainda está em andamento.');
    return { status: 'locked', sent: 0 };
  }

  try {
    const config = getSecrets_();
    const now = new Date();
    const state = loadState_();
    const recentPosts = state.sent.filter(post => {
      return now.getTime() - new Date(post.sentAt).getTime() < 24 * 60 * 60 * 1000;
    });

    if (recentPosts.length >= RADAR_CONFIG.maximumDailyPosts) {
      return { status: 'daily_limit', sent: 0, dailyCount: recentPosts.length };
    }

    if (state.sent.length) {
      const lastSentAt = new Date(state.sent[state.sent.length - 1].sentAt);
      const elapsedMinutes = (now.getTime() - lastSentAt.getTime()) / 60000;
      if (elapsedMinutes < RADAR_CONFIG.minimumIntervalMinutes) {
        return { status: 'cooldown', sent: 0, elapsedMinutes: elapsedMinutes };
      }
    }

    const candidates = collectCandidates_(now, config.githubToken);
    const fresh = candidates.filter(item => !hasSeenUrl_(item.url));
    if (!fresh.length) {
      return { status: 'no_new_items', sent: 0 };
    }

    const preferredKind = state.lastKind === 'github' ? 'news' : 'github';
    const chosen = fresh.find(item => item.kind === preferredKind) || fresh[0];
    const messageId = sendTelegram_(formatPost_(chosen), config.telegramToken, config.telegramChatId);
    markSeenUrl_(chosen.url);

    state.sent.push({
      kind: chosen.kind,
      sentAt: new Date().toISOString(),
      messageId: messageId,
    });
    state.sent = state.sent.slice(-RADAR_CONFIG.recentPostLimit);
    state.lastKind = chosen.kind;
    saveState_(state);
    cleanupSeenUrls_();

    const result = { status: 'sent', sent: 1, kind: chosen.kind, url: chosen.url, messageId: messageId };
    console.log(JSON.stringify(result));
    return result;
  } finally {
    lock.releaseLock();
  }
}

/** Instala um único gatilho recorrente. Execute esta função uma vez. */
function installRadarTrigger() {
  getSecrets_();
  ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === 'runRadarBot')
    .forEach(trigger => ScriptApp.deleteTrigger(trigger));

  ScriptApp.newTrigger('runRadarBot')
    .timeBased()
    .everyMinutes(30)
    .create();

  console.log('Gatilho instalado: runRadarBot será executado a cada 30 minutos.');
}

/** Mostra nos registros o próximo conteúdo, sem publicar no Telegram. */
function previewNextPost() {
  const githubToken = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN') || '';
  const state = loadState_();
  const fresh = collectCandidates_(new Date(), githubToken)
    .filter(item => !hasSeenUrl_(item.url));

  if (!fresh.length) {
    console.log('Nenhum conteúdo novo encontrado.');
    return null;
  }

  const preferredKind = state.lastKind === 'github' ? 'news' : 'github';
  const chosen = fresh.find(item => item.kind === preferredKind) || fresh[0];
  const preview = formatPost_(chosen);
  console.log(preview);
  return preview;
}

/** Confere a configuração sem revelar credenciais e sem publicar mensagens. */
function diagnoseConfiguration() {
  const properties = PropertiesService.getScriptProperties();
  const telegramToken = normalizeSecret_(properties.getProperty('TELEGRAM_BOT_TOKEN'));
  const telegramChatId = normalizeSecret_(properties.getProperty('TELEGRAM_CHAT_ID'));
  const result = {
    telegramTokenConfigured: Boolean(telegramToken && telegramToken !== 'TELEGRAM_BOT_TOKEN'),
    telegramChatIdConfigured: Boolean(telegramChatId && telegramChatId !== 'TELEGRAM_CHAT_ID'),
    githubTokenConfigured: Boolean(normalizeSecret_(properties.getProperty('GITHUB_TOKEN'))),
  };
  console.log(JSON.stringify(result));
  return result;
}

function collectCandidates_(now, githubToken) {
  const candidates = [];
  const errors = [];

  try {
    candidates.push.apply(candidates, fetchGithubProjects_(now, githubToken));
  } catch (error) {
    errors.push('GitHub: ' + error.message);
  }

  try {
    candidates.push.apply(candidates, fetchTechNews_(now));
  } catch (error) {
    errors.push('Hacker News: ' + error.message);
  }

  if (!candidates.length && errors.length) {
    throw new Error(errors.join(' | '));
  }
  if (errors.length) {
    console.warn(errors.join(' | '));
  }
  return candidates;
}

function fetchGithubProjects_(now, githubToken) {
  const cutoff = new Date(now.getTime() - RADAR_CONFIG.githubMaximumAgeDays * 86400000)
    .toISOString().slice(0, 10);
  const headers = {
    Accept: 'application/vnd.github+json',
    'User-Agent': RADAR_CONFIG.userAgent,
  };
  if (githubToken) {
    headers.Authorization = 'Bearer ' + githubToken;
  }

  const byUrl = {};
  RADAR_CONFIG.githubTopics.forEach(topic => {
    const query = 'topic:' + topic + ' created:>' + cutoff + ' stars:>=' + RADAR_CONFIG.githubMinimumStars;
    const url = 'https://api.github.com/search/repositories?q=' + encodeURIComponent(query) +
      '&sort=stars&order=desc&per_page=15';
    const response = UrlFetchApp.fetch(url, { headers: headers, muteHttpExceptions: true });
    ensureSuccess_(response, 'GitHub');
    const data = JSON.parse(response.getContentText());

    (data.items || []).forEach(item => {
      if (!item.html_url || item.archived || item.disabled) return;
      const created = String(item.created_at || '').slice(0, 10);
      const createdAt = new Date(created + 'T00:00:00Z');
      if (isNaN(createdAt.getTime()) || createdAt > now || createdAt < new Date(cutoff + 'T00:00:00Z')) return;
      byUrl[item.html_url] = {
        kind: 'github',
        url: item.html_url,
        title: clean_(item.full_name, 120),
        description: clean_(item.description, 220),
        stars: Number(item.stargazers_count || 0),
        language: clean_(item.language || 'não informada', 40),
        published: created,
      };
    });
  });

  return Object.keys(byUrl)
    .map(url => byUrl[url])
    .sort((a, b) => b.stars - a.stars);
}

function fetchTechNews_(now) {
  const response = UrlFetchApp.fetch('https://news.ycombinator.com/rss', {
    headers: { 'User-Agent': RADAR_CONFIG.userAgent },
    muteHttpExceptions: true,
  });
  ensureSuccess_(response, 'Hacker News');

  const document = XmlService.parse(response.getContentText());
  const channel = document.getRootElement().getChild('channel');
  if (!channel) return [];

  return channel.getChildren('item').map(item => {
    const title = clean_(childText_(item, 'title'), 180);
    const url = childText_(item, 'link');
    const published = childText_(item, 'pubDate');
    const discussion = childText_(item, 'comments');
    if (!title || !isHttpUrl_(url) || !isTech_(title) || !isRecent_(published, now)) return null;
    return {
      kind: 'news',
      url: url,
      title: title,
      published: published,
      discussion: isHttpUrl_(discussion) ? discussion : '',
      source: hostname_(url),
    };
  }).filter(Boolean);
}

function sendTelegram_(text, token, chatId) {
  const response = UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/sendMessage', {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({
      chat_id: chatId,
      text: text,
      disable_web_page_preview: false,
    }),
    muteHttpExceptions: true,
  });
  ensureSuccess_(response, 'Telegram');
  const data = JSON.parse(response.getContentText());
  if (!data.ok) throw new Error('Telegram: ' + (data.description || 'falha desconhecida'));
  return data.result && data.result.message_id;
}

function formatPost_(item) {
  if (item.kind === 'github') {
    let descriptionPt = item.description || 'O autor ainda não publicou uma descrição detalhada.';
    if (item.description) {
      try {
        descriptionPt = LanguageApp.translate(item.description, '', 'pt');
      } catch (err) {
        console.warn('Falha na tradução automática: ' + err.message);
      }
    }

    return '📡 RADAR TECH OPEN SOURCE\n🚀 PROJETO NOVO NO GITHUB\n\n' +
      '📦 ' + item.title + '\n\n' +
      '💡 O que é e o que é capaz de fazer:\n' + descriptionPt + '\n\n' +
      '⭐ ' + item.stars + ' estrelas • Linguagem: ' + item.language + '\n' +
      '📅 Criado em: ' + item.published + '\n\n' +
      '🔗 Código e detalhes: ' + item.url;
  }

  let titlePt = item.title;
  try {
    titlePt = LanguageApp.translate(item.title, '', 'pt');
  } catch (err) {
    console.warn('Falha na tradução de notícia: ' + err.message);
  }

  const discussion = item.discussion ? '\n💬 Discussão no Hacker News: ' + item.discussion : '';
  const original = titlePt !== item.title ? '\n📌 Título original: ' + item.title : '';
  return '📡 RADAR TECH OPEN SOURCE\n📰 NOTÍCIA DE TECNOLOGIA\n\n' +
    titlePt + '\n' +
    original + '\n' +
    '🌐 Fonte: ' + item.source + '\n\n' +
    '🔗 Leia na fonte: ' + item.url + discussion;
}


function getSecrets_() {
  const properties = PropertiesService.getScriptProperties();
  const telegramToken = normalizeSecret_(properties.getProperty('TELEGRAM_BOT_TOKEN'));
  const telegramChatId = normalizeSecret_(properties.getProperty('TELEGRAM_CHAT_ID'));
  const missing = [];
  if (!telegramToken || telegramToken === 'TELEGRAM_BOT_TOKEN') missing.push('TELEGRAM_BOT_TOKEN');
  if (!telegramChatId || telegramChatId === 'TELEGRAM_CHAT_ID') missing.push('TELEGRAM_CHAT_ID');
  if (missing.length) {
    throw new Error(
      'Propriedades ausentes ou inválidas: ' + missing.join(', ') +
      '. Abra Configurações do projeto > Propriedades do script.'
    );
  }
  return {
    telegramToken: telegramToken,
    telegramChatId: telegramChatId,
    githubToken: normalizeSecret_(properties.getProperty('GITHUB_TOKEN')),
  };
}

function normalizeSecret_(value) {
  return String(value || '').trim().replace(/^['"]|['"]$/g, '');
}

function loadState_() {
  const raw = PropertiesService.getScriptProperties().getProperty('RADAR_STATE');
  if (!raw) return { sent: [], lastKind: '' };
  try {
    const parsed = JSON.parse(raw);
    return {
      sent: Array.isArray(parsed.sent) ? parsed.sent : [],
      lastKind: parsed.lastKind || '',
    };
  } catch (error) {
    console.warn('Estado inválido; iniciando um novo histórico.');
    return { sent: [], lastKind: '' };
  }
}

function saveState_(state) {
  PropertiesService.getScriptProperties().setProperty('RADAR_STATE', JSON.stringify(state));
}

function hasSeenUrl_(url) {
  return Boolean(PropertiesService.getScriptProperties().getProperty(seenKey_(url)));
}

function markSeenUrl_(url) {
  PropertiesService.getScriptProperties().setProperty(seenKey_(url), String(Date.now()));
}

function seenKey_(url) {
  const digest = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    String(url),
    Utilities.Charset.UTF_8
  );
  const shortDigest = Utilities.base64EncodeWebSafe(digest.slice(0, 12)).replace(/=+$/, '');
  return 'SEEN_' + shortDigest;
}

function cleanupSeenUrls_() {
  const properties = PropertiesService.getScriptProperties();
  const all = properties.getProperties();
  const cutoff = Date.now() - RADAR_CONFIG.seenUrlRetentionDays * 86400000;
  const expired = Object.keys(all).filter(key => {
    return key.indexOf('SEEN_') === 0 && Number(all[key]) < cutoff;
  });
  expired.forEach(key => properties.deleteProperty(key));
}

function ensureSuccess_(response, service) {
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error(service + ' respondeu HTTP ' + code + ': ' + response.getContentText().slice(0, 300));
  }
}

function childText_(element, name) {
  const child = element.getChild(name);
  return child ? child.getText().trim() : '';
}

function clean_(value, limit) {
  return String(value || '').replace(/\s+/g, ' ').trim().slice(0, limit);
}

function isTech_(title) {
  const value = String(title || '').toLocaleLowerCase('pt-BR');
  return TECH_TERMS.some(term => value.indexOf(term) !== -1);
}

function isRecent_(value, now) {
  const published = new Date(value);
  if (isNaN(published.getTime())) return false;
  const age = now.getTime() - published.getTime();
  return age >= -5 * 60000 && age <= RADAR_CONFIG.newsMaximumAgeHours * 3600000;
}

function isHttpUrl_(value) {
  return /^https:\/\//i.test(String(value || ''));
}

function hostname_(value) {
  const match = String(value || '').match(/^https:\/\/([^/]+)/i);
  return match ? match[1] : 'fonte original';
}
