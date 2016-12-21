
# coding: utf-8

# The Displaybot should show a window on a small wall-mounted display that plays gifs and videos from a telegram group or tunes to a web radio station.
#
# First, I need to create a Telegram bot. For this, install the Python Telegram Bot library and the peewee database ORM with
#
#     $ pip install peewee python-telegram-bot sqlite3 ffmpy --upgrade
#
# and then setup logging. I follow the [echobot example](https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/echobot2.py).
#
# Also, setup your Telegram api token below. Get a token by talking to [this bot](https://telegram.me/botfather) on Telegram.

# In[1]:

import os
import logging

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# create a file handler
handler = logging.FileHandler('hello.log')
handler.setLevel(logging.DEBUG)

# create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(handler)

# Use appdata to store all persistent application state
appdata = dict()
DATA_DIR = os.path.join(os.path.realpath("."), "userdata")

TELEGRAM_API_TOKEN = "YOUR TOKEN HERE"
with open(os.path.join(DATA_DIR, "TELEGRAM_API_TOKEN")) as f:
    TELEGRAM_API_TOKEN = f.read().strip()

# As anyone will be able to add the bot and add pictures to your display,
# you can filter telegram usernames here
ALLOWED_USERS = []

SUPPORTED_TYPES = ["video/mp4", "video/webm", "image/gif"]

SERVER_URL = "http://localhost:3000"

playnext = None


# ## Basic commands for a bot
#
# Define a few command handlers for Telegram. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.
#
# The start command is sent when the bot is started.

# In[2]:

def start(bot, update):
    update.message.reply_text('Gimme dat gif. Send an .mp4 link!')


# Handle errors, just in case

# In[3]:

def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))


# ## Receive clips from Telegram
#
# Next ist the receiver for our app. It will look at incoming messages and determine, whether they contain a link and then wether that link points at an mp4 video. This will then be added to the database for display.
#
# There are special cases:
# - if `url` ends in `gifv`, that is rewritten to `mp4`
# - if `url` ends in `gif`, the gif is downloaded and converted to a local `mp4` (see code for that below)

# In[4]:

import requests

def receive(bot, update):
    elems = update.message.parse_entities(types=["url"])
    logger.info("Receiving message with {} url entities".format(len(elems)))

    for elem in elems:
        url = update.message.text[elem.offset:(elem.offset + elem.length)]

        # Rewrite gifv links extension and try that
        if url[-4:] == "gifv":
            url = url[:-4] + "mp4"
            logger.info("Rewrite .gifv to {}".format(url))

        try:
            link = requests.head(url)
            logging.debug(link)

        except requests.exceptions.RequestException:
            logger.warning("Link not valid")
            update.message.reply_text("Link not valid")

        else:
            if "Content-Type" in link.headers and link.headers["Content-Type"] in SUPPORTED_TYPES:
                logging.info("Preparing download")
                if download_clip(url=url, author=update.message.from_user.first_name):
                    update.message.reply_text("Added video to database")
                else:
                    update.message.reply_text("Reposter!")

            else:
                logger.info("Link not supported: {}".format(link.headers))


# ## Download and file clips
#
# Then write a handler to store received videos in the database and computes a cached JSON response on disk with all current videos

# In[5]:

import os
import tempfile
import datetime

from sh import rm

def download_clip(url, author):
    global appdata
    if duplicate(url):
        logger.info("Detected duplicate {}".format(url))
        rv = False
    else:
        fname = url.split("/")[-1]
        fpath = os.path.join(DATA_DIR, "clips", fname)
        logger.info("Downloading clip to {}...".format(fpath))

        with open(fpath, "w+") as f:
            r = requests.get(url, stream=True)
            if r.ok:
                for block in r.iter_content(1024):
                    f.write(block)
            else:
                logger.error("Download failed {}".format(r))

        # Convert gif files using ffmpeg
        if url[-3:] == "gif":
            fpath = convert_gif(fpath)
            fname = os.path.basename(fpath)

        clip = {
            "url": url,
            "author": author,
            "filename": fname,
            "created": datetime.datetime.now().isoformat()
        }
        appdata["clips"].append(clip)
        appdata["incoming"] = clip
        save()

        rv = True
        logger.info("Saved new clip {} from {}".format(fname, author))
    return rv

