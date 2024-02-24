import WIFI_CONFIG
from network_manager import NetworkManager
from plasma import plasma_stick
import plasma
import json
import socket
import time
import _thread
import uasyncio

# Adjust these based on your hardware / preferences
PORT = 10191
NUM_LEDS = 50
ANIMATION_TIME = 0.5

# Initialize WS2812 / NeoPixel™ LEDs
# Normally would prefer to do this in main but need it at this scope for 
#   the status_handler
led_strip = plasma.WS2812(
        NUM_LEDS, 0, 0, plasma_stick.DAT, color_order=plasma.COLOR_ORDER_RGB)
led_strip.start()

# Define some global variables
lock = None
palette = [[0, 255, 0] for _ in range(NUM_LEDS)]

def status_handler(mode, status, ip):
    """ reports wifi connection status; taken from weather example """
    
    print(mode, status, ip)
    print('Connecting to wifi...')
    # flash while connecting
    for i in range(NUM_LEDS):
        led_strip.set_rgb(i, 255, 255, 255)
        time.sleep(0.02)
    for i in range(NUM_LEDS):
        led_strip.set_rgb(i, 0, 0, 0)
    if status is not None:
        if status:
            print('Connection successful!')
        else:
            print('Connection failed!')
            # light up red if connection fails
            for i in range(NUM_LEDS):
                led_strip.set_rgb(i, 255, 0, 0)

def net_thread():
    """ Update the palette with updates from a client

        based on:
        https://RandomNerdTutorials.com/raspberry-pi-pico-web-server-micropython/
    """
    global lock
    
    # Set up socket and start listening
    addr = socket.getaddrinfo('0.0.0.0', PORT)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)

    print('Listening on', addr)
    while True:
        # Receive and parse the request
        request = s.recvfrom(2048)
        
        # try to acquire lock - wait if in use
        lock.acquire()
        
        # Update the Palette!
        data = json.loads(request[0])
        global palette
        palette = data

        # release lock
        lock.release()


def display_thread():
    """ Handle the LED updates """
    global lock
    
    counter = 0
    while True:
        
        # try to acquire lock - wait if in use
        lock.acquire()
        
        # Update the LEDs
        global palette
        for i, (r, g, b) in enumerate(palette):
            led_strip.set_rgb((i + counter) % NUM_LEDS, r, g, b)
            
        # release lock
        lock.release()
        
        time.sleep(ANIMATION_TIME)
        counter += 1

def main():
    """ Entry Point """

    # set up wifi
    network_manager = NetworkManager(
            WIFI_CONFIG.COUNTRY, status_handler=status_handler)
    uasyncio.get_event_loop().run_until_complete(
            network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK))

    # create a global lock
    global lock
    lock = _thread.allocate_lock()

    # Startup the threads!
    # https://bytesnbits.co.uk/multi-thread-coding-on-the-raspberry-pi-pico-in-micropython/
    second_thread = _thread.start_new_thread(net_thread, ())
    display_thread()

if __name__ == "__main__":
    main()
