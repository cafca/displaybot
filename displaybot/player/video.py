class VideoPlayer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.logger = logging.getLogger("oxo")
        self.close_player = False
        self.stopped = False

    @classmethod
    def filepath(self, current_clip):
        return os.path.join(DATA_DIR, "clips", current_clip["filename"])

    def run(self):
        while not self.stopped:
            current_clip = VideoPlayer.get_next()
            self.logger.info("Starting video player with clip {}".format(current_clip["filename"]))
            self.player = mplayer(self.filepath(current_clip),
                "-slave",
                "-fs",
                "-vo", "sdl",
                _bg=True,
                _out=self.interact,
                _done=self.teardown)
            try:
                self.player.wait()
            except ErrorReturnCode_1:
                self.logger.error("Video player returned code 1.")
        self.logger.debug("Exit video player")

    @property
    def running(self):
        return self.player and self.player is not None and self.player != ''

    def stop(self):
        self.logger.debug("Stopping video player")
        self.stopped = True
        if self.running:
            try:
                self.player.terminate()
            except OSError as e:
                self.logger.debug(
                    "Error stopping video player '{}'\n{}".format(type(self.player), e), exc_info=True)
            self.logger.info("Video player stopped")
        else:
            self.logger.debug("Video player did not play")

    @classmethod
    def interact(cls, line, stdin):
        START_PLAYBACK = "Starting playback..."

        logger = logging.getLogger("oxo")
        if START_PLAYBACK in line:
            nextclip = cls.get_next()
            path = cls.filepath(nextclip)
            cmd = "loadfile {} 1\n".format(path)
            logger.info("Enqueued clip {}".format(nextclip['filename']))
            stdin.put(cmd)

    @classmethod
    def teardown(cls, cmd, success, exit_code):
        logger = logging.getLogger("oxo")
        logger.debug("Video player {} exits with success {} and exit code {}".format(cmd, success, exit_code))

    @classmethod
    def get_next(cls):
        global appdata
        logger = logging.getLogger("oxo")

        if "incoming" in appdata.keys() and appdata["incoming"]:
            rv = appdata["incoming"]
            appdata["incoming"] = None
            save()
            logger.info("Enqueuing shortlisted clip {}".format(rv["filename"]))
        elif len(appdata["clips"]) > 0:
            rv = choice(appdata["clips"])
        else:
            rv = None
        return rv
