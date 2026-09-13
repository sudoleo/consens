const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const {chromium}=require('playwright-core');
const {ROOT,OUT,FF,findChrome}=require('./runtime.cjs');
const timing=JSON.parse(fs.readFileSync(path.join(__dirname,'timing.json'),'utf8'));
const introEnd=timing.intro.duration+timing.intro.transitionDuration,introOffset=introEnd-timing.intro.resumeSource;
const stills=process.argv.includes('--stills'),fps=timing.fps,duration=timing.sourceDuration+introOffset+timing.readingWindows.reduce((n,w)=>n+w.extra,0);
const toOutput=t=>Number((t+introOffset+timing.readingWindows.reduce((n,w)=>n+w.extra*Math.max(0,Math.min(1,(t-w.start)/(w.end-w.start))),0)).toFixed(6));
const b64=(p,type)=>`data:${type};base64,${fs.readFileSync(p).toString('base64')}`;
const content=JSON.parse(fs.readFileSync(path.join(__dirname,'content.json'),'utf8'));
const icon=file=>b64(path.join(ROOT,'assets/icons',file),file.endsWith('.svg')?'image/svg+xml':'image/png');
const {reader,providers:providerAssets,...story}=content;
const color=JSON.parse(fs.readFileSync(path.join(__dirname,'color.json'),'utf8'));
const study={...story,color,font:b64(path.join(ROOT,'assets/fonts/InterVariable.woff2'),'font/woff2'),logo:b64(path.join(ROOT,'assets/logo.png'),'image/png'),models:story.models.map(m=>({...m,icon:icon(m.icon)})),judgeMotion:timing.judgeMotion,cleanEntry:true,semanticSynthesis:true,modelEntrance:[-.46,0,.46,.92,1.38,1.84],modelReveal:[.72,1.11,1.5,1.89,2.28,2.67]};
const providers=providerAssets.map(p=>({...p,icon:icon(p.icon)}));
const data={study,providers,timing,reader};
const referenceArg=process.argv.find(a=>a.startsWith('--reference='));
const baseScene=fs.readFileSync(path.join(__dirname,'full-film-study.js'),'utf8'),scene=fs.readFileSync(path.join(__dirname,'full-film-scene.js'),'utf8');
const html=`<!doctype html><html><head><meta charset="utf-8"><title>consens.io product film</title><style>body{margin:0;background:${color.bg}}canvas{display:block;width:1080px;height:1350px}canvas[hidden]{display:none}</style></head><body><canvas id="film"></canvas><script>${baseScene}</script><script>${scene}</script><script>window.ready=initFullFilm(${JSON.stringify(data)})</script></body></html>`;
function run(args){return new Promise((resolve,reject)=>{const p=spawn(FF,args,{stdio:['ignore','ignore','pipe']});let log='';p.stderr.on('data',d=>log+=d);p.on('close',code=>code?reject(Error(log)):resolve(log));});}
async function main(){
 fs.mkdirSync(path.join(OUT,'qa/stills'),{recursive:true});fs.writeFileSync(path.join(OUT,'source.html'),html);
 fs.copyFileSync(path.join(ROOT,'src/preview.html'),path.join(OUT,'index.html'));
 fs.copyFileSync(path.join(ROOT,'assets/fonts/InterVariable.woff2'),path.join(OUT,'font.woff2'));
 fs.copyFileSync(path.join(ROOT,'assets/audio/credit.json'),path.join(OUT,'music-credit.json'));
 const browser=await chromium.launch({executablePath:findChrome(),headless:true,args:['--force-color-profile=srgb','--hide-scrollbars']});
 try{
 const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.setContent(html);await page.evaluate(()=>window.ready);
 const originalTimes=[.7,2.7,2.92,3.08,5.8,6.35,6.45,6.6,6.8,6.9,6.99,7,7.2,7.48,7.52,8.6,9.5,10.6,11.6,12.6,13.8,14.8,15.8,16.8,17.6,18.75,19.8,20.6,21.7,22.15,22.8,23.1,23.8,24.9,25.7,26.3,27.2,28.3,29.2,30.1,30.9,31.8,32.8,33.6,34.2,35.3,35.8,36.2,36.8,37.7,38.75,39.1,40.5,42.2,43.4,44.8,46.8];
 const times=[...new Set([...originalTimes.map(t=>t>=13.85?Number((t+3).toFixed(2)):t),11.22,11.7,12.15,12.85,13.55,14.5,15.2,15.6,16,16.35,16.45,16.85,19.65,20,20.5,21,21.5,22,22.5,23,23.2,23.5,28.8,29.3,30,31,32,33,34,35,36,37,37.2,3.2,4.4,5.4,7.8,8.2,9,9.8,10.3,10.9,11.1,25.05,25.6,25.75,26,35.5,35.8,36.1,47.5,48,48.5,49.4])].map(toOutput).sort((a,b)=>a-b);
 times.push(...[0,.3,.65,1,1.4,1.8,2.2,2.6,3.1,3.5,4,4.3,4.6,4.9,5,5.15,5.25,5.35,5.55,5.7]);times.sort((a,b)=>a-b);
 const qa=[];for(const t of [...new Set(times)]){const report=await page.evaluate(t=>drawFullFilm(t),t);await page.locator('#fullFilm').screenshot({path:path.join(OUT,'qa/stills',`${t}.png`)});qa.push(report);}
 const seek=[];for(const t of [0,3.8,6.4,6.9,7.3,8.2,9.8,10.9,11,12.85,14.8,17.6,20.5,22.8,25.8,27.7,29,31.2,34.8,36.2,38.9,44.5].map(t=>toOutput(t>=13.85?t+3:t))){
 const a=await page.evaluate(t=>{drawFullFilm(t);return document.getElementById('fullFilm').toDataURL();},t);await page.evaluate(t=>drawFullFilm(t),duration-t);
 const b=await page.evaluate(t=>{drawFullFilm(t);return document.getElementById('fullFilm').toDataURL();},t);seek.push({t,identical:a===b});}
 for(const t of [0,.3,1.4,2.2,3.5,4.6,5.15,5.55]){
   const draw=t=>{drawFullFilm(t);return document.getElementById('fullFilm').toDataURL();};
   const a=await page.evaluate(draw,t);await page.evaluate(t=>drawFullFilm(t),duration-t);
   seek.push({t,identical:a===await page.evaluate(draw,t)});
 }
 const frameText=t=>qa.find(f=>Math.abs(f.sourceTime-t)<1e-5).text.filter(x=>x.alpha>.9).map(x=>x.text);
 const visible=t=>frameText(t>=13.85?Number((t+3).toFixed(2)):t);
 const exact=t=>qa.find(f=>Math.abs(f.sourceTime-t)<1e-5);
 const editorial=[{check:'Field, send button and hint share the same zoom transform',ok:[3.2,4.4,5.4].every(t=>{const r=exact(t).inputZoom;return r.field[0]>1&&JSON.stringify(r.field)===JSON.stringify(r.send)&&JSON.stringify(r.field)===JSON.stringify(r.hint);})},{check:'Answer arrivals use the existing scene duration and reduce the final hold',ok:!frameText(9.8).includes(study.models[5].excerpt)&&frameText(10.9).includes(study.models[5].excerpt)&&study.models.every(m=>frameText(11.1).includes(m.excerpt))},{check:'Provider icons preserve their original aspect ratios',ok:exact(11.1).icons.length===6&&exact(11.1).icons.every(i=>Math.abs(i.natural[0]/i.natural[1]-i.drawn[0]/i.drawn[1])<1e-8)},{check:'Contradiction phrase keeps its exact casing and punctuation',ok:[25.6,25.75,26].every(t=>frameText(t).includes('only after inactivity.')&&!frameText(t).some(s=>s.startsWith('Only after')))},{check:'All nine landing-page providers are visible in the outro',ok:exact(49.4).providers.length===9&&exact(49.4).providers.every(p=>p.alpha===1&&p.drawn[0]>0&&p.drawn[1]>0)},{check:'Source contributions and each synthesized recommendation are visible together',ok:[['Find the first win.','Remove setup friction.',study.synthesis[0]].every(s=>frameText(12.85).includes(s)),study.models.every(m=>frameText(14.5).includes(m.excerpt)),study.synthesis.every(s=>frameText(14.5).includes(s))].every(Boolean)},{check:'Finished synthesis remains under its title',ok:[14.8,15.8].every(t=>['One richer answer.',...study.synthesis,'Remind users','only after inactivity.'].every(s=>visible(t).includes(s)))},{check:'Coverage precedes Differences',ok:visible(17.6).includes('Coverage judge')&&!visible(17.6).includes('Differences judge')&&visible(18.75).includes('Differences judge')},{check:'Question precedes competing recommendations',ok:visible(21.7).includes('When should reminders be sent?')&&visible(22.8).includes('only after inactivity.')&&!visible(23.1).includes('Every day')&&visible(24.9).includes('Every day')},{check:'Reader opens directly to excerpts',ok:qa.filter(f=>f.reader).every(f=>!f.reader.nativeOverview)&&qa.some(f=>f.reader?.selected==='Claude')}];
 editorial.push(
 {check:'Quiet judges contain no mini answers, connectors or travel dots',ok:qa.filter(f=>f.judges).length>0&&qa.filter(f=>f.judges).every(f=>!f.judges.miniAnswers&&!f.judges.connectors&&!f.judges.travelDots)},
 {check:'Differences are highlighted in the shared answer',ok:qa.some(f=>f.judges?.highlightInSharedAnswer&&f.text.some(x=>x.text==='Find differences'&&x.alpha>.9)&&f.text.some(x=>x.text==='Contradiction'&&x.alpha>.9))},
 {check:'Different advice has no redundant closing tagline',ok:qa.every(f=>!f.text.some(x=>x.text==='Same goal. Different timing.'))},
 {check:'Sources remain conditional and return context without a verdict or example',ok:qa.some(f=>f.sourceCheck?.returnedToAnswer)&&qa.filter(f=>f.sourceCheck).every(f=>f.sourceCheck.majorOnly&&f.sourceCheck.factualOnly&&f.sourceCheck.citedSourcesOnly&&!f.sourceCheck.outcomeClaimed&&!f.sourceCheck.concreteExample)}
 );
 editorial.push(
   {check:'The intro explains multiple AI models becoming one answer, readable for almost three seconds without a repeated wordmark',ok:[1.4,1.8,2.2,2.6,3.1,3.5,4].every(t=>{
     const r=qa.find(f=>f.time===t);return study.intro.lines.every(line=>r.text.some(x=>x.text===line&&x.alpha>.99))&&r.text.filter(x=>study.intro.lines.includes(x.text)).every(x=>x.width<936);
   })&&qa.filter(r=>r.intro&&r.time<timing.intro.duration).every(r=>r.text.every(x=>x.text!==study.intro.brand))},
   {check:'Six distinct provider marks establish the input before converging into Consens',ok:qa.find(f=>f.time===1.4).introNodes.every(n=>n.alpha>.99&&n.merge===0)&&qa.find(f=>f.time===4).introNodes.every(n=>n.merge===1&&n.alpha===0)},
   {check:'The small header wordmark enters clear of the question during the handoff',ok:qa.filter(r=>r.intro?.handoff>0).every(r=>{
     const brand=r.text.find(x=>x.text===study.intro.brand),question=r.text.find(x=>x.text==='One question.');
     return brand&&question&&brand.y+20<question.y-question.size;
   })}
 );
 if(errors.length||seek.some(x=>!x.identical)||editorial.some(x=>!x.ok))throw Error(JSON.stringify({errors,seek,editorial}));
 const phraseFrames=[];
 for(let f=Math.floor(toOutput(24.75)*fps);f<=Math.ceil(toOutput(26.15)*fps);f++){
   const r=await page.evaluate(t=>drawFullFilm(t),f/fps);
   const phrases=r.phrases||[];
   if(phrases.length!==1||phrases[0].text!=='only after inactivity.')throw Error(`Missing or duplicate selected phrase at ${f}`);
   phraseFrames.push({time:f/fps,...phrases[0]});
 }
 const phraseStable=phraseFrames.every((p,i)=>p.weight===550&&p.fontSize===35&&p.tracking===-.25&&Math.abs(p.width-phraseFrames[0].width)<1e-6&&(!i||(Math.abs(p.x-phraseFrames[i-1].x)<25&&Math.abs(p.y-phraseFrames[i-1].y)<12&&Math.abs(p.scale-phraseFrames[i-1].scale)<.06)));
 editorial.push({check:'Selected phrase is a single persistent glyph run with constant weight, tracking and smooth transform',ok:phraseStable});
 if(!phraseStable)throw Error(JSON.stringify({phraseFrames}));
 // Optional comparison against a supplied self-contained source.html.
 const retained=[];
 if(referenceArg){
   const reference=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
   await reference.setContent(fs.readFileSync(path.resolve(referenceArg.slice('--reference='.length)),'utf8'));await reference.evaluate(()=>window.ready);
   for(const t of [...new Set([...Array.from({length:Math.ceil(duration*4)},(_,i)=>i/4),...times])].filter(t=>t>=introEnd&&t<duration).sort((a,b)=>a-b)){
     const draw=t=>{drawFullFilm(t);return document.getElementById('fullFilm').toDataURL();};
     const a=await reference.evaluate(draw,Number((t-introOffset).toFixed(6))),b=await page.evaluate(draw,t);
     retained.push({time:t,referenceTime:t-introOffset,identical:a===b,ok:a===b});
   }
   await reference.close();if(retained.some(x=>!x.ok))throw Error(JSON.stringify({retained}));
 }
 const keyframes=[];
 for(let i=0;i<study.prompt.length;i++){
   let frame=Math.ceil((introOffset+timing.typing.start+(i+1)*timing.typing.duration/study.prompt.length)*fps-1e-8);
   let at=await page.evaluate(t=>drawFullFilm(t).promptCount,frame/fps);
   if(at<i+1){frame++;at=await page.evaluate(t=>drawFullFilm(t).promptCount,frame/fps);}
   const before=await page.evaluate(t=>drawFullFilm(t).promptCount,(frame-1)/fps);
   if(before!==i||at!==i+1)throw Error(`Typing synchronization failed for character ${i+1}: ${before}/${at}`);
   keyframes.push({index:i+1,char:study.prompt[i],frame,time:frame/fps,before,after:at});
 }
 const pacing=timing.readingWindows.map(w=>({...w,outputStart:toOutput(w.start),outputEnd:toOutput(w.end)}));
 if(Math.abs(duration-60)>1e-8||toOutput(timing.intro.resumeSource)!==introEnd)throw Error('Unexpected duration or intro handoff');
 const motionFrames=await page.evaluate(({fps,introOffset})=>{
   const crop=document.createElement('canvas');crop.width=64;crop.height=64;const ctx=crop.getContext('2d'),previous={},frames=[];
   for(let f=19.65*fps;f<=27.8*fps;f++){
     const r=drawFullFilm(f/fps+introOffset),animations=(r.judges?.animations||[]).map(a=>{
       ctx.clearRect(0,0,64,64);ctx.drawImage(document.getElementById('fullFilm'),(a.role==='coverage'?481:940)-32,1032,64,64,0,0,64,64);
       const pixels=crop.toDataURL(),pixelChanged=previous[a.role]!==pixels;previous[a.role]=pixels;return {...a,pixelChanged};
     });frames.push({time:r.time,sourceTime:r.sourceTime,animations,mark:r.mark});
   }return frames;
 },{fps,introOffset});
 const motionChecks=[];
 for(const role of ['coverage','differences']){
   const states=motionFrames.flatMap((r,i)=>r.animations.filter(a=>a.role===role).map(a=>({...a,time:r.time,sourceDelta:i?r.sourceTime-motionFrames[i-1].sourceTime:0})));
   const spinning=states.filter(a=>a.enter===1&&a.spinnerAlpha===1),checks=states.filter(a=>a.checkProgress>0&&a.checkProgress<1);
   motionChecks.push({check:`${role}: spinner advances every encoded frame, including slowed reading windows`,samples:spinning.length,readingWindowSamples:spinning.filter(a=>a.sourceDelta<.5/fps).length,ok:spinning.length>30&&spinning.some(a=>a.sourceDelta<.5/fps)&&spinning.every((a,i)=>a.pixelChanged&&Math.abs(a.motionTime-(a.time-introOffset))<1e-8&&(!i||Math.abs(a.angle-spinning[i-1].angle-6/fps)<1e-8))});
   motionChecks.push({check:`${role}: checkmark draws without stalls in 0.3-0.4 seconds`,samples:checks.length,ok:checks.length>=18&&checks.length<=24&&checks.every((a,i)=>a.pixelChanged&&(!i||a.checkProgress>checks[i-1].checkProgress))&&states.some(a=>a.checkProgress===1&&a.spinnerAlpha===0)});
 }
 const sweep=motionFrames.filter(r=>r.mark?.progress>0&&r.mark.progress<1),label=motionFrames.filter(r=>r.mark?.labelAlpha>0&&r.mark.labelAlpha<1);
 motionChecks.push({check:'Highlight sweeps continuously for 0.8-0.9 seconds across the narrative reading hold',samples:sweep.length,ok:sweep.length>=48&&sweep.length<=54&&sweep.every((r,i)=>!i||(r.mark.progress>sweep[i-1].mark.progress&&r.mark.progress-sweep[i-1].mark.progress<.04))&&motionFrames.some(r=>r.mark?.progress===1)});
 motionChecks.push({check:'Contradiction label starts with the highlight and finishes fading within 0.25 seconds',samples:label.length,ok:label.length>=12&&label.length<=15&&label[0]?.time===sweep[0]?.time&&label.every((r,i)=>!i||r.mark.labelAlpha>label[i-1].mark.labelAlpha)&&sweep.some(r=>r.mark.labelAlpha===1)});
 if(motionChecks.some(x=>!x.ok))throw Error(JSON.stringify({motionChecks}));
 const readerFrames=await page.evaluate(({fps,introOffset})=>{
   const frames=[];for(let f=Math.floor(43.7*fps);f<49*fps;f++){const r=drawFullFilm(f/fps+introOffset);if(r.cursorMotion)frames.push(r.cursorMotion);}return frames;
 },{fps,introOffset});
 const sourceSurfaceFrames=await page.evaluate(introOffset=>{
   const frames=[];for(let t=40.9;t<43.21;t+=1/30){const r=drawFullFilm(t+introOffset),s=r.sourceCheck.surface,pixel=[...document.getElementById('fullFilm').getContext('2d').getImageData(s.x+s.w/2,s.y+12,1,1).data];frames.push({time:t+introOffset,pixel});}return frames;
 },introOffset);
 const polishChecks=[
   {check:'Empty-input caret has a visible gap before the placeholder A',ok:exact(2.92).caret.typedCount===0&&exact(2.92).caret.placeholderX-exact(2.92).caret.x-exact(2.92).caret.width>=5},
   {check:'Question text is gone before model cards enter',ok:[6.9,6.99,7.2,7.48].every(t=>exact(t).text.every(x=>!x.text.includes('I built a habit tracker')||x.alpha===0))},
   {check:'Redundant synthesis subtitle removed',ok:qa.every(f=>f.text.every(x=>x.text!=='Combine the useful parts.'))},
   {check:'Source-check surface remains the same white through its return and rest',samples:sourceSurfaceFrames.length,ok:sourceSurfaceFrames.every(f=>JSON.stringify(f.pixel)===JSON.stringify([...color.paper.slice(1).match(/../g).map(h=>parseInt(h,16)),255]))}
 ];
 for(const kind of ['open-original-answers','switch-model']){
   const frames=readerFrames.filter(f=>f.kind===kind),travel=frames.filter(f=>f.progress>0&&f.progress<1),hold=frames.filter(f=>f.progress===1&&f.press===0&&f.alpha>.5);
   const peakSpeed=Math.max(...travel.slice(1).map((f,i)=>Math.hypot(f.x-travel[i].x,f.y-travel[i].y)*fps));
   polishChecks.push({check:`${kind}: eased travel takes about one second, with a pause before clicking`,travelFrames:travel.length,holdFrames:hold.length,peakPixelsPerSecond:peakSpeed,ok:travel.length>=59&&travel.length<=66&&peakSpeed<1850&&hold.length>=8&&frames.filter(f=>f.press>0).every(f=>f.progress===1)});
 }
 if(polishChecks.some(x=>!x.ok))throw Error(JSON.stringify({polishChecks}));
 fs.writeFileSync(path.join(OUT,'qa/render-checks.json'),JSON.stringify({errors,seek,editorial,retained,phraseFrames,motionChecks,motionFrames,polishChecks,readerFrames,sourceSurfaceFrames,duration,fps,pacing,typing:{...timing.typing,prompt:study.prompt,keyframes},frames:qa},null,2));
 if(stills){console.log('STILLS READY');return;}
 const silent=path.join(OUT,'consensio-4x5-silent.mp4');
 const encoder=spawn(FF,['-y','-v','error','-f','image2pipe','-framerate',String(fps),'-c:v','mjpeg','-i','pipe:0','-vf','scale=in_color_matrix=bt601:out_color_matrix=bt709:in_range=pc:out_range=tv','-c:v','libx264','-preset','medium','-crf','16','-pix_fmt','yuv420p','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv','-movflags','+faststart',silent],{stdio:['pipe','ignore','pipe']});
 let log='';encoder.stderr.on('data',d=>log+=d);const closed=once(encoder,'close');
 for(let f=0;f<duration*fps;f++){const jpeg=await page.evaluate(t=>{drawFullFilm(t);return document.getElementById('fullFilm').toDataURL('image/jpeg',.97).split(',')[1];},f/fps);if(!encoder.stdin.write(Buffer.from(jpeg,'base64')))await once(encoder.stdin,'drain');if(f%120===0)console.log('RENDER',`${f/fps}/${duration}s`);}
 encoder.stdin.end();const [code]=await closed;if(code)throw Error(log);
 await run(['-y','-v','error','-i',silent,'-i',path.join(ROOT,'assets/audio/soundtrack.m4a'),'-map','0:v','-map','1:a','-c:v','copy','-c:a','copy','-t',String(duration),'-movflags','+faststart',path.join(OUT,'consensio-4x5.mp4')]);
 await run(['-y','-v','error','-ss',String(toOutput(17.8)),'-i',silent,'-frames:v','1',path.join(OUT,'poster.jpg')]);
 fs.writeFileSync(path.join(OUT,'cut.json'),JSON.stringify({duration,fps,width:1080,height:1350,frames:duration*fps,color:{name:color.name,palette:color,primaries:'bt709',transfer:'bt709',matrix:'bt709',range:'tv'},prompt:study.prompt,reference:'60-second composition with a five-second cinematic explanation and continuous brand-to-question handoff.',chapters:[{t:0,label:'What is consens.io?'},...[{t:3,label:'Question'},{t:7.5,label:'Model answers'},{t:11.2,label:'Combine the useful parts'},{t:16.4,label:'Consensus'},{t:19.65,label:'Two judges'},{t:23.2,label:'Different recommendations'},{t:28.8,label:'Conditional source judge'},{t:37.3,label:'Original answers'},{t:45,label:'Outro'}].map(ch=>({...ch,t:toOutput(ch.t)}))],intro:timing.intro,introOffset,readingWindows:timing.readingWindows,provenance:'Authored illustrated workflow. Content pairs explain this example, not a fixed model-pairing algorithm. Direct labelled original-answer excerpts. No native overview, live model run, or factual check outcome asserted.',sceneSha256:crypto.createHash('sha256').update(scene+baseScene+JSON.stringify(color)).digest('hex')},null,2));
 console.log('MASTER READY');
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exit(1)});
