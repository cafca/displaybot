# coding: utf-8

"""Videoplayer and Radio."""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from threading import Thread

logger = logging.getLogger('oxo')


def inline_keyboard(options):
    """Return an inline Keyboard given a dictionary of callback:display pairs."""
    rv = InlineKeyboardMarkup([[InlineKeyboardButton(v, callback_data=k)]
        for k, v in list(options.items())])
    return rv


def log_exceptions(func):
    """Wrapper to log exceptions to logger."""
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(e, exc_info=True)
    return wrapper


class Player(Thread):
    """Player class."""

    def __init__(self):
        """Init as Thread."""
        super(Player, self).__init__()
        self.player = None
        self.logger = logging.getLogger("oxo")

    @classmethod
    def run(cls):
        """Mock run method."""
        cls.player = None

    @property
    def running(self):
        """Boolean property, true when external player loaded."""
        return self.player is not None

    def stop(self):
        """Quit mplayer instance."""
        self.logger.debug("Stopping {} player...".format(self.__class__.__name__))
        self.stopped = True
        if self.running:
            try:
                self.player.terminate()
            except OSError as e:
                self.logger.debug(
                    "Error stopping {} player '{}'\n{}".format(
                        self.__class__.__name__, self.player, e), exc_info=True)
            self.logger.info("{} stopped".format(self.__class__.__name__))
        else:
            self.logger.debug("{} did not play".format(self.__class__.__name__))
