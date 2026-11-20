(function () {
  const copyBtn = document.getElementById('copy-link');
  const shareInput = document.getElementById('share-link');

  if (copyBtn && shareInput) {
    copyBtn.addEventListener('click', async function () {
      try {
        await navigator.clipboard.writeText(shareInput.value);
        MJ.toast('链接已复制，发给长辈吧');
      } catch (e) {
        shareInput.select();
        document.execCommand('copy');
        MJ.toast('链接已复制');
      }
    });
  }

  const storyList = document.querySelector('.story-list');

  const COMPACT_CONTEXT = 14;

  function appendSegments(body, segments, compact) {
    body.textContent = '';
    (segments || []).forEach(function (seg) {
      if (compact && seg.kind === 'same' && seg.text.length > COMPACT_CONTEXT * 2 + 1) {
        const head = document.createElement('span');
        head.textContent = seg.text.slice(0, COMPACT_CONTEXT);
        body.appendChild(head);
        const gap = document.createElement('span');
        gap.className = 'diff-gap';
        gap.textContent = ' … ';
        body.appendChild(gap);
        const tail = document.createElement('span');
        tail.textContent = seg.text.slice(-COMPACT_CONTEXT);
        body.appendChild(tail);
        return;
      }
      let el;
      if (seg.kind === 'add') {
        el = document.createElement('ins');
        el.className = 'diff-add';
      } else if (seg.kind === 'del') {
        el = document.createElement('del');
        el.className = 'diff-del';
      } else {
        el = document.createElement('span');
      }
      el.textContent = seg.text;
      body.appendChild(el);
    });
  }

  function toggleDiffOnly(btn) {
    const box = btn.closest('.diff-box');
    const body = box && box.querySelector('[data-diff-body]');
    if (!body || !box._segments) return;
    const compact = btn.getAttribute('data-mode') !== 'compact';
    appendSegments(body, box._segments, compact);
    btn.setAttribute('data-mode', compact ? 'compact' : 'full');
    btn.textContent = compact ? '看完整全文' : '只看改动';
    if (!box.open) box.open = true;
  }

  function buildDiffNode(data) {
    if (!data.diff || !data.diff.has_change) {
      const p = document.createElement('p');
      p.className = 'diff-none muted';
      p.textContent = data.summary || '原话未改动';
      return p;
    }
    const details = document.createElement('details');
    details.className = 'diff-box';
    const summary = document.createElement('summary');
    summary.textContent = (data.summary || '') + ' · 看看改了什么';
    details.appendChild(summary);

    const spans = data.diff.spans || [];
    const length = data.diff.length || 0;
    if (spans.length && length) {
      const ribbon = document.createElement('div');
      ribbon.className = 'diff-ribbon';
      ribbon.title = '改动在全文里的位置';
      spans.forEach(function (sp) {
        const tick = document.createElement('span');
        tick.className = 'diff-tick';
        const w = sp.end - sp.start;
        tick.style.left = (sp.start / length * 100).toFixed(2) + '%';
        tick.style.width = (w > 0 ? w / length * 100 : 0.6).toFixed(2) + '%';
        ribbon.appendChild(tick);
      });
      details.appendChild(ribbon);
    }

    const body = document.createElement('div');
    body.className = 'diff-body';
    body.setAttribute('data-diff-body', '');
    appendSegments(body, data.diff.segments, false);
    details.appendChild(body);

    const tools = document.createElement('div');
    tools.className = 'diff-tools';
    const legend = document.createElement('p');
    legend.className = 'diff-legend muted';
    legend.innerHTML = '<ins class="diff-add">加粗下划线</ins> = AI 新增，<del class="diff-del">删除线</del> = AI 删掉的原话。不满意就点「还是用我的原话」。';
    const only = document.createElement('button');
    only.className = 'btn btn-sm diff-only';
    only.type = 'button';
    only.setAttribute('data-action', 'diff-only');
    only.setAttribute('data-mode', 'full');
    only.textContent = '只看改动';
    tools.appendChild(legend);
    tools.appendChild(only);
    details.appendChild(tools);

    details._segments = data.diff.segments;
    return details;
  }

  function refreshDiff(card, data) {
    const old = card.querySelector('.diff-box') || card.querySelector('.diff-none');
    if (!old) return;
    old.replaceWith(buildDiffNode(data));

    const actions = card.querySelector('.story-actions');
    const restore = actions.querySelector('[data-action="restore-raw"]');
    const changed = data.diff && data.diff.has_change;
    if (changed && !restore) {
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm';
      btn.type = 'button';
      btn.dataset.action = 'restore-raw';
      btn.textContent = '还是用我的原话';
      actions.insertBefore(btn, actions.querySelector('[data-action="delete"]'));
    } else if (!changed && restore) {
      restore.remove();
    }
  }

  function refreshMetrics() {
    const card = document.getElementById('metrics-card');
    if (!card || !card.dataset.token) return;
    MJ.request('/api/projects/' + card.dataset.token + '/metrics')
      .then(function (data) {
        const m = data.metrics;
        card.querySelectorAll('[data-metric]').forEach(function (el) {
          const key = el.dataset.metric;
          if (key === 'percent') {
            el.textContent = m.percent + '%';
          } else if (key === 'covered') {
            el.textContent = m.covered_topics;
          } else if (m[key] !== undefined) {
            el.textContent = m[key];
          }
        });
        const ring = card.querySelector('.ring-fill');
        if (ring) {
          ring.setAttribute('stroke-dasharray', (314 * m.percent / 100).toFixed(1) + ' 314');
        }
      })
      .catch(function () {});
  }

  if (storyList) {
    storyList.addEventListener('click', async function (event) {
      const btn = event.target.closest('button[data-action]');
      if (!btn) return;

      if (btn.getAttribute('data-action') === 'diff-only') {
        toggleDiffOnly(btn);
        return;
      }

      const card = btn.closest('.story-card');
      const storyId = card.dataset.storyId;
      const status = card.querySelector('[data-status]');
      const editor = card.querySelector('.story-editor');
      const action = btn.dataset.action;

      const form = new FormData();

      try {
        if (action === 'save' || action === 'restore-raw') {
          const text = action === 'restore-raw' ? card.dataset.raw || '' : editor.value;
          form.append('polished_text', text);
          MJ.setBusy(btn, true, action === 'restore-raw' ? '还原中…' : '保存中…');
          const data = await MJ.request('/api/stories/' + storyId, { method: 'PATCH', body: form });
          if (action === 'restore-raw') {
            editor.value = data.story.polished_text;
            refreshDiff(card, data.story);
            status.textContent = '已还原为原话';
            MJ.toast('已还原为原话，一个字都没改');
          } else {
            status.textContent = '已保存';
            refreshDiff(card, data.story);
            MJ.toast('已保存');
          }
          refreshMetrics();
        } else if (action === 'repolish' || action === 'vivid') {
          form.append('vivid', action === 'vivid' ? 'true' : 'false');
          MJ.setBusy(btn, true, '润色中…');
          const data = await MJ.request('/api/stories/' + storyId + '/repolish', {
            method: 'POST',
            body: form,
          });
          editor.value = data.story.polished_text;
          refreshDiff(card, data.story);
          status.textContent = data.polish_ok ? '已润色' : '离线整理';
          MJ.toast(data.polish_ok ? '润色完成，点开看看改了什么' : '离线模式：只做了断句整理');
          refreshMetrics();
        } else if (action === 'followup') {
          MJ.setBusy(btn, true, '想问题…');
          const data = await MJ.request('/api/stories/' + storyId + '/followup', { method: 'POST' });
          status.textContent = '';
          MJ.toast('追问：' + data.question, 6000);
        } else if (action === 'delete') {
          if (!window.confirm('确定删除这一段吗？删除后不可恢复。')) return;
          MJ.setBusy(btn, true, '删除中…');
          await MJ.request('/api/stories/' + storyId, { method: 'DELETE' });
          card.remove();
          MJ.toast('已删除');
          refreshMetrics();
        }
      } catch (err) {
        MJ.toast(err.message);
        status.textContent = '';
      } finally {
        MJ.setBusy(btn, false);
      }
    });
  }

  const photoForm = document.getElementById('photo-form');
  if (photoForm) {
    photoForm.addEventListener('submit', async function (event) {
      event.preventDefault();
      const fileInput = photoForm.querySelector('input[name="file"]');
      const captionInput = photoForm.querySelector('input[name="caption"]');
      if (!fileInput.files.length) return;

      const token = photoForm.dataset.token;
      if (!token) return;

      const form = new FormData();
      form.append('file', fileInput.files[0]);
      form.append('caption', captionInput.value);

      const submitBtn = photoForm.querySelector('button[type="submit"]');
      MJ.setBusy(submitBtn, true, '上传中…');
      try {
        const data = await MJ.request('/api/projects/' + token + '/photos', {
          method: 'POST',
          body: form,
        });
        const grid = document.getElementById('photo-grid');
        const item = document.createElement('div');
        item.className = 'photo-item';
        item.dataset.photoId = data.photo.id;
        item.innerHTML =
          '<img src="' + data.photo.url + '" alt="">' +
          '<p class="muted"></p>' +
          '<button class="btn btn-xs btn-danger" data-action="delete-photo" type="button">移除</button>';
        item.querySelector('p').textContent = data.photo.caption || '';
        grid.appendChild(item);
        photoForm.reset();
        MJ.toast('照片已上传');
      } catch (err) {
        MJ.toast(err.message);
      } finally {
        MJ.setBusy(submitBtn, false);
      }
    });
  }

  const photoGrid = document.getElementById('photo-grid');
  if (photoGrid) {
    photoGrid.addEventListener('click', async function (event) {
      const btn = event.target.closest('[data-action="delete-photo"]');
      if (!btn) return;
      const item = btn.closest('.photo-item');
      if (!window.confirm('移除这张照片？')) return;
      try {
        await MJ.request('/api/photos/' + item.dataset.photoId, { method: 'DELETE' });
        item.remove();
        MJ.toast('已移除');
      } catch (err) {
        MJ.toast(err.message);
      }
    });
  }
})();