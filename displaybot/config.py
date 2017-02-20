# coding: utf-8

"""Configuration."""

import logging
import os
import json

from tinydb import TinyDB, Query

# Setup db

DATA_DIR = os.path.expanduser(os.path.join("~", ".displayBot"))

config_fname = os.path.join(DATA_DIR, "database.json")
db = TinyDB(config_fname)

TELEGRAM_API_TOKEN = "YOUR TOKEN HERE"
with open(os.path.join(DATA_DIR, "TELEGRAM_API_TOKEN")) as f:
    TELEGRAM_API_TOKEN = f.read().strip()

# As anyone will be able to add the bot and add pictures to your display,
# you can filter telegram usernames here
ALLOWED_USERS = []
SUPPORTED_TYPES = ["video/mp4", "video/webm", "image/gif"]
SERVER_URL = "http://localhost:3000"
playnext = None

router_url = "http://192.168.188.1"
router_passfile = os.path.join(DATA_DIR, "ROUTER_LOGIN")

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


def setup():
    Config = Query()
    if(len(db.search(Config.type == "radio")) == 0):
        logger.info("Seting up initial configuration\nFile: {}".format(config_fname))
        db.remove(eids=[e.eid for e in db.all()])

        try:
            with open(os.path.join(DATA_DIR, "data.json")) as f:
                data = json.load(f)
                for clip in data["clips"]:
                    clip["type"] = "clip"
                    logger.info("Adding old clip {}".format(clip))
                    db.insert(clip)
                logger.warning("Please delete data.json")
        except Exception:
            pass

        radio = {
            "type": "radio",
            "station_playing": None,
            "station_playing_sent": None,
            "station_title": None,
            "station_title_sent": None,
        }
        db.insert(radio)

        stations = {
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

        db.insert_multiple([{"type": "station", "name": name, "url": url}
            for name, url in stations.items()])

        db.insert({"type": "incoming", "clip": {}})
    else:
        q = Query()
        logger.info("Database loaded with {} clips and {} stations.".format(
            db.count(q.type == "clip"),
            db.count(q.type == "station")
        ))
