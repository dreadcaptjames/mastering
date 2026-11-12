/* MasterForge AI Web Studio v1.0 beta — offline web/mobile and native desktop mastering studio.
 * No audio is uploaded unless the user explicitly configures Studio API mode.
 * Local measurements are intentionally labelled estimates, not calibrated LUFS/true peak.
 */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const desktop = window.masterforgeDesktop?.isDesktop === true ? window.masterforgeDesktop : null;
  // iPadOS 13+ reports desktop Safari as MacIntel with touch input.
  const iPadMode = !desktop && (/iPad|iPhone|iPod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1));
  // iPad has NO fixed file-size or duration cutoff. Safari's available memory,
  // decoder support, and the WAV format itself remain practical constraints.
  // Preserve the existing desktop / general-web safeguards in this patch.
  const MAX_BYTES = null; // No artificial file size cap; device memory still limits rendering.
  const MAX_SECONDS = null; // Full-song processing; no fixed track duration cap.
  const LONG_TRACK_BYTES = 75 * 1024 * 1024;
  // Keep UI styles and the browser DSP engine in sync across web-app updates.
  const PRESET_CURVES = Object.freeze({
    natural: {warmth:.1,clarity:.15,lowMid:-.15,comp:1.13},
    balanced:{warmth:.35,clarity:.5,lowMid:-.5,comp:1.4},
    impact:{warmth:.8,clarity:.8,lowMid:-.8,comp:1.7},
    reference:{warmth:1.9,clarity:2,lowMid:-3.1,comp:1.17}
  });
  const isValidPreset = value => Object.prototype.hasOwnProperty.call(PRESET_CURVES,value);
  // Keep the legacy 'reference' engine ID for compatibility, but always display 'Signature'.
  const presetName = value => value === 'reference' ? 'Signature' : value;
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true;
  const state = {
    buffer: null, sourceFile: null, originalUrl: null, masterUrl: null,
    masterBuffer: null, sourceMetrics: null, masterMetrics: null,
    sourceName: '', preset: 'reference', side: 'original', rendering: false,
    engine: 'local', apiUrl: '', renderSettings: null, studioMetrics: null,
    sourcePeaks: null, masteredPeaks: null, exporting: false
  };
  let audioContext = null;
  let toastTimeout = null;
  const originalAudio = new Audio();
  const masteredAudio = new Audio();
  for (const audio of [originalAudio, masteredAudio]) {
    audio.preload = 'metadata';
    audio.addEventListener('timeupdate', updateTransport);
    audio.addEventListener('ended', updateTransport);
    audio.addEventListener('play', updateTransport);
    audio.addEventListener('pause', updateTransport);
  }

  function toast(message) {
    const el = $('toast');
    el.textContent = message; el.classList.add('show');
    clearTimeout(toastTimeout); toastTimeout = setTimeout(() => el.classList.remove('show'), 4300);
  }
  function fmtTime(seconds) {
    const sec = Math.max(0, Math.floor(seconds || 0));
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
  }
  function db(value) { return 20 * Math.log10(Math.max(value, 1e-12)); }
  function lin(decibels) { return Math.pow(10, decibels / 20); }
  function round(v, places = 1) { return Number.isFinite(v) ? v.toFixed(places) : '—'; }
  function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
  function currentAudio() { return state.side === 'master' ? masteredAudio : originalAudio; }
  function currentMetrics() { return state.side === 'master' ? state.masterMetrics : state.sourceMetrics; }
  function getSettings() {
    return { preset: state.preset, warmth: Number($('warmth').value), clarity: Number($('clarity').value), intensity: Number($('intensity').value), target: Number($('target').value) };
  }
  async function getContext() {
    audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
    if (audioContext.state === 'suspended') await audioContext.resume();
    return audioContext;
  }
  function measure(buffer) {
    const { numberOfChannels: ch, length: len, sampleRate } = buffer;
    if (!len || !ch) throw new Error('The audio file is empty.');
    const left = buffer.getChannelData(0);
    const right = ch > 1 ? buffer.getChannelData(1) : left;
    const step = Math.max(1, Math.floor(len / 900000));
    let squares = 0, pairs = 0, leftSq = 0, rightSq = 0, cross = 0, peak = 0, clipped = 0, count = 0;
    for (let i = 0; i < len; i += step) {
      const l = left[i], r = right[i];
      if (!Number.isFinite(l) || !Number.isFinite(r)) throw new Error('Invalid audio samples detected.');
      peak = Math.max(peak, Math.abs(l), Math.abs(r));
      if (Math.abs(l) >= .999 || Math.abs(r) >= .999) clipped++;
      squares += (l * l + r * r) * .5;
      leftSq += l * l; rightSq += r * r; cross += l * r;
      pairs += (l - r) * (l - r); count++;
    }
    const rms = Math.sqrt(squares / count);
    const rmsDb = db(rms), peakDb = db(peak);
    const correlation = ch === 1 ? 1 : cross / (Math.sqrt(leftSq * rightSq) + 1e-12);
    const crest = peakDb - rmsDb;
    return {rmsDb, peakDb, crest, correlation: clamp(correlation, -1, 1), clippedFraction: clipped / count, sampleRate, channels: ch, seconds: len / sampleRate, width: Math.sqrt(pairs / count), peak};
  }
  function buildPeaks(buffer, bins = 980) {
    const result = new Float32Array(bins);
    if (!buffer) return result;
    const channelA = buffer.getChannelData(0), channelB = buffer.numberOfChannels > 1 ? buffer.getChannelData(1) : channelA;
    const len = buffer.length;
    for (let p = 0; p < bins; p++) {
      const a = Math.floor(p * len / bins), b = Math.min(len, Math.floor((p + 1) * len / bins));
      const stride = Math.max(1, Math.floor((b - a) / 150));
      let max = 0;
      for (let i = a; i < b; i += stride) max = Math.max(max, Math.abs(channelA[i]), Math.abs(channelB[i]));
      result[p] = max;
    }
    return result;
  }
  function drawWave() {
    const canvas = $('waveCanvas'), ctx = canvas.getContext('2d');
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    const W = Math.max(100, rect.width), H = rect.height || 250;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);
    const waveStyle = getComputedStyle(canvas);
    const waveColor = (name, fallback) => waveStyle.getPropertyValue(name).trim() || fallback;
    ctx.strokeStyle = waveColor('--wave-grid','#29444c'); ctx.lineWidth = 1;
    for (let i = 1; i < 6; i++) {const x = W * i / 6; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();}
    for (let i = 1; i < 4; i++) {const y = H * i / 4; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();}
    const peaks = state.side === 'master' && state.masteredPeaks ? state.masteredPeaks : state.sourcePeaks;
    if (!peaks) return;
    const bars = Math.floor(W / 3); const mid = H / 2;
    const maxP = Math.max(.06, ...peaks);
    const scale = .91 / maxP;
    for (let x = 0; x < bars; x++) {
      const index = Math.floor(x / bars * peaks.length), amp = Math.max(.012, peaks[index] * scale);
      const height = amp * mid;
      ctx.fillStyle = state.side === 'master' ? waveColor('--wave-master','#93e8f0') : waveColor('--wave-source','#64d7b5');
      ctx.globalAlpha = .83;
      ctx.fillRect(x * 3 + .4, mid - height, 1.7, height * 2);
    }
    ctx.globalAlpha = 1;
    const position = state.buffer ? currentAudio().currentTime / state.buffer.duration : 0;
    if (position >= 0 && position <= 1) {
      const x = position * W;
      ctx.strokeStyle = waveColor('--wave-playhead','#e2ffdf');ctx.lineWidth = 1.5;ctx.beginPath();ctx.moveTo(x, 0);ctx.lineTo(x, H);ctx.stroke();
      ctx.fillStyle = waveColor('--wave-playhead','#e2ffdf');ctx.fillRect(x - 3, 0, 6, 5);
    }
  }
  function refreshWave() { drawWave(); }
  function updateTransport() {
    const audio = currentAudio();
    const seconds = state.buffer?.duration || 0;
    $('currentTime').textContent = fmtTime(audio.currentTime);
    $('totalTime').textContent = fmtTime(seconds);
    $('seekbar').value = seconds ? String(Math.round((audio.currentTime / seconds) * 1000)) : '0';
    const playing = !audio.paused && !audio.ended;
    $('playIcon').innerHTML = playing ? '<path d="M6 5h4v14H6zM14 5h4v14h-4z"/>' : '<path d="M8 5v14l11-7z"/>';
    $('playBtn').setAttribute('aria-label', playing ? 'Pause audio' : 'Play audio');
    if (playing) requestAnimationFrame(() => {drawWave();}); else drawWave();
  }
  function loopPlayhead() {
    if (!currentAudio().paused) {drawWave();requestAnimationFrame(loopPlayhead);}
  }
  function updateMetrics() {
    const m = currentMetrics();
    $('rmsMetric').textContent = m ? round(m.rmsDb) : '—';
    $('peakMetric').textContent = m ? round(m.peakDb) : '—';
    $('crestMetric').textContent = m ? round(m.crest) : '—';
    $('stereoMetric').textContent = m ? round(m.correlation, 2) : '—';
  }
  function updatePlaybackGain() {
    const volume = Number($('volume').value) / 100;
    const a = state.sourceMetrics, b = state.masterMetrics;
    if (!a || !b) {originalAudio.volume = volume; masteredAudio.volume = volume;return;}
    if (!$('levelMatch').checked) {originalAudio.volume = volume; masteredAudio.volume = volume; return;}
    const commonDb = Math.min(a.rmsDb, b.rmsDb);
    originalAudio.volume = clamp(volume * lin(commonDb - a.rmsDb), 0, 1);
    masteredAudio.volume = clamp(volume * lin(commonDb - b.rmsDb), 0, 1);
  }
  function switchSide(side) {
    if (side === 'master' && !state.masterUrl) return;
    if (side === state.side) return;
    const old = currentAudio(), wasPlaying = !old.paused, time = old.currentTime;
    old.pause();state.side = side;
    const audio = currentAudio();
    try { audio.currentTime = Math.min(time, Math.max(0, (state.buffer?.duration || 0) - .03)); } catch (_) {}
    $('originalBtn').classList.toggle('ab-active',side === 'original');
    $('masterBtn').classList.toggle('ab-active',side === 'master');
    updateMetrics();updatePlaybackGain();updateTransport();
    if (wasPlaying) audio.play().then(loopPlayhead).catch(() => toast('Tap play to resume playback.'));
  }
  function makeFindings(metrics) {
    const res = [];
    if (metrics.peakDb > -.7 || metrics.clippedFraction > 0.0001) res.push({severity:'warning', title:'Very hot peaks detected', detail:'Your mix is close to digital full scale. Limiting and extra gain should be restrained.'});
    if (metrics.crest < 8) res.push({severity:'warning', title:'Limited dynamic headroom', detail:'The source already has a low peak-to-average ratio. Extra compression will be minimized to protect transients.'});
    if (metrics.rmsDb > -11) res.push({severity:'warning', title:'Already a loud mix', detail:'A loud premaster may not benefit from more gain. Consider Natural mode to preserve space.'});
    if (metrics.correlation < .15) res.push({severity:'warning', title:'Stereo compatibility needs attention', detail:'Low channel correlation can cause elements to disappear or change when collapsed to mono.'});
    if (metrics.channels === 1) res.push({severity:'neutral', title:'Mono source', detail:'The track will be rendered to stereo with identical channels; no artificial widening is added.'});
    if (res.length === 0) res.push({severity:'positive', title:'No major level or phase warnings', detail:'The basic checks look healthy. A light mastering pass is a reasonable starting point.'});
    res.push({severity:'neutral', title:'Source analysis complete', detail:`${metrics.channels} channel${metrics.channels > 1 ? 's' : ''} · ${(metrics.sampleRate / 1000).toFixed(1)} kHz · ${fmtTime(metrics.seconds)}. Local estimates are not calibrated loudness or artifact recognition.`});
    return res;
  }
  function renderFindings() {
    if (!state.sourceMetrics) return;
    const items = makeFindings(state.sourceMetrics);
    const container = $('findings');
    container.replaceChildren();
    for (const f of items) {
      const item = document.createElement('div');item.className = 'finding';
      const dot = document.createElement('span');dot.className = 'finding-dot ' + (f.severity === 'warning' ? 'warning' : f.severity === 'neutral' ? 'neutral' : '');
      const text = document.createElement('div'), title = document.createElement('strong'), detail = document.createElement('p');
      title.textContent = f.title;detail.textContent = f.detail;
      text.append(title, detail);item.append(dot,text);container.appendChild(item);
    }
    $('analysisStatus').textContent = `${items.length} FINDINGS`;
    const m = state.sourceMetrics;
    const lines = [`I've analyzed ${state.sourceName}.`];
    if (m.crest < 8 || m.rmsDb > -11) lines.push('This mix is already dense. I recommend Natural or Balanced, with restraint on added compression.');
    else if (m.correlation < .15) lines.push('Stereo compatibility deserves a listen before release. Mastering alone cannot reliably repair an unstable stereo mix.');
    else lines.push('The initial level and stereo checks look reasonable. Balanced is a good first master to audition.');
    lines.push('I use bounded, repeatable processing rules in this version—not a trained artifact-detection model. Always trust a level-matched listen.');
    $('assistantMessage').textContent = lines.join('\n\n');
  }
  function resetMaster() {
    masteredAudio.pause();masteredAudio.removeAttribute('src');masteredAudio.load();
    if (state.masterUrl) URL.revokeObjectURL(state.masterUrl);
    state.masterUrl=null;state.masterBlob=null;state.masterBuffer=null;state.masterMetrics=null;state.masteredPeaks=null;state.studioMetrics=null;state.renderSettings=null;
    if (state.side === 'master') state.side='original';
    $('masterBtn').disabled=true;$('downloadBtn').disabled=true;$('reportBtn').disabled=true;$('topExportBtn').disabled=true;$('shareBtn').disabled=true;
    $('originalBtn').classList.add('ab-active');$('masterBtn').classList.remove('ab-active');
    $('compareHint').textContent='Level-matched A/B after mastering';
    $('renderNote').textContent='Ready for a new master.';
    updatePlaybackGain();updateMetrics();drawWave();
  }
  function resetSource() {
    originalAudio.pause();originalAudio.removeAttribute('src');originalAudio.load();
    if (state.originalUrl) URL.revokeObjectURL(state.originalUrl);
    resetMaster();state.buffer=null;state.sourceFile=null;state.sourceMetrics=null;state.sourcePeaks=null;state.sourceName='';state.originalUrl=null;
    $('trackInfo').hidden=true;$('playBtn').disabled=true;$('seekbar').disabled=true;$('masterAction').disabled=true;
    $('stageTitle').textContent='Your next great sound starts here.';
    $('versionTag').textContent='READY FOR AUDIO';
    $('waveformEmpty').hidden=false;$('analysisStatus').textContent='AWAITING TRACK';
    $('findings').innerHTML='<div class="finding empty-finding"><span class="finding-dot neutral"></span><div><strong>Your mix, understood.</strong><p>Load a song to see its dynamics, level, stereo behavior, and processing advice.</p></div></div>';
    $('assistantMessage').textContent='Hey there. I\'m ready to help shape your next release.\n\nDrop in your mix and I\'ll highlight technical issues, suggest a mastering style, and explain the processing choices.';
    $('renderNote').textContent='Choose an audio file to begin.';
    $('waveformDuration').textContent='00:00';$('waveMid').textContent='0:00';$('waveEnd').textContent='0:00';$('totalTime').textContent='0:00';$('currentTime').textContent='0:00';
    $('rateLabel').textContent='Source rate';updateMetrics();drawWave();
  }
  async function loadFile(file, suppliedBuffer = null) {
    if (state.rendering || state.exporting) {toast('Finish mastering or exporting before opening another track.');return;}
    if (MAX_BYTES !== null && file.size > MAX_BYTES) {toast(`File exceeds the ${Math.round(MAX_BYTES/1048576)} MB limit on this device. Choose a smaller file.`);return;}
    if (file.size < 64) {toast('File is too small to contain audio.');return;}
    try {
      $('analysisStatus').textContent = 'DECODING';
      const context = await getContext();
      const decoded = suppliedBuffer || await context.decodeAudioData(await file.arrayBuffer());
      if (!decoded.duration || !Number.isFinite(decoded.duration)) throw new Error('The selected file contains no readable audio.');
      if (MAX_SECONDS !== null && decoded.duration > MAX_SECONDS) throw new Error(`Tracks must be less than ${MAX_SECONDS/60} minutes long on this device.`);
      if (decoded.numberOfChannels > 2) throw new Error('Please upload a mono or stereo mix.');
      const newMetrics=measure(decoded); const newPeaks=buildPeaks(decoded);
      resetSource();
      state.buffer=decoded;state.sourceFile=file;state.sourceName=file.name;state.sourceMetrics=newMetrics;state.sourcePeaks=newPeaks;
      state.originalUrl=URL.createObjectURL(file);originalAudio.src=state.originalUrl;originalAudio.load();
      $('trackInfo').hidden=false;$('trackName').textContent=file.name;
      $('trackSub').textContent=`${(file.size/1048576).toFixed(1)} MB · ${(decoded.sampleRate/1000).toFixed(1)} kHz · ${fmtTime(decoded.duration)}`;
      $('stageTitle').textContent=file.name.replace(/\.[^.]+$/, '').slice(0,64);
      $('versionTag').textContent='SOURCE LOADED';
      $('waveformEmpty').hidden=true;
      $('waveformDuration').textContent=fmtTime(decoded.duration);$('waveMid').textContent=fmtTime(decoded.duration/2);$('waveEnd').textContent=fmtTime(decoded.duration);
      $('playBtn').disabled=false;$('seekbar').disabled=false;$('masterAction').disabled=false;
      $('rateLabel').textContent=(state.engine === 'studio' || state.engine === 'desktop') ? '48 kHz' : `${(decoded.sampleRate/1000).toFixed(1)} kHz`;
      updateMetrics();renderFindings();updatePlaybackGain();drawWave();
      if (iPadMode && (decoded.duration > 4*60 || file.size > LONG_TRACK_BYTES)) {
        $('renderNote').textContent='Long track loaded. No fixed time limit; rendering depends on available device memory. Keep this app open while mastering.';
        toast(`Long track ready (${fmtTime(decoded.duration)}). Processing may take longer on this device.`);
      } else {
        toast('Audio ready. Choose your mastering style.');
      }
    } catch (error) {
      $('analysisStatus').textContent=state.buffer ? 'ANALYZED' : 'AWAITING TRACK';
      toast(`Couldn't decode audio: ${error.message || 'Unsupported format.'}${iPadMode ? ' If device memory is low, close other apps or try the desktop edition.' : ''}`);
    }
  }
  function makeDemo() {
    const sr=44100, seconds=12, count=seconds*sr;
    const ctx = audioContext;
    const buffer=ctx.createBuffer(2,count,sr);
    let seed=19284;
    const noise=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967295*2-1;};
    const chordHz=[220,261.63,329.63,196,246.94,293.66,174.61,220];
    for(let i=0;i<count;i++) {
      const t=i/sr, beat=t*2, kickPhase=beat%1, bar=Math.floor(t/1.5)%4;
      const kick=(Math.sin(2*Math.PI*(70*t+7*Math.exp(-kickPhase*25))) * Math.exp(-kickPhase*16))*.36;
      const snarePhase=(beat+.5)%1;
      const snare=(noise()*.10 + Math.sin(2*Math.PI*160*t)*.045) * Math.exp(-snarePhase*32);
      const hatPhase=(beat*2)%1, hat=noise() * .028 * Math.exp(-hatPhase*32);
      const hz=chordHz[bar*2], envelope=.58 + .12*Math.sin(2*Math.PI*.25*t);
      const synth=(Math.sin(2*Math.PI*hz*t)+.45*Math.sin(2*Math.PI*hz*1.5*t)+.25*Math.sin(2*Math.PI*hz*2*t))*.115*envelope;
      const bassHz=hz/2, bass=Math.sin(2*Math.PI*bassHz*t)*.15;
      const val=clamp(kick+snare+hat+synth+bass,-.93,.93);
      buffer.getChannelData(0)[i]=val;
      buffer.getChannelData(1)[i]=clamp(kick+snare+hat+synth*.93+bass+.015*Math.sin(2*Math.PI*(hz*1.01)*t),-.93,.93);
    }
    return buffer;
  }
  function addBiquad(offline, input, type, frequency, gain, q = .72) {
    if(Math.abs(gain)<.01 && type!=='highpass') return input;
    const node=offline.createBiquadFilter();node.type=type;node.frequency.value=frequency;
    if(type==='peaking')node.Q.value=q;
    if(type!=='highpass')node.gain.value=gain;
    input.connect(node);return node;
  }
  async function processLocal(buffer, settings) {
    const dsp=window.MasterForgeWebDSP;
    if(!dsp)throw new Error('Dynamic mastering engine not loaded. Refresh while online to update MasterForge.');
    return await dsp.master(buffer,settings,(stage,progress)=>{
      $('renderNote').textContent=stage + ' · ' + Math.round(progress*100) + '%';
    });
  }
  function wavBlob(buffer, bits = 24) {
    const channels=2, rate=buffer.sampleRate, frames=buffer.length, bytesPerSample=bits/8;
    const blockAlign=channels*bytesPerSample, dataSize=frames*blockAlign;
    if(dataSize>0xFFFFFFFF-44) throw new Error('Audio is too large for a standard WAV file.');
    const head=new ArrayBuffer(44), view=new DataView(head);
    const word=(p,s)=>{for(let i=0;i<s.length;i++)view.setUint8(p+i,s.charCodeAt(i));};
    word(0,'RIFF');view.setUint32(4,36+dataSize,true);word(8,'WAVE');word(12,'fmt ');view.setUint32(16,16,true);
    view.setUint16(20,1,true);view.setUint16(22,channels,true);view.setUint32(24,rate,true);view.setUint32(28,rate*blockAlign,true);view.setUint16(32,blockAlign,true);view.setUint16(34,bits,true);
    word(36,'data');view.setUint32(40,dataSize,true);
    const A=buffer.getChannelData(0),B=buffer.numberOfChannels>1?buffer.getChannelData(1):A;
    const chunkFrames=8192;const chunks=[head];
    for(let a=0;a<frames;a+=chunkFrames) {
      const limit=Math.min(frames,a+chunkFrames), chunk=new Uint8Array((limit-a)*blockAlign);let p=0;
      for(let i=a;i<limit;i++) for(const value of [A[i],B[i]]) {
        const dither=(Math.random()-Math.random())/(2**(bits-1));
        const x=clamp(value+dither,-1,1-1/(2**(bits-1)));
        if(bits===24){let q=Math.round(x*8388607);if(q<0)q+=16777216;chunk[p++]=q&255;chunk[p++]=(q>>>8)&255;chunk[p++]=(q>>>16)&255;}
        else {const q=Math.round(x*32767);chunk[p++]=q&255;chunk[p++]=(q>>>8)&255;}
      }
      chunks.push(chunk);
    }
    return new Blob(chunks,{type:'audio/wav'});
  }
  function safeFilename(name) {return name.replace(/\.[^.]+$/,'').replace(/[^a-z0-9_-]+/gi,'-').replace(/^-+|-+$/g,'').slice(0,65)||'track';}
  async function processStudio(file, settings) {
    const controller=new AbortController(), abort=setTimeout(()=>controller.abort(),180000);
    try {
      const form=new FormData();form.append('file',file);form.append('preset',settings.preset);
      for(const k of ['warmth','clarity','intensity','target'])form.append(k,String(settings[k]));
      const response=await fetch(`${state.apiUrl.replace(/\/+$/,'')}/api/v1/master`,{method:'POST',body:form,signal:controller.signal});
      if(!response.ok) {let reason='Studio mastering request failed.';try{const body=await response.json();reason=body.detail||reason;}catch(_){}throw new Error(typeof reason==='string'?reason:JSON.stringify(reason));}
      const blob=await response.blob();
      if(!blob.size)throw new Error('The server returned an empty file.');
      let metrics=null;
      const encoded=response.headers.get('X-MasterForge-Metrics');
      if(encoded) {try{metrics=JSON.parse(decodeURIComponent(encoded));}catch(_){}}
      return {blob,studioMetrics:metrics};
    } finally {clearTimeout(abort);}
  }
  async function processDesktop(file, settings) {
    if (!desktop) throw new Error('Desktop mastering is available only in the installed desktop app.');
    // Raw audio is transferred to the isolated Electron process, never transmitted over a network.
    // The desktop process runs bundled FFmpeg and returns only the rendered WAV and measurements.
    const raw = new Uint8Array(await file.arrayBuffer());
    const result = await desktop.masterAudio(raw, settings);
    if (!result?.bytes?.byteLength) throw new Error('The local mastering engine returned no audio.');
    return {blob: new Blob([result.bytes], {type:'audio/wav'}), studioMetrics: result.metrics};
  }
  async function startMastering() {
    if(!state.buffer||state.rendering)return;
    const settings=getSettings();
    if(!isValidPreset(settings.preset)){toast('Mastering style is unavailable in this app version. Reload the app online.');return;}
    state.rendering=true;
    $('masterAction').disabled=true;$('masterAction').textContent='✦  MASTERING AUDIO…';
    $('renderNote').textContent=state.engine==='studio'?'Sending audio to your configured studio service…':state.engine==='desktop'?'Rendering locally with bundled FFmpeg (two-pass)…':'Processing audio privately on your device…';
    try {
      let blob, rendered, recipe, studioMetrics=null;
      if(state.engine==='studio' || state.engine==='desktop') {
        if(state.engine==='studio' && settings.preset==='reference')throw new Error('Signature Beta requires Desktop Studio or Browser Local. The optional remote Studio API does not yet support this mode.');
        if(state.engine==='studio' && !state.apiUrl)throw new Error('Set a trusted Studio API URL in engine settings first.');
        const result=state.engine==='desktop' ? await processDesktop(state.sourceFile,settings) : await processStudio(state.sourceFile,settings);
        blob=result.blob;studioMetrics=result.studioMetrics;
        const c=await getContext();rendered=await c.decodeAudioData(await blob.arrayBuffer());
        recipe={engine:'FFmpeg two-pass loudnorm',details:'See exported studio report for measured LUFS and true peak.'};
      } else {
        const output=await processLocal(state.buffer,settings);
        rendered=output.buffer;recipe=output.recipe;studioMetrics=output.studioMetrics||null;
        $('renderNote').textContent='Encoding a 24-bit WAV…';
        await new Promise(resolve=>setTimeout(resolve,10));
        blob=wavBlob(rendered);
      }
      const metrics=measure(rendered),peaks=buildPeaks(rendered);
      resetMaster();
      // Retaining a second decoded copy is costly on iPad and unnecessary after
      // the mastered WAV Blob and lightweight waveform/metrics are produced.
      state.masterBuffer=null;state.masterMetrics=metrics;state.masteredPeaks=peaks;state.studioMetrics=studioMetrics;
      state.renderSettings={...settings,engine:state.engine,recipe,createdAt:new Date().toISOString()};
      state.masterUrl=URL.createObjectURL(blob);state.masterBlob=blob;
      masteredAudio.src=state.masterUrl;masteredAudio.load();
      $('masterBtn').disabled=false;$('downloadBtn').disabled=false;$('topExportBtn').disabled=false;$('reportBtn').disabled=false;$('shareBtn').disabled=false;
      $('versionTag').textContent=`${presetName(settings.preset).toUpperCase()} MASTER`;
      $('renderNote').textContent='Master ready. Use Level-match A/B for tone or switch it off to hear the output level difference.';
      $('compareHint').textContent=$('levelMatch').checked?'Matched using approximate RMS levels':'Actual relative output level';
      const pre=state.sourceMetrics;
      const delta=metrics.rmsDb-pre.rmsDb;
      $('assistantMessage').textContent=`Your ${presetName(settings.preset)} master is ready.\n\nEstimated RMS changed ${delta>=0?'+':''}${round(delta)} dB and sample peak is ${round(metrics.peakDb)} dBFS.\n\n${(state.engine==='studio' || state.engine==='desktop') && studioMetrics?.output ? `Studio metering: ${studioMetrics.output.input_i||studioMetrics.output.integrated_lufs||'see report'} integrated LUFS (see report for measured fields).\n\n` : ''}Switch ORIGINAL / MASTERED for a level-matched comparison. The final decision should be made by listening, not the numbers alone.`;
      rendered=null; // Allow Safari to reclaim PCM after encoding.
      updateDynamicReport(recipe);
      updatePlaybackGain();switchSide('master');toast('Master complete! Compare and download when ready.');
    } catch(error) { $('renderNote').textContent=iPadMode?'Mastering could not finish. Close other apps to free memory, or use the Windows/CachyOS edition for large files.':'Mastering failed. Please check the settings and try again.';toast(`Mastering failed: ${error.message||'Unknown error'}`); }
    finally {state.rendering=false;$('masterAction').disabled=!state.buffer;$('masterAction').innerHTML='<span>✦</span> CREATE MASTER <span>→</span>';}
  }
  const EXPORT_MIMES={wav:'audio/wav',mp3:'audio/mpeg',m4a:'audio/mp4'};
  function selectedExport() {
    const format=$('exportFormat').value;
    if(!Object.hasOwn(EXPORT_MIMES,format)) throw new Error('Choose a supported export format.');
    const bitrate=Number($('exportBitrate').value);
    if(![128,192,256,320].includes(bitrate)) throw new Error('Invalid encoding bitrate.');
    return {format,bitrate};
  }
  function masterFilename(format='wav') {
    return `${safeFilename(state.sourceName)}-masterforge-${presetName(state.renderSettings?.preset||'master').toLowerCase()}.${format}`;
  }
  function refreshExportOptions() {
    const {format}=selectedExport();
    $('exportBitrateRow').hidden=format==='wav';
    if(format==='m4a' && $('exportBitrate').value==='320') $('exportBitrate').value='256';
    $('downloadBtn').textContent=`↓ Download ${format.toUpperCase()} master`;
    $('shareBtn').textContent=`↗ Share ${format.toUpperCase()} / Save to Files`;
    $('formatLabel').textContent=format==='wav'?'WAV · PCM 24-bit':format==='mp3'?`MP3 · ${$('exportBitrate').value} kbps`:`M4A · AAC ${$('exportBitrate').value} kbps`;
    $('exportHint').textContent=format==='wav'?'Uncompressed audio · best for archival.':format==='mp3'?'Compressed MP3 for wide compatibility. Browser export may need a one-time encoder download.':'AAC in an M4A container. Browser support varies; offline desktop export is always available.';
  }
  function downloadBlob(blob, name) {
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download=name;
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  }
  let lameLoader=null;
  function loadMp3Encoder() {
    if(window.lamejs?.Mp3Encoder) return Promise.resolve();
    if(!lameLoader) lameLoader=new Promise((resolve,reject)=>{
      // Only JavaScript code is fetched; audio PCM never leaves the browser.
      // Cache the encoder on first use through the PWA service worker.
      const script=document.createElement('script');
      script.src='https://cdn.jsdelivr.net/npm/lamejs@1.2.1/lame.min.js';
      script.onload=()=>window.lamejs?.Mp3Encoder?resolve():reject(new Error('MP3 encoder did not initialize.'));
      script.onerror=()=>reject(new Error('MP3 encoder unavailable. Connect to the internet for the initial encoder download, or export from the desktop app.'));
      document.head.appendChild(script);
    }).catch(error=>{lameLoader=null;throw error;});
    return lameLoader;
  }
  async function encodeMp3Browser(wav,bitrate) {
    await loadMp3Encoder();
    const ctx=await getContext();
    const audio=await ctx.decodeAudioData(await wav.arrayBuffer());
    const rate=audio.sampleRate;
    if(rate<32000 || rate>48000) throw new Error('MP3 encoding supports source rates from 32–48 kHz. Use the desktop app for other rates.');
    const encoder=new window.lamejs.Mp3Encoder(2,rate,bitrate);
    const L=audio.getChannelData(0),R=audio.numberOfChannels>1?audio.getChannelData(1):L;
    const chunks=[];
    const batch=1152*8;
    const left=new Int16Array(batch),right=new Int16Array(batch);
    for(let pos=0;pos<L.length;pos+=batch){
      const len=Math.min(batch,L.length-pos);
      for(let i=0;i<len;i++){left[i]=Math.round(clamp(L[pos+i],-1,1)*32767);right[i]=Math.round(clamp(R[pos+i],-1,1)*32767);}
      const encoded=encoder.encodeBuffer(left.subarray(0,len),right.subarray(0,len));
      if(encoded.length)chunks.push(new Uint8Array(encoded));
      // Yield periodically so large exports do not completely freeze the interface.
      if((pos/batch)%24===0){$('renderNote').textContent=`Encoding MP3… ${Math.round(100*(pos+len)/L.length)}%`;await new Promise(r=>setTimeout(r,0));}
    }
    const last=encoder.flush();if(last.length)chunks.push(new Uint8Array(last));
    const blob=new Blob(chunks,{type:'audio/mpeg'});
    if(blob.size<100)throw new Error('The MP3 encoder returned an empty file.');
    return blob;
  }
  function browserM4aMime(){
    if(typeof MediaRecorder==='undefined'||typeof MediaRecorder.isTypeSupported!=='function')return null;
    return ['audio/mp4;codecs=mp4a.40.2','audio/mp4','video/mp4;codecs=mp4a.40.2'].find(x=>MediaRecorder.isTypeSupported(x))||null;
  }
  async function encodeM4aBrowser(wav,bitrate) {
    const mime=browserM4aMime();
    if(!mime)throw new Error('This browser cannot encode M4A/AAC. Try Safari on a supported device or the Windows/CachyOS desktop app.');
    const ctx=await getContext();
    const audio=await ctx.decodeAudioData(await wav.arrayBuffer());
    const encoderCtx=new (window.AudioContext||window.webkitAudioContext)({sampleRate:audio.sampleRate});
    const destination=encoderCtx.createMediaStreamDestination();
    const source=encoderCtx.createBufferSource();source.buffer=audio;source.connect(destination);
    const chunks=[];
    try{
      return await new Promise(async(resolve,reject)=>{
        let recorder,tick,finished=false;
        const done=(error,blob)=>{if(finished)return;finished=true;clearInterval(tick);try{source.stop();}catch(_){};
          try{destination.stream.getTracks().forEach(t=>t.stop());}catch(_){};
          if(error)reject(error);else resolve(blob);};
        try{
          recorder=new MediaRecorder(destination.stream,{mimeType:mime,audioBitsPerSecond:bitrate*1000});
          recorder.ondataavailable=e=>{if(e.data?.size)chunks.push(e.data);};
          recorder.onerror=e=>done(new Error(`M4A recording failed: ${e.error?.message||'unknown error'}`));
          recorder.onstop=()=>{
            const blob=new Blob(chunks,{type:'audio/mp4'});
            if(blob.size<100)done(new Error('M4A encoder produced no audio.'));else done(null,blob);
          };
          const startedAt=performance.now();
          recorder.start(1000);
          await encoderCtx.resume();
          source.start();
          $('renderNote').textContent=`Encoding M4A in real time (${fmtTime(audio.duration)} of audio)…`;
          tick=setInterval(()=>{const elapsed=(performance.now()-startedAt)/1000;$('renderNote').textContent=`Encoding M4A… ${fmtTime(elapsed)} / ${fmtTime(audio.duration)}. Keep this app open.`;},1000);
          source.onended=()=>{if(recorder.state!=='inactive')recorder.stop();};
        }catch(err){done(err);}
      });
    }finally {encoderCtx.close().catch(()=>{});}
  }
  async function getExportBlob(format,bitrate){
    if(format==='wav')return state.masterBlob;
    if(desktop?.encodeAudio) {
      const encoded=await desktop.encodeAudio(new Uint8Array(await state.masterBlob.arrayBuffer()),format,bitrate);
      if(!encoded?.byteLength)throw new Error('Desktop encoder returned no output.');
      return new Blob([encoded],{type:EXPORT_MIMES[format]});
    }
    if(format==='mp3')return encodeMp3Browser(state.masterBlob,bitrate);
    return encodeM4aBrowser(state.masterBlob,bitrate);
  }
  async function exportMaster(share=false){
    if(!state.masterBlob || state.exporting || state.rendering)return;
    const {format,bitrate}=selectedExport();
    state.exporting=true;
    $('downloadBtn').disabled=$('topExportBtn').disabled=$('shareBtn').disabled=true;
    const note=$('renderNote').textContent;
    let success=false;
    try {
      $('renderNote').textContent=`Preparing ${format.toUpperCase()} export…`;
      const blob=await getExportBlob(format,bitrate);
      const filename=masterFilename(format);
      if(share){
        if(!navigator.share || typeof File==='undefined')throw new Error('System sharing is not supported in this browser. Use Download instead.');
        const file=new File([blob],filename,{type:EXPORT_MIMES[format]});
        if(navigator.canShare && !navigator.canShare({files:[file]}))throw new Error('File sharing is unavailable for this format. Use Download instead.');
        await navigator.share({files:[file],title:`MasterForge AI · ${format.toUpperCase()} master`});
      } else {downloadBlob(blob,filename);toast(`${format.toUpperCase()} export ready. Check your Downloads or Files.`);}
      success=true;
    } catch(e){if(e?.name!=='AbortError'){$('renderNote').textContent=`${format.toUpperCase()} export failed: ${e.message||e}`;toast(`Export failed: ${e.message||e}`);}else success=true;}
    finally {state.exporting=false;$('downloadBtn').disabled=$('topExportBtn').disabled=$('shareBtn').disabled=!state.masterBlob;if(success)$('renderNote').textContent=note;}
  }
  function report() {
    if(!state.renderSettings)return;
    const data={app:'MasterForge AI',version:'1.0.0-beta',source:state.sourceName,presetName:presetName(state.renderSettings.preset),settings:state.renderSettings,
      input:state.sourceMetrics,output:state.masterMetrics,studioMeasurements:state.studioMetrics,
      limitations:['Browser Dynamic Studio uses a K-weighted gated LUFS estimate rather than a certified meter. Browser 4x peak estimates and limiter are not equivalent to the FFmpeg true-peak chain.','No trained AI artifact classifier is included.','Lossy MP3/AAC exports cannot restore quality absent from the source and can introduce encoder peaks.','Compare masters by ear and check final exports with a trusted meter before distribution.']};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`${safeFilename(state.sourceName)}-masterforge-report.json`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),15000);
  }

  const STARTUP_KEY='masterforge.startup.defaults.v1';
  const FACTORY_STARTUP={preset:'reference',target:-14,warmth:0,clarity:0,intensity:0};
  function readStartupDefaults(){
    try{
      const value=JSON.parse(localStorage.getItem(STARTUP_KEY)||'null');
      if(value && isValidPreset(value.preset) && [-16,-14,-12,-11,-10,-9].includes(Number(value.target))
          && ['warmth','clarity','intensity'].every(k=>Number.isFinite(Number(value[k])))){
        return {...value};
      }
    }catch(_){}
    return {...FACTORY_STARTUP};
  }
  function applyMasterPreferences(v){
    state.preset=v.preset;
    document.querySelectorAll('.preset').forEach(btn=>{
      const selected=btn.dataset.preset===state.preset;
      btn.classList.toggle('active',selected);btn.setAttribute('aria-checked',String(selected));
    });
    $('target').value=String(v.target);
    for(const name of ['warmth','clarity','intensity']){
      const value=clamp(Number(v[name]),name==='intensity'?-2:-3,name==='intensity'?2:3);
      $(name).value=String(value);
      $(name+'Val').textContent=value>0?'+'+value:String(value);
    }
  }
  function loadStartupPreferences(){
    applyMasterPreferences(readStartupDefaults());
    updateDefaultsSummary();
  }
  function updateDefaultsSummary(){
    const target=$('defaultSummary');
    if(!target)return;
    const d=readStartupDefaults();
    const label=({[-16]:'Open',[-14]:'Streaming',[-12]:'Energetic',[-11]:'Signature',[-10]:'Loud',[-9]:'Max Impact'})[d.target]||'Custom';
    target.textContent='Startup: '+presetName(d.preset)+' · '+label+' ('+d.target+' LUFS)';
  }
  function installWebStudioControls(){
    const base=$('target')?.closest('.controls-panel')||$('target')?.parentElement?.parentElement;
    if(base && !$('startupDefaults')){
      const row=document.createElement('div');row.id='startupDefaults';row.className='startup-defaults';
      row.innerHTML='<div id="defaultSummary" class="startup-summary"></div><div class="startup-actions"><button type="button" id="saveStartup">Save current as default</button><button type="button" id="resetStartup">Reset defaults</button></div>';
      base.appendChild(row);
      $('saveStartup').addEventListener('click',()=>{
        try{localStorage.setItem(STARTUP_KEY,JSON.stringify(getSettings()));updateDefaultsSummary();toast('Your mastering defaults are saved on this device.');}
        catch(_){toast('Browser storage is unavailable. Defaults could not be saved.');}
      });
      $('resetStartup').addEventListener('click',()=>{
        try{localStorage.removeItem(STARTUP_KEY);}catch(_){}
        applyMasterPreferences(FACTORY_STARTUP);updateDefaultsSummary();toast('Signature + Streaming startup defaults restored.');
      });
    }
    const anchor=document.querySelector('.changes-panel');
    if(anchor && !$('dynamicAnalysis')){
      const panel=document.createElement('section');panel.id='dynamicAnalysis';panel.className='panel dynamic-analysis';panel.hidden=true;
      panel.innerHTML='<div class="section-top"><h2><span class="panel-num">◈</span> DYNAMIC MASTERING</h2><span class="muted-label">FULL SONG</span></div><div id="dynamicSummary"></div>';
      anchor.insertAdjacentElement('afterend',panel);
    }
  }
  function updateDynamicReport(recipe){
    const panel=$('dynamicAnalysis'),summary=$('dynamicSummary');
    if(!panel||!summary||!recipe?.automation)return;
    const a=recipe.automation,total=a.scene_seconds||{},order=['quiet','steady','dense','transient','silence'];
    const parts=order.filter(k=>total[k]>0.01).map(k=>'<span><b>'+k.toUpperCase()+'</b> '+Math.round(total[k])+'s</span>').join('');
    const l=Number(recipe.estimated_loudness_after_lufs),tp=Number(recipe.true_peak_estimate_db);
    summary.innerHTML='<p>'+a.sections.length+' sections analyzed across '+fmtTime(a.seconds_analyzed)+'. Time-varying gain and EQ follow the track.</p>'+
      '<div class="dynamic-breakdown">'+parts+'</div>'+
      '<p><b>Estimated integrated loudness:</b> '+(Number.isFinite(l)?round(l,1)+' LUFS':'unavailable')+
      ' · <b>Peak estimate:</b> '+(Number.isFinite(tp)?round(tp,1)+' dBTP':'unavailable')+'</p>'+
      '<small>Browser metering is an estimate, not a calibrated reference reading.</small>';
    panel.hidden=false;
  }
  function attachEvents() {
    $('dropzone').addEventListener('click',()=>$('fileInput').click());
    $('dropzone').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('fileInput').click();}});
    $('dropzone').addEventListener('dragover',e=>{e.preventDefault();$('dropzone').classList.add('dragover');});
    $('dropzone').addEventListener('dragleave',()=>$('dropzone').classList.remove('dragover'));
    $('dropzone').addEventListener('drop',e=>{e.preventDefault();$('dropzone').classList.remove('dragover');if(e.dataTransfer.files[0])loadFile(e.dataTransfer.files[0]);});
    $('fileInput').addEventListener('change',e=>{if(e.target.files[0])loadFile(e.target.files[0]);e.target.value='';});
    $('demoBtn').addEventListener('click',async()=>{try {await getContext();const audio=makeDemo();const file=new File([wavBlob(audio,16)],'MasterForge-Demo-Groove.wav',{type:'audio/wav'});await loadFile(file,audio);}catch(e){toast(`Demo unavailable: ${e.message}`);}});
    $('removeFile').addEventListener('click',resetSource);
    document.querySelectorAll('.preset').forEach(btn=>btn.addEventListener('click',()=>{
      if(!isValidPreset(btn.dataset.preset)) {toast('Mastering style is unavailable. Reload the updated app.');return;}
      state.preset=btn.dataset.preset;
      if(state.preset==='reference'){
        $('target').value='-11';
        $('loudnessGuidance').textContent='Signature uses dynamic full-song analysis and gated loudness estimation. Save your preferred Signature + Streaming settings below.';
      }
      document.querySelectorAll('.preset').forEach(other=>{other.classList.toggle('active',other===btn);other.setAttribute('aria-checked',String(other===btn));});
      if(state.masterUrl)$('renderNote').textContent='Style changed. Create a new master to hear it.';
    }));
    for(const id of ['warmth','clarity','intensity'])$(id).addEventListener('input',()=>{$(id+'Val').textContent=Number($(id).value)>0?'+'+$(id).value:$(id).value;if(state.masterUrl)$('renderNote').textContent='Controls changed. Re-render to apply them.';});
    $('target').addEventListener('change',()=>{
      const loud = Number($('target').value) >= -10;
      $('loudnessGuidance').textContent=loud?'Aggressive loudness: listen for pumping or lost transients. Verify final LUFS and peaks with a trusted meter.':'Higher output can reduce punch. Browser measurements are estimates.';
      if(state.masterUrl)$('renderNote').textContent='Loudness target changed. Create a new master to apply it to export.';
    });
    $('resetSliders').addEventListener('click',()=>{for(const id of ['warmth','clarity','intensity']){$(id).value=0;$(id+'Val').textContent='0';}toast('Fine-tuning controls reset.');});
    $('playBtn').addEventListener('click',async()=>{const audio=currentAudio();if(audio.paused){try{await audio.play();loopPlayhead();}catch(error){toast(`Playback unavailable: ${error.message}`);}}else audio.pause();updateTransport();});
    $('originalBtn').addEventListener('click',()=>switchSide('original'));
    $('masterBtn').addEventListener('click',()=>switchSide('master'));
    $('seekbar').addEventListener('input',e=>{const time=Number(e.target.value)/1000*(state.buffer?.duration||0);for(const audio of [originalAudio,masteredAudio]){if(audio.src)try{audio.currentTime=time;}catch(_){}}updateTransport();});
    $('waveCanvas').addEventListener('click',e=>{if(!state.buffer)return;const bounds=e.target.getBoundingClientRect(),ratio=clamp((e.clientX-bounds.left)/bounds.width,0,.999);const time=state.buffer.duration*ratio;for(const audio of [originalAudio,masteredAudio]){if(audio.src)try{audio.currentTime=time;}catch(_){}}updateTransport();});
    $('volume').addEventListener('input',updatePlaybackGain);
    $('levelMatch').addEventListener('change',()=>{updatePlaybackGain();$('compareHint').textContent=$('levelMatch').checked?'Matched using approximate RMS levels':'Actual relative output level';});
    $('masterAction').addEventListener('click',startMastering);
    $('downloadBtn').addEventListener('click',()=>exportMaster(false));$('topExportBtn').addEventListener('click',()=>exportMaster(false));$('reportBtn').addEventListener('click',report);
    $('shareBtn').addEventListener('click',()=>exportMaster(true));
    $('exportFormat').addEventListener('change',refreshExportOptions);
    $('exportBitrate').addEventListener('change',refreshExportOptions);
    $('dismissInstall').addEventListener('click',()=>{ $('ipadInstallTip').hidden=true; });
    window.addEventListener('resize',refreshWave);
    document.addEventListener('keydown',e=>{if(e.code==='Space'&&!['INPUT','SELECT','BUTTON','TEXTAREA'].includes(document.activeElement.tagName)&&!$('settingsDialog').open&&state.buffer){e.preventDefault();$('playBtn').click();}});
    $('settingsBtn').addEventListener('click',()=>$('settingsDialog').showModal());
    if (desktop?.onOpenShortcut) desktop.onOpenShortcut(async () => {
      try {const selected=await desktop.openAudioFile();if(selected?.bytes)await loadFile(new File([selected.bytes],selected.name));}
      catch(error){toast(`Open failed: ${error.message}`);}
    });
    $('settingsDialog').addEventListener('close',()=>{
      if($('settingsDialog').returnValue!=='save')return;
      const newEngine=document.querySelector('input[name="engine"]:checked').value;
      const newUrl=$('apiUrl').value.trim().replace(/\/+$/,'');
      if(newEngine==='desktop'&&!desktop){toast('Desktop Studio is only available in the native app.');return;}
      if(newEngine==='studio'&&(!/^https?:\/\//i.test(newUrl)||newUrl.includes('@'))){toast('Enter a valid Studio API URL (https://...).');return;}
      if(newEngine==='studio') {let parsed;try {parsed=new URL(newUrl);}catch(_){toast('Enter a valid Studio API URL.');return;}if(location.protocol==='https:'&&parsed.protocol!=='https:'){toast('Use HTTPS for a studio server when the website is HTTPS.');return;}if(parsed.username||parsed.password||parsed.search||parsed.hash){toast('Use a server base URL without credentials, query parameters, or fragments.');return;}}
      state.engine=newEngine;state.apiUrl=newUrl;
      try{localStorage.setItem('masterforge.engine',newEngine);localStorage.setItem('masterforge.apiUrl',newUrl);}catch(_){}
      applyEngineUI();toast(newEngine==='local'?'Browser Dynamic Studio enabled. No audio is uploaded.':newEngine==='desktop'?'Offline desktop mastering enabled. Audio never leaves this computer.':'Studio API configured. Uploads will be sent to that server when mastering.');
    });
  }
  function applyEngineUI() {
    const isDesktopEngine=state.engine==='desktop';
    $('engineStatus').textContent=isDesktopEngine?'DESKTOP STUDIO':state.engine==='studio'?'STUDIO API':'DYNAMIC WEB DSP';
    $('engineLabel').textContent=isDesktopEngine?'Offline Studio (FFmpeg)':state.engine==='studio'?'Studio Server':desktop?'Browser DSP':'Browser Dynamic Studio';
    $('rateLabel').textContent=state.engine==='studio'||isDesktopEngine?'48 kHz':state.buffer?`${(state.buffer.sampleRate/1000).toFixed(1)} kHz`:'Source rate';
    document.querySelectorAll('input[name="engine"]').forEach(r=>r.checked=r.value===state.engine);
    $('apiUrl').value=state.apiUrl;
    document.querySelector('.privacy-pill').textContent=state.engine==='studio'?'◈ Studio API sends audio to your configured server':isDesktopEngine?'◈ Fully offline · audio stays on this computer':'◈ Your audio stays on your device in Local mode';
    const desktopOption=$('desktopEngineOption');
    if (desktopOption) desktopOption.hidden=!desktop;
    $('desktopNotice').hidden=!desktop;
    $('studioEngineOption').hidden=!!desktop || iPadMode;
    $('apiUrlLabel').hidden=!!desktop || iPadMode;
    $('apiUrl').hidden=!!desktop || iPadMode;
    $('remoteNotice').hidden=!!desktop || iPadMode;
    $('engineIntro').textContent=iPadMode?'Dynamic mastering runs privately in your browser with whole-song analysis. Long tracks are supported, but mobile memory and codec limits still apply.':desktop?'Desktop Studio uses the built-in FFmpeg engine for offline two-pass mastering. Browser DSP is also available for a faster lightweight render. Neither mode uploads your music.':'Local mode performs full-song Dynamic Signature mastering entirely in your browser. Audio never uploads unless you explicitly configure Studio API.';
  }
  function init() {
    attachEvents();
    installWebStudioControls();
    loadStartupPreferences();
    let storedEngine = null;
    try {storedEngine=localStorage.getItem('masterforge.engine');state.apiUrl=localStorage.getItem('masterforge.apiUrl')||'';}catch(_){}
    // Desktop Studio is the default inside Electron, even if a browser-local preference previously existed.
    state.engine=desktop?(storedEngine==='local'?'local':'desktop'):(iPadMode?'local':storedEngine==='studio'?'studio':'local');
    if(desktop) {
      document.body.classList.add('desktop-app');
      document.querySelector('.trust-panel p').innerHTML='<b>Made for local mastering.</b><br>Your files remain on your computer. Studio mode uses bundled FFmpeg and no cloud service. Processing is experimental and has not yet undergone independent listening tests.';
    }
    if(iPadMode){
      document.body.classList.add('ipad-app');
      $('dropzone').querySelector('strong').textContent='Choose music from Files';
      $('dropzone').querySelector('p').textContent='Tap to browse audio on your device';
      $('dropzone').querySelector('small').textContent='WAV, MP3, M4A · no fixed time limit';
      $('ipadInstallTip').hidden=Boolean(standalone);
      $('shareBtn').hidden=false;
      $('mobileBadge').hidden=false;
      $('mobileLimitation').hidden=false;
      $('studioEngineOption').hidden=true;
      $('assistantMessage').textContent='MasterForge analyzes the complete song and applies dynamic mastering entirely on your device. Signature adapts to quiet, dense and transient-rich sections. Keep the app open until export completes.';
    }
    refreshExportOptions();applyEngineUI();drawWave();
    if(!desktop && 'serviceWorker' in navigator && (location.protocol==='https:' || location.hostname==='localhost' || location.hostname==='127.0.0.1')) {
      window.addEventListener('load',()=>{ navigator.serviceWorker.register('./sw.js').catch(()=>{}); });
    }
  }
  init();
})();
