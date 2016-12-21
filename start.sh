#! /bin/sh
# start.sh

# Start display bot

mplayer http://direct.fipradio.fr/live/fip-midfi.mp3 &
python DisplayBot.py
