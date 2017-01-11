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

from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler

# Use appdata to store all persistent application state
appdata = dict()

DATA_DIR = os.path.expanduser(os.path.join("~", ".displayBot"))

logger = logging.getLogger("oxo")
logger.setLevel(logging.DEBUG)

jqlogger = logging.getLogger("JobQueue")
jqlogger.setLevel(logging.WARNING)

# create a file handler
log_dir = os.path.join(DATA_DIR, "hello.log")
handler = logging.FileHandler(log_dir)
handler.setLevel(logging.DEBUG)

# console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# create a logging format
logfmt = '%(asctime)s %(levelname)s\t: %(message)s'
tmfmt = "%m/%d %H:%M:%S"
formatter = logging.Formatter(logfmt, tmfmt)
handler.setFormatter(formatter)

logfmt1 = '%(asctime)s: %(message)s'
formatter1 = logging.Formatter(logfmt1, tmfmt)
console_handler.setFormatter(formatter1)

# add the handlers to the logger
logger.addHandler(handler)
jqlogger.addHandler(handler)
logger.addHandler(console_handler)
jqlogger.addHandler(console_handler)

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
    # Add attachments
    doc = update.message.document
    try:
        if doc:
            logger.debug("Processing attachment")
            file_data = bot.getFile(doc.file_id)
            logger.debug("Downloading {}".format(file_data["file_path"]))
            download_clip(file_data["file_path"], bot, update, doc["mime_type"],
                fname=doc["file_name"])
    except Exception as e:
        logger.error(e, exc_info=True)


    # Add all URLs in the message
    elems = update.message.parse_entities(types=["url"])
    for elem in elems:
        logger.info("Processing message with {} url entities".format(len(elems)))
        url = update.message.text[elem.offset:(elem.offset + elem.length)]

        # Rewrite gifv links extension and try that
        if url[-4:] == "gifv":
            url = url[:-4] + "mp4"
            logger.debug("Rewrite .gifv to {}".format(url))

        try:
            link = requests.head(url, allow_redirects=True)
            logger.debug(link)

        except requests.exceptions.RequestException:
            logger.warning("Link not valid")
            update.message.reply_text("Link not valid")

        else:
            if "Content-Type" in link.headers:
                download_clip(
                    url=url,
                    bot=bot,
                    update=update,
                    content_type=link.headers["Content-Type"])
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

def download_clip(url, bot, update, content_type, fname=None):
    global appdata

    if not fname:
        fname = url.split("/")[-1]

    author = update.message.from_user.first_name
    if content_type not in SUPPORTED_TYPES:
        logger.info("Link not supported: \n{}\nType{}".format(
            url, content_type))
    if duplicate(fname):
        logger.info("Detected duplicate {}".format(fname))
        update.message.reply_text("👾 Reposter!")
    else:
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

        bot.sendMessage(chat_id=update.message.chat_id, text="👾 Added video to database.")
        logger.info("Saved new clip {} from {}".format(fname, author))


def duplicate(filename):
    return len([c for c in appdata["clips"]
        if "filename" in c and c["filename"] == filename]) > 0



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
        inputs={
            fpath: None
        },
        outputs={
            new_fpath: '-pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2"'
        }
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
            "incoming": None,
            "station_playing": None,
            "station_playing_sent": None,
            "station_title": None,
            "station_title_sent": None,
            "stations": {
                "91.4": "http://138.201.251.233/brf_128",
                "deutschlandfunk": "http://dradio_mp3_dlf_m.akacast.akamaistream.net/7/249/142684/v1/gnl.akacast.akamaistream.net/dradio_mp3_dlf_m",
                "dradio-kultur": "http://dradio_mp3_dkultur_m.akacast.akamaistream.net/7/530/142684/v1/gnl.akacast.akamaistream.net/dradio_mp3_dkultur_m",
                "dronezone": "http://ice1.somafm.com/dronezone-128-aac",
                "fip": "http://direct.fipradio.fr/live/fip-midfi.mp3",
                "fip du groove": "http://direct.fipradio.fr/live/fip-webradio3.mp3",
                "fip du jazz": "http://direct.fipradio.fr/live/fip-webradio2.mp3",
                "fip du monde": "http://direct.fipradio.fr/live/fip-webradio4.mp3",
                "fip du reggae": "http://direct.fipradio.fr/live/fip-webradio6.mp3",
                "fip du rock": "http://direct.fipradio.fr/live/fip-webradio1.mp3",
                "fip tout nouveau": "http://direct.fipradio.fr/live/fip-webradio5.mp3"
            }
        }

    logger.debug("@LOAD {} clips".format(len(appdata["clips"])))
    return appdata

def save():
    global appdata

    logger.debug("@SAVE {} clips".format(len(appdata["clips"])))
    with open(config_fname, "w") as f:
        json.dump(appdata, f, indent=2, sort_keys=True)




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

