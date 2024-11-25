import asyncio
import collections
import io
import time
import wave
from collections import deque

from shazamio import Shazam, Serialize
import pyaudio
import threading

from shazamio.schemas.models import SongSection

SAMPLE_RATE = 16000
SOUND_BUFFER_S = 12
READ_PER_CALL = SAMPLE_RATE//2
IDENTIFY_PAUSE = 2.5

audio_queue = deque(maxlen=SAMPLE_RATE * SOUND_BUFFER_S)
now_playing = deque(maxlen=5)
running = True
def audio_recording_thread():
    global running
    p = pyaudio.PyAudio()

    input_device = p.get_default_input_device_info()
    input_stream = p.open(SAMPLE_RATE, 1, pyaudio.paInt16, input=True, input_device_index=input_device['index'])

    input_stream.start_stream()
    while running:
        samples_in = input_stream.read(READ_PER_CALL, exception_on_overflow=False)
        audio_queue.extend(samples_in)

def visualizer_thread():
    global running
    import pygame
    import requests

    icon_cache = {}

    screen = pygame.display.set_mode((1280, 720))

    pygame.font.init()
    draw_font = pygame.font.Font('SourGummy-VariableFont_wdth,wght.ttf', size=40)
    clockity = pygame.time.Clock()
    old_track = None
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
        screen.fill((0, 0, 0))

        if now_playing and time.time() - now_playing[-1][0] < 6:
            track_info = now_playing[-1][1]
            if old_track != track_info:
                print(track_info)
                for section in track_info.sections:
                    if isinstance(section, SongSection):
                        for page in section.meta_pages:
                            if page.caption == track_info.title:
                                print(page.image)
                                icon_cache[track_info.title] = pygame.image.load(io.BytesIO(requests.get(page.image).content), page.image).convert()
            old_track = now_playing[-1]
            render_font = draw_font.render(str(track_info), False, (255, 255, 255))
            screen.blit(render_font, (10, 10))

            if icon_cache[track_info.title]:
                screen.blit(icon_cache[track_info.title], (10, 720 - icon_cache[track_info.title].get_height() - 10))
        pygame.display.flip()
        clockity.tick(60)

async def main():
    global running

    shazam = Shazam()

    audio_thread = threading.Thread(target=audio_recording_thread, name="Recording thread", daemon=True)
    visual_thread = threading.Thread(target=visualizer_thread, name="Visualizer thread", daemon=True)
    audio_thread.start()
    visual_thread.start()
    print("Start")
    while running:
        try:
            if len(audio_queue) == audio_queue.maxlen:
                wav_out = io.BytesIO()
                wave_file = wave.open(wav_out, 'wb')
                wave_file.setnchannels(1)
                wave_file.setframerate(SAMPLE_RATE)
                wave_file.setsampwidth(2)
                wave_file.writeframes(bytes(audio_queue))
                wave_file.close()
                recognized_song = await shazam.recognize(data=wav_out.getvalue())
                recognize_result = Serialize.full_track(data=recognized_song)
                if recognize_result.track:
                    now_playing.append((time.time(), recognize_result.track, recognize_result.timestamp))

                sleep_time = 5
                if recognize_result.retry_ms:
                    sleep_time = min(sleep_time, recognize_result.retry_ms / 1000)
                await asyncio.sleep(sleep_time)
            else:
                print('waiting', len(audio_queue))
                await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            running = False
    audio_thread.join(timeout=5)
    visual_thread.join(timeout=5)


asyncio.get_event_loop_policy().get_event_loop().run_until_complete(main())