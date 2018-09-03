# DisplayBot

This script runs on a Raspberry Pi and provides a fullscreen infinite gif loop
as well as a webradio. Both can be accessed and controlled through a Telegram bot.

# Installation

First, install `mplayer` and `ffmpeg` through a package manager. Then clone 
displaybot to `~/displaybot` and make a virtual environment for it.

Then

    $ pip install -r requirements.txt

Finally

    $ ./scripts/setup.sh

# Router controller

The bot can control a FritzBox through its web interface, which requires
additional dependencies.

* Install `node` and `npm`
* Install `PhantomJS`, either with

    $ npm install -g phantomjs-prebuilt

  Or on a Raspberry 2 or 3 with [these instructions](https://github.com/fg2it/phantomjs-on-raspberry/tree/master/rpi-2-3/wheezy-jessie/v2.1.1).
* Place your router password in `~/displaybot/ROUTER_LOGIN`.

# License

MIT License. See LICENSE file.
