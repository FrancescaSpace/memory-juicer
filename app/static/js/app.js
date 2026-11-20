(function () {
  const toastEl = document.getElementById('toast');
  let toastTimer = null;

  function toast(message, ms) {
    if (!toastEl) return;
    toastEl.textContent = message;
    toastEl.hidden = false;
    requestAnimationFrame(() => toastEl.classList.add('show'));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.classList.remove('show');
      setTimeout(() => { toastEl.hidden = true; }, 240);
    }, ms || 2400);
  }

  async function request(url, options) {
    const opts = Object.assign({ method: 'GET' }, options || {});
    const res = await fetch(url, opts);
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }
    if (!res.ok) {
      const detail = data && data.detail ? data.detail : '请求失败（' + res.status + '）';
      throw new Error(detail);
    }
    return data;
  }

  function setBusy(button, busy, busyText) {
    if (!button) return;
    if (busy) {
      button.dataset.originalText = button.textContent;
      button.textContent = busyText || '处理中…';
      button.disabled = true;
    } else {
      if (button.dataset.originalText) button.textContent = button.dataset.originalText;
      button.disabled = false;
    }
  }

  function initAudioPlayers(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-audio-player]').forEach(function (player) {
      if (player.dataset.audioReady) return;
      player.dataset.audioReady = '1';

      const audio = player.querySelector('audio');
      const toggle = player.querySelector('[data-audio-toggle]');
      const track = player.querySelector('[data-audio-track]');
      const bar = player.querySelector('[data-audio-progress]');
      const knob = player.querySelector('[data-audio-knob]');
      const timeEl = player.querySelector('[data-audio-time]');
      if (!audio || !toggle || !track) return;

      function paint() {
        const duration = audio.duration;
        const ratio = duration && isFinite(duration) ? audio.currentTime / duration : 0;
        const percent = Math.max(0, Math.min(100, ratio * 100));
        if (bar) bar.style.width = percent + '%';
        if (knob) knob.style.left = percent + '%';
        if (timeEl) timeEl.textContent = fmtTime(audio.currentTime) + ' / ' + fmtTime(duration);
      }

      function setPlaying(on) {
        player.classList.toggle('is-playing', on);
        toggle.setAttribute('aria-label', on ? '暂停原声' : '播放原声');
      }

      function seekTo(event) {
        const duration = audio.duration;
        if (!duration || !isFinite(duration)) return;
        const rect = track.getBoundingClientRect();
        if (!rect.width) return;
        const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
        audio.currentTime = (x / rect.width) * duration;
        paint();
      }

      toggle.addEventListener('click', function () {
        if (audio.paused) {
          document.querySelectorAll('audio').forEach(function (other) {
            if (other !== audio && !other.paused) other.pause();
          });
          const promise = audio.play();
          if (promise && promise.catch) {
            promise.catch(function () { toast('这段原声暂时放不出来，可能文件还没传完'); });
          }
        } else {
          audio.pause();
        }
      });

      audio.addEventListener('play', function () { setPlaying(true); });
      audio.addEventListener('pause', function () { setPlaying(false); });
      audio.addEventListener('ended', function () { setPlaying(false); paint(); });
      audio.addEventListener('timeupdate', paint);
      audio.addEventListener('loadedmetadata', paint);
      audio.addEventListener('durationchange', paint);

      track.addEventListener('click', seekTo);
      track.addEventListener('pointerdown', function (event) {
        seekTo(event);
        if (track.setPointerCapture) track.setPointerCapture(event.pointerId);
        const move = function (e) { seekTo(e); };
        const up = function () {
          track.removeEventListener('pointermove', move);
          track.removeEventListener('pointerup', up);
        };
        track.addEventListener('pointermove', move);
        track.addEventListener('pointerup', up);
      });
      track.addEventListener('keydown', function (event) {
        if (!audio.duration || !isFinite(audio.duration)) return;
        if (event.key === 'ArrowLeft') {
          audio.currentTime = Math.max(0, audio.currentTime - 5);
          event.preventDefault();
          paint();
        } else if (event.key === 'ArrowRight') {
          audio.currentTime = Math.min(audio.duration, audio.currentTime + 5);
          event.preventDefault();
          paint();
        }
      });

      paint();
    });
  }

  function fmtTime(seconds) {
    if (!isFinite(seconds) || seconds < 0) seconds = 0;
    const total = Math.floor(seconds);
    const m = Math.floor(total / 60);
    const s = total % 60;
    return m + ':' + (s < 10 ? '0' + s : String(s));
  }

  function boot() {
    initAudioPlayers(document);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.MJ = { toast: toast, request: request, setBusy: setBusy, initAudioPlayers: initAudioPlayers };
})();