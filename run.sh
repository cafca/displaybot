killall python
display=:0 &
cd frontend/build/
python -m SimpleHTTPServer &
cd -
python DisplayBot.py &
# epiphany -a --profile ~/.config http://localhost:8000/
chromium http://localhost:8000/
xte 'sleep 10' 'key F11'&
