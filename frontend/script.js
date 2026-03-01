/**
 * AUDIOVISION - Frontend application
 * WebSocket control, video feed, detection list, toasts, shortcuts
 */

(function () {
  'use strict';

  const API_WS = (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws';
  const VIDEO_FEED_URL = '/video-feed';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = {
    ws: null,
    detecting: false,
    voiceEnabled: true,
    sensitivity: 0.5,
    detectionHistory: [],
    detectionLog: [],
    lastDetectionIds: new Set(),
    toastTimer: null,
  };

  const elements = {
    videoFeed: () => document.getElementById('video-feed'),
    placeholder: () => document.getElementById('camera-placeholder'),
    stopped: () => document.getElementById('camera-stopped'),
    startBtn: () => document.getElementById('start-btn'),
    stopBtn: () => document.getElementById('stop-btn'),
    voiceToggle: () => document.getElementById('voice-toggle'),
    sensitivity: () => document.getElementById('sensitivity'),
    sensitivityValue: () => document.getElementById('sensitivity-value'),
    detectionList: () => document.getElementById('detection-list'),
    objectCount: () => document.getElementById('object-count'),
    logContainer: () => document.getElementById('log-container'),
    clearHistoryBtn: () => document.getElementById('clear-history-btn'),
    downloadLogBtn: () => document.getElementById('download-log-btn'),
    screenshotBtn: () => document.getElementById('screenshot-btn'),
    highContrastBtn: () => document.getElementById('high-contrast-btn'),
    toast: () => document.getElementById('toast'),
  };

  function connectWS() {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) return state.ws;
    const ws = new WebSocket(API_WS);
    ws.onopen = () => {
      console.log('AUDIOVISION: WebSocket connected');
    };
    ws.onclose = () => {
      console.log('AUDIOVISION: WebSocket closed');
    };
    ws.onerror = (e) => console.error('WebSocket error', e);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'detections') handleDetections(data.objects);
        if (data.type === 'status') handleStatus(data.status);
      } catch (_) {}
    };
    state.ws = ws;
    return ws;
  }

  function send(action, payload = {}) {
    const ws = connectWS();
    if (ws.readyState !== WebSocket.OPEN) {
      ws.addEventListener('open', () => send(action, payload));
      return;
    }
    ws.send(JSON.stringify({ action, ...payload }));
  }

  function handleStatus(status) {
    if (status === 'started') {
      state.detecting = true;
      showVideoFeed(true);
      setControlsStarted(true);
    } else if (status === 'stopped') {
      state.detecting = false;
      showVideoFeed(false);
      setControlsStarted(false);
    }
  }

  function showVideoFeed(active) {
    const img = elements.videoFeed();
    const placeholder = elements.placeholder();
    const stopped = elements.stopped();
    if (active) {
      img.src = VIDEO_FEED_URL + '?t=' + Date.now();
      img.classList.add('active');
      img.alt = 'Live camera feed with object detection overlay';
      placeholder.classList.add('hidden');
      stopped.classList.add('hidden');
    } else {
      img.src = '';
      img.classList.remove('active');
      placeholder.classList.add('hidden');
      stopped.classList.remove('hidden');
    }
  }

  function setControlsStarted(started) {
    elements.startBtn().disabled = started;
    elements.stopBtn().disabled = !started;
  }

  function handleDetections(objects) {
    if (!Array.isArray(objects) || objects.length === 0) {
      updateDetectionList([]);
      return;
    }

    const list = elements.detectionList();
    const countEl = elements.objectCount();
    const seen = new Set();

    objects.forEach((obj) => {
      const key = `${obj.label}-${obj.direction}`;
      if (seen.has(key)) return;
      seen.add(key);
      const id = key + '-' + (obj.confidence || 0);
      if (!state.lastDetectionIds.has(id)) {
        state.lastDetectionIds.add(id);
        state.detectionLog.push({
          time: new Date().toISOString(),
          label: obj.label,
          confidence: obj.confidence,
          direction: obj.direction,
        });
        addLogEntry(obj);
        showToast(`Detected: ${obj.label}`);
      }
    });

    state.detectionHistory = objects;
    updateDetectionList(objects);
    countEl.textContent = objects.length;

    setTimeout(() => {
      state.lastDetectionIds.clear();
    }, 2000);
  }

  function updateDetectionList(objects) {
    const list = elements.detectionList();
    list.innerHTML = '';
    objects.forEach((obj) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span>${escapeHtml(obj.label)} <span class="direction">(${obj.direction})</span></span>
        <span class="confidence">${Math.round((obj.confidence || 0) * 100)}%</span>
      `;
      list.appendChild(li);
    });
    elements.objectCount().textContent = objects.length;
  }

  function addLogEntry(obj) {
    const container = elements.logContainer();
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${obj.label} ${(obj.confidence || 0) * 100}% (${obj.direction})`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
    while (container.children.length > 100) container.removeChild(container.firstChild);
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function showToast(message) {
    const toast = elements.toast();
    if (state.toastTimer) clearTimeout(state.toastTimer);
    toast.textContent = message;
    toast.classList.add('show');
    state.toastTimer = setTimeout(() => {
      toast.classList.remove('show');
      state.toastTimer = null;
    }, 3000);
  }

  function startDetection() {
    const sensitivity = parseInt(elements.sensitivity().value, 10) / 100;
    send('start', { sensitivity, voice: state.voiceEnabled });
  }

  function stopDetection() {
    send('stop');
  }

  function clearHistory() {
    state.detectionHistory = [];
    state.detectionLog = [];
    updateDetectionList([]);
    elements.objectCount().textContent = '0';
    elements.logContainer().innerHTML = '';
    showToast('History cleared');
  }

  function downloadLog() {
    const data = JSON.stringify(state.detectionLog, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `audiovision-log-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    showToast('Log downloaded');
  }

  function captureScreenshot() {
    const img = elements.videoFeed();
    if (!img.src || !img.src.includes('video-feed')) {
      showToast('Start detection first to capture');
      return;
    }
    const w = img.naturalWidth || img.width || 640;
    const h = img.naturalHeight || img.height || 480;
    if (w === 0 || h === 0) {
      showToast('Waiting for frame… try again');
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    try {
      ctx.drawImage(img, 0, 0);
      const dataUrl = canvas.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = `audiovision-${Date.now()}.png`;
      a.click();
      showToast('Screenshot saved');
    } catch (err) {
      showToast('Screenshot failed (allow same-origin feed)');
    }
  }

  function setHighContrast(enabled) {
    document.body.classList.toggle('high-contrast', enabled);
    elements.highContrastBtn().setAttribute('aria-pressed', enabled);
  }

  function init() {
    connectWS();

    elements.startBtn().addEventListener('click', startDetection);
    elements.stopBtn().addEventListener('click', stopDetection);

    elements.voiceToggle().addEventListener('click', () => {
      state.voiceEnabled = !state.voiceEnabled;
      elements.voiceToggle().setAttribute('aria-pressed', state.voiceEnabled);
      elements.voiceToggle().querySelector('.toggle-text').textContent = state.voiceEnabled ? 'On' : 'Off';
      send('voice', { enabled: state.voiceEnabled });
    });

    elements.sensitivity().addEventListener('input', (e) => {
      const v = e.target.value;
      state.sensitivity = parseInt(v, 10) / 100;
      elements.sensitivityValue().textContent = v + '%';
      elements.sensitivity().setAttribute('aria-valuenow', v);
      send('sensitivity', { value: state.sensitivity });
    });

    elements.clearHistoryBtn().addEventListener('click', clearHistory);
    elements.downloadLogBtn().addEventListener('click', downloadLog);
    elements.screenshotBtn().addEventListener('click', captureScreenshot);

    elements.highContrastBtn().addEventListener('click', () => {
      const pressed = document.body.classList.toggle('high-contrast');
      elements.highContrastBtn().setAttribute('aria-pressed', pressed);
    });

    document.addEventListener('keydown', (e) => {
      if (e.target.closest('input, textarea, select')) return;
      switch (e.key.toLowerCase()) {
        case 's':
          if (!state.detecting) startDetection();
          e.preventDefault();
          break;
        case 'e':
          if (state.detecting) stopDetection();
          e.preventDefault();
          break;
        case 'v':
          state.voiceEnabled = !state.voiceEnabled;
          elements.voiceToggle().setAttribute('aria-pressed', state.voiceEnabled);
          elements.voiceToggle().querySelector('.toggle-text').textContent = state.voiceEnabled ? 'On' : 'Off';
          send('voice', { enabled: state.voiceEnabled });
          e.preventDefault();
          break;
        case '?':
          showToast('S Start · E Stop · V Voice');
          e.preventDefault();
          break;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
