/* MasterForge AI — browser-native Dynamic Mastering (v1.0 beta).
 * All PCM stays on device. Browser DSP is not bit-equivalent to Python/FFmpeg.
 * Copyright MasterForge contributors. Uses Web Audio plus bounded JS DSP.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.MasterForgeWebDSP = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
  const toDb = x => 20 * Math.log10(Math.max(x, 1e-12));
  const toGain = x => Math.pow(10, x / 20);
  const percentile = (arr, p) => {
    if (!arr.length) return 0;
    const x = arr.slice().sort((a,b) => a-b), i=(x.length-1)*p, lo=Math.floor(i), hi=Math.ceil(i);
    return x[lo] + (x[hi]-x[lo])*(i-lo);
  };
  const PRESET_STRENGTH={natural:.16,balanced:.47,impact:.66,reference:.78,signature:.78};
  function normalPreset(p) { const q=p==='reference'?'signature':p; if (!Object.hasOwn(PRESET_STRENGTH,q)) throw new Error('Unknown mastering preset.'); return q; }
  function validateBuffer(buffer) {
    if (!buffer || !buffer.length || !buffer.sampleRate || buffer.numberOfChannels < 1 || buffer.numberOfChannels > 2)
      throw new Error('Please load a supported mono or stereo track.');
    return {left:buffer.getChannelData(0),right:buffer.getChannelData(buffer.numberOfChannels>1?1:0),rate:buffer.sampleRate,n:buffer.length};
  }
  function analyzeSections(buffer, preset='signature') {
    const {left,right,rate,n}=validateBuffer(buffer);
    const profile=normalPreset(preset), decimate=Math.max(1,Math.floor(rate/18000)), effective=rate/decimate;
    const alpha=f=>1-Math.exp(-2*Math.PI*f/effective);
    const a180=alpha(180),a1100=alpha(1100),a4000=alpha(4000),a7000=alpha(Math.min(7000,effective*.40));
    let low=0,mid=0,hi=0,top=0, count=0, peak=0, energy=0, bassE=0,midsE=0,presE=0,airE=0;
    const widthStats={a:0,b:0,ab:0,side:0}, sections=[], win=Math.max(1,Math.round(rate*2/decimate));
    let globalBass=0,globalMids=0,globalPres=0,globalAir=0;
    const push=()=>{
      if (!count) return;
      const rms=Math.sqrt(energy/count), rmsDb=toDb(rms), crest=toDb(peak)-rmsDb;
      const start=sections.length*2, end=Math.min(n/rate, start+(count*decimate/rate));
      const bands={bass:Math.sqrt(bassE/count),mids:Math.sqrt(midsE/count),presence:Math.sqrt(presE/count),air:Math.sqrt(airE/count)};
      sections.push({start_seconds:start,end_seconds:end,rms_dbfs:rmsDb,crest_db:crest,scene:'steady',gain_db:0,bands});
      globalBass+=bassE;globalMids+=midsE;globalPres+=presE;globalAir+=airE;
      count=0;peak=0;energy=0;bassE=midsE=presE=airE=0;
    };
    for (let i=0;i<n;i+=decimate) {
      const l=left[i],r=right[i], v=(l+r)*.5;
      if (!Number.isFinite(v)) throw new Error('Invalid audio samples in source recording.');
      low+=a180*(v-low);mid+=a1100*(v-mid);hi+=a4000*(v-hi);top+=a7000*(v-top);
      const b=low,m=mid-low,p=hi-mid,air=v-top;
      bassE+=b*b;midsE+=m*m;presE+=p*p;airE+=air*air;
      energy+=(l*l+r*r)*.5;peak=Math.max(peak,Math.abs(l),Math.abs(r));
      widthStats.a+=l*l;widthStats.b+=r*r;widthStats.ab+=l*r;widthStats.side+=(l-r)*(l-r);
      count++;
      if(count>=win)push();
    }
    push();
    const valid=sections.filter(x=>x.rms_dbfs>-65), rms=valid.map(x=>x.rms_dbfs), crests=valid.map(x=>x.crest_db);
    if(!valid.length)throw new Error('This track is effectively silent.');
    const p25=percentile(rms,.25),median=percentile(rms,.5),p75=percentile(rms,.75),crestMedian=percentile(crests,.5),spread=p75-p25;
    const strength=PRESET_STRENGTH[profile], totals={quiet:0,steady:0,dense:0,transient:0,silence:0};
    const avgBands={bass:Math.sqrt(globalBass/Math.max(1,n/decimate)),mids:Math.sqrt(globalMids/Math.max(1,n/decimate)),presence:Math.sqrt(globalPres/Math.max(1,n/decimate)),air:Math.sqrt(globalAir/Math.max(1,n/decimate))};
    for(const s of sections){
      const l=s.rms_dbfs,transient=s.crest_db>=Math.max(10,crestMedian+3);
      s.scene=l<=-65?'silence':transient?'transient':spread<2?'steady':l<=p25?'quiet':l>=p75?'dense':'steady';
      if(s.scene==='quiet')s.gain_db=strength*Math.min(.85,.24+Math.max(0,median-l)*.075);
      else if(s.scene==='dense')s.gain_db=-strength*Math.min(.82,.22+Math.max(0,l-median)*.08);
      else if(s.scene==='transient')s.gain_db=l>=median?0:strength*.10;
      else s.gain_db=0;
      s.gain_db=Math.round(s.gain_db*1000)/1000;
      totals[s.scene]+=s.end_seconds-s.start_seconds;
    }
    const correlation=(left===right?1:widthStats.ab/(Math.sqrt(widthStats.a*widthStats.b)+1e-12));
    return {analysis_coverage:'entire_recording',seconds_analyzed:n/rate,window_seconds:2,sections,
      scene_seconds:Object.fromEntries(Object.entries(totals).map(([k,v])=>[k,Math.round(v*10)/10])),
      p25_dbfs:p25,median_dbfs:median,p75_dbfs:p75,median_crest_db:crestMedian,
      max_abs_gain_db:Math.max(...sections.map(s=>Math.abs(s.gain_db))),
      correlation:clamp(correlation,-1,1),side_rms:Math.sqrt(widthStats.side/Math.max(1,n/decimate)),
      avg_bands:avgBands};
  }
  function toneSettings(analysis, settings){
    const p=normalPreset(settings.preset),b=analysis.avg_bands,ratio=(x,y)=>toDb(x)-toDb(y);
    let bass,lowMid,presence,air;
    if(p==='signature'){
      bass=clamp(1.55+clamp(ratio(b.mids,b.bass),-12,12)*.09+(settings.warmth||0)*.55,.35,2.7);
      lowMid=-clamp(2.5+clamp(ratio(b.mids,b.presence),-12,12)*.09,1.4,4.2);
      presence=clamp(1.5+clamp(ratio(b.mids,b.presence),-12,12)*.08+(settings.clarity||0)*.4,.3,2.9);
      air=clamp(.65+clamp(ratio(b.mids,b.air),-18,18)*.012+(settings.clarity||0)*.18,0,1.3);
    } else {
      const base={natural:[.1,-.15,.15,.08],balanced:[.35,-.5,.5,.17],impact:[.8,-.8,.8,.2]}[p];
      bass=clamp(base[0]+(settings.warmth||0)*.55,-2.5,2.8);
      lowMid=base[1];presence=clamp(base[2]+(settings.clarity||0)*.4,-2.2,2.9);
      air=clamp(base[3]+(settings.clarity||0)*.18,-.8,1.3);
    }
    return {bass,lowMid,presence,air};
  }
  function kFilterCoeffs(sampleRate) {
    const f=1681.974450955533,G=3.999843853973347,Q=.7071752369554196;
    const K=Math.tan(Math.PI*f/sampleRate), Vh=Math.pow(10,G/20),Vb=Math.pow(Vh,.4996667741545416),den=1+K/Q+K*K;
    const shelf={b0:(Vh+Vb*K/Q+K*K)/den,b1:2*(K*K-Vh)/den,b2:(Vh-Vb*K/Q+K*K)/den,a1:2*(K*K-1)/den,a2:(1-K/Q+K*K)/den};
    const f2=38.13547087602444,Q2=.5003270373238773,K2=Math.tan(Math.PI*f2/sampleRate),d2=1+K2/Q2+K2*K2;
    const hp={b0:1/d2,b1:-2/d2,b2:1/d2,a1:2*(K2*K2-1)/d2,a2:(1-K2/Q2+K2*K2)/d2};
    return [shelf,hp];
  }
  function biquad(c){let x1=0,x2=0,y1=0,y2=0;return x=>{const y=c.b0*x+c.b1*x1+c.b2*x2-c.a1*y1-c.a2*y2;x2=x1;x1=x;y2=y1;y1=y;return y;};}
  async function integratedLufs(buffer, progress) {
    const {left,right,rate,n}=validateBuffer(buffer),ch=buffer.numberOfChannels;
    const [a,b]=kFilterCoeffs(rate), L1=biquad(a),L2=biquad(b),R1=biquad(a),R2=biquad(b);
    const blocks=[], blockLen=Math.max(1,Math.round(rate*.4)),hop=Math.max(1,Math.round(rate*.1));
    // Compute exact overlapping 400 ms blocks from 100 ms sub-block energies.
    const sub=[],group=Math.max(1,hop), chunk=262144;
    let energy=0,count=0;
    for(let i=0;i<n;i++){
      const x=L2(L1(left[i])),y=ch===1?x:R2(R1(right[i]));
      energy+=(x*x+(ch===1?0:y*y));count++;
      if(count===group || i===n-1){sub.push({energy,count});energy=0;count=0;}
      if(i%chunk===chunk-1){if(progress)progress('Measuring loudness',.5+i/n*.4);await new Promise(resolve=>setTimeout(resolve,0));}
    }
    const kBlocks=Math.max(1,Math.round(blockLen/group));
    let eSum=0,nSum=0;
    for(let i=0;i<sub.length;i++){
      eSum+=sub[i].energy;nSum+=sub[i].count;
      if(i>=kBlocks){eSum-=sub[i-kBlocks].energy;nSum-=sub[i-kBlocks].count;}
      if(i>=kBlocks-1)blocks.push(eSum/nSum);
    }
    if(!blocks.length)blocks.push(sub.reduce((s,x)=>s+x.energy,0)/Math.max(1,n));
    const lu=e=>-.691+10*Math.log10(Math.max(e,1e-20));
    const eligible=blocks.filter(e=>lu(e)>-70);
    if(!eligible.length)return -70;
    const first=eligible.reduce((a,b)=>a+b,0)/eligible.length,relative=lu(first)-10;
    const final=eligible.filter(e=>lu(e)>relative);
    return lu(final.reduce((a,b)=>a+b,0)/Math.max(1,final.length));
  }
  function truePeakEstimate(buffer, maxEvery=1) {
    const {left,right,n}=validateBuffer(buffer),channels=left===right?[left]:[left,right];
    // Four-point cubic interpolation at 4x; useful for protection, not a
    // substitute for a standards-calibrated oversampled true-peak meter.
    let peak=0;
    for(const a of channels){
      for(let i=0;i<n;i+=maxEvery){
        const x0=a[Math.max(0,i-1)],x1=a[i],x2=a[Math.min(n-1,i+1)],x3=a[Math.min(n-1,i+2)];
        peak=Math.max(peak,Math.abs(x1));
        const A=-.5*x0+1.5*x1-1.5*x2+.5*x3,B=x0-2.5*x1+2*x2-.5*x3,C=-.5*x0+.5*x2;
        for(const t of [.25,.5,.75]){const q=((A*t+B)*t+C)*t+x1;peak=Math.max(peak,Math.abs(q));}
      }
    }
    return {linear:peak,dbtp:toDb(peak),method:'4x cubic-interpolation estimate (not calibrated dBTP)'};
  }
  function attachBiquad(ctx,input,type,frequency,gain,q=.8){
    const f=ctx.createBiquadFilter();f.type=type;f.frequency.value=frequency;
    if(type==='peaking')f.Q.value=q;
    if(type!=='highpass')f.gain.value=gain;
    input.connect(f);return f;
  }
  function automate(param, sections, duration, fn){
    const v0=fn(sections[0]);param.setValueAtTime(v0,0);
    for(const s of sections){
      const center=clamp((s.start_seconds+s.end_seconds)*.5,0,duration);
      param.linearRampToValueAtTime(fn(s),center);
    }
    param.linearRampToValueAtTime(fn(sections[sections.length-1]),duration);
  }
  async function master(buffer,settings,progress,offlineCtor) {
    const {n,rate}=validateBuffer(buffer),p=normalPreset(settings.preset),send=(msg,f)=>{if(progress)progress(msg,f);};
    send('Analyzing entire track',0.04);
    const analysis=analyzeSections(buffer,p),tone=toneSettings(analysis,settings);
    await new Promise(resolve=>setTimeout(resolve,0));
    const Offline=offlineCtor||(typeof OfflineAudioContext !== 'undefined'?OfflineAudioContext:null)||(typeof webkitOfflineAudioContext!=='undefined'?webkitOfflineAudioContext:null);
    if(!Offline)throw new Error('OfflineAudioContext is unavailable in this browser.');
    const ctx=new Offline(2,n,rate);const src=ctx.createBufferSource();src.buffer=buffer;
    let o=attachBiquad(ctx,src,'highpass',26,0,.7);
    o=attachBiquad(ctx,o,'lowshelf',115,tone.bass);
    o=attachBiquad(ctx,o,'peaking',p==='signature'?560:315,tone.lowMid,.8);
    o=attachBiquad(ctx,o,'peaking',p==='signature'?4400:3300,tone.presence,.8);
    o=attachBiquad(ctx,o,'highshelf',8500,tone.air);
    if(p==='signature'){
      // Bounded automated low-mid and high-frequency resonance suppression.
      const m=attachBiquad(ctx,o,'peaking',560,0,1.15);o=m;
      automate(m.gain,analysis.sections,buffer.duration,s=>{
        const rel=toDb(s.bands.mids)-toDb(analysis.avg_bands.mids);
        return -clamp((rel-1.5)*.18,0,1.6);
      });
      const h=attachBiquad(ctx,o,'peaking',6200,0,1.35);o=h;
      automate(h.gain,analysis.sections,buffer.duration,s=>{
        const rel=toDb(s.bands.air)-toDb(analysis.avg_bands.air);
        return -clamp((rel-2)*.15,0,1.4);
      });
    }
    const gain=ctx.createGain();o.connect(gain);o=gain;
    automate(gain.gain,analysis.sections,buffer.duration,s=>toGain(s.gain_db));
    let width=1;
    if(p==='signature' && buffer.numberOfChannels===2 && analysis.correlation>.32 && analysis.correlation<.985 && analysis.side_rms>.001){
      width=1.12;
      const splitter=ctx.createChannelSplitter(2),merger=ctx.createChannelMerger(2);
      const paths=[];
      for(const coef of [[(1+width)/2,(1-width)/2],[(1-width)/2,(1+width)/2]]){
        const gains=coef.map(v=>{const g=ctx.createGain();g.gain.value=v;return g;});paths.push(gains);
      }
      o.connect(splitter);
      for(let output=0;output<2;output++)for(let input=0;input<2;input++){
        splitter.connect(paths[output][input],input);paths[output][input].connect(merger,0,output);
      }
      o=merger;
    }
    const dynamic=analysis.p75_dbfs-analysis.p25_dbfs;
    const compress=p!=='natural' && (p==='signature'?(dynamic>=8&&analysis.median_dbfs<-17):(dynamic>5&&analysis.median_dbfs<-11));
    if(compress){
      const c=ctx.createDynamicsCompressor();c.threshold.value=p==='signature'?-15:p==='impact'?-20:-18;
      c.knee.value=p==='signature'?5:12;c.ratio.value=p==='signature'?1.17:p==='impact'?1.65:1.35;
      c.attack.value=p==='signature'?.045:.033;c.release.value=p==='signature'?.28:.23;
      o.connect(c);o=c;
    }
    o.connect(ctx.destination);src.start();
    send('Rendering adaptive mastering chain',.22);
    const rendered=await ctx.startRendering();
    send('Measuring integrated loudness',.49);
    const before=await integratedLufs(rendered,progress);
    const target=clamp(Number(settings.target)+(Number(settings.intensity)||0)*(p==='signature'?.2:.4),-18,-9);
    const requested=clamp(target-before,-15,15),boost=toGain(requested);
    const ceilingDb=p==='signature'?-1.3:(target<=-14?-1.3:-1.5),ceiling=toGain(ceilingDb); // Conservative headroom for intersample reconstruction.
    const l=rendered.getChannelData(0),r=rendered.getChannelData(1);
    let envelope=1,minGain=1,limited=0;const release=1-Math.exp(-1/(.10*rate));
    send('Applying peak protection',.91);
    for(let i=0;i<n;i++){
      const amplitude=Math.max(Math.abs(l[i]),Math.abs(r[i]))*boost;
      const wanted=amplitude>ceiling?ceiling/Math.max(amplitude,1e-9):1;
      envelope=wanted<envelope?wanted:envelope+(wanted-envelope)*release;
      if(envelope<.999){limited++;minGain=Math.min(minGain,envelope);}
      l[i]*=boost*envelope;r[i]*=boost*envelope;
    }
    const tp=truePeakEstimate(rendered);
    // Allow headroom for more accurate reconstruction in downstream codecs.
    const safety=tp.linear>ceiling?ceiling/tp.linear:1;
    if(safety<1)for(let i=0;i<n;i++){l[i]*=safety;r[i]*=safety;}
    const outputLufs=await integratedLufs(rendered,null),outputTp=truePeakEstimate(rendered);
    send('Master ready',1);
    return {buffer:rendered,recipe:{engine:'Browser Dynamic Signature v1.0 beta',analysis_coverage:'entire recording',
      eq_db:tone,automation:analysis,compressor_applied:compress,stereo_width:width,
      loudness_target_lufs:target,measured_loudness_before_lufs:before,estimated_loudness_after_lufs:outputLufs,
      loudness_note:'EBU-style gated K-weighted estimate; verify with an external calibrated meter.',
      true_peak_ceiling_db:ceilingDb,true_peak_estimate_db:outputTp.dbtp,
      true_peak_note:outputTp.method,limiter_min_gain_db:toDb(minGain),limited_fraction:limited/Math.max(1,n)},
      studioMetrics:{output:{integrated_lufs:outputLufs,estimated_true_peak_dbtp:outputTp.dbtp},note:'Local estimates, not a calibrated EBU R128 / dBTP meter.'}};
  }
  return {analyzeSections,toneSettings,integratedLufs,truePeakEstimate,master,version:'1.0.0-beta'};
});