/* Deterministic full-film composition. Source time controls reading;
 * output time controls judge and cursor motion.
 */
window.initFullFilm=async function(data){
  await initStudy(data.study);
  const study=document.getElementById('film');study.hidden=true;
  const cv=document.createElement('canvas');cv.id='fullFilm';cv.width=1080;cv.height=1350;document.body.append(cv);
  const c=cv.getContext('2d',{alpha:false}),W=1080,H=1350;
  const load=async src=>{const im=new Image();im.src=src;await im.decode();return im;};
  const logo=await load(data.study.logo),icons=await Promise.all(data.study.models.map(m=>load(m.icon)));
  const providerMarks=await Promise.all(data.providers.map(async p=>{
    const im=await load(p.icon),cv=document.createElement('canvas');cv.width=im.width||256;cv.height=im.height||256;
    const ctx=cv.getContext('2d');ctx.drawImage(im,0,0,cv.width,cv.height);ctx.globalCompositeOperation='source-in';ctx.fillStyle='#222428';ctx.fillRect(0,0,cv.width,cv.height);return cv;
  }));
  const mark=document.createElement('canvas');mark.width=logo.width;mark.height=logo.height;
  const mc=mark.getContext('2d');mc.drawImage(logo,0,0);mc.globalCompositeOperation='source-in';mc.fillStyle='#222428';mc.fillRect(0,0,mark.width,mark.height);
  const P={bg:'#f5f4f1',paper:'#fffefd',ink:'#222428',secondary:'#62666d',quiet:'#9a9c9f',line:'#deddd8',amber:'#f7edcf',amberInk:'#946b1f'};
  const clamp=x=>Math.max(0,Math.min(1,x)),mix=(a,b,p)=>a+(b-a)*p;
  const smooth=x=>{x=clamp(x);return x*x*x*(x*(x*6-15)+10);},out=x=>1-Math.pow(1-clamp(x),4);
  const q=(t,a,d,fn=smooth)=>fn((t-a)/d),bez=(a,b,d,e,p)=>{const v=1-p;return v*v*v*a+3*v*v*p*b+3*v*p*p*d+p*p*p*e;};
  let report;
  function path(x,y,w,h,r=20){c.beginPath();c.roundRect(x,y,Math.max(.01,w),Math.max(.01,h),r);}
  function box(x,y,w,h,{fill=P.paper,r=22,shadow=1,stroke=true}={}){c.save();path(x,y,w,h,r);c.fillStyle=fill;c.shadowColor=`rgba(34,36,40,${.07*shadow})`;c.shadowBlur=26*shadow;c.shadowOffsetY=12*shadow;c.fill();c.shadowColor='transparent';if(stroke){c.lineWidth=1.2;c.strokeStyle=P.line;c.stroke();}c.restore();}
  function font(size,weight){c.font=`${weight} ${size}px Inter`;c.letterSpacing=size>=58?'-2.4px':size>=36?'-1px':'-.25px';}
  function txt(s,x,y,size=36,weight=450,color=P.ink,alpha=1,align='left'){
    if(alpha<=0)return 0;c.save();c.globalAlpha*=clamp(alpha);font(size,weight);c.textAlign=align;c.textBaseline='alphabetic';c.fillStyle=color;c.fillText(s,x,y);
    const width=c.measureText(s).width;report.text.push({text:s,x,y,width,size,alpha:c.globalAlpha});c.restore();return width;
  }
  function wrap(s,x,y,w,size=36,weight=450,color=P.ink,alpha=1,lh=size*1.3){
    c.save();font(size,weight);let line='',row=0,lastWidth=0;
    for(const word of s.split(' ')){const next=line?line+' '+word:word;if(c.measureText(next).width>w&&line){txt(line,x,y+row*lh,size,weight,color,alpha);line=word;row++;}else line=next;}
    if(line)lastWidth=txt(line,x,y+row*lh,size,weight,color,alpha);c.restore();return {rows:row+1,x:x+lastWidth,y:y+row*lh};
  }
  function brand(alpha=1){c.save();c.globalAlpha*=alpha;c.drawImage(mark,72,59,45,45*mark.height/mark.width);txt('consens.io',132,87,30,620);c.restore();}
  function icon(i,x,y,size=35,alpha=1){
    const im=icons[i],scale=size/Math.max(im.width,im.height),w=im.width*scale,h=im.height*scale;
    c.save();c.globalAlpha*=alpha;c.drawImage(im,x+(size-w)/2,y+(size-h)/2,w,h);
    report.icons.push({name:data.study.models[i].name,natural:[im.width,im.height],drawn:[w,h],alpha:c.globalAlpha});c.restore();
  }
  function rule(x,y,w,alpha=1){c.save();c.globalAlpha*=alpha;c.strokeStyle=P.line;c.lineWidth=1.3;c.beginPath();c.moveTo(x,y);c.lineTo(x+w,y);c.stroke();c.restore();}
  function chip(s,x,y,w,alpha=1){c.save();c.globalAlpha*=alpha;box(x,y,w,43,{fill:'#ebeae6',r:21,shadow:0,stroke:false});txt(s,x+w/2,y+29,21,540,P.secondary,1,'center');c.restore();}
  function cursor(x,y,alpha=1,press=0){c.save();c.globalAlpha*=alpha;c.translate(x,y);c.scale(1-.13*press,1-.13*press);c.shadowColor='#00000022';c.shadowBlur=7;c.shadowOffsetY=3;c.beginPath();c.moveTo(0,0);c.lineTo(0,38);c.lineTo(10,28);c.lineTo(20,47);c.lineTo(28,42);c.lineTo(18,25);c.lineTo(33,24);c.closePath();c.fillStyle=P.ink;c.fill();c.shadowColor='transparent';c.strokeStyle='white';c.lineWidth=2.2;c.stroke();c.restore();}
  function pacedCursor(event,target,kind){
    const t=report.motionTime;if(t<event.start||t>=event.fade+event.fadeDuration)return;
    const progress=q(t,event.start,event.duration),press=q(t,event.click,.08)*(1-q(t,event.click+.08,.14));
    const x=mix(event.from[0],target.x,progress),y=mix(event.from[1],target.y,progress)-event.arc*Math.sin(progress*Math.PI);
    const alpha=q(t,event.start,.18)*(1-q(t,event.fade,event.fadeDuration));
    cursor(x,y,alpha,press);report.cursorTarget={kind,...target,press};
    report.cursorMotion={kind,time:t,x,y,progress,press,alpha:alpha*c.globalAlpha};
  }
  function arrow(x,y,size=20,color=P.paper){c.save();c.strokeStyle=color;c.lineCap='round';c.lineJoin='round';c.lineWidth=3;c.beginPath();c.moveTo(x,y+size/2);c.lineTo(x,y-size/2);c.moveTo(x-size/2,y);c.lineTo(x,y-size/2);c.lineTo(x+size/2,y);c.stroke();c.restore();}
  function stream(s,x,y,w,size,t,start,dur){const words=s.split(' '),n=Math.ceil(words.length*clamp((t-start)/dur));if(n>0)wrap(words.slice(0,n).join(' '),x,y,w,size,510);}
  function footer(){txt('Illustrated workflow · authored demo',72,1290,18,430,P.secondary,.78);txt('Neon · Scott Buckley · CC BY 4.0',1008,1290,17,430,P.secondary,.78,'right');}
  function cinematicIntro(t){
    const handoff=q(t,data.timing.intro.duration,data.timing.intro.transitionDuration);
    const landing=q(t,3.9,data.timing.intro.duration-3.9),copyAlpha=q(t,.12,.62,out)*(1-q(t,4.15,.7));
    // A quiet push-in: recognizable providers gather into the shared answer.
    // All marks retain their proportions; the logo moves into the header.
    const camera=mix(1.055,1,q(t,0,4.5));
    c.save();c.translate(540,520);c.scale(camera,camera);c.translate(-540,-520);
    const light=c.createRadialGradient(540,480,20,540,480,470);
    light.addColorStop(0,'rgba(255,254,250,.95)');light.addColorStop(.55,'rgba(237,228,206,.28)');light.addColorStop(1,'rgba(245,244,241,0)');
    c.save();c.globalAlpha=1-q(t,4.3,.8);c.fillStyle=light;c.fillRect(50,30,980,940);c.restore();
    const points=[[272,315],[540,230],[808,315],[808,607],[540,702],[272,607]];
    report.introNodes=[];
    for(let i=0;i<6;i++){
      const enter=q(t,i*.055,.65,out),merge=q(t,1.65+i*.095,1.4),alpha=clamp(enter*(1-q(merge,.66,.34)));
      const drift=Math.sin(t*.7+i)*8*(1-merge);
      const x=mix(points[i][0],540,merge),y=mix(points[i][1]+drift,465,merge),size=mix(106,40,merge);
      c.save();c.globalAlpha*=alpha;box(x-size/2,y-size/2+22*(1-enter),size,size,{r:25,shadow:1.15,stroke:false});
      icon(i,x-size*.25,y-size*.25+22*(1-enter),size*.5);c.restore();
      report.introNodes.push({i,x,y,merge,alpha});
    }
    c.restore();
    const logoEnter=q(t,.75,1.05,out),logoWidth=mix(166,45,landing);
    const lx=bez(457,457,72,72,landing),ly=bez(395,280,59,59,landing);
    c.save();c.globalAlpha=logoEnter;c.translate(lx+logoWidth/2,ly+logoWidth*mark.height/mark.width/2);
    c.rotate(-.07*(1-logoEnter));c.drawImage(mark,-logoWidth/2,-logoWidth*mark.height/mark.width/2,logoWidth,logoWidth*mark.height/mark.width);c.restore();
    txt(data.study.intro.lines[0],540,890+20*(1-copyAlpha),70,520,P.ink,copyAlpha,'center');
    txt(data.study.intro.lines[1],540,983+20*(1-copyAlpha),70,580,P.ink,q(t,.6,.65,out)*(1-q(t,4.15,.7)),'center');
    if(handoff>0){
      txt(data.study.intro.brand,132,87,30,620,P.ink,handoff);
      c.save();c.globalAlpha=handoff;
      intro(data.timing.intro.resumeSource-data.timing.intro.transitionDuration+t-data.timing.intro.duration);
      footer();c.restore();
    }
    report.phase='cinematic-intro';report.intro={handoff,landing,logoWidth,copyAlpha};
  }
  function intro(t){
    const transform=q(t,1.7,1.03),exit=q(t,6.55,.65),enter=q(t,0,.72,out);
    c.save();c.globalAlpha*=1-exit;
    txt('One question.',72,mix(454,236,transform)+30*(1-enter),mix(102,78,transform),580,P.ink,enter*(1-q(t,6.51,.13)));
    txt('More perspectives.',72,580+26*(1-enter),91,580,P.ink,enter*(1-q(t,1.65,.58)));
    const a=q(t,1.95,.7,out),zoom=1+.035*q(t,3.1,1.25)*(1-q(t,5.75,.6));
    c.save();c.translate(540,610);c.scale(zoom,zoom);c.translate(-540,-610);c.globalAlpha*=a;
    const y=mix(735,423,a);box(72,y,936,480,{r:28,shadow:1.2});c.globalAlpha*=1-q(t,6.5,.13);
    const matrix=()=>{const m=c.getTransform();return [m.a,m.b,m.c,m.d,m.e,m.f];};report.inputZoom={field:matrix()};
    txt('YOUR QUESTION',120,y+63,21,550,P.secondary);
    const typedCount=typedCountSafe(t);
    const typed=data.study.prompt.slice(0,typedCount);
    if(!typedCount)txt('Ask anything...',120,y+149,55,440,P.quiet,1-q(t,3,.15));
    const end=wrap(typed,120,y+149,815,55,490,P.ink,1,72);
    if(t>2.85&&t<6.15){const caretX=typedCount?end.x+5:112;c.save();c.fillStyle=P.ink;c.globalAlpha*=t<5.7?1:.55+.45*Math.cos(t*9);c.fillRect(caretX,end.y-44,3,54);c.restore();report.caret={x:caretX,width:3,placeholderX:120,typedCount};}
    const sendLocal={x:932,y:y+394};
    c.save();c.globalAlpha*=1-q(t,6.51,.13);report.inputZoom.send=matrix();box(sendLocal.x-36,sendLocal.y-36,72,72,{fill:P.ink,r:36,shadow:0,stroke:false});arrow(sendLocal.x,sendLocal.y,23);
    report.inputZoom.hint=matrix();txt('Six independent perspectives',120,y+405,25,440,P.secondary);c.restore();c.restore();
    const send={x:540+(sendLocal.x-540)*zoom,y:610+(sendLocal.y-610)*zoom};
    if(t>=2.1&&t<3.38){const p=q(t,2.1,.82,out);cursor(mix(940,148,p),mix(1090,583,p)-125*Math.sin(p*Math.PI),q(t,2.1,.15)*(1-q(t,3.08,.25)));}
    if(t>=5.8){const p=q(t,5.8,.55,out),press=q(t,6.34,.06)*(1-q(t,6.4,.15));cursor(mix(1020,send.x,p),mix(1090,send.y,p)-65*Math.sin(p*Math.PI),q(t,5.8,.13),press);report.cursorTarget={kind:'send',...send,press};}
    c.restore();
    report.promptCount=typedCountSafe(t);report.phase=t<3?'intro':t<6.5?'input':'send';
  }
  function typedCountSafe(t){return Math.floor(data.study.prompt.length*clamp((t-data.timing.typing.start)/data.timing.typing.duration));}
  function travellingLine(x1,y1,x2,y2,progress,alpha=1){
    if(progress<=0)return;c.save();c.globalAlpha*=alpha;c.strokeStyle='#c5c6be';c.lineWidth=2;c.beginPath();c.moveTo(x1,y1);c.lineTo(x2,y2);c.stroke();
    if(progress<1){c.fillStyle=P.ink;c.beginPath();c.arc(mix(x1,x2,progress),mix(y1,y2,progress),5,0,Math.PI*2);c.fill();}c.restore();
  }
  function smallConsensus(t){
    const a=q(t,25.65,.4,out),leave=q(t,27.13,.22);c.save();c.globalAlpha*=a*(1-leave);const y=mix(470,424,a);
    box(72,y,936,447,{r:24,shadow:1});c.globalAlpha*=1-q(t,27.09,.12);c.drawImage(mark,110,y+33,36,36*mark.height/mark.width);txt('Consensus',161,y+58,28,600);
    for(let i=0;i<3;i++)txt(data.study.synthesis[i],112,y+142+i*75,39,510);
    rule(112,y+336,854);box(112,y+362,242,54,{fill:'#eeede9',r:14,shadow:0});txt('Answers',132,y+398,28,550);chip('6',282,y+370,47);
    pacedCursor(data.timing.readerMotion.open,{x:238,y:y+389},'open-original-answers');c.restore();
  }
  function outro(t){
    const u=t-34,enter=q(u,0,.72,out),logoMove=q(u,.25,1.45),settle=q(u,1.65,.7);
    const x=bez(72,190,720,430,logoMove),y=bez(59,290,335,450,logoMove),w=mix(45,220,logoMove);
    c.save();c.translate(x+w/2,y+w*mark.height/mark.width/2);c.rotate(-.085*Math.sin(logoMove*Math.PI));c.drawImage(mark,-w/2,-w*mark.height/mark.width/2,w,w*mark.height/mark.width);c.restore();
    txt('consens.io',540,768+42*(1-settle),95,610,P.ink,settle,'center');
    const field=q(u,2.08,.68,out);c.save();c.globalAlpha*=field;const fy=909+45*(1-field);box(224,fy,632,110,{r:23,shadow:.55});txt('Your next question...',259,fy+68,35,440,P.secondary);box(772,fy+26,59,59,{fill:P.ink,r:29.5,shadow:0,stroke:false});arrow(801.5,fy+55.5,19);
    if(u>2.85){const a=q(u,2.85,.25);c.fillStyle=P.ink;c.globalAlpha*=a*(.66+.34*Math.cos((u-2.85)*6));c.fillRect(255,fy+37,2.3,42);}c.restore();
    report.providers=[];
    for(let i=0;i<providerMarks.length;i++){
      const p=q(u,2.65+i*.075,.4,out),im=providerMarks[i],size=48*data.providers[i].scale,ratio=size/Math.max(im.width,im.height),mw=im.width*ratio,mh=im.height*ratio;
      const cx=540+(i-(providerMarks.length-1)/2)*82,cy=1130+16*(1-p);
      c.save();c.globalAlpha*=.62*p;c.drawImage(im,cx-mw/2,cy-mh/2,mw,mh);c.restore();
      report.providers.push({name:data.providers[i].name,alpha:p,natural:[im.width,im.height],drawn:[mw,mh]});
    }
    report.phase='outro';
  }
  function inputBridge(t){
    // One input panel contracts upward; answer cards enter their final places.
    // There are no crossfading full-scene bitmaps or duplicated card fans.
    const collapse=q(t,6.48,.48),textExit=1-q(t,6.45,.13),barExit=1-q(t,6.72,.26);
    txt('One question.',72,236,78,580,P.ink,1-q(t,6.45,.18));
    txt('Six answers.',72,236+16*(1-q(t,6.79,.3,out)),78,580,P.ink,q(t,6.79,.3,out));
    txt('A habit tracker. Better retention.',76,287,26,440,P.secondary,q(t,6.95,.3));
    const y=mix(423,318,collapse),h=mix(480,63,collapse);
    c.save();c.globalAlpha*=barExit;box(72,y,936,h,{r:mix(28,18,collapse),shadow:mix(1.2,.35,collapse)});
    c.save();path(100,y+15,880,Math.max(20,h-30),8);c.clip();
    txt('YOUR QUESTION',120,486,21,550,P.secondary,textExit);
    wrap(data.study.prompt,120,572,815,55,490,P.ink,textExit,72);
    c.restore();
    c.save();c.globalAlpha*=textExit;box(896,781,72,72,{fill:P.ink,r:36,shadow:0,stroke:false});arrow(932,817,23);txt('Six independent perspectives',120,828,25,440,P.secondary);c.restore();c.restore();
    for(let i=0;i<6;i++){
      const p=window.studyCardEntry((t-7.5)*1.8/2.1,i),x=72+(i%2)*492,gy=400+Math.floor(i/2)*240,y=gy+53*(1-p);
      c.save();c.globalAlpha*=p;box(x,y,444,198,{r:22,shadow:.8});icon(i,x+27,y+25,32);txt(data.study.models[i].name,x+74,y+49,25,560);
      c.save();path(x+28,y+160,388,5,2.5);c.fillStyle='#e9e8e4';c.fill();c.clip();const v=(((t-7.5)*1.15+i*.16)%1+1)%1;c.fillStyle='#94999e';c.fillRect(x+28-65+v*483,y+160,76,5);c.restore();c.restore();
    }
    cursor(932,817,1-q(t,6.45,.18));report.phase='send-to-answers';report.promptCount=data.study.prompt.length;
  }
  function structuredSources(t){
    const u=t-25.8,enter=q(t,25.94,.38,out),exit=1-q(t,34.05,.22);
    const back=q(u,6.35,.8),grow=q(u,6.15,.8),documentsOut=1-q(u,6.22,.35);
    c.save();c.globalAlpha*=enter*exit;
    txt('Check the sources.',72,236+16*(1-enter),76,580,P.ink,1-q(t,33.96,.18));
    txt('For major factual disputes.',76,302,34,490,P.secondary,q(u,.32,.28));

    // The answer stays in view: only the disputed passage branches into a check.
    // These are intentional document illustrations, never invented source text.
    const answerIn=q(u,.55,.5,out),ay=414+28*(1-answerIn),ah=mix(242,458,grow);
    c.save();c.globalAlpha*=answerIn;box(72,ay,936,ah,{r:24,shadow:.85});
    c.drawImage(mark,108,ay+29,34,34*mark.height/mark.width);txt('Consensus',153,ay+54,28,600);
    rule(108,ay+80,864);
    c.strokeStyle='#c9cbc5';c.lineWidth=5;c.lineCap='round';
    for(const [yy,width] of [[ay+119,694],[ay+149,786]]){c.beginPath();c.moveTo(111,yy);c.lineTo(111+width,yy);c.stroke();}
    const band=q(u,.78,.4,out);c.save();c.globalAlpha*=band;
    box(106,ay+173,695,33,{fill:P.amber,r:6,shadow:0,stroke:false});
    c.strokeStyle='#b89c5c';c.lineWidth=4;c.beginPath();c.moveTo(119,ay+189);c.lineTo(769,ay+189);c.stroke();c.restore();
    const citation=q(u,1.03,.35,out);
    for(let i=0;i<2;i++){
      const x=858+i*69;c.save();c.globalAlpha*=citation;
      box(x-22,ay+167,44,44,{fill:'#eeede9',r:12,shadow:0,stroke:false});txt(String(i+1),x,ay+197,24,560,P.secondary,1,'center');c.restore();
    }
    c.restore();

    // Citation branches lead to two intact pages. The highlighted excerpts keep
    // their page context while the judge receives them; no blank merged page.
    const branches=q(u,1.35,.47),pageEnter=q(u,1.42,.62,out);
    c.save();c.globalAlpha*=documentsOut;
    for(let i=0;i<2;i++){
      const x=90+i*468,w=432,py=739+39*(1-q(u,1.42+i*.18,.52,out));
      const a=q(u,1.42+i*.18,.52,out),mid=x+w/2;
      c.save();c.globalAlpha*=branches*.7;c.strokeStyle='#c2c4bb';c.lineWidth=1.8;
      c.beginPath();c.moveTo(858+i*69,ay+214);c.bezierCurveTo(858+i*69,710,mid,679,mid,py);c.stroke();
      if(branches<1&&branches>0){const bx=bez(858+i*69,858+i*69,mid,mid,branches),by=bez(ay+214,710,679,py,branches);c.fillStyle=P.amberInk;c.beginPath();c.arc(bx,by,4,0,Math.PI*2);c.fill();}c.restore();
      c.save();c.globalAlpha*=a;box(x,py,w,267,{r:18,shadow:.7});
      // A quiet browser/document header, linked to the citation on the answer.
      c.strokeStyle='#9da39b';c.lineWidth=1.7;c.beginPath();c.arc(x+36,py+36,10,0,Math.PI*2);c.moveTo(x+26,py+36);c.lineTo(x+46,py+36);c.moveTo(x+36,py+26);c.bezierCurveTo(x+28,py+32,x+28,py+40,x+36,py+46);c.moveTo(x+36,py+26);c.bezierCurveTo(x+44,py+32,x+44,py+40,x+36,py+46);c.stroke();
      rule(x+62,py+36,237,.9);chip(String(i+1),x+w-62,py+18,38);
      rule(x+26,py+67,w-52);
      const focus=q(u,3.03+i*.37,.42,out),lineY=py+124+i*29;
      c.save();c.globalAlpha*=focus;box(x+25,lineY-13,w-50,27,{fill:P.amber,r:5,shadow:0,stroke:false});c.restore();
      c.strokeStyle='#b8bcb3';c.lineWidth=3;c.lineCap='round';
      for(let k=0;k<5;k++){const yy=py+95+k*29,ww=w-58-(k===4?100:k===0?44:0);c.beginPath();c.moveTo(x+29,yy);c.lineTo(x+29+ww,yy);c.stroke();}
      // Both cited passages travel into the same source judge.
      const extract=q(u,4.05+i*.32,.68),endX=442+i*196,endY=1079;
      if(extract>0&&extract<1){const xx=bez(mid,mid,endX,endX,extract),yy=bez(lineY,lineY+105,endY-45,endY,extract),width=mix(250,84,extract);box(xx-width/2,yy-11,width,22,{fill:P.amber,r:5,shadow:.1,stroke:false});}
      c.restore();
    }
    txt('Cited sources',72,708,25,520,P.secondary,pageEnter);
    c.restore();

    const judge=q(u,3.8,.45,out),jy=mix(1080,696,back),jx=mix(90,108,back),jw=mix(900,864,back);
    const reading=1-q(u,6.58,.16),context=q(u,6.78,.3,out);
    c.save();c.globalAlpha*=judge;box(jx,jy,jw,134,{r:20,shadow:mix(.55,0,back),fill:P.paper});
    txt('Source judge',jx+30,jy+40,24,510,P.secondary,reading);
    txt('Compare the evidence',jx+30,jy+94,41,550,P.ink,reading);
    txt('Source check',jx+30,jy+40,24,510,P.secondary,context);
    txt('Explain the disagreement',jx+30,jy+94,41,550,P.ink,context);
    // Magnifying glass, not a success tick: no verdict is asserted for this demo.
    const mx=jx+jw-62,my=jy+66;c.strokeStyle=P.ink;c.lineWidth=2.6;c.beginPath();c.arc(mx,my,15,0,Math.PI*2);c.moveTo(mx+11,my+11);c.lineTo(mx+24,my+24);c.stroke();c.restore();
    txt('Follow the citations.',72,1166,36,490,P.ink,q(u,.95,.3)*(1-q(u,3.52,.22)));
    c.restore();
    report.phase='conditional-source-check';
    report.sourceCheck={conditional:true,majorOnly:true,factualOnly:true,citedSourcesOnly:true,outcomeClaimed:false,concreteExample:false,sharedAnswerAnchor:true,returnedToAnswer:back>.99,surfaceFill:P.paper,surface:{x:jx,y:jy,w:jw,h:134},step:u<3.8?'follow-citations':u<6.35?'compare-cited-passages':'return-source-context'};
  }
  function directReader(t){
    const enter=q(t,34.3,.42,out),end=1-q(t,42,.6);c.save();c.globalAlpha*=enter*end;
    txt('Read every answer.',72,236+16*(1-enter),76,580,P.ink,q(t,34.4,.24)*(1-q(t,41.9,.2)));
    smallConsensus(t-8.65);
    const reveal=q(t,35.77,.54,out),excerpt=q(t,35.91,.36),switching=q(t,38.76,.32,out);
    if(reveal>0){
      const y=mix(424,382,reveal),h=mix(447,754,reveal);c.save();c.globalAlpha*=reveal;box(72,y,936,h,{r:24,shadow:1});c.save();path(94,y+22,892,h-44,10);c.clip();c.globalAlpha*=excerpt;
      txt('ORIGINAL ANSWER · EXCERPT',112,y+55,21,550,P.secondary);
      for(let i=0;i<6;i++){const x=111+i*148,active=i===0?1-switching:i===1?switching:0;if(active>0){c.save();c.globalAlpha*=active;box(x-9,y+86,118,80,{fill:'#eeede9',r:16,shadow:0});c.restore();}icon(i,x+27,y+106,38,active>0?.6+.4*active:.52);}
      rule(112,y+195,856);
      for(let i=0;i<2;i++){
        const a=i===0?1-q(t,38.73,.14):q(t,38.88,.22,out);if(a<=0)continue;c.save();c.globalAlpha*=a;c.translate((i===0?-1:1)*24*(i===0?switching:1-switching),0);
        icon(i,113,y+234,47);txt(data.study.models[i].name,181,y+272,36,580);
        const answer=data.reader[i];wrap(answer.heading,112,y+362,850,56,560,P.ink,q(t,i?38.88:35.99,.26,out));
        wrap(answer.reason,112,y+447+12*(1-q(t,i?39.13:36.25,.4,out)),826,37,450,P.secondary,q(t,i?39.13:36.25,.4,out),50);
        rule(112,y+553,850);txt('REMINDERS',112,y+598,19,550,P.secondary,q(t,i?39.61:36.61,.3));wrap(i===0?'Only after inactivity.':'Every day to build a routine.',112,y+654,840,38,490,P.ink,q(t,i?39.61:36.61,.4,out));c.restore();
      }
      c.restore();c.restore();
      pacedCursor(data.timing.readerMotion.switch,{x:307,y:y+127},'switch-model');
      report.reader={nativeOverview:false,excerpt:true,selected:t<38.78?'OpenAI':'Claude',source:'content.json authored scenario'};
    }
    c.restore();report.phase=t<35.77?'open-original-answers':'original-answers';
  }
  const storyClock=[[7.5,0],[9.6,1.8],[11.2,3.15],[11.5,3.3],[12.35,3.65],[13.2,4.03],[14.1,4.41],[15.3,4.72],[16.4,5.5],[16.85,5.65],[17.55,6.23],[19.2,6.45],[19.65,6.8],[20.1,7.05],[20.65,7.35],[21.35,7.65],[21.85,8],[22.65,8.45],[23.2,8.85],[24,9.45],[24.8,10.03],[25.1,10.3],[25.7,10.78],[28.8,12]];
  function studyTime(t){for(let i=1;i<storyClock.length;i++){const a=storyClock[i-1],b=storyClock[i];if(t<=b[0])return mix(a[1],b[1],clamp((t-a[0])/(b[0]-a[0])));}return 12;}
  function sourceTime(t){
    let added=0;
    for(const w of data.timing.readingWindows){
      const start=w.start+added,end=w.end+added+w.extra;
      if(t<start)return t-added;
      if(t<=end)return mix(w.start,w.end,(t-start)/(end-start));
      added+=w.extra;
    }
    return t-added;
  }
  window.drawFullFilm=function(t){
    const outputTime=t,introTiming=data.timing.intro,offset=introTiming.duration+introTiming.transitionDuration-introTiming.resumeSource;
    // Subtracting the offset must not turn a scene boundary such as 6.45
    // into 6.449999999999999 and leave one frame in the preceding scene.
    const motionTime=Number((t-offset).toFixed(9));t=sourceTime(motionTime);
    report={time:outputTime,motionTime,sourceTime:t,text:[],icons:[],phase:''};c.setTransform(1,0,0,1,0,0);c.globalAlpha=1;c.fillStyle=P.bg;c.fillRect(0,0,W,H);
    if(outputTime<introTiming.duration+introTiming.transitionDuration){cinematicIntro(outputTime);window.fullFilmReport=report;return report;}
    if(t>=7.5&&t<28.55){const v=studyTime(t);drawStudy(v,motionTime);c.drawImage(study,0,0);report.phase=window.studyReport.phase;report.text=window.studyReport.text;report.icons=window.studyReport.icons;report.phrases=window.studyReport.phrases;report.judges=window.studyReport.judges;report.mark=window.studyReport.mark;report.studyTime=v;window.fullFilmReport=report;return report;}
    // The legacy scene clock runs after the targeted reading-time remap above.
    const mediaTime=t;if(t>=28.55)t-=3;
    if(t<42)brand();
    if(t<6.45)intro(t);else if(t<7.5)inputBridge(t);
    if(t>=25.55&&t<26.15){drawStudy(studyTime(mediaTime),motionTime);c.save();c.globalAlpha=1-q(t,25.55,.35);c.drawImage(study,0,0);c.restore();}
    if(t>=25.8&&t<34.35)structuredSources(t);
    if(t>=34.25&&t<42.6)directReader(t);
    if(t>=42)outro(t-8);
    footer();window.fullFilmReport=report;return report;
  };
  window.drawFullFilm(0);
};
