#! /bin/sh
# start.sh

# Start display bot

NUM_PROCESSES=$(ps aux | grep python | wc -l);

if [ $NUM_PROCESSES -eq 1 ];
then
    export DISPLAY=:0;
    nohup python ~/displaybot/displaybot/displaybot.py &
fi
