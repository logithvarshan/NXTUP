/* ═══════════════════════════════════════════════════════════════════════
   NXTUP — Main JavaScript
   ═══════════════════════════════════════════════════════════════════════ */

'use strict';

// ── Dark / Light Theme Toggle ─────────────────────────────────────────
(function initThemeToggle() {
  const STORAGE_KEY = 'nxtup-theme';
  const root = document.documentElement;
  const metaThemeColor = document.querySelector('meta[name="theme-color"]');
  const buttons = document.querySelectorAll('[data-theme-toggle]');

  function getCurrentTheme() {
    return root.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  }

  function applyTheme(theme, persist) {
    const normalized = theme === 'light' ? 'light' : 'dark';
    root.setAttribute('data-theme', normalized);

    if (metaThemeColor) {
      const targetColor = normalized === 'light'
        ? (metaThemeColor.getAttribute('data-light-theme-color') || '#F7F8F5')
        : (metaThemeColor.getAttribute('data-dark-theme-color') || '#0B0B0B');
      metaThemeColor.setAttribute('content', targetColor);
    }

    buttons.forEach(btn => {
      const isLight = normalized === 'light';
      btn.setAttribute('aria-pressed', String(isLight));
      btn.setAttribute('aria-label', isLight ? 'Light mode active. Switch to dark mode' : 'Dark mode active. Switch to light mode');
      btn.setAttribute('title', isLight ? 'Light Mode (switch to Dark)' : 'Dark Mode (switch to Light)');
    });

    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, normalized);
      } catch (e) {
        // Ignore storage restrictions
      }
    }
  }

  applyTheme(getCurrentTheme(), false);

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const next = getCurrentTheme() === 'light' ? 'dark' : 'light';
      applyTheme(next, true);
    });
  });
})();

// ── Scroll fade-in animations ─────────────────────────────────────────
(function initScrollAnimations() {
  const els = document.querySelectorAll('.scroll-fade-in');
  if (!els.length) return;

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) {
    els.forEach(el => el.classList.add('visible'));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          observer.unobserve(e.target);
        }
      });
    },
    { threshold: 0.08, rootMargin: '0px 0px -20px 0px' }
  );

  els.forEach(el => observer.observe(el));
})();

// ── Accordion ─────────────────────────────────────────────────────────
(function initAccordions() {
  document.querySelectorAll('.accordion-header').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.accordion-item');
      const isOpen = item.classList.contains('open');
      item.closest('.accordion')?.querySelectorAll('.accordion-item').forEach(i => {
        i.classList.remove('open');
        const body = i.querySelector('.accordion-body');
        if (body) body.style.display = '';
      });
      if (!isOpen) {
        item.classList.add('open');
      }
    });
  });
})();

// ── Mobile filter toggle ──────────────────────────────────────────────
(function initFilterToggle() {
  const toggleBtn = document.getElementById('filter-toggle');
  const panel = document.getElementById('filter-panel');
  if (!toggleBtn || !panel) return;

  toggleBtn.addEventListener('click', () => {
    panel.classList.toggle('collapsed');
    const isOpen = !panel.classList.contains('collapsed');
    toggleBtn.setAttribute('aria-expanded', isOpen);
    const label = toggleBtn.querySelector('.filter-toggle-label');
    if (label) label.textContent = isOpen ? 'Hide Filters' : 'Show Filters';
  });
})();