class Radio(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.url = None
        self.player = None
        self.logger = logging.getLogger("oxo")

    @log_exceptions
    def run(self):
        self.stopped = False
        current_url = None
        title = None
        self.reset_title()

        while not self.stopped:
            self.update()
            if current_url != self.url:
                self.logger.debug("Station changed")
                if self.running:
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
                        _done=self.teardown,
                        _ok_code=[0, 1])
                current_url = self.url

            elif title != self.title:
                title = self.title
                self.logger.info("Title is {}".format(title))

            sleep(1)

    @property
    def running(self):
        return self.player is not None and self.player != ''

    @classmethod
    def interact(cls, line, stdin):
        logger = logging.getLogger("oxo")
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

    @classmethod
    def teardown(cls, cmd, success, exit_code):
        logger = logging.getLogger("oxo")
        logger.debug("Radio player {} exits with success {} and exit code {}".format(cmd, success, exit_code))


    def update(self):
        global appdata
        self.url = appdata["stations"].get(appdata["station_playing"])
        self.title = appdata.get("station_title")

    @classmethod
    def send_title(cls, bot, job):
        logger = logging.getLogger("oxo")
        global appdata
        t = appdata["station_title"]
        t0 = appdata["station_title_sent"]
        if t != t0:
            if t:
                msg = "▶️ Now playing {}".format(t)
                bot.sendMessage(chat_id=job.context, text=msg)
                if t.find(" - "):
                    cls.send_research(t[:t.find(" - ")], bot, job)
                else:
                    logger.debug("Not compiling research for this title")
            logger.debug("Title changed from '{}' to '{}'".format(t0, t))
            appdata["station_title_sent"] = t
            save()


    @classmethod
    def send_fip_title(cls, bot, job):
        logger = logging.getLogger("oxo")
        global appdata

        logger.debug("Requesting fip current track")
        last = appdata["station_title_sent"]

        fip_stations = {
            "fip": 7,
            "fip du groove": 66,
            "fip du jazz": 65,
            "fip du monde": 69,
            "fip du reggae": 71,
            "fip du rock": 64,
            "fip tout nouveau": 70
        }

        fip_station = fip_stations.get(appdata["station_playing"])
        url = "http://www.fipradio.fr/livemeta/{}".format(fip_station)
        req = requests.get(url)
        data = req.json()

        if "levels" not in data or len(data["levels"]) == 0:
            logger.warning("No data found in fip livemeta:\n\n{}".format(data))
            return None

        position = data["levels"][0]["position"]
        currentItemId = data["levels"][0]['items'][position]
        currentItem = data["steps"][currentItemId]

        current = {
            "artist": currentItem["authors"].title() if "authors" if currentItem else None,
            "performer": currentItem["performers"].title() if "performers" if currentItem else None,
            "title": currentItem["title"].title() if "title" if currentItem else None,
            "album": currentItem["titreAlbum"].title() if "titreAlbum" if currentItem else None,
            "label": currentItem["label"].title() if "label" if currentItem else None,
            "image": currentItem.get("visual")
        }

        def titlestr(t):
            if t:
                return "{} - {} ({})".format(
                    t["artist"], t["title"], t["album"])
            else:
                return None

        if titlestr(current) != last:
            msg = u"▶️ Now playing {artist} – _{title}_ \nfrom {album}".format(
                title=current["title"],
                artist=current["artist"],
                album=current["album"])

            bot.sendMessage(chat_id=job.context,
                text=msg,
                disable_notification=True,
                parse_mode=ParseMode.MARKDOWN)

            appdata["station_title_sent"] = titlestr(current)
            save()

            logger.debug("Title changed from '{}' to '{}'".format(
                last, titlestr(current)))

            cls.send_research(
                current["artist"], bot, job, image_url=current["image"])

    @classmethod
    def send_research(cls, subject, bot, job, image_url=None):
            logger = logging.getLogger("oxo")
            logger.info("Researching '{}'".format(subject))
            bot.sendChatAction(chat_id=job.context, action=ChatAction.TYPING)

            wp_articles = wikipedia.search(subject)
            logger.debug("WP Articles: {}".format(wp_articles))
            if len(wp_articles) > 0:
                wp = wikipedia.page(wp_articles[0])
                logger.debug("Wikipedia: {}".format(wp))
                msg = u"*{}*\n{}\n\n[Wikipedia]({})".format(
                    wp.title, wp.summary, wp.url)

                bot.sendMessage(chat_id=job.context,
                    text=msg,
                    disable_notification=True,
                    disable_web_page_preview=True,
                    parse_mode=ParseMode.MARKDOWN)

                if image_url is None:
                    wp_images = filter(lambda url: url.endswith("jpg"), wp.images)
                    image_url = wp_images[0] if len(wp_images) > 0 else None

                if image_url:
                    logger.debug("Sending photo {}".format(image_url))
                    try:
                        bot.sendPhoto(chat_id=job.context, photo=image_url)
                    except Exception as e:
                        logger.error(e)
            else:
                logger.debug("No wikipedia articles found.")



    def reset_title(self):
        global appdata
        appdata["station_title"] = None

    def stop(self):
        self.logger.debug("Stopping radio player...")
        self.stopped = True
        if self.running:
            try:
                self.player.terminate()
            except OSError as e:
                self.logger.debug(
                    "Error stopping radio player '{}'\n{}".format(self.player, e), exc_info=True)
            self.logger.info("Radio stopped")
        else:
            self.logger.debug("Radio did not play")

    @classmethod
    @log_exceptions
    def telegram_command(cls, bot, update, job_queue, args=list()):
        global appdata

        # Remove the old title data job
        if len(job_queue.jobs()) > 0:
            job = job_queue.jobs()[0]
            logger.debug("Removing {}".format(job))
            job.schedule_removal()

        appdata["station_playing"] = None
        appdata["station_playing_sent"] = None
        save()

        # Radio station selector
        msg = "⏹ Radio turned off.\n\nSelect a station to start."
        kb = inline_keyboard(OrderedDict(
            sorted({k:k for k in appdata["stations"].keys()}.items())))
        bot.sendMessage(chat_id=update.message.chat_id, text=msg,
            reply_markup=kb)

    @classmethod
    @log_exceptions
    def telegram_change_station(cls, bot, update, job_queue):
        # Answer callback from radio station selector
        global appdata
        q = update.callback_query
        station = q.data
        if station in appdata["stations"]:
            logger.info("Requesting station {} (inline)".format(station))
            bot.answerCallbackQuery(q.id,
                text="Tuning to {}...".format(station))

            appdata["station_playing"] = station
            save()

            if station.startswith("fip"):
                logger.info("Starting fip api title crawler...")
                job_function = Radio.send_fip_title
                delay = 7.0
            else:
                job_function = Radio.send_title
                delay = 1.0

            rv = Job(job_function,
                delay, repeat=True, context=q.message.chat_id)
            job_queue.put(rv)

            bot.editMessageText(
                text="📻 Changed station to {}.".format(station),
                chat_id=q.message.chat_id,
                message_id=q.message.message_id)
        else:
            bot.answerCallbackQuery(q.id)
            bot.sendMessage(q.message.chat_id,
                text="I don't know about '{}'".format(station))

    @classmethod
    @log_exceptions
    def telegram_manual(cls, bot, update, args=list()):
        global appdata

        rv = ""
        if len(args) == 1:
            url = args[0]
            logger.debug("Manual play requested: {}".format(url))
            try:
                requests.head(url)
            except requests.exceptions.RequestException:
                logger.error("Requested URL invalid")
                rv = "Can't play this URL"
            else:
                appdata["stations"]["manual"] = url
                appdata["station_playing"] = "manual"
                appdata["station_playing_sent"] = None
                rv = "Switching playback..."
                save()
        else:
            logger.warning("Manual play did not receive URL parameter")
            rv = "Please send a URL with this command to play it."

        bot.sendMessage(update.message.chat_id, text=rv)


