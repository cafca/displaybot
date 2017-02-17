# coding: utf-8

"""Radio player."""

import wikipedia
import logging
import requests

from time import sleep
from collections import OrderedDict
from telegram.ext import Job
from sh import mplayer

from telegram import ParseMode, ChatAction
from config import load, save
from player import Player, log_exceptions, inline_keyboard

global appdata
appdata = load()


class Radio(Player):
    """Radio class."""

    def __init__(self):
        """Init as Player."""
        super(Radio, self).__init__()
        self.url = None

    @log_exceptions
    def run(self):
        """Thread target."""
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

    #
    # Player state
    #

    def update(self):
        """Update player from global appdata."""
        global appdata
        self.url = appdata["stations"].get(appdata["station_playing"])
        self.title = appdata.get("station_title")

    def reset_title(self):
        """Set title to None."""
        global appdata
        appdata["station_title"] = None

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
                    global appdata
                    appdata["station_title"] = title

    #
    # Telegram interaction
    #

    @classmethod
    def send_title(cls, bot, job):
        """Send current title to chat."""
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
        """Send info about currently playing song on fip through the fip web api."""
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

            appdata["station_title_sent"] = titlestr(current)
            save()

            logger.debug("Title changed from '{}' to '{}'".format(
                last, titlestr(current)))

            cls.send_research(
                current["artist"], bot, job, image_url=current["image"])

    @classmethod
    def send_research(cls, subject, bot, job, image_url=None):
        """Send wikipedia summary and image or supplied image to chat."""
        logger = logging.getLogger("oxo")
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
            sorted({k: k for k in appdata["stations"].keys()}.items())))
        bot.sendMessage(chat_id=update.message.chat_id, text=msg,
            reply_markup=kb)

    @classmethod
    @log_exceptions
    def telegram_change_station(cls, bot, update, job_queue):
        """Answer callback from radio station selector."""
        global appdata
        q = update.callback_query
        station = q.data
        logger = logging.getLogger('oxo')
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
