import time
from gtts import gTTS
tts=gTTS(text="祝大家生日快樂!",lang='zh-tw')
tts.save('生日快樂.mp3')

from pygame import mixer
mixer.init()
mixer.music.load('生日快樂.mp3')
mixer.music.play(loops=0)
time.sleep(1)

import tempfile
def talk(sentence1,lang1):
    with tempfile.NamedTemporaryFile(delete=True) as f:
        tts=gTTS(text=sentence1,lang=lang1)
        tts.save('{}.mp3'.format(f.name))
        mixer.init()
        mixer.music.load('{}.mp3'.format(f.name))
        mixer.music.play(loops=0)

talk('恭喜大家聖誕快樂','zh-tw')
time.sleep(3)
talk('Congratulations to everyone, Merry Christmas','en')
time.sleep(3)
talk('みなさん、おめでとうございます、メリークリスマス','ja')
time.sleep(3)
talk('모두 축하합니다. 메리 크리스마스','ko')
time.sleep(3)
talk('Xin chúc mừng tất cả mọi người, Giáng sinh vui vẻ','vi')
time.sleep(6)
talk('你好嗎?我很好','zh-tw')
time.sleep(3)
talk('お元気ですか？元気です','ja')
time.sleep(3)
talk('어떻게 지내 나는 괜찮아','ko')
time.sleep(3)