// ── Surprise Me ───────────────────────────────────────────────────────
(function initSurpriseMe() {
  const btn = document.getElementById('surprise-btn');
  const tryAnotherBtn = document.getElementById('surprise-try-another');
  const resultEl = document.getElementById('surprise-result');
  const loadingEl = document.getElementById('surprise-loading');

  if (!btn) return;

  let lastEventId = null;

  async function fetchSurprise() {
    if (loadingEl) loadingEl.style.display = 'flex';
    if (resultEl) resultEl.style.display = 'none';
    if (tryAnotherBtn) tryAnotherBtn.style.display = 'none';
    btn.disabled = true;
    if (tryAnotherBtn) tryAnotherBtn.disabled = true;

    try {
      const url = `/api/surprise-me${lastEventId ? `?exclude=${lastEventId}` : ''}`;
      const res = await fetch(url);
      const data = await res.json();

      if (loadingEl) loadingEl.style.display = 'none';
      btn.disabled = false;
      if (tryAnotherBtn) tryAnotherBtn.disabled = false;

      if (!res.ok || data.error) {
        showSurpriseError(data.error || 'No experiences available right now.');
        return;
      }

      lastEventId = data.id;
      showSurpriseResult(data);
    } catch (err) {
      if (loadingEl) loadingEl.style.display = 'none';
      btn.disabled = false;
      if (tryAnotherBtn) tryAnotherBtn.disabled = false;
      showSurpriseError('Something went wrong. Please try again.');
    }
  }

  function showSurpriseResult(event) {
    if (!resultEl) return;

    const date = new Date(event.start_datetime);
    const dateStr = date.toLocaleDateString('en-IN', {
      weekday: 'short', day: 'numeric', month: 'short'
    });

    const price = event.price === 0 ? 'Free' : `₹${event.price.toLocaleString('en-IN')}`;

    resultEl.innerHTML = `
      <div class="surprise-card">
        <div class="surprise-card__reveal">✨ We picked this for you</div>
        <h3 class="surprise-card__title">${escHtml(event.title)}</h3>
        <p class="surprise-card__desc">${escHtml(event.short_description)}</p>
        <div class="surprise-card__meta">
          <span>📅 ${dateStr}</span>
          <span>📍 ${escHtml(event.location_name || event.city)}</span>
          <span>⏱ ${escHtml(event.duration_display)}</span>
          <span>💰 ${price}</span>
        </div>
        <div class="surprise-card__avail">${escHtml(event.availability_label)}</div>
        <div class="surprise-card__actions">
          <a href="${event.url}" class="btn btn-primary">View This Plan →</a>
        </div>
      </div>
    `;

    resultEl.style.display = 'block';
    if (tryAnotherBtn) tryAnotherBtn.style.display = 'inline-flex';
    resultEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function showSurpriseError(msg) {
    if (!resultEl) return;
    resultEl.innerHTML = `<div class="alert alert-info" style="text-align:center">${escHtml(msg)}</div>`;
    resultEl.style.display = 'block';
  }

  btn.addEventListener('click', fetchSurprise);
  if (tryAnotherBtn) tryAnotherBtn.addEventListener('click', fetchSurprise);
})();

// ── Rating stars (interactive) ────────────────────────────────────────
(function initStarRating() {
  const container = document.getElementById('star-rating');
  const input = document.getElementById('rating-input');
  if (!container || !input) return;

  const stars = container.querySelectorAll('.star-btn');
  let selected = parseInt(input.value, 10) || 0;
  highlight(selected);

  stars.forEach((star, idx) => {
    star.addEventListener('mouseenter', () => highlight(idx + 1));
    star.addEventListener('mouseleave', () => highlight(selected));
    star.addEventListener('click', () => {
      selected = idx + 1;
      input.value = selected;
      highlight(selected);
    });
  });

  function highlight(n) {
    stars.forEach((s, i) => {
      s.style.color = i < n ? '#FFB84D' : 'var(--text-muted)';
    });
  }
})();

// ── Form client validation ────────────────────────────────────────────
(function initFormValidation() {
  document.querySelectorAll('form[data-validate]').forEach(form => {
    form.addEventListener('submit', e => {
      let firstInvalid = null;

      form.querySelectorAll('[required], [minlength], [type="email"]').forEach(field => {
        const errEl = field.parentElement.querySelector('.form-error');
        const val = field.value.trim();
        let msg = '';

        if (field.hasAttribute('required') && !val) {
          msg = 'This field is required.';
        } else if (val && field.type === 'email' && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(val)) {
          msg = 'Please enter a valid email address.';
        } else if (val && field.minLength > 0 && val.length < field.minLength) {
          msg = `Please enter at least ${field.minLength} characters.`;
        }

        if (msg) {
          if (errEl) errEl.textContent = msg;
          field.style.borderColor = 'var(--error)';
          if (!firstInvalid) firstInvalid = field;
        } else {
          if (errEl) errEl.textContent = '';
          field.style.borderColor = '';
        }
      });

      if (firstInvalid) {
        e.preventDefault();
        firstInvalid.focus();
      }
    });
  });
})();

// ── Scroll-to-top ──────────────────────────────────────────────────────
(function initScrollTop() {
  const btn = document.getElementById('scroll-top');
  if (!btn) return;

  window.addEventListener('scroll', () => {
    btn.style.opacity = window.scrollY > 400 ? '1' : '0';
    btn.style.pointerEvents = window.scrollY > 400 ? 'auto' : 'none';
  }, { passive: true });

  btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
})();

// ── Utility: escape HTML ──────────────────────────────────────────────
function escHtml(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(str || ''));
  return d.innerHTML;
}

// ── Auto-dismiss flash messages ────────────────────────────────────────
(function initFlashDismiss() {
  document.querySelectorAll('.flash-msg').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 4500);
  });
})();
