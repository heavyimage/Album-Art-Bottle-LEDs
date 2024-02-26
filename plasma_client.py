#!/usr/bin/python3

import PIL
from PIL import Image
import requests
import socket
import json
import time
import os
from colr import Colr
import numpy as np
from sklearn.cluster import KMeans
from itertools import cycle, islice
import subprocess
from dotenv import load_dotenv

# Store your APP_API_KEY and APP_USER in a .env file :-)
load_dotenv()

# Settings you might want to change
API_KEY = os.getenv("APP_API_KEY")  # a last.fm API_KEY
USER = os.getenv("APP_USER")        # a last.fm username
NUM_LEDS = 50                       # full number of LEDs
NUM_COLORS = 5                      # number of colors to extract
SERVER_IP = "192.168.0.92"          # ip of your pico
SORT_COLORS = True                  # Try enabling/disabling
SONG_CMD = 'mpc current'            # replace based on your setup!
SLEEP_TIME = 2                      # How frequently you check for a new song

# You shouldn't need to change these...
ENDPOINT = 'https://ws.audioscrobbler.com/2.0/'
USER_AGENT = 'Dataquest'
SIZE = "small"
PORT = 10191 # fear is the mind killer

def extract_dominant_colors(image):
    """ Extract the dominant colors from an image

        Based on code from here:
        https://pythonintopractice.com/extract-dominant-colors-image-python/
    """

    # TODO: this algorithm might be improved?
    pixels = image.getdata()
    pixels = np.float32(pixels)
    kmeans = KMeans(n_clusters=NUM_COLORS, n_init='auto')
    kmeans.fit(pixels)
    colors = kmeans.cluster_centers_
    return colors.astype(int)

def get_info_from_last_scrobble():
    """ Get the most recent track from a user's last.fm profile

        Based on
        https://www.dataquest.io/blog/last-fm-api-python/
    """

    # Make the request
    headers = {'user-agent': USER_AGENT}

    payload = {
        'method': 'user.getrecenttracks',
        'api_key': API_KEY,
        'format': 'json',
        'user': USER,
        'limit': 1,
    }

    # Ping the server
    response = requests.get(ENDPOINT, headers=headers, params=payload)

    # Pull out the last track's info
    last_track = response.json()['recenttracks']['track'][0]

    # Get the title / artist
    title = last_track['name']
    artist = last_track['artist']['#text']

    # sort out images
    images = last_track['image']
    img_url = [d['#text'] for d in images if d['size'] == SIZE][0]

    # build payload
    payload = {}
    payload['title'] = title
    payload['artist'] = artist
    payload['img_url'] = img_url

    return payload

def print_imgage_in_term(image):
    """ show a preview of the album in the terminal

        based on:
        https://dev.to/pranavbaburaj/print-images-to-console-using-python-23k6
    """

    pixel_values = image.getdata()

    width, height = image.size
    for index, character in enumerate(pixel_values):
        #convert chararacter to colorchar
        if not isinstance(character, (tuple, list)):
            continue
        r, g, b = character
        colorchar = str(Colr().rgb(r, g, b, "\u2584"))

        if index % width == 0:
            print("\n\t", end="")

        # duplicate colorchar so it produces a squarer image
        print("".join([colorchar]*2), end="")
    print("")

def term_display(payload, img, colors):
    """ A function to handle all the terminal drawing:

        * Clearing the terminal
        * The song / band
        * The visualization of the album
        * The palette that is sent to the server
    """

    # Clear
    os.system("clear")

    # Output the song title / artist
    print("")
    info = "%s -- %s" % (payload['title'], payload['artist'])

    if img == None:
        print(info)
        print("Can't fetch / display %s" % payload['img_url'])

    else:
        # center text based on image width
        width, _ = img.size
        print("\t%s" % info.center(width*2, ' '))

        # Display image in terminal for sanity checking!
        print_imgage_in_term(img)

    # Display the color palette
    print("\n")
    pal_str = "".join(
            [str(Colr().rgb(r, g, b, "\u2584")) for r, g, b in colors])
    print("        \t", pal_str)
    print("\n")

def generate_palette():
    """ The 'main' routine which updates the display """

    # get the artist, title and album art!
    payload = get_info_from_last_scrobble()

    # Download and pythonify the album art
    try:
        img_data = requests.get(payload['img_url'], stream=True).raw
        img = Image.open(img_data).convert("RGB")

        # Extract the most common NUM_COLORS colors!
        colors = [[int(i) for i in c] for c in extract_dominant_colors(img)]

    except requests.exceptions.MissingSchema:
        img = None
        colors = [[0, 0, 255] for _ in range(NUM_COLORS)]

    except PIL.UnidentifiedImageError:
        img = None
        colors = [[128, 128, 128] for _ in range(NUM_COLORS)]

    # Exapand that list to the number of LEDS
    colors = list(islice(cycle(colors), NUM_LEDS))

    # Sort the list so it's a bit less chaotic?
    if SORT_COLORS:
        colors = sorted(colors, key = lambda rgb: sum(rgb))

    # Show everything in the terminal
    term_display(payload, img, colors)

    return colors

def main():
    """ Entry Point """

    # Create socket and get address of server
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = socket.getaddrinfo(SERVER_IP, PORT)[0][-1]

    last_song = None

    # Forever...
    while True:

        # Get the current song
        result = subprocess.run(
                SONG_CMD.split(" "),
                stdout=subprocess.PIPE)
        song = result.stdout

        # Don't bother hitting the API unless the song has changed
        if song != last_song:
            # Sleep for 3 seconds so the update makes it to last.fm
            time.sleep(3)
            print("Updating...")

            # Get the palette
            colors = generate_palette()

            # convert to json + send to the server!
            data_string = json.dumps(colors)
            sock.sendto(data_string.encode(), server)

            # update the last song!
            last_song = song

        # Wait before running SONG_CMD again
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main()
