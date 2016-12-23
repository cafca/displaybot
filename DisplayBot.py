#!/usr/bin/env python
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

from telegram.ext import Updater, CommandHandler, MessageHandler

# Use appdata to store all persistent application state
appdata = dict()

DATA_DIR = os.path.expanduser(os.path.join("~", ".displayBot"))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# create a file handler
log_dir = os.path.join(DATA_DIR, "hello.log")
handler = logging.FileHandler(log_dir)
handler.setLevel(logging.DEBUG)

# console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

formatter1 = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
console_handler.setFormatter(formatter1)

# add the handlers to the logger
logger.addHandler(handler)
logger.addHandler(console_handler)

logger.info("Logging to {}".format(log_dir))


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
            logger.debug("Rewrite .gifv to {}".format(url))

        try:
            link = requests.head(url)
            logger.debug(link)

        except requests.exceptions.RequestException:
            logger.warning("Link not valid")
            update.message.reply_text("Link not valid")

        else:
            if "Content-Type" in link.headers and link.headers["Content-Type"] in SUPPORTED_TYPES:
                if download_clip(url=url, author=update.message.from_user.first_name):
                    update.message.reply_text("👾 Added video to database.")
                else:
                    update.message.reply_text("👾 Reposter!")

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
        logger.debug("Downloading clip to {}...".format(fpath))

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
        outputs={new_fpath: '-pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2"'}
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

    logger.debug("@LOAD {} clips".format(len(appdata["clips"])))
    return appdata

def save():
    global appdata

    logger.debug("@SAVE {} clips".format(len(appdata["clips"])))
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

    while len(appdata["clips"]) < 1:
        logger.debug("Waiting for clips")
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
        mplayer(os.path.join(DATA_DIR, "clips", clip["filename"]), "-fs", "-really-quiet")
        logger.debug("Finished {}".format(clip["filename"]))
        clip = get_next()
        sleep(0.1)

# ## Radio player
from threading import Thread
from telegram.ext import Job

class Radio(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.url = None
        self.player = None
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.stopped = False
        current_url = None
        title = None
        self.reset_title()

        while not self.stopped:
            self.update()
            if current_url != self.url:
                self.logger.debug("Station changed")
                if self.player is not None:
                    self.player.terminate()
                    self.logger.info("Stopped running radio")
                    self.player = None
                else:
                    self.logger.debug("No radio playing previously")

                if self.url is not None:
                    self.logger.info("Playing {}".format(self.url))
                    self.player = mplayer(self.url, "-quiet",
                        _bg=True,
                        _out=self.interact,
                        _done=lambda c,s,e: self.logger.info("Completed {} - {} with {}".format(c,s,e))
                    )
                current_url = self.url

            elif title != self.title:
                title = self.title
                self.logger.info("Title is {}".format(title))

            sleep(1)

    @classmethod
    def interact(cls, line, stdin):
        logger = logging.getLogger(__name__)
        if line.startswith("ICY"):
            logger.debug("Found ICY data: {}".format(line))
            s = "StreamTitle="
            start = line.find(s) + len(s) + 1
            end = line.find(";", start) - 1
            if start and end:
                title = line[start:end]
                logger.debug("Found title in ICY: {}".format(title))
                if len(title) > 0:
                    global appdata
                    appdata["station_title"] = title


    def update(self):
        global appdata
        self.url = appdata["stations"].get(appdata["station_playing"])
        self.title = appdata.get("station_title")

    @classmethod
    def send_title(cls, bot, job):
        logger = logging.getLogger(__name__)
        global appdata
        t = appdata["station_title"]
        t0 = appdata["station_title_sent"]
        if t != t0:
            logger.debug("Title changed from '{}' to '{}'".format(t0, t))
            msg = "▶️ Now playing {}".format(t)
            bot.sendMessage(chat_id=job.context, text=msg)
            appdata["station_title_sent"] = t
            save()

    def reset_title(self):
        global appdata
        appdata["station_title"] = None

    def stop(self):
        self.logger.info("Stopping radio player...")
        self.stopped = True
        if self.player is not None:
            self.player.terminate()
            self.logger.info("Radio stopped")
        else:
            self.logger.info("Radio did not play")

def radio_command(bot, update, job_queue, args=list()):
    global appdata

    if len(args) > 0:
        requested_radio = appdata["stations"].get(args[0])
        if requested_radio:
            logger.info("Requesting station {}".format(args[0]))
            appdata["station_playing"] = args[0]
            update.message.reply_text("📻 Changed station to {}".format(args[0]))

            # Setup title relay
            relay_job = Job(Radio.send_title, 1.0, repeat=True, context=update.message.chat_id)
            job_queue.put(relay_job)
            logger.info("Job {} enqueued".format(relay_job))
            save()
        else:
            update.message.reply_text("📻 I don't know about {}".format(args[0]))
    else:
        appdata["station_playing"] = None
        appdata["station_playing_sent"] = None
        station_data = "\n".join(["/radio {}".format(k) for k in sorted(appdata["stations"].keys())])
        update.message.reply_text(
            "⏹ Radio turned off.\n\nAvailable stations:\n{}".format(station_data))
        save()



# ## Main function
#
# Add the main  function, where the handler functions above are registered with the Telegram Bot API

# In[10]:

def main():

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

    dp.add_handler(CommandHandler("radio", radio_command,
        pass_args=True, pass_job_queue=True))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(None, receive))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Start the player
    gif_player = Thread(target=play_video)
    gif_player.setDaemon(True)
    gif_player.start()

    radio = Radio()
    radio.setDaemon(True)
    radio.start()

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

    radio.stop()





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



