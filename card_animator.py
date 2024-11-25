import io
import time
from typing import Tuple, Dict, Optional

import pygame, pygame.gfxdraw
from pygame import Surface

from shazamio.schemas.models import ResponseTrack, SongSection

TRACK_SCROLL_PPS = 50.0
ARTIST_SCROLL_PPS = 30.0

class CardAnimator:
    def __init__(self, draw_font: pygame.font.Font, draw_font_small: pygame.font.Font, icon_cache: Dict[str, Surface], transition_out_time = 0.5, transition_delay_time = 0.2, transition_in_time = 0.5):
        self.draw_font_small = draw_font_small
        self.draw_font = draw_font
        self.icon_cache = icon_cache
        self.transition_in_time = transition_in_time
        self.transition_delay_time = transition_delay_time
        self.transition_out_time = transition_out_time
        self.transition_start_time = 0.0
        self.current_value = (time.time(), None)
        self.last_detection = (time.time(), None)

    def set_detection_to_show(self, detection: (float, ResponseTrack)):
        self.transition_start_time = time.time()
        self.last_detection = self.current_value
        self.current_value = detection

    def __current_animation_time(self) -> float:
        return time.time() - self.transition_start_time

    def __total_animation_duration(self) -> float:
        return self.transition_out_time + self.transition_delay_time + self.transition_in_time

    def __transition_out_and_delay_duration(self) -> float:
        return self.transition_out_time + self.transition_delay_time

    def draw(self, surface: pygame.Surface):
        current_track_position = (surface.get_width()//2, surface.get_height()//2)
        animation_progress_s = self.__current_animation_time()
        current_card = create_music_card(self.current_value, self.icon_cache, self.draw_font, self.draw_font_small, time.time() - self.current_value[0]) if self.current_value[1] is not None else None
        old_card = create_music_card(self.last_detection, self.icon_cache, self.draw_font, self.draw_font_small, time.time() - self.last_detection[0]) if self.last_detection[1] is not None else None
        if animation_progress_s > self.__total_animation_duration():
            if self.current_value[1] is not None:
                #finished
                card = create_music_card(self.current_value, self.icon_cache, self.draw_font, self.draw_font_small, time.time() - self.transition_start_time - self.transition_in_time - self.transition_out_time - self.transition_delay_time)
                draw_pos = (current_track_position[0] - card.get_width()//2, current_track_position[1] - card.get_height()//2)
                surface.blit(card, draw_pos)
        elif animation_progress_s > self.__transition_out_and_delay_duration():
            # transition in
            step_progress = (animation_progress_s - self.__transition_out_and_delay_duration()) / self.transition_in_time
            if current_card is None:
                return
            initial_position = surface.get_height() + current_card.get_height()
            final_position = current_track_position[1] - current_card.get_height()//2
            new_card_pos = (current_track_position[0] - current_card.get_width()//2, initial_position * (1-step_progress) + final_position * step_progress)

            surface.blit(current_card, new_card_pos)
        elif animation_progress_s > self.transition_out_time:
            # delay
            step_progress = (animation_progress_s - self.transition_out_time) / self.transition_delay_time
        else:
            # transition out
            step_progress = animation_progress_s / self.transition_out_time
            if old_card is None:
                return
            initial_position = current_track_position[1] - old_card.get_height()//2
            final_position = surface.get_height() + old_card.get_height()
            old_card_pos = (current_track_position[0] - old_card.get_width()//2, initial_position * (1 - step_progress) + final_position * step_progress)

            surface.blit(old_card, old_card_pos)



def blur_fade(image: pygame.Surface, progress: float) -> pygame.Surface:
    blur_radius = round(progress * 30)
    if blur_radius == 0:
        return image
    return pygame.transform.box_blur(image, blur_radius, False)

def create_music_card(detection_info: Tuple[float, ResponseTrack], icon_cache: Dict[str, pygame.Surface], draw_font: pygame.font.Font, draw_font_small: pygame.font.Font, lifetime: Optional[float] = None):
    '''

    :param detection_info:
    :param icon_cache:
    :param draw_font:
    :param draw_font_small:
    :param lifetime: How long the card has existed for
    :return:
    '''

    FIRST_LINE_HEIGHT = 400
    SECOND_LINE_HEIGHT = 450
    THIRD_LINE_HEIGHT = 480
    import requests
    card = Surface((400, 550), pygame.SRCALPHA)
    detection_timestamp, current_track = detection_info
    track_info = current_track.track
    for section in track_info.sections:
        if isinstance(section, SongSection):
            for page in section.meta_pages:
                if page.caption == track_info.title and track_info.title not in icon_cache:
                    print(page.image)
                    icon_cache[track_info.title] = pygame.image.load(io.BytesIO(requests.get(page.image).content),
                                                                     page.image).convert()
    if icon_cache[track_info.title]:
        card.blit(pygame.transform.smoothscale(icon_cache[track_info.title], (400, 400)), (0, 0))

    track_text = draw_font.render(str(track_info.title), True, (255, 255, 255))
    if track_text.get_width() < card.get_width() or lifetime is None:
        card.blit(track_text, (card.get_width()//2 - track_text.get_width()//2, FIRST_LINE_HEIGHT))
    else:
        text_and_buffer_width = track_text.get_width() + 40
        scroll_offset = (lifetime * TRACK_SCROLL_PPS) % text_and_buffer_width
        first_text_pos = 10 - scroll_offset
        card.blit(track_text, (first_text_pos, FIRST_LINE_HEIGHT))
        if first_text_pos + text_and_buffer_width < card.get_width():
            card.blit(track_text, (first_text_pos + text_and_buffer_width, FIRST_LINE_HEIGHT))

    artist_text = draw_font_small.render(str(track_info.subtitle), True, (255, 255, 255))
    if artist_text.get_width() < card.get_width() or lifetime is None:
        card.blit(artist_text, (card.get_width()//2 - artist_text.get_width()//2, SECOND_LINE_HEIGHT))
    else:
        text_and_buffer_width = artist_text.get_width() + 40
        scroll_offset = (lifetime * ARTIST_SCROLL_PPS) % text_and_buffer_width
        first_text_pos = 10 - scroll_offset
        card.blit(artist_text, (first_text_pos, SECOND_LINE_HEIGHT))
        if first_text_pos + text_and_buffer_width < card.get_width():
            card.blit(artist_text, (first_text_pos + text_and_buffer_width, SECOND_LINE_HEIGHT))

    progress_s = current_track.matches[0].offset + time.time() - detection_timestamp
    minutes = int(progress_s // 60)
    seconds = int(progress_s % 60)

    time_render = draw_font_small.render(f'{minutes:02d}:{seconds:02d}', True, (255, 255, 255))

    card.blit(time_render, (card.get_width()//2 - time_render.get_width()//2, THIRD_LINE_HEIGHT))
    return card
    # return blur_fade(card, (math.cos(math.radians((360*progress_s)/4))+1)/2)
