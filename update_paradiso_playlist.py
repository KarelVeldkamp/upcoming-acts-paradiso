import time
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import calendar
import datetime
import re
import difflib
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from difflib import SequenceMatcher
import time

os.environ["SPOTIPY_REDIRECT_URI"] = "https://google.com/"
SCOPE = ["user-library-read", "playlist-modify-public"]
PLAYLIST_ID = '0rALt9jdkB15XIQvTncxiy'

auth = spotipy.oauth2.SpotifyOAuth(scope=['playlist-modify-public', 'playlist-modify-private'])
spotify = spotipy.Spotify(auth_manager=auth)

# spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(scope=scope))

SCROLL_PAUSE_TIME = .5
N_DAYS = 14
month_dict = {
    'jan': 1,
    'feb': 2,
    'mrt': 3,
    'apr': 4,
    'mei': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'sep': 9,
    'okt': 10,
    'nov': 11,
    'dec': 12
}


def string_similarity(a, b):
    """
    :param a: a string
    :param b: another string
    :return: percentage match between the two strings
    """
    return SequenceMatcher(None, a, b).ratio()


def scrape_events():
    """
    :return: a list of event titles scraped from paradiso.nl
    """
    option = webdriver.ChromeOptions()
    option.add_argument('headless')
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=option)
    driver.get('https://www.paradiso.nl/nl/')

    now = datetime.datetime.now()

    scroll_height = 1000
    # Get scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")
    # scroll down up to the minimum number of days
    while True:
        # Scroll down to bottom
        driver.execute_script(f"window.scrollTo(0, {scroll_height})")
        scroll_height += 1000

        # Wait to load page
        time.sleep(SCROLL_PAUSE_TIME)

        # get final string date
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        date_string = soup.find_all('div', class_='event-list__category col-xs-12 col-lg-2 ng-binding ng-scope')[
            -1].text
        # last 3 letters are the month
        month_number = month_dict[date_string.lower()[-3:]]
        # the numbers are the day
        day_number = int(re.findall('[0-9]+', date_string)[0])
        date = datetime.datetime(year=now.year, month=month_number, day=day_number)

        if (date - now).days > N_DAYS:
            events = soup.find_all('div', class_='event-list__items')
            return events


def extract_titles(events):
    """
    :param events: a list of html onjects concering events from paradiso.nl,
    :return: the tiltles of the events
    """
    # loop though list of events
    titles = []
    for event in events:
        # continue to next iteration if event is canceled or postponed
        message = event.find('span', class_='event-list__item-status ng-binding ng-scope')
        if message:
            if message.text.lower() in ['afgelast', 'uitgesteld']:
                continue
        # get event title
        event_title = event.find('span', 'event-list__item-title ng-binding ng-scope').text
        titles.append(event_title)
    return titles


def clean_title(title):
    """
    :param title: a title tpo an event
    :return: a cleaned version of the title
    """
    title = title.lower()
    if '+' in title:
        title = title.split('+')[0]
    return title


def search_artists(names):
    """

    :param names: list of artist names
    :return: list of artist ids
    """
    ids = []
    for name in names:
        results = spotify.search(q='artist:' + name, type='artist')
        items = results['artists']['items']
        if len(items):
            spotify_name = items[0]['name'].lower()

            if string_similarity(name, spotify_name) > .9:
                ids.append(items[0]['id'])

    return ids


# get a list of artist ids based on paradiso website
events = scrape_events()
titles = extract_titles(events)
artists = [clean_title(t) for t in titles]
artist_ids = search_artists(artists)

# get the ids of the track currently in the playlist
current_tracks = spotify.playlist(PLAYLIST_ID)['tracks']['items']
current_ids = {track['track']['id'] for track in current_tracks}

# get ids from the top n songs of each artist (in the netherlands)
new_track_ids = set()
for artist_id in artist_ids:
    top_tracks = spotify.artist_top_tracks(artist_id, 'NL')['tracks']
    ids = [track['id'] for track in top_tracks]
    new_track_ids.update(ids[:5])

# find out which songs to add and which to remove:
to_remove = list(current_ids - new_track_ids)
to_add = list(new_track_ids - current_ids)

# remove items
n_iter = len(to_remove) // 100 + 1
for i in range(n_iter):
    first = i * 100
    last = min(i * 100 + 100, len(to_remove))
    spotify.playlist_remove_all_occurrences_of_items(PLAYLIST_ID,
                                                     to_remove[first:last])
    time.sleep(3)

# add items
n_iter = len(to_add) // 100 + 1
for i in range(n_iter):
    first = i * 100
    last = min(i * 100 + 100, len(to_add))
    spotify.playlist_add_items(PLAYLIST_ID,
                               track_ids[first:last])
    time.sleep(3)
