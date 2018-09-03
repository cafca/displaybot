# coding: utf-8

"""Download and file clips."""

import logging
import hashlib
import os
import datetime
import ffmpy
import requests

from tinydb import Query
from config import db, SUPPORTED_TYPES, DATA_DIR

logger = logging.getLogger('oxo')


def download_clip(url, bot, update, content_type, fname=None):
    """Download clips."""
    if not fname:
        fname = hashlib.sha1(url.encode(encoding='UTF-8')).hexdigest()

    author = update.message.from_user.first_name
    if content_type not in SUPPORTED_TYPES:
        logger.info("Link not supported: \n{}\nType{}".format(
            url, content_type))
        bot.sendMessage(chat_id=update.message.chat_id, text="👾 Link not supported. Only mp4, webm and gif links.")
    elif duplicate(url):
        logger.info("Detected duplicate {}".format(url))
        update.message.reply_text("👾 Reposter!")
    else:
        fpath = os.path.join(DATA_DIR, "clips", fname)
        logger.debug("Downloading clip to {}...".format(fpath))

        with open(fpath, "wb+") as f:
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
            "type": "clip",
            "url": url,
            "author": author,
            "filename": fname,
            "created": datetime.datetime.now().isoformat(),
            "incoming": True
        }

        db.insert(clip)
        bot.sendMessage(chat_id=update.message.chat_id, text="👾 Added video to database.")
        logger.info("Saved new clip {} from {}".format(fname, author))


def duplicate(url):
    """Boolean, true if given filenam exists in clips."""
    Duplicate = Query()
    return len(db.search(Duplicate.url == url)) > 0

#
# Converting gifs
#


def convert_gif(fpath):
    """Convert gif at fpath using ffmpeg."""
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
