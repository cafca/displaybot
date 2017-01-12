#!/usr/bin/env python
# coding: utf-8

"""The Displaybot should show a window on a small wall-mounted display that plays gifs and videos from a telegram group or tunes to a web radio station."""

from config import save
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler

from player.radio import Radio
from player.video import Video


def main():
    """Main loop for the bot."""
    load()

    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TELEGRAM_API_TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))

    # radio
    dp.add_handler(CommandHandler("radio", Radio.telegram_command,
        pass_args=True, pass_job_queue=True))
    dp.add_handler(CallbackQueryHandler(Radio.telegram_change_station,
        pass_job_queue=True))

    # manual player
    dp.add_handler(CommandHandler("play", Radio.telegram_manual,
        pass_args=True))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(None, receive))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Start the player
    gif_player = Video()
    gif_player.setDaemon(True)
    # gif_player.start()

    radio = Radio()
    radio.setDaemon(True)
    radio.start()

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

    # gif_player.stop()
    radio.stop()

    global appdata
    appdata["station_playing_sent"] = None
    save()

if __name__ == '__main__':
    main()
