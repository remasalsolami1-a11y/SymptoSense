/* SymptoSense V46 — CSP-safe compatibility bridge for legacy HTML event attributes.
 *
 * The application historically used a number of inline onclick/onchange/etc.
 * attributes.  V46 enforces `script-src-attr 'none'`; this small, same-origin
 * script removes those attributes and rebinds only a deliberately restricted
 * grammar through addEventListener.  It does not use eval/new Function.
 */
(function () {
  'use strict';

  var EVENT_ATTRS = {
    onclick: 'click',
    onchange: 'change',
    oninput: 'input',
    onsubmit: 'submit',
    onkeydown: 'keydown',
    onkeyup: 'keyup',
    onfocus: 'focus',
    onblur: 'blur',
    onload: 'load',
    onerror: 'error'
  };

  var ALLOWED_CALLS = new Set([
    'addRelated','addReminderTime','applySymptomSuggestion','askAboutTerm','askAboutTopic','askCalc',
    'asstBackMain','asstChipClick','asstCloseModal','asstFb','asstMhUrgentSupport',
    'asstSend','asstToggle','backToGrid','beginReanalysis','cancelEdit',
    'closeDeleteAll','closeEmergency','closeExplain','confirmDeleteAll','copyEmNum',
    'delFile','deleteAnalysis','deleteField','deleteHealthData','deletePlan','disablePush',
    'doSearch','downloadAnalysisReport','dqAsk','editField','editPlan','enablePush',
    'extractSmartSymptoms','linkBlood','loadCalendar','loadTip','loadVid','logMed','mark',
    'nearMe','openAsstGeneral','openAsstMH','openDoctorHandoff','openExplain','openHeroDemoModal','closeHeroDemoModal',
    'openExplainCurrent','pickRel','pickSug','pwaDismiss','pwaInstallNow',
    'pwaRequestInstall','removeReminderTime','resetPlanForm','restart','runBMI','runCal','runDose','runFluids',
    'runSugar','saveFam','saveField','saveNotifSettings','savePlan','searchDrug',
    'selectFeedbackStar','sendTestPush','showCalc','showDeleteAll','showLv',
    'smartCtxAction','snooze','ssChooseLanguage','ssCloseLoginToast','ssFocusLanguages',
    'startSymptomAnalysis','submitFeedback','submitText','sugTypeChange',
    'switchFamilyMember','toggleAnalytics','toggleDD','toggleDay','toggleInd',
    'toggleResearch','toggleWeekdays','uploadBlood','withdrawAnalytics','withdrawResearch',
    'ssGoto','ssPrint','ssCopyText'
  ]);

  // Admin-only legacy handlers. Keeping these in a separate set prevents a
  // public page from invoking privileged dashboard UI functions through the
  // compatibility parser. The underlying APIs still enforce Admin auth/CSRF.
  var ADMIN_ALLOWED_CALLS = new Set([
    'askData', 'auditUI', 'closeLabTrialCleanup', 'closeLaunchReset', 'closeModal',
    'closeValidationEditor', 'confirmProductionEmail', 'deleteValidationCase', 'downloadAnalyticsExport',
    'downloadValidation', 'exportAudit', 'exportData', 'exportPilotWorkbook',
    'freezeResearchStudy', 'graphDetails', 'graphFocus', 'graphReset',
    'graphZoom', 'loadAI', 'loadAnalysisResults', 'loadAnomalies',
    'loadAudit', 'loadContentGaps', 'loadDropoff', 'loadGraph', 'loadHealth',
    'loadHealthAnalytics', 'loadHeatmap', 'loadInsights', 'loadKB',
    'loadKnowledgeReview', 'loadLive', 'loadMedicationAnalytics', 'loadPrivacyAnalytics',
    'loadProductionReadiness', 'loadPushVerification', 'loadPerformanceBenchmark', 'runPerformanceBenchmark', 'loadUsage', 'loadUsers',
    'loadV2Analytics', 'loadXAI', 'logoutAllAdminSessions', 'openContentEditor',
    'openEditor', 'openLabTrialCleanup', 'openLaunchReset', 'openValidationEditor',
    'performLabTrialCleanup', 'performLaunchReset', 'exportLabTrialsExcel',
    'previewAnalyticsExport', 'removeContent', 'removeItem', 'render',
    'renderAudit', 'renderContent', 'renderGraph', 'renderResultDetails',
    'sendAdminTestPush', 'sendAuthEmailTest', 'show', 'testErrorMonitoring',
    'testProductionEmail', 'testProductionPush', 'toggleDropDates', 'toggleExportDates',
    'toggleLive', 'toggleUser', 'closeAnalysisResultDetails',
  ]);

  function isAllowedCall(name) {
    if (ALLOWED_CALLS.has(name)) return true;
    return /^\/admin(?:\/|$)/.test(window.location.pathname || '') && ADMIN_ALLOWED_CALLS.has(name);
  }


  function splitTopLevel(text, separator) {
    var parts = [];
    var start = 0;
    var depth = 0;
    var quote = '';
    var escaped = false;
    for (var i = 0; i < text.length; i += 1) {
      var ch = text[i];
      if (quote) {
        if (escaped) { escaped = false; continue; }
        if (ch === '\\') { escaped = true; continue; }
        if (ch === quote) quote = '';
        continue;
      }
      if (ch === '"' || ch === "'") { quote = ch; continue; }
      if (ch === '(' || ch === '[' || ch === '{') { depth += 1; continue; }
      if (ch === ')' || ch === ']' || ch === '}') { if (depth > 0) depth -= 1; continue; }
      if (ch === separator && depth === 0) {
        parts.push(text.slice(start, i).trim());
        start = i + 1;
      }
    }
    parts.push(text.slice(start).trim());
    return parts.filter(function (item) { return item.length > 0; });
  }

  function decodeStringLiteral(token) {
    token = String(token || '').trim();
    if (token.length < 2) throw new Error('invalid string literal');
    var quote = token[0];
    if ((quote !== '"' && quote !== "'") || token[token.length - 1] !== quote) {
      throw new Error('invalid string literal');
    }
    var out = '';
    for (var i = 1; i < token.length - 1; i += 1) {
      var ch = token[i];
      if (ch !== '\\') { out += ch; continue; }
      i += 1;
      if (i >= token.length - 1) { out += '\\'; break; }
      var n = token[i];
      if (n === 'n') out += '\n';
      else if (n === 'r') out += '\r';
      else if (n === 't') out += '\t';
      else if (n === 'b') out += '\b';
      else if (n === 'f') out += '\f';
      else if (n === 'v') out += '\v';
      else if (n === '0') out += '\0';
      else if (n === 'x' && /^[0-9a-fA-F]{2}$/.test(token.slice(i + 1, i + 3))) {
        out += String.fromCharCode(parseInt(token.slice(i + 1, i + 3), 16)); i += 2;
      } else if (n === 'u' && /^[0-9a-fA-F]{4}$/.test(token.slice(i + 1, i + 5))) {
        out += String.fromCharCode(parseInt(token.slice(i + 1, i + 5), 16)); i += 4;
      } else if (n === '\n' || n === '\r') {
        // JavaScript line continuation.
      } else out += n;
    }
    return out;
  }

  function resolveArg(token, element, event) {
    token = String(token || '').trim();
    if (token === '') return undefined;
    if (token === 'this') return element;
    if (token === 'event') return event;
    if (token === 'this.value') return element ? element.value : undefined;
    if (token === 'true') return true;
    if (token === 'false') return false;
    if (token === 'null') return null;
    if (token === 'undefined') return undefined;
    if (/^-?(?:\d+\.?\d*|\.\d+)$/.test(token)) return Number(token);
    if ((token[0] === '"' && token[token.length - 1] === '"') || (token[0] === "'" && token[token.length - 1] === "'")) {
      return decodeStringLiteral(token);
    }
    if ((token[0] === '{' && token[token.length - 1] === '}') || (token[0] === '[' && token[token.length - 1] === ']')) {
      if (token.length > 20000) throw new Error('inline-handler JSON argument too large');
      return JSON.parse(token);
    }
    var byId = token.match(/^document\.getElementById\((.+)\)\.value$/);
    if (byId) {
      var id = resolveArg(byId[1], element, event);
      var target = document.getElementById(String(id || ''));
      return target ? target.value : '';
    }
    var numberCall = token.match(/^Number\((.*)\)$/);
    if (numberCall) return Number(resolveArg(numberCall[1], element, event));
    throw new Error('unsupported inline-handler argument');
  }

  function safeNavigate(raw) {
    var value = String(raw == null ? '' : raw).trim();
    if (!value) return;
    try {
      var url = new URL(value, window.location.href);
      if (!/^https?:$/.test(url.protocol) || url.origin !== window.location.origin) return;
      window.location.href = url.href;
    } catch (_) {}
  }

  function invokeCall(statement, element, event) {
    var match = statement.match(/^([A-Za-z_$][\w$]*)\s*\((.*)\)$/s);
    if (!match || !isAllowedCall(match[1])) throw new Error('unsupported inline-handler call');
    var fn = window[match[1]];
    if (typeof fn !== 'function') throw new Error('inline-handler target unavailable');
    var rawArgs = match[2].trim();
    var args = rawArgs ? splitTopLevel(rawArgs, ',').map(function (item) {
      return resolveArg(item, element, event);
    }) : [];
    return fn.apply(window, args);
  }

  function executeHandler(code, element, event) {
    code = String(code || '').trim();
    if (!code) return;

    var enter = code.match(/^if\s*\(\s*event\.key\s*===?\s*(['"])Enter\1\s*\)\s*(.+)$/s);
    if (enter) {
      if (!event || event.key !== 'Enter') return;
      code = enter[2].trim();
    }
    var selfOnly = code.match(/^if\s*\(\s*event\.target\s*===\s*this\s*\)\s*(.+)$/s);
    if (selfOnly) {
      if (!event || event.target !== element) return;
      code = selfOnly[1].trim();
    }

    var statements = splitTopLevel(code, ';');
    for (var i = 0; i < statements.length; i += 1) {
      var statement = statements[i].trim();
      if (!statement) continue;
      if (statement === 'return false' || statement === 'return false;') {
        if (event) event.preventDefault();
        continue;
      }
      if (/^event\.stopPropagation\(\)$/.test(statement)) {
        if (event) event.stopPropagation();
        continue;
      }
      var nav = statement.match(/^location\.href\s*=\s*(.+)$/s);
      if (nav) {
        safeNavigate(resolveArg(nav[1], element, event));
        continue;
      }
      var result = invokeCall(statement, element, event);
      if (result === false && event) event.preventDefault();
    }
  }

  function bindAttribute(element, attrName, eventName) {
    if (!element || !element.hasAttribute || !element.hasAttribute(attrName)) return;
    var code = element.getAttribute(attrName) || '';
    element.removeAttribute(attrName);
    if (!code.trim()) return;
    element.addEventListener(eventName, function (event) {
      try { executeHandler(code, element, event); }
      catch (_) {
        // Fail closed: an unsupported legacy expression never falls back to eval.
      }
    });
  }

  function bindElement(element) {
    if (!element || element.nodeType !== 1) return;
    Object.keys(EVENT_ATTRS).forEach(function (attrName) {
      bindAttribute(element, attrName, EVENT_ATTRS[attrName]);
    });
  }

  function scan(root) {
    if (!root) return;
    if (root.nodeType === 1) bindElement(root);
    var selector = Object.keys(EVENT_ATTRS).map(function (name) { return '[' + name + ']'; }).join(',');
    if (root.querySelectorAll) root.querySelectorAll(selector).forEach(bindElement);
  }

  // ---- Data-attribute actions (the preferred way; no inline on* attributes) --------------------------------------
  //   <button type="button" data-ss-click="loadUsers">
  //   <button type="button" data-ss-click="removeItem" data-ss-args='["id-7", 3]'>
  //   <select data-ss-change="toggleExportDates auditUI">          (several allow-listed functions, run in order)
  //   <input data-ss-keydown="loadAnalysisResults" data-ss-key="Enter" data-ss-args="[1]">
  //   <div class="modal" data-ss-click="closeModal" data-ss-self>   (only when the backdrop itself is clicked)
//   <a href="/ai" data-ss-click="openAsstGeneral" data-ss-prevent>   (preventDefault, like "return false")
//   <div data-ss-click="ssGoto" data-ss-args='["/profile"]'>         (same-origin navigation)
  // Arguments are JSON; the strings "$this", "$value" and "$event" are replaced by the element, its value and the event.
  // One delegated listener per event type: elements added later work without rebinding. Same allow-list as above.
  // Helpers for markup built in JavaScript strings and for the few non-function legacy handlers.
  window.ssArgs = function (list) {            // JSON for a data-ss-args attribute, safe inside a double-quoted HTML attribute
    return JSON.stringify(list).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  };
  window.ssGoto = function (url) { safeNavigate(url); };                 // same-origin http(s) only
  window.ssPrint = function () { window.print(); };
  window.ssCopyText = function (id) {
    var el = document.getElementById(String(id || ''));
    if (el && navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(el.innerText);
  };

  var DATA_EVENTS = { click: 'data-ss-click', change: 'data-ss-change', input: 'data-ss-input', keydown: 'data-ss-keydown', submit: 'data-ss-submit' };

  function dataArgs(element, event) {
    var raw = element.getAttribute('data-ss-args');
    if (!raw) return [];
    if (raw.length > 20000) throw new Error('data-ss-args too large');
    var list = JSON.parse(raw);
    if (!Array.isArray(list)) throw new Error('data-ss-args must be a JSON array');
    return list.map(function (item) {
      if (item === '$this') return element;
      if (item === '$value') return element.value;
      if (item === '$event') return event;
      return item;
    });
  }

  function runDataActions(element, event, names) {
    var list = dataArgs(element, event);
    var multi = element.hasAttribute('data-ss-multi');       // data-ss-args is then one argument list per function
    String(names || '').split(/\s+/).filter(Boolean).forEach(function (name, index) {
      if (!isAllowedCall(name)) throw new Error('data-ss action not allow-listed');
      var fn = window[name];
      if (typeof fn !== 'function') throw new Error('data-ss action target unavailable');
      var args = multi ? (Array.isArray(list[index]) ? list[index] : []) : list;
      if (fn.apply(window, args) === false && event) event.preventDefault();
    });
  }

  function startDataActions() {
    Object.keys(DATA_EVENTS).forEach(function (type) {
      var attrName = DATA_EVENTS[type];
      document.addEventListener(type, function (event) {
        var el = event.target && event.target.closest ? event.target.closest('[' + attrName + ']') : null;
        if (!el) return;
        if (el.hasAttribute('data-ss-self') && event.target !== el) return;
        var key = el.getAttribute('data-ss-key');
        if (key && event.key !== key) return;                                    // other keys must keep working (typing)
        if (el.hasAttribute('data-ss-prevent')) event.preventDefault();          // replaces "...;return false"
        try { runDataActions(el, event, el.getAttribute(attrName)); }
        catch (err) {                                                            // fail closed, never eval; leave a trace for debugging
          if (window.console && console.warn) console.warn('[ss] ' + attrName + ' action not run: ' + (err && err.message));
        }
      });
    });
  }

  function start() {
    startDataActions();
    scan(document);
    if (!window.MutationObserver || !document.documentElement) return;
    var observer = new MutationObserver(function (records) {
      records.forEach(function (record) {
        if (record.type === 'childList') {
          record.addedNodes.forEach(scan);
        } else if (record.type === 'attributes') {
          bindElement(record.target);
        }
      });
    });
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: Object.keys(EVENT_ATTRS)
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