def duplicate(url):
    return len([c for c in appdata["clips"] if "url" in c and c["url"] == url]) > 0



# ## Converting gifs
#
# In order to convert gifs to the less ressource intensive mp4 format, we can use the ffmpy library, which calls ffmpeg for us outside of python, to make the conversion.
#
# This function creates a temporary file and writes the gif to it. Then ffmpeg is called with settings for converting a gif to an mp4 and the result is stored in `frontend/public/videos/`, where the frontend script will be able to access it.

# In[6]:

import ffmpy

def convert_gif(fpath):
    logger.info("Converting gif to mp4...")

    new_fpath = fpath + ".mp4"

    ff = ffmpy.FFmpeg(
        inputs={fpath: None},
        outputs={new_fpath: '-movflags faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2"'}
    )
    ff.run()
    return new_fpath


# ## Config persistence
#
# We use a dictionary to store all application data and serialize it in a JSON file.

# In[7]:

import json

config_fname = os.path.join(DATA_DIR, "data.json")
def load():
    global appdata

    try:
        with open(config_fname) as f:
            appdata = json.load(f)
    except IOError, ValueError:
        logger.info("Bootstrap config loaded")
        appdata = {
            "clips": [],
            "config": {}
        }

    logger.info("@LOAD\n\n{}".format(json.dumps(appdata, indent=2, sort_keys=True)))
    return appdata

def save():
    global appdata

    logger.info("@SAVE\n\n{}".format(json.dumps(appdata, indent=2, sort_keys=True)))
    with open(config_fname, "w") as f:
        json.dump(appdata, f, indent=2, sort_keys=True)


# ## Timeout
#
# This is for the timeout

# In[8]:

def toggle_timeout(bot, update, args=list()):
    """Toggle the timeout config option."""
    global appdata

    if len(args) > 0:
        # user has submitted a parameter
        try:
            timeout = int(args[0])
        except ValueError:
            update.message.reply_text("What")
        else:
            timeout = max(timeout, MIN_TIMEOUT)
            appdata["config"]["timeout"] = timeout
    else:
        # toggle timeout
        if config["timeout"] > 0:
            config["timeout"] = 0
        else:
            config["timeout"] = 10

    save()

    update.message.reply_text('Timeout {}'.format(config["timeout"]))
    logger.info('Timeout {}'.format(config["timeout"]))


# ## Videoplayer

# In[9]:

from sh import mplayer
from time import sleep
from random import choice

def get_next():
    global appdata
    logger.info("In getnext {}".format(appdata))

    while len(appdata["clips"]) < 1:
        logger.info("Waiting for clips")
        sleep(10)

    if "incoming" in appdata.keys() and appdata["incoming"]:
        rv = appdata["incoming"]
        appdata["incoming"] = None
        save()
        logger.info("Playing shortlisted clip {}".format(rv["filename"]))
    else:
        rv = choice(appdata["clips"])
    return rv

def play_video():
    clip = get_next()

    while True:
        logger.info("Playing {}".format(clip["filename"]))
        mplayer(os.path.join(DATA_DIR, "clips", clip["filename"]), "-fs", "2>&1 /dev/null")
        logger.info("Finished {}".format(clip["filename"]))
        clip = get_next()
        sleep(0.1)


# ## Main function
#
# Add the main  function, where the handler functions above are registered with the Telegram Bot API

# In[10]:

def main():
    from threading import Thread

    # Load configuration and video database
    load()

    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TELEGRAM_API_TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("timeout", toggle_timeout, pass_args=True))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(None, receive))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Start the player
    player_thread = Thread(target=play_video)
    player_thread.setDaemon(True)
    player_thread.start()

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()





# Start your bot by saving this notebook as `display-bot.py` and running `$ python display-bot.py`.
#
# Before the main loop is started, database contents are dumped to the cache file, accessible by the frontend script.

# In[11]:

if __name__ == '__main__':
    main()



# Ok now we have a database of clips that we want to play. We will open them in a subprocess with the default player you have associated with the clips' filetype.
#
# We could just do this with the built-in `subprocess` module, but there's a pythonic alternative called `sh`. Get it with `pip install sh`.

# In[12]:

# main()


# In[ ]:




# In[ ]:



