from pydub import AudioSegment
from pydub.silence import detect_silence
import speech_recognition as sr
import glob
import shutil,os
from time import sleep

def emptydir(dirname):
    if os.path.isdir(dirname):
        shutil.rmtree(dirname)
        sleep(2)
    os.mkdir(dirname)

delay=1000
fname='python1'
sound=AudioSegment.from_file(fname+".wav",format="wav")
start_end=detect_silence(sound,delay,sound.dBFS,1)

mslist=[]
for i in range(len(start_end)):
    if i==(len(start_end)-1):
        data=start_end[i][1]
    else:
        data=start_end[i][1]-delay
    mslist.append(data)

timelist=[]
for sss in mslist:
    h,ms=divmod(float(sss),3600000)
    m,ms=divmod(float(ms),60000)
    s,ms=divmod(float(ms),1000)
    ts="%02d:%02d:%02d.%03d" % (h,m,s,ms)
    timelist.append(ts)

emptydir('soundSlice')
for i in range(len(timelist)):
    if i==0:
        start=0
    else:
        start=mslist[i-1]
        e