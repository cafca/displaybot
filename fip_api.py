# coding: utf-8

import requests
import json
import pytz

from datetime import datetime
from bs4 import BeautifulSoup
from titlecase import titlecase


def __fipit(time):
    url = "http://www.fipradio.fr/fip_titres_diffuses/ajax/7/{}/0".format(time)
    r = requests.post(url, data={"js": True})
    json_result = json.loads(r.text)
    rv = BeautifulSoup(json_result[1]['data'], 'html.parser')
    return rv


def __fiptime(s, dt=datetime.today()):
    f = datetime.strptime(s, "%Hh%M")
    dt = dt.replace(hour=f.hour, minute=f.minute, second=0, microsecond=0)
    return dt


def current_track():
    """Return the currently playing track from fip radio."""

    offset = datetime.utcnow().replace(tzinfo=pytz.timezone('Europe/Paris'))
    res = __fipit(offset.strftime("%s"))
    entries = res.select(".son")
    entry = entries[0]

    time = str(__fiptime(entry.select(".titre_date")[0].text.strip(), dt=offset))
    if len(entry.select(".titre_title")) > 0:
        title = titlecase(entry.select(".titre_title")[0].text)
    else:
        title = None

    if len(entry.select('.titre_artiste')) > 0:
        artist = titlecase(entry.select('.titre_artiste')[0].text[7:].strip())
    else:
        artist = None

    if len(entry.select('.titre_album')) > 0:
        album = titlecase(entry.select('.titre_album')[1].text).strip()
    else:
        album = None

    return {
        "artist": artist,
        "title": title,
        "album": album,
        "time": time
    }

if __name__ == '__main__':
    print "Currently playing\n{}".format(current_track())
