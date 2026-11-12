const assert=require('node:assert/strict');
const dsp=require('../web-mastering.js');
const rate=16000,duration=24,n=rate*duration;
const left=new Float32Array(n),right=new Float32Array(n);
for(let i=0;i<n;i++){
  const t=i/rate;
  const amp=t<8?.05:t<16?.4:.1;
  const kick=(t>=16 && i%4000<3)? .7:0;
  left[i]=amp*Math.sin(2*Math.PI*220*t)+kick;
  right[i]=amp*.9*Math.sin(2*Math.PI*220*t+.01)+kick;
}
const buffer={length:n,numberOfChannels:2,sampleRate:rate,duration, getChannelData:i=>i?right:left};
const a=dsp.analyzeSections(buffer,'signature');
assert.equal(a.sections.length,12);
assert.ok(a.sections[2].gain_db>0,`quiet section gain=${a.sections[2].gain_db}`);
assert.ok(a.sections[6].gain_db<0,`dense section gain=${a.sections[6].gain_db}`);
assert.ok(a.sections[9].scene==='transient');
assert.ok(a.sections[9].gain_db >= 0,`transients were cut ${a.sections[9].gain_db}`);
assert.ok(a.max_abs_gain_db <.7);
assert.ok(dsp.toneSettings(a,{preset:'reference',warmth:0,clarity:0}).bass>0);
console.log('PASS full-song analysis, section decisions and bounded EQ');
console.log(JSON.stringify(a.sections.map(s=>({start:s.start_seconds,scene:s.scene,gain:s.gain_db})),null,2));
(async()=>{
 const silent={length:48000,numberOfChannels:1,sampleRate:48000,duration:1,getChannelData:()=>new Float32Array(48000)};
 const l=await dsp.integratedLufs(silent);assert.equal(l,-70);
 const tp=dsp.truePeakEstimate(buffer);assert.ok(Number.isFinite(tp.dbtp));
 console.log('PASS gated LUFS silence and interpolated peak measurement');
})().catch(e=>{console.error(e);process.exitCode=1});