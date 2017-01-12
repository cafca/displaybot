# ## Videoplayer and Radio

# In[9]:
import wikipedia

from sh import mplayer, ErrorReturnCode_1
from time import sleep
from random import choice
from collections import OrderedDict

# ## Radio player
from threading import Thread
from telegram.ext import Job
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ChatAction

def inline_keyboard(options):
    """Return an inline Keyboard given a dictionary of callback:display pairs."""
    rv = InlineKeyboardMarkup([[InlineKeyboardButton(v, callback_data=k)]
        for k, v in options.items()])
    return rv

def log_exceptions(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(e, exc_info=True)
    return wrapper