class VideoPlayer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.logger = logging.getLogger("oxo")
        self.close_player = False
        self.stopped = False

    @classmethod
    def filepath(self, current_clip):
        return os.path.join(DATA_DIR, "clips", current_clip["filename"])

    def run(self):
        while not self.stopped:
            current_clip = VideoPlayer.get_next()
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

    @property
    def running(self):
        return self.player and self.player is not None and self.player != ''

    def stop(self):
        self.logger.debug("Stopping video player")
        self.stopped = True
        if self.running:
            try:
                self.player.terminate()
            except OSError as e:
                self.logger.debug(
                    "Error stopping video player '{}'\n{}".format(type(self.player), e), exc_info=True)
            self.logger.info("Video player stopped")
        else:
            self.logger.debug("Video player did not play")

    @classmethod
    def interact(cls, line, stdin):
        START_PLAYBACK = "Starting playback..."

        logger = logging.getLogger("oxo")
        if START_PLAYBACK in line:
            nextclip = cls.get_next()
            path = cls.filepath(nextclip)
            cmd = "loadfile {} 1\n".format(path)
            logger.info("Enqueued clip {}".format(nextclip['filename']))
            stdin.put(cmd)

    @classmethod
    def teardown(cls, cmd, success, exit_code):
        logger = logging.getLogger("oxo")
        logger.debug("Video player {} exits with success {} and exit code {}".format(cmd, success, exit_code))

    @classmethod
    def get_next(cls):
        global appdata
        logger = logging.getLogger("oxo")

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

    # radio
    dp.add_handler(CommandHandler("radio", Radio.telegram_command,
        pass_args=True, pass_job_queue=True))
    dp.add_handler(CallbackQueryHandler(Radio.telegram_change_station,
        pass_job_queue=True))

    # manual player
    dp.add_handler(CommandHandler("play", Radio.telegram_manual,
        pass_args=True))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(None, receive))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Start the player
    gif_player = VideoPlayer()
    gif_player.setDaemon(True)
    gif_player.start()

    radio = Radio()
    radio.setDaemon(True)
    radio.start()

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

    gif_player.stop()
    radio.stop()

    global appdata
    appdata["station_playing_sent"] = None
    save()





# Start your bot by saving this notebook as `display-bot.py` and running `$ python display-bot.py`.
#
# Before the main loop is started, database contents are dumped to the cache file, accessible by the frontend script.

# In[11]:

if __name__ == '__main__':
    main()

