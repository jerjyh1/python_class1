from pytube import YouTube
from pytube import Playlist
yt=YouTube('https://www.youtube.com/watch?v=g3S-2XTn-kI')
p = Playlist('https://www.youtube.com/playlist?list=PLf5BnbCRqFj5W-2kc9K9RQMjoUztnkf-R')
# p = Playlist('https://www.youtube.com/c/TaylorSwift/playlist')
for video in p.videos:
    print(video.title)
for url in p.video_urls:
    try:
        yt = YouTube(url)
        print(f'下載中 影片: {yt.title}')
        yt.streams.get_highest_resolution().download('./videos')
    except:
        print(f'影片: {yt.title} 無法下載，跳過繼續下載下一部。', end='\n\n')
    else:
        print("影片下載完成", end='\n\n')
print('開始下載影片，請稍後!')
yt.streams.first().download()
yt.streams.get_highest_resolution().download()
print('下載影片完成!')