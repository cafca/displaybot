# coding: utf-8

"""Configuration."""
import logging
import requests

from config import router_url, router_passfile
from conversion import download_clip

logger = logging.getLogger('oxo')

# ## Basic commands for a bot
#
# Define a few command handlers for Telegram. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.
#


def start(bot, update):
    """The start command is sent when the bot is started."""
    update.message.reply_text('Gimme dat gif. Send an .mp4 link!')


def error(bot, update, error):
    """Handle errors, just in case."""
    logger.warn('Update "%s" caused error "%s"' % (update, error))


def reboot(bot, update):
    """Let router controller start reboot sequence."""
    try:
        from router import RouterController
    except ModuleNotFoundError:
        logger.warning("Please install Selenium to access router")
    else:
        logger.debug("Received reboot command from telegram")
        bot.sendMessage(update.message.chat_id, text='Preparing to reboot FritzBox...')
        router = RouterController(router_url, router_passfile)

        logger.debug("Starting reboot command")
        bot.sendMessage(update.message.chat_id, text='Rebooting now. See ya 💋')
        router.reboot()


def receive(bot, update):
    """Receive clips from Telegram.

    Next ist the receiver for our app. It will look at incoming messages and determine, whether they contain a link and then wether that link points at an mp4 video. This will then be added to the database for display.

    There are special cases:
    - if `url` ends in `gifv`, that is rewritten to `mp4`
    - if `url` ends in `gif`, the gif is downloaded and converted to a local `mp4` (see code for that below)
    """
    doc = update.message.document
    try:
        if doc:
            logger.debug("Processing attachment")
            file_data = bot.getFile(doc.file_id)
            logger.debug("Downloading {}".format(file_data["file_path"]))
            download_clip(file_data["file_path"], bot, update, doc["mime_type"],
                fname=doc["file_name"])
    except Exception as e:
        logger.error(e, exc_info=True)

    # Add all URLs in the message
    elems = update.message.parse_entities(types=["url"])
    for elem in elems:
        logger.info("Processing message with {} url entities".format(len(elems)))
        url = update.message.text[elem.offset:(elem.offset + elem.length)]

        # Rewrite gifv links extension and try that
        if url[-4:] == "gifv":
            url = url[:-4] + "mp4"
            logger.debug("Rewrite .gifv to {}".format(url))

        try:
            link = requests.head(url, allow_redirects=True)
            logger.debug(link)

        except requests.exceptions.RequestException:
            logger.warning("Link not valid")
            update.message.reply_text("Link not valid")

        else:
            if "Content-Type" in link.headers:
                download_clip(
                    url=url,
                    bot=bot,
                    update=update,
                    content_type=link.headers["Content-Type"])
            else:
                logger.info("Link not supported: {}".format(link.headers))
