
# coding: utf-8

# The Displaybot should show a window on a small wall-mounted display that plays gifs and videos from a telegram group or tunes to a web radio station.
#
# First, I need to create a Telegram bot. For this, install the Python Telegram Bot library and the peewee database ORM with
#
#     $ pip install peewee python-telegram-bot sqlite3 --upgrade
#
# and then setup logging. I follow the [echobot example](https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/echobot2.py).
#
# Also, setup your Telegram api token below. Get a token by talking to [this bot](https://telegram.me/botfather) on Telegram.

# In[ ]:

import logging
import requests
import json

from requests.exceptions import RequestException
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# TELEGRAM_API_TOKEN = "YOUR TOKEN HERE"
TELEGRAM_API_TOKEN = "266345127:AAE2PgynHDQKvtYcyMmSxAsdihS6TlviGC8"

# This will be the database of video clips
DATABASE_FILENAME = "memory.db"

# This cache file is used to feed the webserver with data
CACHE_LOCATION = "frontend/public/data.json"

# As anyone will be able to add the bot and add pictures to your display,
# you can filter telegram usernames here
ALLOWED_USERS = []

SERVER_URL = "http://localhost:3000"


# Define a few command handlers. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.

# The start command is sent when the bot is started.

# In[ ]:

def start(bot, update):
    update.message.reply_text('Gimme dat gif. Send an .mp4 link!')


# Handle errors, just in case

# In[ ]:

def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))


# Next ist the receiver for our app. It will look at incoming messages and determine, whether they contain a link and then wether that link points at an mp4 video. This will then be added to the database for display.

# In[ ]:

def receive(bot, update):
    elems = update.message.parse_entities(types=["url"])
    logger.info("Incoming message with {} entities".format(len(elems)))

    for elem in elems:
        url = update.message.text[elem.offset:(elem.offset + elem.length)]

        # Rewrite gifv links extension and try that
        if url[-4:] == "gifv":
            url = url[:-4] + "mp4"
            logger.info("Rewrite .gifv to {}".format(url))

        # Convert gif files using ffmpeg
        if url[-3:] == "gif":
            url = convert_gif(url)

        try:
            link = requests.head(url)

        except RequestException:
            logger.warning("Link not valid")
            update.message.reply_text("Link not valid")

        else:
            if "Content-Type" in link.headers and link.headers["Content-Type"] in ["video/mp4", "video/webm"]:
                if add_url(url=url, author=update.message.from_user.first_name):
                    update.message.reply_text("Added video to database")
                else:
                    update.message.reply_text("Reposter!")

            else:
                logger.info("Link not supported: {}".format(link.headers))

import tempfile, ffmpy

def convert_gif(url):
    rv = False
    temp = tempfile.NamedTemporaryFile()
    r = requests.get(url, stream=True)
    if r.ok:
        logger.info("Downloading gif to {}...".format(temp.name))
        for block in r.iter_content(1024):
            temp.write(block)

        logger.info("Converting...")
        fname = url.split("/")[-1]
        ff = ffmpy.FFmpeg(
            inputs={temp.name: None},
            outputs={'frontend/public/videos/{}.mp4'.format(fname): '-movflags faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2"'}
        )
        ff.run()
        rv = "{}/videos/{}.mp4".format(SERVER_URL, fname)
        logger.info(rv)
    return rv


# Now setup a local database, handled by the Peewee ORM, which allows us to simply handle Python objects for db access instead of writing SQL queries.

# In[ ]:

from peewee import IntegerField, CharField, DateTimeField, BaseModel, Model, OperationalError
from playhouse.sqlite_ext import SqliteExtDatabase
import datetime

db = SqliteExtDatabase(DATABASE_FILENAME)

class BaseModel(Model):
    class Meta:
        database = db

class Video(BaseModel):
    url = CharField(unique=True)
    created = DateTimeField(default=datetime.datetime.now)
    author = CharField()

    def __repr__(self):
        return "<Video by '{}' at '{}' />".format(self.author, self.url)

    def serialize(self):
        rv = {
            "url": self.url,
            "author": self.author,
            "created": self.created.isoformat()
        }
        return rv


# Connect to the database and create tables for the models
db.connect()
try:
    db.create_tables([Video])
except OperationalError:
    logger.info("Tables already exist")


# Then write a handler to store received videos in the database and computes a cached JSON response on disk with all current videos

# In[ ]:

def add_url(url, author):
    try:
        video = Video.create(url=url, author=author)
    except IntegrityError:
        logger.info("Video already exists {}".format(url))
        video = None
    else:
        logger.info("Stored new Video {}".format(video))
        refresh_cache()
        return video

def refresh_cache():
    videos = Video.select().order_by(Video.created.desc())
    rv = {
        "videos": {v.id: v.serialize() for v in videos},
        "config": None
    }
    with open(CACHE_LOCATION, "w") as f:
        json.dump(rv, f)
    logger.info("Cache refreshed. Total {} videos".format(len(rv["videos"])))


# Add the main  function, where the handler functions above are registered with the Telegram Bot API and continous polling for new messages as well as the flask server are started.

# In[ ]:

def main():
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

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


# Start your bot by saving this notebook as `display-bot.py` and running `$ python display-bot.py`

# In[ ]:

if __name__ == '__main__':
    refresh_cache()
    main()

