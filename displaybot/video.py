# coding: utf-8

"""Video player."""

import logging
from sh import mplayer, ErrorReturnCode_1
from random import choice
from config import save
from player import Player

logger = logging.getLogger("oxo")


class Video(Player):
    """Video player class."""

    def __init__(self):
        """Init as Player."""
        super(Video, self).__init__()
        print super(Video, self)
        self.logger = logging.getLogger("oxo")
        self.close_player = False
        self.stopped = False

    @classmethod
    def filepath(cls, clip):
        """Return disk location of a clip."""
        return os.path.join(DATA_DIR, "clips", clip["filename"])

    def run(self):
        """Thread target."""
        while not self.stopped:
            current_clip = Video.get_next()
            self.logger.info("Starting video player with clip {}".format(current_clip["filename"]))
            self.player = mplayer(self.filepath(current_clip),
                "-slave",
                "-fs",
                "-vo", "sdl",
                _bg=True,
                _out=self.interact,
                _done=self.teardown)
            try:
                self.player.wait()
            except ErrorReturnCode_1:
                self.logger.error("Video player returned code 1.")
        self.logger.debug("Exit video player")

    @classmethod
    def interact(cls, line, stdin):
        """Enqueue clips continuously through mplayer STDIN."""
        start_playback = "Starting playback..."

        logger = logging.getLogger("oxo")
        if start_playback in line:
            nextclip = cls.get_next()
            path = cls.filepath(nextclip)
            cmd = "loadfile {} 1\n".format(path)
            logger.info("Enqueued clip {}".format(nextclip['filename']))
            stdin.put(cmd)

    @classmethod
    def get_next(cls):
        """Select recently added video or a random one from appdata."""
        global appdata

        if "incoming" in appdata.keys() and appdata["incoming"]:
            rv = appdata["incoming"]
            appdata["incoming"] = None
            save()
            logger.info("Enqueuing shortlisted clip {}".format(rv["filename"]))
        elif len(appdata["clips"]) > 0:
            rv = choice(appdata["clips"])
        else:
            rv = None
        return rv
