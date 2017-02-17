# coding: utf-8

"""Download and file clips."""

import logging
import os
import datetime
import ffmpy
from config import save

logger = logging.getLogger('oxo')


def download_clip(url, bot, update, content_type, fname=None):
    """Download clip and save to appdata."""
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

        global appdata
        appdata["clips"].append(clip)
        appdata["incoming"] = clip
        save()

        bot.sendMessage(chat_id=update.message.chat_id, text="👾 Added video to database.")
        logger.info("Saved new clip {} from {}".format(fname, author))


def duplicate(filename):
    """Boolean, true if given filenam exists in clips."""
    return len([c for c in appdata["clips"]
        if "filename" in c and c["filename"] == filename]) > 0

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
