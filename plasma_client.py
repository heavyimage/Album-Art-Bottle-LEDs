#!/usr/bin/python3

import socket
import json
import time
import os
import subprocess
from itertools import cycle, islice
import requests
import numpy as np
import PIL
from PIL import Image
from colr import Colr
from dotenv import load_dotenv
from sklearn.cluster import KMeans, AgglomerativeClustering
import colour as cl
from colour.models import RGB_COLOURSPACE_sRGB
from colorthief import ColorThief
from requests.adapters import HTTPAdapter, Retry

# Store your APP_API_KEY and APP_USER in a .env file :-)
load_dotenv()

# Settings you might want to change
API_KEY = os.getenv("APP_API_KEY")  # a last.fm API_KEY
USER = os.getenv("APP_USER")        # a last.fm username
NUM_LEDS = 50                       # full number of LEDs
NUM_COLORS = 6                      # number of colors to extract
SERVER_IP = "192.168.0.92"          # ip of your pico
SORT_COLORS = True                  # Try enabling/disabling
SONG_CMD = 'mpc current'            # replace based on your setup!
SLEEP_TIME = 1                      # How frequently you check for a new song
COLOR_EXT_METHOD = 3                # Which color extraction method to use

# You shouldn't need to change these...
ENDPOINT = 'https://ws.audioscrobbler.com/2.0/'
USER_AGENT = 'Dataquest'
SIZE = "small"
PORT = 10191 # fear is the mind killer
ILLUMINANT = np.array([0.34570, 0.35850])



# A few utility functions for converting between lab, rgb, and xyz
def rgb_to_xyz(p):
    """ converts from rgb to xyz """
    return cl.RGB_to_XYZ(p, RGB_COLOURSPACE_sRGB, ILLUMINANT, "Bradford")

def xyz_to_rgb(p):
    """ converts from xyz to rgb """
    return cl.XYZ_to_RGB(p, RGB_COLOURSPACE_sRGB, ILLUMINANT, "Bradford")

def rgb_to_lab(p):
    """ converts from rgb to lab """
    return cl.XYZ_to_Lab(rgb_to_xyz(p))

def lab_to_rgb(p):
    """ converts from lab to rgb """
    return xyz_to_rgb(cl.Lab_to_XYZ(p))

def extract_dominant_colors1(image):
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
    return [list(c) for c in colors.astype(int)]

def extract_dominant_colors2(image):
    """ Extract the dominant colors using kmeans in lab space

        based on code from:
        https://tatasz.github.io/dominant_colors/
    """
    pixels = image.getdata()
    pixels = np.float32(pixels)
    kmeans_lab = KMeans(n_clusters=NUM_COLORS, n_init='auto')
    kmeans_lab = kmeans_lab.fit(rgb_to_lab(pixels))
    centroids_lab = kmeans_lab.cluster_centers_
    centroids_lab = lab_to_rgb(centroids_lab)
    return [list(c) for c in centroids_lab.astype(int)]

def extract_dominant_colors3(image):
    """ Extract the dominant colors using AgglomerativeClustering

        based on code from:
        https://tatasz.github.io/dominant_colors/
    """

    # convert to lab
    pixels = image.getdata()
    pixels = np.float32(pixels)
    pixels_lab = rgb_to_lab(pixels)

    # fit clusters
    ag_clusters = AgglomerativeClustering(
            n_clusters=NUM_COLORS, metric='l1', linkage='complete')
    ag_clusters_fit = ag_clusters.fit(rgb_to_lab(pixels))

    # get centroids
    centroids_ag = []
    for i in range(NUM_COLORS):
        center = pixels_lab[ag_clusters_fit.labels_ == i].mean(0)
        centroids_ag.append(list(lab_to_rgb(center).astype(int)))

    return centroids_ag

def extract_dominant_colors4(image):
    """ extract the dominant colors using MMCQ

        based on code from:
        https://github.com/fengsp/color-thief-py
    """

    # Monkey patch the init method so we can set the image data directly...
    def fake_constructor(self):
        self.image = None
    ColorThief.__init__ = fake_constructor
    color_thief = ColorThief()
    color_thief.image = image

    # Generate a palette using this library!
    palette = color_thief.get_palette(color_count=NUM_COLORS, quality=1)
    return palette

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

def print_image_in_term(image):
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

def term_display(payload, img, colors, methods):
    """ A function to handle all the terminal drawing:

        * Clearing the terminal
        * The song / band
        * The visualization of the album
        * The palette that is sent to the server
    """

    # Clear the screen
    os.system("clear")

    # Output the song title / artist
    print("")
    info = "%s -- %s" % (payload['title'], payload['artist'])

    if img == None:
        print(info)
        print("Can't fetch / display %s" % payload['img_url'])
        return

    # center text based on image width
    width, _ = img.size
    print("\t%s" % info.center(width*2, ' '))

    # Display image in terminal for sanity checking!
    print_image_in_term(img)

    # Display all the extracted palettes
    print("\n")
    for key in sorted(methods):
        method = methods[key]
        display_pal(img, method)

def display_pal(img, func):
    """ Helper function to display palettes! """
    pal = func(img)
    pal = list(islice(cycle(pal), NUM_LEDS))
    if SORT_COLORS:
        pal = sorted(pal, key = lambda rgb: sum(rgb))
    pal_str = "".join(
            [str(Colr().rgb(r, g, b, "\u2584")) for r, g, b in pal])
    print("        \t", pal_str)

def generate_palette(session, methods):
    """ The 'main' routine which updates the display """

    # get the artist, title and album art!
    payload = get_info_from_last_scrobble()

    # Download and pythonify the album art
    try:
        img_data = session.get(payload['img_url'], stream=True).raw
        img = Image.open(img_data).convert("RGB")

        # Extract the most common NUM_COLORS colors using COLOR_EXT_METHOD
        method = methods[COLOR_EXT_METHOD]
        colors = [[int(i) for i in c] for c in method(img)] # convert int32

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
    term_display(payload, img, colors, methods)

    return colors

def send_to_server(server, data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(data, server)
    sock.close()

def main():
    """ Entry Point """

    # get the address of server
    server = socket.getaddrinfo(SERVER_IP, PORT)[0][-1]

    last_song = None

    # define all the extraction methods
    methods = {
            1: extract_dominant_colors1,
            2: extract_dominant_colors2,
            3: extract_dominant_colors3,
            4: extract_dominant_colors4,
    }

    # Setup the session
    session = requests.Session()
    retries = Retry(total=5,
                    backoff_factor=0.1,
                    status_forcelist=[ 500, 502, 503, 504 ])

    session.mount('http://', HTTPAdapter(max_retries=retries))

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
            colors = generate_palette(session, methods)

            # convert to json...
            data_string = json.dumps(colors).encode()

            # ...and send to the server!
            #
            # by putting this in the while loop it'll create the socket
            # on demand which means it'll work if the client started
            # after the server!
            send_to_server(server, data_string)

            # update the last song!
            last_song = song

        # Wait before running SONG_CMD again
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main()
