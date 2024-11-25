import asyncio
import io
import time
import wave
from collections import deque

from shazamio import Shazam, Serialize
import pyaudio
import threading

from card_animator import CardAnimator

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
    print("Recording with", input_device)
    input_stream = p.open(SAMPLE_RATE, 1, pyaudio.paInt16, input=True, input_device_index=input_device['index'])

    input_stream.start_stream()
    while running:
        samples_in = input_stream.read(READ_PER_CALL, exception_on_overflow=False)
        audio_queue.extend(samples_in)

def visualizer_thread():
    global running
    import pygame

    icon_cache = {}

    screen = pygame.display.set_mode((1280, 720))

    pygame.font.init()
    draw_font = pygame.font.Font('PlayfairDisplay-VariableFont_wght.ttf', size=40)
    draw_font_small = pygame.font.Font('PlayfairDisplay-VariableFont_wght.ttf', size=25)
    clockity = pygame.time.Clock()
    animator = CardAnimator(draw_font, draw_font_small, icon_cache)
    old_to_show = None
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
        screen.fill((0, 0, 0))

        to_show = now_playing[-1] if now_playing else None

        if to_show is not None:

            # song is undetected for less than 15s, just show previous for now
            if to_show[1] is None:
                if time.time() - to_show[0] <= 15 and len(now_playing) > 1:
                    to_show = now_playing[-2]

            if to_show != old_to_show:
                animator.set_detection_to_show(to_show)
        old_to_show = to_show
        animator.draw(screen)

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
                record_timestamp = time.time()
                wav_out = io.BytesIO()
                wave_file = wave.open(wav_out, 'wb')
                wave_file.setnchannels(1)
                wave_file.setframerate(SAMPLE_RATE)
                wave_file.setsampwidth(2)
                wave_file.writeframes(bytes(audio_queue))
                wave_file.close()
                try:
                    recognized_song = await shazam.recognize(data=wav_out.getvalue())
                except Exception as e:
                    print("Error calling shazam:", e)
                    await asyncio.sleep(10)
                    continue
                recognize_result = Serialize.full_track(data=recognized_song)
                if recognize_result.track:
                    print(recognize_result)
                    if len(now_playing) == 0 or now_playing[-1][1] is None or recognize_result.track.key != now_playing[-1][1].track.key:
                        if len(now_playing) >= 2 and now_playing[-2][1] is not None and now_playing[-2][1].track.key == recognize_result.track.key:
                            now_playing.pop()
                        else:
                            now_playing.append((record_timestamp, recognize_result))
                else:
                    print('not recognized')
                    now_playing.append((record_timestamp, None))

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