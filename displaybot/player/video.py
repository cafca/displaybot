# coding: utf-8

"""Video player."""

import logging
import os

from sh import mplayer, ErrorReturnCode_1
from random import choice
from config import db, DATA_DIR
from omxplayer.player import OMXPlayer
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
                self.logger.debug("Starting video player with clip [{}]".format(
                    current_clip["filename"][:6]))

                full_path = self.filepath(current_clip)

                if machine() == "armv7l":
                    player_args = [
                        '--blank',
                        '-o', 'hdmi',
                        '--loop',
                        '--no-osd',
                        '--aspect-mode', 'fill',
                        '--win', "'0, 0, 810, 540'"
                    ]
                else:
                    player_args = [
                        '-b',
                        '--loop'
                    ]

                if self.player is None:
                    self.player = OMXPlayer(full_path, player_args)
                else:
                    self.player.load(full_path, player_args)
                    self.player.play()

                sleep(5)
                self.player.pause()
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
