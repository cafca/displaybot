#! /bin/sh
# start.sh

# Start display bot

mplayer http://direct.fipradio.fr/live/fip-midfi.mp3 2>&1 /dev/null &
python DisplayBot.py
