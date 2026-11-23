/* SymptoSense — Health knowledge graph explorer (V292).
   Shows one item and its direct links at a time. Phones get the list only; wider screens also
   get a radial drawing. All text is inserted with textContent (no HTML from the server). */
(function () {
  'use strict';
  var root = document.getElementById('kgRoot');
  if (!root) return;
  var lang = root.getAttribute('data-lang') === 'en' ? 'en' : 'ar';
  var T = {};
  try { T = JSON.parse(document.getElementById('kgText').textContent || '{}'); } catch (e) { T = {}; }
  var ORDER = ['condition', 'symptom', 'lab', 'medicine', 'source'];
  var COLOR = { condition: '#F59E0B', symptom: '#3B82C4', lab: '#E5484D', medicine: '#8B6CDB', source: '#22A35A' };
  var panel = document.getElementById('kgPanel');
  var canvas = document.getElementById('kgCanvas');
  var input = document.getElementById('kgSearch');
  var sugg = document.getElementById('kgSugg');
  var SVGNS = 'http://www.w3.org/2000/svg';
  var current = '';

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function api(params) {
    var qs = Object.keys(params).map(function (k) { return k + '=' + encodeURIComponent(params[k]); }).join('&');
    return fetch('/api/knowledge-graph?' + qs + '&lang=' + lang, { headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); });
  }

  function open(id, push) {
    if (!id) return;
    api({ node: id }).then(function (d) {
      if (!d || !d.ok) return;
      current = id;
      renderPanel(d);
      renderCanvas(d);
      if (push !== false) { try { history.replaceState(null, '', '#' + encodeURIComponent(id)); } catch (e) {} }
    }).catch(function () {});
  }

  function renderPanel(d) {
    panel.textContent = '';
    var head = el('div', 'kg-center');
    var type = el('div', 'kg-center-type kg-t-' + d.center.type, d.center.type_label);
    head.appendChild(type);
    head.appendChild(el('h2', '', d.center.label));
    if (d.center.note) head.appendChild(el('p', 'kg-limit', d.center.note));
    panel.appendChild(head);
    var groups = {};
    d.links.forEach(function (l) { (groups[l.node.type] = groups[l.node.type] || []).push(l); });
    ORDER.forEach(function (t) {
      if (!groups[t]) return;
      var g = el('div', 'kg-group');
      var h = el('h3');
      h.appendChild(el('span', 'kg-dot kg-d-' + t));
      h.appendChild(document.createTextNode((T.labels && T.labels[t]) || t));
      g.appendChild(h);
      var ul = el('ul');
      groups[t].forEach(function (l) {
        var li = el('li', 'kg-link');
        if (l.node.type === 'source' && l.node.url) {
          var a = el('a', '', l.node.label);
          a.href = l.node.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
          a.style.gridRow = 'auto'; a.style.gridColumn = '1/3'; a.style.whiteSpace = 'normal'; a.style.fontSize = '14px';
          li.appendChild(a);
        } else {
          var b = el('button', '', l.node.label);
          b.type = 'button';
          b.addEventListener('click', function () { open(l.node.id); window.scrollTo({ top: root.offsetTop, behavior: 'smooth' }); });
          li.appendChild(b);
          if (l.evidence_url) {
            var src = el('a', '', l.evidence_label || T.source || 'Source');
            src.href = l.evidence_url; src.target = '_blank'; src.rel = 'noopener noreferrer';
            li.appendChild(src);
          }
        }
        li.appendChild(el('small', '', l.relation));
        ul.appendChild(li);
      });
      g.appendChild(ul);
      // V292.1: each relation kind says once what it does not mean (source scope, group-level, not causation)
      var limits = [];
      groups[t].forEach(function (l) { if (l.limit && limits.indexOf(l.limit) < 0) limits.push(l.limit); });
      limits.forEach(function (txt) { g.appendChild(el('p', 'kg-limit', txt)); });
      panel.appendChild(g);
    });
    if (d.total_links > d.links.length) panel.appendChild(el('p', 'kg-more', '+' + (d.total_links - d.links.length) + ' ' + (T.more || '')));
  }

  function renderCanvas(d) {
    if (!canvas || getComputedStyle(canvas).display === 'none') return;
    canvas.textContent = '';
    var W = 640, H = 500, cx = W / 2, cy = H / 2;
    var svg = document.createElementNS(SVGNS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('role', 'img');
    svg.setAttribute('direction', 'ltr'); svg.style.direction = 'ltr'; // anchors mean left/right even on Arabic pages
    var links = d.links.filter(function (l) { return l.node.type !== 'source'; }).slice(0, 12);
    var n = links.length || 1;
    var R = Math.min(W, H) / 2 - 70;
    links.forEach(function (l, i) {
      var ang = (-Math.PI / 2) + (2 * Math.PI * i / n);
      var r = R; // one ring: alternating radii made outer labels collide with inner ones
      l._x = cx + r * Math.cos(ang); l._y = cy + r * Math.sin(ang);
      var line = document.createElementNS(SVGNS, 'line');
      line.setAttribute('x1', cx); line.setAttribute('y1', cy); line.setAttribute('x2', l._x); line.setAttribute('y2', l._y);
      line.setAttribute('class', 'kg-edge');
      line.setAttribute('stroke-width', String(0.8 + 2.4 * (l.weight || 0.4)));
      svg.appendChild(line);
    });
    function nodeG(x, y, r, color, label, id, big) {
      var g = document.createElementNS(SVGNS, 'g');
      g.setAttribute('class', 'kg-n');
      if (id) { g.setAttribute('tabindex', '0'); g.addEventListener('click', function () { open(id); }); g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(id); } }); }
      var c = document.createElementNS(SVGNS, 'circle');
      c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('r', r); c.setAttribute('fill', color);
      c.setAttribute('stroke', '#fff'); c.setAttribute('stroke-width', '2');
      g.appendChild(c);
      var t = document.createElementNS(SVGNS, 'text');
      // labels point away from the centre so neighbours do not overlap
      var dx = x - W / 2;
      if (big || Math.abs(dx) < 12) { t.setAttribute('x', x); t.setAttribute('y', y + r + 15); t.setAttribute('text-anchor', 'middle'); }
      else { t.setAttribute('x', x + (dx > 0 ? r + 5 : -(r + 5))); t.setAttribute('y', y + 4); t.setAttribute('text-anchor', dx > 0 ? 'start' : 'end'); }
      if (big) t.setAttribute('font-weight', '800');
      t.textContent = label.length > 20 ? label.slice(0, 19) + '…' : label;
      g.appendChild(t);
      return g;
    }
    links.forEach(function (l) { svg.appendChild(nodeG(l._x, l._y, 9, COLOR[l.node.type] || '#94A3B8', l.node.label, l.node.id)); });
    svg.appendChild(nodeG(cx, cy, 18, COLOR[d.center.type] || '#334155', d.center.label, null, true));
    canvas.appendChild(svg);
  }

  var timer = null;
  input.addEventListener('input', function () {
    clearTimeout(timer);
    var q = input.value.trim();
    if (!q) { sugg.hidden = true; return; }
    timer = setTimeout(function () {
      api({ q: q }).then(function (d) {
        sugg.textContent = '';
        var res = (d && d.results) || [];
        if (!res.length) { sugg.appendChild(el('button', '', T.empty || '')); }
        res.forEach(function (r) {
          var b = el('button'); b.type = 'button';
          b.appendChild(el('span', '', r.label));
          b.appendChild(el('small', '', r.type_label));
          b.addEventListener('click', function () { sugg.hidden = true; input.value = r.label; open(r.id); });
          sugg.appendChild(b);
        });
        sugg.hidden = false;
      }).catch(function () {});
    }, 180);
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('.kg-search')) sugg.hidden = true; });
  root.querySelectorAll('[data-kg-node]').forEach(function (b) { b.addEventListener('click', function () { open(b.getAttribute('data-kg-node')); }); });
  var startId = '';
  try { startId = decodeURIComponent((location.hash || '').slice(1)); } catch (e) { startId = ''; }
  open(startId || root.getAttribute('data-start'), false);
  var lastWide = window.innerWidth >= 768;
  window.addEventListener('resize', function () { var wide = window.innerWidth >= 768; if (wide !== lastWide) { lastWide = wide; if (current) open(current, false); } });

  // V292.1: compare several symptoms — the conditions they share in the knowledge base.
  var X = T.x || {};
  var xIn = document.getElementById('kgXInput'), xSugg = document.getElementById('kgXSugg');
  var xChosen = document.getElementById('kgXChosen'), xOut = document.getElementById('kgXOut');
  var chosen = [], xTimer = null;
  if (!xIn || !xOut) return;

  function xAdd(r) {
    if (chosen.length >= 5 || chosen.some(function (c) { return c.id === r.id; })) return;
    chosen.push({ id: r.id, label: r.label });
    xIn.value = ''; xSugg.hidden = true; xRun();
  }
  function xTags() {
    xChosen.textContent = '';
    chosen.forEach(function (c, i) {
      var tag = el('span', 'kg-x-tag', c.label);
      var rm = el('button', '', '×'); rm.type = 'button';
      rm.setAttribute('aria-label', (X.remove || 'Remove') + ' ' + c.label);
      rm.addEventListener('click', function () { chosen.splice(i, 1); xRun(); });
      tag.appendChild(rm); xChosen.appendChild(tag);
    });
  }
  function xRun() {
    xTags();
    if (!chosen.length) { xOut.textContent = ''; xOut.appendChild(el('p', 'kg-x-hint', X.pick || '')); return; }
    api({ explore: chosen.map(function (c) { return c.id; }).join(',') }).then(function (d) {
      if (!d || !d.ok) return;
      xOut.textContent = '';
      (d.alarms || []).forEach(function (a) { xOut.appendChild(el('p', 'kg-x-alarm', (X.alarm || '') + ': ' + a.label + ' — ' + a.advice)); });
      if (!d.results.length) { xOut.appendChild(el('p', 'kg-x-hint', X.none || '')); return; }
      var ul = el('ul', 'kg-x-list'), m = d.chosen.length;
      d.results.forEach(function (r) {
        var li = el('li', 'kg-x-item'), head = el('div', 'kg-x-head');
        var b = el('button', '', r.condition.label); b.type = 'button'; b.title = X.open || '';
        b.addEventListener('click', function () { open(r.condition.id); var st = document.querySelector('.kg-stage'); if (st) st.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
        head.appendChild(b);
        if (m > 1) head.appendChild(el('span', 'kg-x-count', String(X.match || '').replace('{n}', r.count).replace('{m}', m)));
        li.appendChild(head);
        var ms = el('div', 'kg-x-m');
        r.matched.forEach(function (x) { ms.appendChild(el('span', '', x.symptom.label + ' · ' + x.strength)); });
        li.appendChild(ms);
        if (r.source) { var a = el('a', 'kg-x-src', r.source_label || T.source || 'Source'); a.href = r.source; a.target = '_blank'; a.rel = 'noopener noreferrer'; li.appendChild(a); }
        ul.appendChild(li);
      });
      xOut.appendChild(ul);
      if (d.total > d.results.length) xOut.appendChild(el('p', 'kg-more', '+' + (d.total - d.results.length) + ' ' + (X.more || '')));
    }).catch(function () {});
  }
  xIn.addEventListener('input', function () {
    clearTimeout(xTimer);
    var q = xIn.value.trim();
    if (!q) { xSugg.hidden = true; return; }
    xTimer = setTimeout(function () {
      api({ q: q, type: 'symptom' }).then(function (d) {
        xSugg.textContent = '';
        var res = (d && d.results) || [];
        if (!res.length) { xSugg.appendChild(el('button', '', T.empty || '')); }
        res.forEach(function (r) {
          var b = el('button'); b.type = 'button';
          b.appendChild(el('span', '', r.label));
          b.addEventListener('click', function () { xAdd(r); });
          xSugg.appendChild(b);
        });
        xSugg.hidden = false;
      }).catch(function () {});
    }, 180);
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('.kg-x-search')) xSugg.hidden = true; });
  var tryBtn = document.getElementById('kgXTry');
  if (tryBtn) tryBtn.addEventListener('click', function () {
    chosen = [];
    xAdd({ id: 'symptom:headache', label: lang === 'en' ? 'Headache' : 'صداع' });
    xAdd({ id: 'symptom:fever', label: lang === 'en' ? 'Fever' : 'حمى' });
  });
})();
