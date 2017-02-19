# coding: utf-8

"""Radio player."""

import wikipedia
import logging
import requests

from time import sleep
from collections import OrderedDict
from telegram.ext import Job
from sh import mplayer
from tinydb import Query
from telegram import ParseMode, ChatAction

from config import db
from player import Player, log_exceptions, inline_keyboard


class Radio(Player):
    """Radio class."""

    def __init__(self):
        """Init as Player."""
        super(Radio, self).__init__()

    @classmethod
    def state(cls):
        """Return a db query and radio state."""
        q = Query()
        q_config = db.search(q.type == "radio")
        return (q, q_config[0]) if len(q_config) > 0 else (q, {})

    def stop(self):
        """Reset sent title state before stopping thread."""
        q = Query()
        db.update({"station_playing_sent": None}, q.type == "radio")
        super(Radio, self).stop()

    @log_exceptions
    def run(self):
        """Thread target."""
        self.stopped = False
        current_url = None
        current_title = None

        q, state = Radio.state()
        db.update({"station_title": None}, q.type == "radio")

        while not self.stopped:
            # Restart mplayer whenever station changes
            q, state = Radio.state()
            title = state.get("station_title")

            q_station = db.search(q.name == state.get("station_playing"))
            url = q_station[0]["url"] if len(q_station) > 0 else None

            if current_url != url:
                self.logger.debug("Station changed")
                if self.running:
                    self.stop()
                    self.player = None

                if url is not None:
                    self.logger.info("Playing {}".format(url))
                    self.player = mplayer(url,
                        _bg=True,
                        _out=self.interact,
                        _ok_code=[0, 1])
                current_url = url

            elif current_title != title:
                current_title = title
                self.logger.info("Title is {}".format(current_title))

            sleep(1)

    #
    # Player state
    #

    @classmethod
    def interact(cls, line, stdin):
        """Handle text output of mplayer, line by line.

        The data contains ICY data / track metadata.
        """
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
                    q = Query()
                    db.update({"station_title": title}, q.type == "radio")

    #
    # Telegram interaction
    #

    @classmethod
    def send_title(cls, bot, job):
        """Send current title to chat."""
        logger = logging.getLogger("oxo")

        q, state = Radio.state()
        t = state.get("station_title")
        t0 = state.get("station_title_sent")

        if t != t0:
            if t:
                msg = "▶️ Now playing {}".format(t)
                bot.sendMessage(chat_id=job.context, text=msg)
                if t.find(" - "):
                    cls.send_research(t[:t.find(" - ")], bot, job)
                else:
                    logger.debug("Not compiling research for this title")
            logger.debug("Title changed from '{}' to '{}'".format(t0, t))

            db.update({"station_title_sent": t}, q.type == "radio")

    @classmethod
    def send_fip_title(cls, bot, job):
        """Send info about currently playing song on fip through the fip web api."""
        logger = logging.getLogger("oxo")
        logger.debug("Requesting fip current track")

        q, state = Radio.state()
        last = state["station_title_sent"]
        station_playing = state["station_playing"]

        fip_stations = {
            "fip": 7,
            "fip du groove": 66,
            "fip du jazz": 65,
            "fip du monde": 69,
            "fip du reggae": 71,
            "fip du rock": 64,
            "fip tout nouveau": 70
        }

        fip_station = fip_stations.get(station_playing)
        url = "http://www.fipradio.fr/livemeta/{}".format(fip_station)
        req = requests.get(url)
        data = req.json()

        if "levels" not in data or len(data["levels"]) == 0:
            logger.warning("No data found in fip livemeta:\n\n{}".format(data))
            return None

        # fip, y u no flat data
        position = data["levels"][0]["position"]
        item_id = data["levels"][0]['items'][position]
        item = data["steps"][item_id]

        current = {
            "artist": item["authors"].title() if "authors" in item else None,
            "performer": item["performers"].title() if "performers" in item else None,
            "title": item["title"].title() if "title" in item else None,
            "album": item["titreAlbum"].title() if "titreAlbum" in item else None,
            "label": item["label"].title() if "label" in item else None,
            "image": item.get("visual")
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

            db.update({"station_title_sent": titlestr(current)}, q.type == "radio")

            logger.debug("Title changed from '{}' to '{}'".format(
                last, titlestr(current)))

            cls.send_research(
                current["artist"], bot, job, image_url=current["image"])

    @classmethod
    def send_research(cls, subject, bot, job, image_url=None):
        """Send wikipedia summary and image or supplied image to chat."""
        logger = logging.getLogger("oxo")

        if subject is None:
            return

        logger.info("Researching '{}'".format(subject))
        bot.sendChatAction(chat_id=job.context, action=ChatAction.TYPING)

        wp_articles = wikipedia.search(subject)
        logger.debug("WP Articles: {}".format(wp_articles))
        if len(wp_articles) > 0:
            for i in xrange(len(wp_articles)):
                try:
                    wp = wikipedia.page(wp_articles[0])
                    break
                except wikipedia.DisambiguationError:
                    logger.warning("Wikipedia: DisambiguationError for {}".format(wp_articles[0]))
            else:
                logger.warning("Wikipedia articles exhausted")
                return

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

    @classmethod
    @log_exceptions
    def telegram_command(cls, bot, update, job_queue, args=list()):
        """Handle telegram /radio command."""
        logger = logging.getLogger('oxo')

        # Remove the old title data job
        if len(job_queue.jobs()) > 0:
            job = job_queue.jobs()[0]
            logger.debug("Removing {}".format(job))
            job.schedule_removal()

        q, state = Radio.state()
        db.update({
            "station_playing": None,
            "station_playing_sent": None
        }, q.type == "radio")

        # Radio station selector
        q_station_names = db.search(q.type == "station")
        station_dict = {s["name"]: s["name"] for s in q_station_names}
        msg = "⏹ Radio turned off.\n\nSelect a station to start."
        kb = inline_keyboard(OrderedDict(sorted(station_dict.items())))
        bot.sendMessage(chat_id=update.message.chat_id, text=msg,
            reply_markup=kb)

    @classmethod
    @log_exceptions
    def telegram_change_station(cls, bot, update, job_queue):
        """Answer callback from radio station selector."""
        q = update.callback_query
        station = q.data
        logger = logging.getLogger('oxo')

        db_q = Query()
        q_station = db.search(db_q.name == station)
        if len(q_station) > 0:
            logger.info("Requesting station {} (inline)".format(station))
            bot.answerCallbackQuery(q.id,
                text="Tuning to {}...".format(station))

            db.update({"station_playing": station}, db_q.type == "radio")

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
