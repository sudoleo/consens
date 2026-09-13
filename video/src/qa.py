"""Render review sheets and inspect the actual encoded full film."""
from pathlib import Path
import subprocess,json,re,hashlib,shutil,sys
import numpy as np
from PIL import Image,ImageDraw
from runtime import ROOT, OUT, ffmpeg
QA=OUT/'qa'
FF=ffmpeg()

def run(args):return subprocess.run([str(FF),*args],capture_output=True,check=True)
def sheet(paths,times,target):
    w,h=216,270;cols=5;canvas=Image.new('RGB',(cols*(w+10),((len(times)+cols-1)//cols)*(h+30)),'#252a2f');draw=ImageDraw.Draw(canvas)
    for i,(file,t) in enumerate(zip(paths,times)):
        im=Image.open(file).convert('RGB');im.thumbnail((w,h));x=(i%cols)*(w+10);y=(i//cols)*(h+30);canvas.paste(im,(x,y+25));draw.text((x+6,y+6),f'{t:.2f}s',fill='white')
    canvas.save(target,quality=95)
timing=json.loads((ROOT/'src/timing.json').read_text())
intro_offset=timing['intro']['duration']+timing['intro']['transitionDuration']-timing['intro']['resumeSource']

def output_time(t):return round(t+intro_offset+sum(w['extra']*max(0,min(1,(t-w['start'])/(w['end']-w['start']))) for w in timing['readingWindows']),6)
report=json.loads((QA/'render-checks.json').read_text())
duration=report['duration'];frame_count=round(duration*report['fps'])
assert not report['errors'] and all(s['identical'] for s in report['seek']) and all(s['ok'] for s in report['editorial'])
assert all(s['ok'] for s in report['retained'])
assert all(s['ok'] for s in report['motionChecks'])
assert all(s['ok'] for s in report['polishChecks'])
if '--stills' in sys.argv:
    times=[f['time'] for f in report['frames']]
    for name,lo,hi in [('intro',0,7.5),('answers',7.5,11.2),('synthesis',10.5,17),('consensus',17,23),('contradiction',23,29),('sources',29,37.3),('reader',37.3,45),('outro',45,51)]:
        start=0 if name=='intro' else output_time(lo)
        selected=[t for t in times if start<=t<output_time(hi)];sheet([QA/'stills'/f'{t}.png' for t in selected],selected,QA/f'preflight-{name}.jpg')
    print('PREFLIGHT SHEETS READY');sys.exit()
video=OUT/'consensio-4x5.mp4'
result=run(['-hide_banner','-i',str(video),'-af','loudnorm=I=-16:TP=-2:LRA=9:print_format=json','-f','null','-']);log=result.stderr.decode(errors='replace');(QA/'decode-audio.txt').write_text(log,encoding='utf8')
assert '1080x1350' in log and '60 fps' in log
counts=re.findall(r'frame=\s*(\d+)',log);assert counts and int(counts[-1])==frame_count
assert not re.search('corrupt decoded|Invalid data|Error while',log,re.I)
assert re.search(r'Video:.*yuv420p\(tv,\s*bt709\)',log), 'Export must declare limited-range Rec.709'
levels=json.loads(log[log.rfind('{'):log.rfind('}')+1]);assert -24<float(levels['input_i'])<-18;assert float(levels['input_tp'])<=-1.5
palette=json.loads((ROOT/'src/color.json').read_text(encoding='utf-8'))
expected_bg=np.array([int(palette['bg'][i:i+2],16) for i in (1,3,5)])
color_samples=[]
for t in [1.8,8.4,21.8,33.15,44,57.8]:
    raw=run(['-v','error','-ss',str(t),'-i',str(video),'-frames:v','1','-vf','crop=12:12:24:24','-pix_fmt','rgb24','-f','rawvideo','pipe:1']).stdout
    rgb=np.frombuffer(raw,np.uint8).reshape(-1,3).mean(axis=0)
    sample={'time':t,'rgb':np.round(rgb,2).tolist(),'maxChannelError':round(float(np.abs(rgb-expected_bg).max()),2)}
    assert sample['maxChannelError']<=4, f'Encoded background color drift: {sample}'
    color_samples.append(sample)
groups={'story':[.8,4.8,7.2,9.6,11.7,13.4,15.8,17.6,19.2,20.9,22.8,23.9,25.2,27.1,28.9,30.4,31.7,33.4,35.3,36.6,38.75,39.7,43.5,46.3], 'joins':[6.35,6.5,6.65,6.8,6.95,7.1,7.3,7.48,7.52,7.7,25.55,25.7,25.85,26,26.15,34.1,34.3,34.5,35.8,36.1], 'contradiction':[19.9,20.5,21.4,21.9,22.15,22.4,22.8,23.2,23.6,24.1,24.8,25.3], 'sources':[26.4,27.25,28,28.8,29.6,30.2,30.7,31.4,32.1,32.8,33.4,34], 'reader':[35.4,35.8,36.1,36.6,37.2,38.75,39.2,40.5]}
groups={name:[round(t+3,2) if t>=13.85 else t for t in times] for name,times in groups.items()}
groups['synthesis']=[11.2,11.7,12.15,12.85,13.55,14.5,15.2,15.6,16,16.35,16.45,16.85,17.8,18.8]
groups['zoom']=[3.2,3.8,4.4,5.4,5.8,6.15,6.35,6.45]
groups['answers']=[6.96,7.2,7.48,7.52,7.8,8.2,8.6,9,9.5,9.8,10.3,10.9,11.1]
groups['text-continuity']=[24.85,25.05,25.2,25.4,25.6,25.7,25.75,25.8,26]
groups['outro']=[45.5,46.5,47.5,48,48.5,49,49.8]
groups={name:[output_time(t) for t in times] for name,times in groups.items()}
groups['intro']=[0,.3,.65,1,1.4,1.8,2.2,2.6,3.1,3.5,4,4.3,4.6,4.9,5,5.15,5.25,5.35,5.55,5.7,6.3]
groups['story']=[1.4,3.5,5.35]+groups['story'][1:]
for name,times in groups.items():
    folder=QA/f'encoded-{name}';folder.mkdir(exist_ok=True);paths=[]
    for i,t in enumerate(times):
        file=folder/f'{i:02}.png';run(['-y','-v','error','-ss',str(t),'-i',str(video),'-frames:v','1','-vf','scale=432:540',str(file)]);paths.append(file)
    sheet(paths,times,QA/f'encoded-{name}.jpg')
raw=run(['-v','error','-i',str(video),'-vf','fps=12,scale=216:270','-pix_fmt','gray','-f','rawvideo','pipe:1']).stdout
frames=np.frombuffer(raw,np.uint8).reshape(-1,270,216);d=np.abs(np.diff(frames.astype(np.float32),axis=0)).mean(axis=(1,2));spans=[];start=None
for i,still in enumerate(d<.04):
    if still and start is None:start=i
    if start is not None and (not still or i==len(d)-1):
        end=i if not still else i+1
        if (end-start)/12>=.5:spans.append({'start':round(start/12,2),'end':round(end/12,2),'duration':round((end-start)/12,2)})
        start=None
summary={'duration':duration,'fps':60,'frames':frame_count,'size':[1080,1350],'LUFS':float(levels['input_i']),'truePeak':float(levels['input_tp']),'seekChecks':len(report['seek']),'editorialChecks':report['editorial'],'nearStaticSpans':spans,'motionMeasurement':'12 fps decoded sample at 216x270, mean absolute luminance delta <0.04/255; diagnostic only, not an aesthetic score.','sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'subjectiveAudioReview':'Not performed. No assertion of subjective real-time listening.','scope':'Current standalone film: deterministic seeks, editorial checks, judge motion, source-card continuity, paced cursors and cinematic intro and included 60-second soundtrack.'}
summary['referenceFrames']=report['retained']
summary['colorGrade']={'name':palette['name'],'profile':'Rec.709 / limited range','background':palette['bg'],'decodedBackgroundSamples':color_samples}
def audio_hash(file):return hashlib.sha256(run(['-v','error','-i',str(file),'-map','0:a:0','-c:a','copy','-f','adts','pipe:1']).stdout).hexdigest()
summary['audioStreamSha256']=audio_hash(video)
summary['audioStreamIdenticalToSoundtrack']=summary['audioStreamSha256']==audio_hash(ROOT/'assets/audio/soundtrack.m4a')
assert summary['audioStreamIdenticalToSoundtrack']
summary['motionChecks']=report['motionChecks']
summary['polishChecks']=report['polishChecks']
summary['audioDesign']=json.loads((OUT/'music-credit.json').read_text())['audioDesign']
summary['readingWindows']=report['pacing']
summary['inputCharacterTimingChecks']=len(report['typing']['keyframes'])
summary['phraseContinuityFrames']=len(report['phraseFrames'])
for name,start,length in [('intro-review',0,9),('opening-review',0,19.5),('source-reader-review',40+intro_offset,13)]:
    run(['-y','-v','error','-ss',str(start),'-i',str(video),'-t',str(length),'-c:v','libx264','-crf','17','-preset','medium','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(OUT/f'{name}.mp4')])
motion_sheets=[('input-caret',2.88,.22,(100,518,420,76),(630,114),3,12),('input-handoff',6.6,1.1,(60,165,960,465),(576,279),3,6),('source-surface',41,2.25,(60,400,960,560),(576,336),3,6),('reader-open',43.65,1.7,(60,350,960,800),(432,360),3,6),('reader-switch',47,1.95,(60,350,960,800),(432,360),3,6)]
for name,start,length,(x,y,w,h),(sw,sh),cols,rate in motion_sheets:
    start+=intro_offset
    raw=run(['-v','error','-ss',str(start),'-i',str(video),'-t',str(length),'-vf',f'fps={rate},crop={w}:{h}:{x}:{y},scale={sw}:{sh}','-pix_fmt','rgb24','-f','rawvideo','pipe:1']).stdout
    frames=np.frombuffer(raw,np.uint8).reshape(-1,sh,sw,3);canvas=Image.new('RGB',(cols*(sw+8),((len(frames)+cols-1)//cols)*(sh+28)),'#252a2f');draw=ImageDraw.Draw(canvas)
    for i,frame in enumerate(frames):
        x=(i%cols)*(sw+8);y=(i//cols)*(sh+28);canvas.paste(Image.fromarray(frame),(x,y+24));draw.text((x+5,y+5),f'{start+i/rate:.3f}s',fill='white')
    canvas.save(QA/f'encoded-{name}.jpg',quality=96)
summary['motionReviewSheets']=[f'qa/encoded-{name}.jpg' for name,*_ in motion_sheets]
(OUT/'qa-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print(json.dumps({k:summary[k] for k in ['duration','fps','frames','size','LUFS','truePeak','sha256','audioStreamIdenticalToSoundtrack']},indent=2))
