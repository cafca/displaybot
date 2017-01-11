
# coding: utf-8

# For a long time I wanted to setup a Raspberry Pi in our flatshare's common room. I wanted it to show a looping playlist of GIFs and then maybe extend it to other functionality that is cool to have in a shared flat. This christmas I finally got around to building this thing and it has been so much fun!
# 
# I started developing in Jupyter Notebook and below you can read the results of that. After some time the thing had gotten pretty complex and so I started working in a conventional editor. I still want to post what I did in Jupyter though, because I think it can be pretty interesting as a simple example of a Python Telegram bot.
# 
# In the meantime I have added much more robust video playback, more options for adding animations and also a web radio that allows selecting stations through the chat bot and sends background information as well as images about the music that it is playing to the group. You can see the code for this on the project's Github page.
# 
# But let's get back to the simple version I started with.
# 
# 

# ## Build a Telegram Bot
# 
# For this project I am using a wall-mounted Raspberry Pi 3 model B in a simple transparent case from Amazon with a Kuman 3.5" touch-enabled display. The Pi runs a Raspian Jessie image provided by the display manufacturer. 
# 
# The display bot will be controlled through a chatbot that lives in a Telegram group shared with my flatmates. First, I need to create the Telegram bot. For this, install the Python Telegram Bot library and the peewee database ORM with 

# ## Basic Setup
# 
# First, you want to install `python-telegram-bot` through Python's "package manager" pip.
# 
#     $ pip install python-telegram-bot requests sh ffmpy --upgrade
#     
# Also make sure you have ffmpeg (for conversation of GIFs to MP4s) and mplayer installed.
# 
# And then setup logging. I followed Python-Telegram-Bot's [echobot example](https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/echobot2.py) for writing this.

# In[3]:

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

TELEGRAM_API_TOKEN = "266345127:AAE2PgynHDQKvtYcyMmSxAsdihS6TlviGC8"

# or uncomment these two lines to load the token from disk

# with open(os.path.join(DATA_DIR, "TELEGRAM_API_TOKEN")) as f:
#     TELEGRAM_API_TOKEN = f.read().strip()

SUPPORTED_TYPES = ["video/mp4", "video/webm", "image/gif"]

SERVER_URL = "http://localhost:3000"

playnext = None


# ## Basic commands for a bot
# 
# Define a few command handlers for Telegram. These usually take the two arguments `bot` and
# `update`. Error handlers also receive the raised `TelegramError` object in error.
# 
# The `start` command is sent when the bot is started.

# In[4]:

def start(bot, update):
    update.message.reply_text('Gimme dat gif. Send an .mp4 link!')


# Handle errors, just in case

# In[5]:

def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))


#  These two function will later be registered with the Telegram bot API.

# ## Config persistence
# 
# We need a way to keep track of all the videos we will download and maybe other stuff later on. While what I did is not the most elegant solution, it works for now: We use a global dictionary that loads from and saves to a JSON-serialized file on disk.

# In[9]:

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


# ## Receive clips from Telegram 
# 
# Next ist the receiver for our app. It will look at incoming messages and determine, whether they contain links. Iterating over the link elements contained in the message, we check that the link is valid by sending an HTTP `HEAD` request and checking the HTTP headers to see whether the link points at one of the supported animation file types,
# 
# Special case: if `url` ends in `gif`, the gif is downloaded and converted to a local `mp4` (see code for that below).

# In[6]:

import requests

def receive(bot, update):
    elems = update.message.parse_entities(types=["url"])
    logger.info("Receiving message with {} url entities".format(len(elems)))

    for elem in elems:
        url = update.message.text[elem.offset:(elem.offset + elem.length)]

        # Rewrite gifv links extension to mp4 and see whether this gets us a video
        if url[-4:] == "gifv":
            url = url[:-4] + "mp4"
            logger.info("Rewrite .gifv to {}".format(url))

        try:
            link = requests.head(url)

        except requests.exceptions.RequestException:
            logger.warning("Link not valid")
            update.message.reply_text("Link not valid")

        else:
            if "Content-Type" in link.headers and link.headers["Content-Type"] in SUPPORTED_TYPES:
                if download_clip(url=url, author=update.message.from_user.first_name):
                    update.message.reply_text("Added video to database")
                else:
                    update.message.reply_text("Reposter!")

            else:
                logger.info("Link not supported: {}".format(link.headers))


# ## Download and file clips
# 
# This handler downloads URLs, calls the GIF conversion function and adds new clip's data to the `appdata` dictionary.

# In[7]:

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
        
        with open(fpath, "w+") as f:
            r = requests.get(url, stream=True)
            if r.ok:
                logger.info("Downloading clip to {}...".format(fpath))
                for block in r.iter_content(1024):
                    f.write(block)
                    
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
    


# ## Convert gifs
# 
# In order to convert gifs to the less ressource intensive mp4 format, we can use the ffmpy library, which calls ffmpeg for us outside of python, to make the conversion. 
# 
# This function creates a temporary file and writes the gif to it. Then ffmpeg is called with settings for converting a gif to an mp4 and returns its new file path. 

# In[8]:

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


# ## Videoplayer
# 
# The video player itself consists of two function: The first, `get_next` returns the next video file to play, which is a random one, unless we have just added a new video, in which case it will be this. The second one `play_video` starts `mplayer`, an external video player, with the return value of the first function, waits until it has finished playing and then starts over. Forever!

# In[11]:

from sh import mplayer
from time import sleep
from random import choice

def get_next():
    global appdata
    
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


# ## Main function
# 
# Here, all loose ends tie up: A `Telegram Updater` connects to the Telegram Bot API for us. The three handlers are added - one to give instructions after the bot is first started, one to handle any incoming message and one for errors and finally the endless video-playing loop is started.

# In[12]:

def main():
    # Load configuration and video database
    load()
    
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TELEGRAM_API_TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(None, receive))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()
    
    # Start the player
    play_video()

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    # updater.idle()


# Start your bot by saving this notebook as `display-bot.py` and running `$ python display-bot.py`.
# 
# Before you start the bot, make sure that 
# 
# - there is a folder named `userdata` next to this script 
# - and inside userdata there is a folder `clips`
# - and that you have set your Telegram token at the top of this file
# - and that you have installed all dependencies.
# 
# Yay bot :)

# In[ ]:

# This starts the program
main()

# You can also uncomment the following and comment out the above line to make it runnable from outside the notebook.

# if __name__ == '__main__':
#     main()
    

