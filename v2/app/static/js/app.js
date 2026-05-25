/* Sistema de Leads V2 — UI helpers (vanilla, zero deps) */

(function () {
  'use strict';

  // ────── Toast ──────
  const ICONS = {
    success: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    fail: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
  };

  function ensureContainer() {
    let c = document.querySelector('.toast-container');
    if (!c) {
      c = document.createElement('div');
      c.className = 'toast-container';
      document.body.appendChild(c);
    }
    return c;
  }

  window.toast = function (message, type = 'info', ms = 3600) {
    const c = ensureContainer();
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<span class="toast-icon">${ICONS[type] || ICONS.info}</span><span>${message}</span>`;
    c.appendChild(t);
    setTimeout(() => {
      t.classList.add('leave');
      t.addEventListener('animationend', () => t.remove(), { once: true });
    }, ms);
  };

  // Flash toasts from query string
  const params = new URLSearchParams(location.search);
  if (params.has('toast')) {
    toast(params.get('toast'), params.get('toast_type') || 'success');
    params.delete('toast'); params.delete('toast_type');
    const q = params.toString();
    history.replaceState(null, '', location.pathname + (q ? '?' + q : ''));
  }

  // ────── Modal ──────
  window.openModal = function (id) {
    const m = document.getElementById(id);
    if (m) m.classList.add('show');
  };
  window.closeModal = function (id) {
    const m = document.getElementById(id);
    if (m) m.classList.remove('show');
  };
  document.addEventListener('click', e => {
    if (e.target.matches('.modal-backdrop')) e.target.classList.remove('show');
    if (e.target.dataset.modalClose) closeModal(e.target.dataset.modalClose);
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.querySelectorAll('.modal-backdrop.show').forEach(m => m.classList.remove('show'));
  });

  // ────── Copy to clipboard ──────
  document.addEventListener('click', async e => {
    const el = e.target.closest('[data-copy]');
    if (!el) return;
    e.preventDefault();
    const txt = el.dataset.copy;
    try {
      await navigator.clipboard.writeText(txt);
      toast('Copiado!', 'success', 1800);
    } catch (err) { toast('Não foi possível copiar', 'fail'); }
  });

  // ────── Confirm before destructive ──────
  document.addEventListener('click', e => {
    const el = e.target.closest('[data-confirm]');
    if (!el) return;
    if (!confirm(el.dataset.confirm)) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  // ────── Bulk select (rows + master) ──────
  function initBulk() {
    const tables = document.querySelectorAll('[data-bulk]');
    tables.forEach(tbl => {
      const master = tbl.querySelector('[data-bulk-master]');
      const rows = () => tbl.querySelectorAll('[data-bulk-row]');
      const bar = document.querySelector('[data-bulk-bar]');
      const countEl = document.querySelector('[data-bulk-count]');

      function refresh() {
        const checked = tbl.querySelectorAll('[data-bulk-row]:checked');
        const n = checked.length;
        if (countEl) countEl.textContent = n;
        if (bar) bar.classList.toggle('show', n > 0);
        rows().forEach(cb => cb.closest('tr')?.classList.toggle('selected', cb.checked));
        if (master) master.checked = n > 0 && n === rows().length;
      }

      if (master) master.addEventListener('change', () => {
        rows().forEach(cb => cb.checked = master.checked);
        refresh();
      });
      tbl.addEventListener('change', e => {
        if (e.target.matches('[data-bulk-row]')) refresh();
      });
    });

    // Wire bulk-action buttons
    document.querySelectorAll('[data-bulk-action]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const ids = Array.from(document.querySelectorAll('[data-bulk-row]:checked')).map(cb => cb.value);
        if (ids.length === 0) return;
        const action = btn.dataset.bulkAction;
        const value = btn.dataset.bulkValue || '';
        if (btn.dataset.confirm && !confirm(btn.dataset.confirm.replace('{n}', ids.length))) return;
        try {
          btn.disabled = true;
          const res = await fetch('/api/leads/bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids.map(Number), action, value }),
          });
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          toast(`${data.updated} leads actualizados`, 'success');
          setTimeout(() => location.reload(), 700);
        } catch (e) {
          toast('Falha: ' + e.message, 'fail');
        } finally {
          btn.disabled = false;
        }
      });
    });
  }

  // ────── Export CSV ──────
  document.querySelectorAll('[data-export]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      const params = new URLSearchParams(location.search);
      const url = `/api/leads/export?${params.toString()}`;
      window.location.href = url;
    });
  });

  // ────── Gooey Search ──────
  function initGooeySearch() {
    const root = document.querySelector('[data-gooey-search]');
    if (!root) return;

    const button = root.querySelector('[data-gooey-button]');
    const input = root.querySelector('.gooey-input');
    const panel = root.querySelector('[data-gooey-panel]');

    // Detect Safari / iOS Chrome — disable gooey filter (creates artefacts)
    const ua = (navigator.userAgent || '').toLowerCase();
    const isUnsupported =
      (ua.includes('safari') && !ua.includes('chrome') && !ua.includes('chromium') && !ua.includes('android') && !ua.includes('firefox'))
      || ua.includes('crios');
    if (isUnsupported) root.classList.add('no-goo');

    let debounceTimer = null;
    let lastFocused = -1;
    let currentResults = [];

    function expand() {
      root.classList.add('open');
      setTimeout(() => input.focus(), 220);
    }

    function collapse() {
      root.classList.remove('open', 'loading', 'has-results');
      input.value = '';
      panel.innerHTML = '';
      currentResults = [];
      lastFocused = -1;
    }

    button.addEventListener('click', (e) => {
      if (!root.classList.contains('open')) {
        e.preventDefault();
        expand();
      }
    });

    document.addEventListener('click', (e) => {
      if (!root.contains(e.target) && root.classList.contains('open')) {
        collapse();
      }
    });

    // Cmd/Ctrl+K to open
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (root.classList.contains('open')) input.focus();
        else expand();
      }
      if (e.key === 'Escape' && root.classList.contains('open')) {
        collapse();
      }
    });

    // Keyboard navigation in results
    input.addEventListener('keydown', (e) => {
      if (!root.classList.contains('has-results')) return;
      const items = panel.querySelectorAll('.gooey-panel-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        lastFocused = Math.min(items.length - 1, lastFocused + 1);
        items.forEach((it, i) => it.classList.toggle('focused', i === lastFocused));
        items[lastFocused]?.scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        lastFocused = Math.max(0, lastFocused - 1);
        items.forEach((it, i) => it.classList.toggle('focused', i === lastFocused));
        items[lastFocused]?.scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'Enter') {
        if (lastFocused >= 0 && items[lastFocused]) {
          e.preventDefault();
          items[lastFocused].click();
        } else if (input.value.trim()) {
          window.location.href = `/leads?q=${encodeURIComponent(input.value.trim())}`;
        }
      }
    });

    // Debounced fetch
    input.addEventListener('input', () => {
      const q = input.value.trim();
      clearTimeout(debounceTimer);
      if (!q) {
        root.classList.remove('loading', 'has-results');
        panel.innerHTML = '';
        return;
      }
      root.classList.add('loading');
      debounceTimer = setTimeout(async () => {
        try {
          const res = await fetch(`/api/leads?q=${encodeURIComponent(q)}&limit=8`);
          if (!res.ok) throw new Error('search failed');
          currentResults = await res.json();
          renderResults(currentResults, q);
        } catch (err) {
          panel.innerHTML = `<div class="gooey-panel-empty">Erro na pesquisa</div>`;
          root.classList.add('has-results');
        } finally {
          root.classList.remove('loading');
        }
      }, 280);
    });

    function renderResults(items, q) {
      if (!items.length) {
        panel.innerHTML = `<div class="gooey-panel-empty">
          Nenhum lead encontrado para "<strong>${escapeHtml(q)}</strong>".
          <br><br>
          <a href="/leads?q=${encodeURIComponent(q)}" style="color: var(--brand-2)">Procurar com filtros completos →</a>
        </div>`;
        root.classList.add('has-results');
        return;
      }
      panel.innerHTML = items.map(l => {
        const scoreCls = ((l.score || 0) >> 0) >= 75 ? 'score-4' : (l.score || 0) >= 50 ? 'score-3' : (l.score || 0) >= 25 ? 'score-2' : 'score-1';
        const scoreText = l.score != null ? l.score : '—';
        const stage = l.stage ? `<span class="stage stage-${l.stage}" style="font-size: 9.5px;">${l.stage}</span>` : '';
        const contact = l.phone_e164 || l.email || l.city || '';
        return `
          <a class="gooey-panel-item" href="/leads/${l.id}">
            <span class="score ${scoreCls}">${scoreText}</span>
            <span class="gooey-pi-name">${escapeHtml(l.name || '—')}</span>
            <span class="gooey-pi-meta">${escapeHtml(contact)}</span>
            ${stage}
          </a>
        `;
      }).join('') + `<a class="gooey-panel-item" href="/leads?q=${encodeURIComponent(q)}" style="border-top: 1px solid var(--border); color: var(--brand-2); justify-content: center; margin-top: 4px; padding-top: 9px;">Ver todos os resultados de "${escapeHtml(q)}" →</a>`;
      root.classList.add('has-results');
      lastFocused = -1;
    }
  }

  // ────── Live preview (campaign templates) ──────
  function initLivePreview() {
    const wrap = document.querySelector('[data-preview]');
    if (!wrap) return;
    const sources = wrap.querySelectorAll('[data-tmpl]');
    sources.forEach(src => {
      src.addEventListener('input', () => render(src));
      render(src);
    });
    function render(src) {
      const target = document.getElementById(src.dataset.tmpl);
      if (!target) return;
      // Sanitize then replace placeholders with pills
      let val = escapeHtml(src.value);
      val = val
        .replace(/\{\{\s*nome\s*\}\}/gi, '<span class="placeholder-pill">João</span>')
        .replace(/\{\{\s*nome_negocio\s*\}\}/gi, '<span class="placeholder-pill">Padaria Central</span>')
        .replace(/\{\{\s*cidade\s*\}\}/gi, '<span class="placeholder-pill">Lisboa</span>')
        .replace(/\{\{\s*nicho\s*\}\}/gi, '<span class="placeholder-pill">padaria</span>')
        .replace(/\{\{\s*personalizacao\s*\}\}/gi, '<span class="placeholder-pill">frase única da IA</span>');
      target.innerHTML = val.replace(/\n/g, '<br>');
    }
  }

  // ────── Health check live refresh ──────
  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function initHealth() {
    const grid = document.querySelector('[data-health-grid]');
    if (!grid) return;
    async function load() {
      try {
        const res = await fetch('/api/health/detailed');
        const data = await res.json();
        grid.innerHTML = data.checks.map(c => {
          const badge = c.status === 'ok' ? 'success dot' : c.status === 'fail' ? 'bad dot' : 'dot';
          const label = c.status === 'ok' ? 'Operacional' : c.status === 'fail' ? 'Falha' : 'Desactivado';
          const icon = c.status === 'ok' ? ICONS.success : c.status === 'fail' ? ICONS.fail : ICONS.info;
          const hint = c.hint ? `<div class="status-hint">→ ${escapeHtml(c.hint)}</div>` : '';
          const lat = c.latency_ms != null ? `<span class="status-latency ml-auto">${c.latency_ms}ms</span>` : '';
          return `
            <div class="status-card ${c.status}">
              <div class="status-head">
                <div class="status-icon">${icon}</div>
                <div>
                  <div class="status-name">${escapeHtml(c.name)}</div>
                  <div class="badge ${badge}">${label}</div>
                </div>
                ${lat}
              </div>
              <div class="status-msg">${escapeHtml(c.message)}</div>
              ${hint}
            </div>
          `;
        }).join('');
      } catch (e) {
        grid.innerHTML = '<div class="empty"><div class="empty-desc">Falha ao carregar estado das integrações.</div></div>';
      }
    }
    load();
    setInterval(load, 30000);
  }

  // ────── Init ──────
  document.addEventListener('DOMContentLoaded', () => {
    initBulk();
    initLivePreview();
    initHealth();
    initGooeySearch();
  });
})();
