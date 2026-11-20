(function () {
  const bar = document.getElementById('topic-bar');
  if (!bar) return;

  const token = bar.dataset.token;
  const questionText = document.getElementById('question-text');
  const questionHint = document.getElementById('question-hint');
  const recordBtn = document.getElementById('record-btn');
  const recordLabel = recordBtn.querySelector('.record-label');
  const waveform = document.getElementById('waveform');
  const timerEl = document.getElementById('record-timer');
  const recordHint = document.getElementById('record-hint');
  const answerText = document.getElementById('answer-text');
  const submitBtn = document.getElementById('submit-btn');
  const submitStatus = document.getElementById('submit-status');
  const resultCard = document.getElementById('result-card');
  const resultText = document.getElementById('result-text');
  const followupBtn = document.getElementById('followup-btn');
  const followupBox = document.getElementById('followup-box');
  const nextBtn = document.getElementById('next-btn');

  const HINTS = {
    ice: '慢慢讲，讲多久都可以。',
    probe: '顺着刚才的话题再往下说说。',
    hook: '这个问题可以慢慢想，不着急。',
  };

  let topic = 'childhood';
  let question = null;
  let recorder = null;
  let stream = null;
  let chunks = [];
  let audioBlob = null;
  let timerId = null;
  let seconds = 0;
  let storyId = null;

  function pickMime() {
    const candidates = ['audio/webm', 'audio/mp4', 'audio/ogg'];
    for (let i = 0; i < candidates.length; i++) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(candidates[i])) {
        return candidates[i];
      }
    }
    return '';
  }

  function formatTime(total) {
    const m = String(Math.floor(total / 60)).padStart(2, '0');
    const s = String(total % 60).padStart(2, '0');
    return m + ':' + s;
  }

  function resetRecording() {
    audioBlob = null;
    chunks = [];
    seconds = 0;
    timerEl.textContent = '00:00';
    waveform.hidden = true;
    recordBtn.classList.remove('recording');
    recordLabel.textContent = '按住说话';
    recordHint.textContent = '点一下开始，再点一下结束';
  }

  async function loadQuestion() {
    questionText.textContent = '正在准备问题…';
    questionHint.textContent = '';
    try {
      const data = await MJ.request('/api/projects/' + token + '/question?topic=' + topic);
      if (data.finished) {
        question = null;
        questionText.textContent = '这个话题已经聊完了，换一个吧';
        submitBtn.disabled = true;
        return;
      }
      question = data.question;
      questionText.textContent = question.text;
      questionHint.textContent = HINTS[question.kind] || '慢慢讲。';
      submitBtn.disabled = false;
    } catch (err) {
      questionText.textContent = '问题加载失败：' + err.message;
    }
  }

  bar.addEventListener('click', function (event) {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    bar.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('chip-active'); });
    chip.classList.add('chip-active');
    topic = chip.dataset.topic;
    resultCard.hidden = true;
    answerText.value = '';
    resetRecording();
    loadQuestion();
  });

  if (!navigator.mediaDevices || !window.MediaRecorder) {
    recordBtn.disabled = true;
    recordHint.textContent = '这台设备不支持录音，请直接打字';
  }

  recordBtn.addEventListener('click', async function () {
    if (recorder && recorder.state === 'recording') {
      recorder.stop();
      return;
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      MJ.toast('无法访问麦克风：' + err.message);
      return;
    }

    const mime = pickMime();
    recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    chunks = [];

    recorder.ondataavailable = function (e) {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };

    recorder.onstop = function () {
      clearInterval(timerId);
      if (stream) {
        stream.getTracks().forEach(function (t) { t.stop(); });
        stream = null;
      }
      audioBlob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
      waveform.hidden = true;
      recordBtn.classList.remove('recording');
      recordLabel.textContent = '重录';
      recordHint.textContent = '已录 ' + formatTime(seconds) + '，可以再点一次重录';
    };

    recorder.start();
    seconds = 0;
    timerEl.textContent = '00:00';
    waveform.hidden = false;
    recordBtn.classList.add('recording');
    recordLabel.textContent = '正在录，点一下结束';
    recordHint.textContent = '讲完再点一下按钮';
    timerId = setInterval(function () {
      seconds += 1;
      timerEl.textContent = formatTime(seconds);
    }, 1000);
  });

  submitBtn.addEventListener('click', async function () {
    if (!question) {
      MJ.toast('这个话题已经聊完了，换一个主题吧');
      return;
    }

    const typed = answerText.value.trim();
    if (!typed && !audioBlob) {
      MJ.toast('先录一段音，或者打几个字');
      return;
    }

    const form = new FormData();
    form.append('topic', topic);
    form.append('question', question.text);
    form.append('text', typed);
    if (audioBlob) {
      const ext = audioBlob.type.indexOf('mp4') >= 0 ? 'm4a' : 'webm';
      form.append('audio', audioBlob, 'answer.' + ext);
    }

    MJ.setBusy(submitBtn, true, '正在整理…');
    submitStatus.textContent = '正在把您说的话整理成故事，请稍等';
    try {
      const data = await MJ.request('/api/projects/' + token + '/stories', {
        method: 'POST',
        body: form,
      });
      storyId = data.story.id;
      resultText.textContent = data.story.polished_text || data.story.raw_text;
      resultCard.hidden = false;
      followupBox.hidden = true;
      answerText.value = '';
      resetRecording();
      submitStatus.textContent = '';
      if (data.asr_error) {
        MJ.toast(data.asr_error, 6000);
      } else if (data.polish_ok) {
        MJ.toast('整理好了，往下看看');
      } else {
        MJ.toast('未走 AI 润色，只做了断句整理' + (data.polish_error ? '：' + data.polish_error : ''), 6000);
      }
      resultCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (err) {
      submitStatus.textContent = '';
      MJ.toast(err.message, 5000);
    } finally {
      MJ.setBusy(submitBtn, false);
    }
  });

  followupBtn.addEventListener('click', async function () {
    if (!storyId) return;
    MJ.setBusy(followupBtn, true, '想问题…');
    try {
      const data = await MJ.request('/api/stories/' + storyId + '/followup', { method: 'POST' });
      followupBox.textContent = '追问：' + data.question;
      followupBox.hidden = false;
      if (data.note) {
        MJ.toast(data.note, 6000);
      }
    } catch (err) {
      MJ.toast(err.message, 6000);
    } finally {
      MJ.setBusy(followupBtn, false);
    }
  });

  nextBtn.addEventListener('click', function () {
    resultCard.hidden = true;
    answerText.value = '';
    resetRecording();
    loadQuestion();
  });

  const firstChip = bar.querySelector('.chip-active');
  if (firstChip) topic = firstChip.dataset.topic;
  loadQuestion();
})();