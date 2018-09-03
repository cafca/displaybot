mkdir ~/displaybot
mkdir ~/displaybot/clips

echo Please enter the Telegram API token for your displaybot: 

read API_TOKEN

echo $API_TOKEN > ~/displaybot/TELEGRAM_API_TOKEN

read -n1 -p "Install displaybot as a service (assumes /home/pi/displaybot root)? [y/n]" SERVICE_ANSWER

case SERVICE_ANSWER in
    y|Y) sudo cp displaybot.service /lib/systemd/system/; sudo systemctl daemon-reload; sudo systemctl enable displaybot;
    n|N) echo "Skipping unit file install"

echo "Run `python3 /home/pi/displaybot/displaybot/displaybot.py` to start"
