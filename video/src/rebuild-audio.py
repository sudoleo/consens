"""Rebuild the calm music bed from the original source; leaves the accepted soundtrack untouched."""
from pathlib import Path
import json, subprocess, hashlib, wave
import numpy as np

from runtime import ROOT, OUT, ffmpeg
OUT=OUT/'audio-rebuild'
OUT.mkdir(parents=True,exist_ok=True)
FF=ffmpeg()
MUSIC=ROOT/'assets/audio/neon-source.mp3'
credit=json.loads((ROOT/'assets/audio/credit.json').read_text(encoding='utf-8'))
if not MUSIC.is_file():
    raise SystemExit('Missing assets/audio/neon-source.mp3. See assets/audio/README.md.')
if hashlib.sha256(MUSIC.read_bytes()).hexdigest()!=credit['sourceSha256']:
    raise SystemExit('Original music SHA-256 differs from credit.json; verify the source before rebuilding.')
RATE=48000

def run(args):
    return subprocess.run([str(FF),*args],capture_output=True,check=True)

def write_wav(path,samples):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(RATE)
        f.writeframes(np.round(np.clip(samples,-1,1)*32767).astype('<i2').tobytes())

def rms(x):return float(np.sqrt(np.mean(x.astype(np.float64)**2)))
def db(x):return float(20*np.log10(max(float(x),1e-12)))
timing=json.loads((ROOT/'src/timing.json').read_text())
intro=timing['intro'];intro_offset=intro['duration']+intro['transitionDuration']-intro['resumeSource']
duration=timing['sourceDuration']+intro_offset+sum(w['extra'] for w in timing['readingWindows']);fade_in=3.;fade_out=1.45
assert duration==60
source_start=115.15;phrase_duration=18.;period=16.;overlap=2.
raw=run(['-v','error','-ss',str(source_start),'-i',str(MUSIC),'-t',str(phrase_duration),'-ar',str(RATE),'-ac','2','-f','f32le','pipe:1']).stdout
phrase=np.frombuffer(raw,np.float32).reshape(-1,2)
assert len(phrase)==round(phrase_duration*RATE)
# 16 seconds preserve the measured half-second rhythmic grid. Complementary
# cosine fades overlap two seconds without concatenation clicks or gaps.
length=round(duration*RATE);loop=np.zeros((length,2),dtype=np.float32)
xf=.5-.5*np.cos(np.linspace(0,np.pi,round(overlap*RATE),endpoint=True))
seams=[]
for repeat,start in enumerate(np.arange(0,duration,period)):
    piece=phrase.copy()
    if repeat:piece[:len(xf)]*=xf[:,None];seams.append(float(start))
    piece[-len(xf):]*=(1-xf)[:,None]
    at=round(start*RATE);n=min(len(piece),length-at);loop[at:at+n]+=piece[:n]
write_wav(OUT/'music-loop-raw.wav',loop)
# Use a static gain measured on the new passage, preserving its dynamics.
measurement=run(['-hide_banner','-i',str(OUT/'music-loop-raw.wav'),'-af','loudnorm=I=-21:TP=-3:LRA=9:print_format=json','-f','null','-']).stderr.decode(errors='replace')
levels=json.loads(measurement[measurement.rfind('{'):measurement.rfind('}')+1])
gain_db=-21-float(levels['input_i'])
music=loop*10**(gain_db/20)
times=np.arange(length)/RATE
music*=np.clip(times/fade_in,0,1)[:,None]
music*=np.clip((duration-times)/fade_out,0,1)[:,None]
write_wav(OUT/'music-bed.wav',music)
write_wav(OUT/'score.wav',music)
assert (OUT/'music-bed.wav').read_bytes()==(OUT/'score.wav').read_bytes()
audio_design={
    'musicFadeInSeconds':fade_in,'musicFadeOutSeconds':fade_out,
    'musicTargetBeforeFadesLUFS':-21,'musicStaticGainDb':round(gain_db,2),
    'musicSourceRange':[source_start,source_start+phrase_duration],
    'musicLoopPeriodSeconds':period,'musicCrossfadeSeconds':overlap,
    'musicRepeatStarts':seams,'musicDuckDuringTypingDb':0,
    'typingEnabled':False,'typingEvents':0,
    'mixPeakDbFS':round(db(np.max(np.abs(music))),2),
    'scoreIdenticalToMusicBed':True
}
meta={
    'title':'Neon (No Melody Alt Mix)','artist':'Scott Buckley',
    'source':'https://www.scottbuckley.com.au/library/neon/','license':'CC BY 4.0',
    'licenseUrl':'https://creativecommons.org/licenses/by/4.0/',
    'sourceSha256':hashlib.sha256(MUSIC.read_bytes()).hexdigest(),
    'sourceStart':source_start,'sourceEnd':source_start+phrase_duration,
    'changes':'Calm passage repeated every 16 seconds with two-second cosine crossfades, restrained level, three-second entry fade and 1.45-second exit fade. Typing and its music duck removed.',
    'audioDesign':audio_design,'subjectiveListening':'Not performed; technical checks only.'
}
(OUT/'music-credit.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
print('MUSIC-ONLY SCORE READY')
