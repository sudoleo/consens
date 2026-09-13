/* Model contributions, synthesis and judges for the current film.
 * Authored editorial explanation, not a recording of a live model run.
 */
window.initStudy = async function(data) {
  const P=data.color;
  const W=1080,H=1350,cv=document.getElementById('film');cv.width=W;cv.height=H;
  const c=cv.getContext('2d',{alpha:false});
  const face=new FontFace('Inter',`url(${data.font})`,{weight:'100 900'});await face.load();document.fonts.add(face);
  const load=async(src)=>{const im=new Image();im.src=src;await im.decode();return im;};
  const logo=await load(data.logo),icons=await Promise.all(data.models.map(m=>load(m.icon)));
  const mark=document.createElement('canvas');mark.width=logo.width;mark.height=logo.height;
  const mc=mark.getContext('2d');mc.drawImage(logo,0,0);mc.globalCompositeOperation='source-in';mc.fillStyle=P.ink;mc.fillRect(0,0,mark.width,mark.height);
  const clamp=x=>Math.max(0,Math.min(1,x)),mix=(a,b,u)=>a+(b-a)*u;
  const smooth=x=>{x=clamp(x);return x*x*x*(x*(x*6-15)+10);};
  const out=x=>1-Math.pow(1-clamp(x),4),into=x=>Math.pow(clamp(x),3);
  const q=(t,a,d,fn=smooth)=>fn((t-a)/d);
  const bez=(a,b,d,e,u)=>{const v=1-u;return v*v*v*a+3*v*v*u*b+3*v*u*u*d+u*u*u*e;};
  let report=[],iconReport=[],phraseReport=[],judgeReport=null,markReport=null,time=0,motionTime=0;
  const JM=data.judgeMotion;
  function path(x,y,w,h,r=20){c.beginPath();c.roundRect(x,y,w,h,r);}
  function box(x,y,w,h,{fill=P.paper,r=22,shadow=1,stroke=true}={}){
    c.save();path(x,y,w,h,r);c.fillStyle=fill;c.shadowColor=`rgba(${P.shadowRgb.join(',')},${P.shadowOpacity*shadow})`;c.shadowBlur=26*shadow;c.shadowOffsetY=12*shadow;c.fill();c.shadowColor='transparent';
    if(stroke){c.lineWidth=1.2;c.strokeStyle=P.line;c.stroke();}c.restore();
  }
  function txt(s,x,y,size=36,weight=450,color=P.ink,alpha=1,align='left'){
    if(alpha<=0)return;c.save();c.globalAlpha*=clamp(alpha);c.font=`${weight} ${size}px Inter`;c.letterSpacing=size>=58?'-2.4px':size>=36?'-1px':'-.25px';c.textAlign=align;c.textBaseline='alphabetic';c.fillStyle=color;c.fillText(s,x,y);
    const width=c.measureText(s).width;report.push({text:s,x,y,width,size,alpha:c.globalAlpha});c.restore();return width;
  }
  function lines(s,x,y,width,size=36,weight=450,color=P.ink,alpha=1,lh=size*1.24){
    c.save();c.font=`${weight} ${size}px Inter`;c.letterSpacing=size>=36?'-1px':'-.25px';let line='',row=0;
    for(const word of s.split(' ')){const next=line?line+' '+word:word;if(c.measureText(next).width>width&&line){txt(line,x,y+row*lh,size,weight,color,alpha);line=word;row++;}else line=next;}
    if(line)txt(line,x,y+row*lh,size,weight,color,alpha);c.restore();return row+1;
  }
  function selectedPhrase(s,x,y,scale,alpha){
    if(!s||alpha<=0)return;
    // Draw one fixed glyph run. Scaling its transform avoids font-size tracking
    // thresholds, weight interpolation and a duplicate crossfading text layer.
    c.save();c.translate(x,y);c.scale(scale,scale);
    const width=txt(s,0,0,35,550,P.ink,alpha);
    phraseReport.push({text:s,x,y,scale,weight:550,fontSize:35,tracking:-.25,width,alpha});
    c.restore();
  }
  function brand(alpha=1){c.save();c.globalAlpha=alpha;c.drawImage(mark,72,59,45,45*mark.height/mark.width);txt('consens.io',132,87,30,620);c.restore();}
  function icon(i,x,y,size=35,alpha=1){
    const im=icons[i],scale=size/Math.max(im.width,im.height),w=im.width*scale,h=im.height*scale;
    c.save();c.globalAlpha*=alpha;c.drawImage(im,x+(size-w)/2,y+(size-h)/2,w,h);
    iconReport.push({name:data.models[i].name,natural:[im.width,im.height],drawn:[w,h],alpha:c.globalAlpha});c.restore();
  }
  window.studyCardEntry=(t,i)=>data.modelEntrance?q(t,data.modelEntrance[i],.4,out):1;
  function capsule(s,x,y,w,alpha=1){c.save();c.globalAlpha*=alpha;path(x,y,w,36,18);c.fillStyle=P.chip;c.fill();txt(s,x+w/2,y+24,17,520,P.secondary,1,'center');c.restore();}
  function heading(t){
    const sections=[{a:0,b:3.15,text:'Six answers.',sub:'A habit tracker. Better retention.'},{a:data.semanticSynthesis?3.15:3.55,b:6.55,text:'One richer answer.',sub:''},{a:6.85,b:8.75,text:'Compare all answers.',sub:'',size:72},{a:9.05,b:12.2,text:'Different advice.',sub:'When should reminders be sent?',subSize:34}];
    for(const s of sections){const a=(s.a===0?1:q(t,s.a,.28,out))*(1-q(t,s.b-.18,.18));if(a<=0)continue;const dy=s.a===0?0:18*(1-q(t,s.a,.35,out));
      txt(s.text,72,236+dy,s.size||78,580,P.ink,a);if(s.sub)txt(s.sub,76,287,s.subSize||26,440,P.secondary,a);
    }
  }
  function check(x,y,progress,size=14){
    c.save();c.strokeStyle=P.ink;c.lineWidth=2.2;c.lineCap='round';c.lineJoin='round';c.beginPath();c.moveTo(x-size*.48,y);if(progress<.35)c.lineTo(mix(x-size*.48,x-size*.08,progress/.35),mix(y,y+size*.35,progress/.35));else{c.lineTo(x-size*.08,y+size*.35);c.lineTo(mix(x-size*.08,x+size*.65,(progress-.35)/.65),mix(y+size*.35,y-size*.45,(progress-.35)/.65));}c.stroke();c.restore();
  }
  function smallLoader(x,y,w,t,i,alpha=1){
    c.save();c.globalAlpha*=alpha;path(x,y,w,5,2.5);c.fillStyle=P.track;c.fill();c.clip();const u=(t*1.15+i*.16)%1;c.fillStyle=P.trackInk;c.fillRect(x-65+u*(w+95),y,76,5);c.restore();
  }
  function answer(i,x,y,w,h,t,alpha=1,scale=1,angle=0,revealStart=.72+i*.23){
    c.save();c.globalAlpha*=alpha;c.translate(x+w/2,y+h/2);c.rotate(angle);c.scale(scale,scale);c.translate(-w/2,-h/2);
    box(0,0,w,h,{r:22,shadow:.8});
    c.save();c.globalAlpha*=1-q(t,3.34,.18);icon(i,27,25,32);txt(data.models[i].name,74,49,25,560);
    const show=q(t,revealStart,.27,out);smallLoader(28,h-38,w-56,t,i,1-show);
    c.save();c.beginPath();c.rect(27,75,w-54,(h-84)*show);c.clip();
    lines(data.models[i].excerpt,28,112+10*(1-show),w-56,w>500?42:34,480,P.ink,show,43);c.restore();
    c.restore();c.restore();
  }
  const grid=[[72,400],[564,400],[72,640],[564,640],[72,880],[564,880]];
  function pairedSynthesis(t){
    // These pairs illustrate the authored example, not a fixed pairing rule
    // in the product. Both source ideas stay readable alongside their result.
    const collect=q(t,4.72,.78),sourcesOut=1-q(t,4.74,.22),paperOut=1-q(t,4.87,.4);
    for(let row=0;row<3;row++){
      const start=3.3+row*.34,p=q(t,start,.29),result=q(t,start+.29,.24,out);
      const gy=400+row*240,baseline=mix(gy+135,384+187+row*129,collect);
      const y=mix(gy,baseline-93,collect),h=mix(198,110,collect);
      c.save();c.globalAlpha*=paperOut;
      c.save();c.globalAlpha*=p;box(72,y,936,h,{r:22,shadow:.8});c.restore();
      for(let side=0;side<2;side++){c.save();c.globalAlpha*=1-p;box(72+side*492,y,444,h,{r:22,shadow:.8});c.restore();}
      c.restore();
      for(let side=0;side<2;side++){
        const i=row*2+side,gx=72+side*492;
        c.save();c.globalAlpha*=sourcesOut;
        icon(i,gx+27,mix(gy+25,gy+37,p),mix(32,27,p));
        txt(data.models[i].name,gx+74,gy+49,25,560,P.ink,1-q(t,start,.13));
        lines(data.models[i].excerpt,mix(gx+28,gx+69,p),mix(gy+112,gy+59,p),mix(388,369,p),mix(34,29,p),480,P.ink,1,43);
        c.restore();
      }
      txt('+',540,gy+59,26,450,P.secondary,p*sourcesOut,'center');
      const divider=q(t,start+.16,.22)*(1-collect);
      c.save();c.globalAlpha*=divider;c.strokeStyle=P.line;c.lineWidth=1;c.beginPath();c.moveTo(103,gy+86);c.lineTo(977,gy+86);c.stroke();c.restore();
      txt(String(row+1).padStart(2,'0'),119,baseline,20,520,P.quiet,result);
      txt(data.synthesis[row],171,baseline+12*(1-result),43,510,P.ink,result);
      // Result text arrives at the exact coordinates used by the document.
      c.save();c.globalAlpha*=.45*collect;c.strokeStyle=P.line;c.lineWidth=1;c.beginPath();c.moveTo(171,baseline+42);c.lineTo(925,baseline+42);c.stroke();c.restore();
    }
  }
  function modelScene(t){
    if(data.semanticSynthesis&&t>=3.15){if(t<5.5)pairedSynthesis(t);return;}
    const gather=q(t,3.15,.9),fade=1-q(t,3.78,.38);
    if(t>=4.16)return;
    c.save();c.beginPath();c.rect(0,330,W,890);c.clip();
      for(let i=0;i<6;i++){
        const [gx,gy]=grid[i],entry=data.cleanEntry?window.studyCardEntry(t,i):out((t+.2-i*.035)/.82),entryY=data.cleanEntry?(1-entry)*53:(i%2?1:-1)*(1-entry)*290;
        const targetX=90+(i%2)*9,targetY=495+Math.floor(i/2)*123;
        const xx=bez(gx,gx+(i%2?62:-62),targetX+30,targetX,gather),yy=mix(gy+entryY,targetY,gather);
        answer(i,xx,yy,mix(444,880,gather),mix(198,100,gather),t,fade*(data.cleanEntry?entry:1),1,data.cleanEntry?0:((i%2?1:-1)*.018*(1-entry)),data.modelReveal?.[i]??(.72+i*.23));
      }

    c.restore();
  }
  function streamed(s,x,y,w,size,t,start,duration,weight=490,color=P.ink){
    const words=s.split(' '),u=clamp((t-start)/duration),count=Math.ceil(words.length*u);if(count<=0)return;
    lines(words.slice(0,count).join(' '),x,y,w,size,weight,color,1,size*1.25);
  }
  function trace(x1,y1,x2,y2,p,alpha=1){
    if(p<=0)return;c.save();c.globalAlpha=alpha;const mid=(y1+y2)/2;c.lineWidth=2;c.strokeStyle=P.connector;c.beginPath();
    c.moveTo(x1,y1);for(let i=1;i<=45;i++){const u=Math.min(p,i/45);const x=bez(x1,x1,x2,x2,u),y=bez(y1,mid,mid,y2,u);c.lineTo(x,y);if(i/45>=p)break;}c.stroke();
    if(p<1){const x=bez(x1,x1,x2,x2,p),y=bez(y1,mid,mid,y2,p);c.fillStyle=P.ink;c.beginPath();c.arc(x,y,4,0,Math.PI*2);c.fill();}c.restore();
  }
  function judges(t){
    const leave=1-q(motionTime,JM.exitStart,JM.exitDuration);
    if(motionTime<=JM.coverage.start||leave<=0)return;
    judgeReport={role:motionTime<JM.differences.start?'coverage':'differences',miniAnswers:false,connectors:false,travelDots:false,highlightInSharedAnswer:motionTime>JM.highlight.start,animations:[]};
    // Output time is continuous even when the narrative clock pauses for reading.
    for(let kind=0;kind<2;kind++){
      const role=kind?'differences':'coverage',event=JM[role];
      const enter=q(motionTime,event.start,JM.enterDuration,out);
      if(enter<=0)continue;
      const spinnerAlpha=1-q(motionTime,event.complete,JM.spinnerFadeDuration);
      const ready=q(motionTime,event.complete+JM.checkDelay,JM.checkDuration);
      const angle=(motionTime-event.start)*JM.spinnerRadiansPerSecond;
      const dim=kind?1:1-.4*q(motionTime,JM.differences.start+.2,.28),x=90+kind*459,y=973+20*(1-enter);
      c.save();c.globalAlpha*=enter*leave;
      box(x,y,441,150,{r:18,shadow:.4});c.globalAlpha*=dim;
      txt(kind?'Differences judge':'Coverage judge',x+26,y+43,24,490,P.secondary);
      txt(kind?'Find differences':'Check support',x+26,y+99,34,550);
      const cx=x+391,cy=y+91;c.strokeStyle=P.spinnerTrack;c.lineWidth=2;
      c.beginPath();c.arc(cx,cy,17,0,Math.PI*2);c.stroke();
      if(spinnerAlpha>0){c.save();c.globalAlpha*=spinnerAlpha;c.strokeStyle=P.ink;c.beginPath();c.arc(cx,cy,17,angle,angle+Math.PI*1.15);c.stroke();c.restore();}
      if(ready>0)check(cx,cy,ready,12);
      c.restore();
      judgeReport.animations.push({role,motionTime,angle,spinnerAlpha,checkProgress:ready,enter,leave});
    }
  }
  function cursor(x,y,alpha=1,click=0){
    c.save();c.globalAlpha=alpha;c.translate(x,y);c.scale(1-.13*click,1-.13*click);c.shadowColor='#00000022';c.shadowBlur=7;c.shadowOffsetY=3;
    c.beginPath();c.moveTo(0,0);c.lineTo(0,38);c.lineTo(10,28);c.lineTo(20,47);c.lineTo(28,42);c.lineTo(18,25);c.lineTo(33,24);c.closePath();c.fillStyle=P.ink;c.fill();c.shadowColor='transparent';c.strokeStyle='white';c.lineWidth=2.2;c.stroke();c.restore();
  }
  function documentScene(t){
    if(t<3.2)return;
    const enter=data.semanticSynthesis?q(t,4.82,.5,out):q(t,3.32,.54,out),judgeMove=q(t,6.45,.52),focus=q(t,8.85,.78),split=q(t,10.3,.48,out);
    // The answer is a stable spatial anchor, including while the camera crops
    // tightly into the disputed phrase. The clipping window excludes titles.
    const dx=mix(72,90,judgeMove),dy=mix(384,368,judgeMove),dw=mix(936,900,judgeMove),dh=mix(718,570,judgeMove);
    const sx=dw/936,reminderLocalY=mix(586,490,judgeMove);
    const cameraScale=mix(1,1.43,focus),reminderY=dy+reminderLocalY*sx;
    const cameraX=mix(0,76-(dx+48*sx)*1.43,focus),cameraY=mix(0,655-reminderY*1.43,focus);
    c.save();c.beginPath();c.rect(0,318,W,885);c.clip();
    c.translate(cameraX,cameraY);c.scale(cameraScale,cameraScale);
    c.save();c.globalAlpha=enter*(1-q(t,10.12,.16));box(dx,dy+18*(1-enter),dw,dh,{r:24,shadow:1.2});
    c.translate(dx,dy);c.scale(sx,sx);
    c.drawImage(mark,43,33,38,38*mark.height/mark.width);txt('Consensus',97,58,27,600);
    c.strokeStyle=P.line;c.lineWidth=1;c.beginPath();c.moveTo(43,85);c.lineTo(893,85);c.stroke();
    smallLoader(47,118,238,t,1,1-q(t,4.12,.18));
    const ys=[mix(187,152,judgeMove),mix(316,251,judgeMove),mix(445,350,judgeMove)];
    for(let i=0;i<3;i++){
      if(data.semanticSynthesis&&t<5.5)continue;
      const start=4.05+i*.48;txt(String(i+1).padStart(2,'0'),47,ys[i],20,520,P.quiet,q(t,start,.15));
      streamed(data.synthesis[i],99,ys[i],783,43,t,start,.46,510);
      const reveal=q(t,start,.5);c.save();c.globalAlpha*=.45*reveal;c.strokeStyle=P.line;c.lineWidth=1;c.beginPath();c.moveTo(99,ys[i]+42);c.lineTo(853,ys[i]+42);c.stroke();c.restore();
    }
    const remarkStart=5.65;txt('REMINDERS',47,reminderLocalY-45,17,550,P.secondary,q(t,remarkStart,.18));
    c.save();c.font='470 35px Inter';c.letterSpacing='-.25px';
    const markProgress=q(motionTime,JM.highlight.start,JM.highlight.duration),labelAlpha=q(motionTime,JM.highlight.start,JM.highlight.labelDuration),markAlpha=q(motionTime,JM.highlight.start,JM.highlight.fadeDuration,out),markX=47+c.measureText('Remind users ').width;
    c.font='550 35px Inter';const markWidth=c.measureText('only after inactivity.').width;
    c.globalAlpha*=markAlpha;path(markX-6,reminderLocalY-31,(markWidth+12)*markProgress,43,4);c.fillStyle=P.amber;c.fill();c.restore();
    const reminderWords=['Remind','users','only','after','inactivity.'];
    const reminderCount=Math.ceil(reminderWords.length*clamp((t-remarkStart)/.58));
    if(reminderCount>0)txt(reminderWords.slice(0,Math.min(2,reminderCount)).join(' '),47,reminderLocalY,35,470);
    if(labelAlpha>0){txt('Contradiction',47,reminderLocalY+53,21,520,P.amberInk,labelAlpha);}
    markReport={motionTime,progress:markProgress,labelAlpha,alpha:markAlpha};
    // The answer stays quiet while each role is read.
    c.restore();c.restore();
    judges(t);
    const phraseMove=q(t,10.22,.56),sourcePhraseX=cameraX+(dx+markX*sx)*cameraScale;
    const sourcePhraseY=cameraY+(dy+reminderLocalY*sx)*cameraScale;
    selectedPhrase(reminderWords.slice(2,reminderCount).join(' '),
      mix(sourcePhraseX,72,phraseMove),mix(sourcePhraseY,552,phraseMove),
      mix(sx*cameraScale,58/35,phraseMove),enter);
    // Fast approach and a deliberate click land on the exact highlighted words.
    const target={x:cameraX+(dx+(markX+markWidth*.6)*sx)*cameraScale,y:cameraY+(dy+(reminderLocalY-8)*sx)*cameraScale};
    if(t>=9.45&&t<10.6){const p=q(t,9.45,.58,out),press=q(t,10.03,.055)*(1-q(t,10.085,.12)),a=q(t,9.45,.12)*(1-q(t,10.24,.2));
      cursor(mix(935,target.x,p),mix(1005,target.y,p)-70*Math.sin(Math.PI*p),a,press);
      const ring=clamp((t-10.08)/.28);if(t>=10.08&&ring<1){c.save();c.globalAlpha=(1-ring)*.42;c.strokeStyle=P.amberInk;c.lineWidth=2;c.beginPath();c.arc(target.x,target.y,18+28*ring,0,Math.PI*2);c.stroke();c.restore();}
    }
    // The selected words become the first position. The alternative arrives
    // later, after its question and model provenance have been established.
    if(t>=10.12){
      txt('Some models recommend',72,480,29,480,P.secondary,q(t,10.45,.27));
      for(let j=0;j<data.positions[0].length;j++)icon(data.positions[0][j],76+j*52,596,34,q(t,10.5,.3));
      const other=q(t,11.03,.22,out);
      c.save();c.globalAlpha=other;c.strokeStyle=P.line;c.lineWidth=1.4;c.beginPath();c.moveTo(72,703);c.lineTo(1008,703);c.stroke();c.restore();
      txt('Others recommend',72,776+18*(1-other),29,480,P.secondary,other);
      txt('Every day',72,848+18*(1-other),58,550,P.ink,other);
      for(let j=0;j<data.positions[1].length;j++)icon(data.positions[1][j],76+j*52,892,34,q(t,11.08,.22));
    }
    return {document:{x:dx,y:dy,w:dw,h:dh},focus,split,cursorTarget:target};
  }
  window.drawStudy=function(t,mediaSeconds=t){
    const actual=t;
    time=t;motionTime=mediaSeconds;report=[];iconReport=[];phraseReport=[];judgeReport=null;markReport=null;c.setTransform(1,0,0,1,0,0);c.globalAlpha=1;c.fillStyle=P.bg;c.fillRect(0,0,W,H);
    brand();heading(t);
    const doc=documentScene(t);modelScene(t);
    // Restate the header after object drawing; the scene clipping leaves it clear.
    // Cards only cross this zone during their purposeful entrance.
    txt('Illustrated workflow · authored demo',72,1290,18,430,P.secondary,.78);
    txt('Neon · Scott Buckley · CC BY 4.0',1008,1290,17,430,P.secondary,.78,'right');
    window.studyReport={time:actual,visualTime:t,doc,text:report,icons:iconReport,phrases:phraseReport,judges:judgeReport,mark:markReport,phase:t<3.15?'answers':t<6.45?'synthesis':t<8.85?'judges':t<10.3?'focus':'positions'};
    return window.studyReport;
  };
  window.drawStudy(0);
};
