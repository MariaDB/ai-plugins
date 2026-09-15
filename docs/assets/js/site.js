// Copyright (c) 2026, MariaDB plc.
//
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License, version 2.0,
// as published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
// the GNU General Public License, version 2.0, for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software Foundation, Inc.,
// 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

/* MariaDB AI Plugins DevHub — progressive enhancement only.
   Everything here is optional: the page is fully readable with JS disabled. */
(function () {
  'use strict';

  /* --- Theme toggle ------------------------------------------------------ */
  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('mdb-theme', next); } catch (e) { /* private mode */ }
    });
  }

  /* --- Mobile nav -------------------------------------------------------- */
  var navToggle = document.getElementById('nav-toggle');
  var navLinks = document.getElementById('nav-links');
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', function () {
      var open = navToggle.getAttribute('aria-expanded') === 'true';
      navToggle.setAttribute('aria-expanded', String(!open));
      navLinks.hidden = open;
    });
  }

  /* --- Table of contents, built from the article's own headings ---------- */
  var toc = document.getElementById('toc');
  var article = document.querySelector('.article-layout .prose');
  if (toc && article) {
    var headings = article.querySelectorAll('h2[id], h3[id]');
    if (headings.length >= 3) {
      var list = toc.querySelector('ul');
      var links = [];
      Array.prototype.forEach.call(headings, function (h) {
        var li = document.createElement('li');
        var a = document.createElement('a');
        a.href = '#' + h.id;
        a.textContent = h.textContent.trim();
        if (h.tagName === 'H3') { a.style.paddingLeft = '1.6rem'; a.style.fontSize = '.95em'; }
        li.appendChild(a);
        list.appendChild(li);
        links.push({ a: a, el: h });
      });
      toc.hidden = false;

      if ('IntersectionObserver' in window) {
        var visible = new Set();
        var io = new IntersectionObserver(function (entries) {
          entries.forEach(function (e) {
            if (e.isIntersecting) visible.add(e.target); else visible.delete(e.target);
          });
          var active = null;
          for (var i = 0; i < links.length; i++) {
            if (visible.has(links[i].el)) { active = links[i]; break; }
          }
          links.forEach(function (l) { l.a.classList.toggle('is-active', l === active); });
        }, { rootMargin: '-70px 0px -70% 0px' });
        links.forEach(function (l) { io.observe(l.el); });
      }
    }
  }

  /* --- Hero code samples: mark the ones that are cut off ------------------ */
  var codeBodies = Array.prototype.slice.call(document.querySelectorAll('.hero-panel__body'));
  var codePanels = codeBodies.map(function (body) {
    return { body: body, pre: body.querySelector('.hero-code') };
  }).filter(function (p) { return p.pre; });

  if (codePanels.length) {
    /* Below this many pixels hidden, say nothing. It absorbs sub-pixel layout,
       and a sliver narrower than one character is not worth a marker — the fade
       that comes with it would cover more than the sliver it announces. */
    var EDGE_SLACK = 8;

    var markClipped = function () {
      codePanels.forEach(function (p) {
        /* How much is still hidden to the RIGHT, so the marker clears once the
           reader reaches the end rather than staying on because the sample is
           wide. */
        var hidden = p.pre.scrollWidth - p.pre.clientWidth - p.pre.scrollLeft;
        p.body.classList.toggle('is-clipped', hidden > EDGE_SLACK);
      });
    };

    codePanels.forEach(function (p) {
      p.pre.addEventListener('scroll', markClipped, { passive: true });
    });
    /* The panel is resized by the container query, by the hero going two-column
       and by a phone rotating; ResizeObserver catches all three, and the resize
       listener covers browsers without it. */
    if ('ResizeObserver' in window) {
      var ro = new ResizeObserver(markClipped);
      codePanels.forEach(function (p) { ro.observe(p.pre); });
    } else {
      window.addEventListener('resize', markClipped);
    }
    markClipped();
  }

  /* --- Tutorial catalog filters ------------------------------------------ */
  var filters = document.querySelector('[data-filters]');
  if (filters) {
    var cards = Array.prototype.slice.call(document.querySelectorAll('[data-level]'));
    var empty = document.getElementById('filter-empty');
    var state = { level: 'all', area: 'all' };

    function apply() {
      var shown = 0;
      cards.forEach(function (c) {
        var ok = (state.level === 'all' || c.dataset.level === state.level) &&
                 (state.area === 'all' || c.dataset.area === state.area);
        c.hidden = !ok;
        if (ok) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
    }

    filters.addEventListener('click', function (ev) {
      var btn = ev.target.closest('.filter-btn');
      if (!btn) return;
      var group = btn.dataset.group;
      state[group] = btn.dataset.value;
      filters.querySelectorAll('.filter-btn[data-group="' + group + '"]').forEach(function (b) {
        b.setAttribute('aria-pressed', String(b === btn));
      });
      apply();
    });
    apply();
  }
})();
