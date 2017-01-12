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
