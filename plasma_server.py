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
ANIMATION_DELAY = 1
TRANSITION_DELAY = 0.005

# Initialize WS2812 / NeoPixel™ LEDs
# Normally would prefer to do this in main but need it at this scope for 
#   the status_handler
led_strip = plasma.WS2812(
        NUM_LEDS, 0, 0, plasma_stick.DAT, color_order=plasma.COLOR_ORDER_RGB)
led_strip.start()

# Define some global variables
lock = None
current_palette = [[0, 255, 0] for _ in range(NUM_LEDS)]
new_palette = None

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
        
        data = json.loads(request[0])
        
        # try to acquire lock - wait if in use
        lock.acquire()
        
        # Update the Palette!
        global new_palette
        new_palette = data

        # release lock
        lock.release()


def display_thread():
    """ Handle the LED updates """
    global lock
    global new_palette
    global current_palette
    
    counter = 0
    while True:
        
        # try to acquire lock - wait if in use
        lock.acquire()

        # If there hasn't been a recent update:
        if new_palette == None:
            # release lock
            lock.release()
            for i, (r, g, b) in enumerate(current_palette):
                led_strip.set_rgb((i + counter) % NUM_LEDS, r, g, b)
                
        # If there has we enter the "transition" cycle
        else:
            # Make a copy of the palette and release the lock!
            new_pal = new_palette.copy()
            lock.release()
            
            # calculate the maximum number of steps we'll need -- the max distance between a value in the old and new palettes
            max_steps = max([abs(current_palette[i][c]-new_pal[i][c]) for c in range(3) for i in range(NUM_LEDS)])
        
            # for each step...
            for step in range(max_steps):
                
                # for each LED
                for i in range(NUM_LEDS):
                    
                    # For each color in that LED...
                    for c in range(3):
                        # move us towards the new value!
                        if current_palette[i][c] > new_pal[i][c]:
                            current_palette[i][c] -= 1
                        elif current_palette[i][c] < new_pal[i][c]:
                            current_palette[i][c] += 1
                    # Display the LED's new value
                    led_strip.set_rgb((i + counter) % NUM_LEDS, current_palette[i][0], current_palette[i][1], current_palette[i][2])
                    
                # ater the step is done, sleep a bit so we can see the transition
                time.sleep(TRANSITION_DELAY)
                counter += 1
                
                
            # set new_palette to None!
            lock.acquire()
            new_palette = None
            lock.release()

        
        time.sleep(ANIMATION_DELAY)
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
