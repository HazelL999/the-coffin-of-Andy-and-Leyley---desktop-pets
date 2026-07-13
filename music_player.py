"""Background music player: cross-platform looped playback via pygame.mixer.

Drop .mp3 / .ogg / .wav files into assets/music/ — the first found file is
played on loop. If pygame isn't installed (or no music files), the app runs
identically without sound — no crash, no nag.

Uses pygame.mixer (not the full pygame engine) so it's lightweight. Init is
lazy: the mixer only starts when start() is called, and fails silently.
"""

import sys

import config


class MusicPlayer:
    """A thin wrapper around pygame.mixer for ambient looped music.

    All methods are best-effort — if pygame isn't installed or the audio
    file can't load, everything degrades to silence without raising.
    """

    def __init__(self):
        self._mixer = None    # the pygame.mixer module (or None if unavailable)
        self._playing = False
        self._track = None    # path to the currently loaded track
        self._available = False
        self._init_mixer()

    def _init_mixer(self):
        """Try to import pygame and init the mixer. Sets _available."""
        try:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            self._mixer = pygame.mixer
            self._available = True
        except Exception:
            # pygame not installed, or audio device unavailable. Silent.
            self._available = False

    def _find_track(self):
        """Find the first audio file in MUSIC_DIR. Returns a path str or None."""
        if not config.MUSIC_DIR.is_dir():
            return None
        exts = {".mp3", ".ogg", ".wav", ".flac", ".m4a"}
        try:
            files = sorted(p for p in config.MUSIC_DIR.iterdir()
                           if p.suffix.lower() in exts)
        except Exception:
            return None
        return str(files[0]) if files else None

    def start(self):
        """Begin playing the first found track on loop (if configured)."""
        if not self._available or not config.MUSIC_ENABLED:
            return
        track = self._find_track()
        if not track:
            return
        self._load_and_play(track)

    def _load_and_play(self, track):
        try:
            self._mixer.music.load(track)
            self._mixer.music.set_volume(config.MUSIC_VOLUME)
            self._mixer.music.play(loops=-1)  # loop forever
            self._track = track
            self._playing = True
        except Exception:
            self._available = False

    def toggle(self):
        """Toggle music on/off. Returns True if now playing, False if paused."""
        if not self._available:
            return False
        if self._playing:
            try:
                self._mixer.music.pause()
            except Exception:
                pass
            self._playing = False
            return False
        else:
            try:
                if self._track and self._mixer.music.get_busy() is not None:
                    # Already loaded — just unpause.
                    self._mixer.music.unpause()
                else:
                    # Never started (e.g. MUSIC_ENABLED was False at init).
                    track = self._find_track()
                    if track:
                        self._load_and_play(track)
            except Exception:
                pass
            self._playing = True
            return True

    @property
    def is_playing(self):
        return self._playing

    @property
    def is_available(self):
        """True if pygame loaded and an audio device is usable."""
        return self._available

    def shutdown(self):
        """Cleanly stop music on app quit."""
        if not self._available:
            return
        try:
            self._mixer.music.stop()
            self._mixer.quit()
        except Exception:
            pass
