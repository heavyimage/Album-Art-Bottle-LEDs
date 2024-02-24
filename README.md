# Album art bottle LEDS

![Picture of project on desk](docs/hero.jpeg)

I got a [Pimoroni Wireless Plasma Kit](https://shop.pimoroni.com/products/wireless-plasma-kit?variant=40372594704467) and wanted to do something fun with it!  I had the idea to create a custom palette of colors based on what I was listening to!

Album art is often iconic and I thought it'd be cool to get a subtle hint of the colors of my favorite album covers as their songs play!

I realized that last.fm shares album art over its API and as a long time member, that seemed like a great place to start.

By combining code for API access, dominant color extraction, NeoPixel updates and socket networking I was able to throw this together in an evening.

### Materials
* The [Pimoroni Wireless Plasma Kit](https://shop.pimoroni.com/products/wireless-plasma-kit?variant=40372594704467) which acts as a server
* A 'real' computer (client) to generate palettes via API calls
* A last.fm account to pull from
* A last.fm API key
* A CLI tool for checking the currently playing song (eg mpc/mpd)

### Workflow
The server accepts "palette" updates which are a list of `NUM_LED` colors.

The client does most of the heavy lifting by:
* Checking last.fm for the most recently scrobbled track
* Downloading it's cover art
* Extract the `NUM_COLORS` most common colors
* Padding that out `NUM_LEDS` and sending the udpdate to the server.

* I really wish the pico could do all of the image processing but jpeg decoding let alone kmeans is probably a tall order...

### Running the project
* Have a look at the constants at the top of the client / server and see if you wanna make any adjustments
* Install the libraries in `requirements.txt` on your client
* Use thonny or something like it to run the server code on the pi
	* It'll glow green when it's ready for a client connection
* Run the client code (once you add the API key and username) on a 'real' computer

### Good Stuff
* Gentle animation is nice
* The updates are pretty slick
* The palette is updated by the client; if the client does, the palette will keep going forever!
* Pretty pleased by the threading code on the pico for handling animation and network updates :-)
