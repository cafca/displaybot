# coding: utf-8

"""Configuration."""

import logging
import os
import json

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

# ## Config persistence
#
# We use a dictionary to store all application data and serialize it in a JSON file.

# In[7]:

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
