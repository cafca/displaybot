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
            "artist": currentItem["authors"].title() if "authors" in currentItem else None,
            "performer": currentItem["performers"].title() if "performers" in currentItem else None,
            "title": currentItem["title"].title() if "title" in currentItem else None,
            "album": currentItem["titreAlbum"].title() if "titreAlbum" in currentItem else None,
            "label": currentItem["label"].title() if "label" in currentItem else None,
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
