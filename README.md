# DisplayBot

This script runs on a Raspberry Pi and provides a fullscreen infinite gif loop
as well as a webradio. Both can be accessed and controlled through a Telegram bot.

# Installation

First, install `mplayer`, `omxplayer` and `ffmpeg` through a package manager. Then clone 
displaybot to `~/displaybot` and make a Python 3 virtual environment for it.

Then

    $ pip install -r requirements.txt

Finally

    $ ./scripts/setup.sh

This script creates folders for the clips, asks you for a Telegram bot API token
(which you can get by adding @BotFather in Telegram) and optionally installs
a systemd unit file to start the script automatically on system start.

# License

MIT License. See LICENSE file.
