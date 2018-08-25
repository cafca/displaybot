# coding: utf-8

"""Video player."""

import logging
import os

from sh import mplayer, ErrorReturnCode_1
from random import choice
from config import db, DATA_DIR
from player import Player
from tinydb import Query
from time import sleep
from platform import machine
from json.decoder import JSONDecodeError

logger = logging.getLogger("oxo")


class Video(Player):
    """Video player class."""

    def __init__(self):
        """Init as Player."""
        super(Video, self).__init__()
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
            if current_clip is None:
                self.logger.debug("No clips in database. Waiting...")
                sleep(5)
            else:
                self.logger.info("Starting video player with clip {}".format(current_clip["filename"]))
                if machine() == "armv7l":
                    # Raspberry
                    player_args = [
                        "-slave",
                        "-fs",
                        "-vo", "sdl"
                    ]
                else:
                    # Dev
                    player_args = ["-slave"]

                self.player = mplayer(Video.filepath(current_clip),
                    _bg=True,
                    _out=Video.interact,
                    *player_args)
                try:
                    self.player.wait()
                    self.logger.debug("Player ended {}".format(self.player))
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
        """Select recently added video or a random one from db."""
        q = Query()
        q_incoming = db.search(q.incoming == True)
        if len(q_incoming) > 0:
            rv = q_incoming[0]
            db.update({"incoming": False}, q.incoming == True)
            logger.info("Enqueuing shortlisted clip {}".format(rv["filename"]))
        else:
            q = Query()
            try:
                q_clips = db.search(q.type == "clip")
            except JSONDecodeError:
                rv = None
            else:
                rv = choice(q_clips) if len(q_clips) > 0 else None
        return rv
