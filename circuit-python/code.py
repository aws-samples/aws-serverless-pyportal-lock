# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import json
import time
from collections import namedtuple
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
import adafruit_touchscreen
import audioio
import board
import busio
import digitalio
import displayio
import neopixel
from adafruit_bitmap_font import bitmap_font
from adafruit_button import Button
from adafruit_display_shapes.rect import Rect
from adafruit_display_text.label import Label
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager

### WiFi ###

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = digitalio.DigitalInOut(board.ESP_CS)
esp32_ready = digitalio.DigitalInOut(board.ESP_BUSY)
esp32_reset = digitalio.DigitalInOut(board.ESP_RESET)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

# Verify nina-fw version >= 1.4.0
assert (
    int(bytes(esp.firmware_version).decode("utf-8")[2]) >= 4
), "Please update nina-fw to >=1.4.0."

status_light = neopixel.NeoPixel(
    board.NEOPIXEL, 1, brightness=0.2
)
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

# Enable the speaker
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_enable.value = True

a = audioio.AudioOut(board.SPEAKER)
data = open("beep.wav", "rb")
wav = audioio.WaveFile(data)

lock_relay = digitalio.DigitalInOut(board.D4)
lock_relay.direction = digitalio.Direction.OUTPUT

Coords = namedtuple("Point", "x y")

ts = adafruit_touchscreen.Touchscreen(board.TOUCH_YU, board.TOUCH_YD,
                                      board.TOUCH_XL, board.TOUCH_XR,
                                      calibration=((5200, 59000), (5800, 57000)),
                                      size=(240, 320))

# Settings
BUTTON_WIDTH = 60
BUTTON_HEIGHT = 30
BUTTON_MARGIN = 8
MAX_DIGITS = 29
BLACK = 0x0
ORANGE = 0xff9902
LIGHT_ORANGE = 0xffb547
WHITE = 0xFFFFFF
GRAY = 0x888888
LABEL_OFFSET = 290

# Make the display context
numpad_group = displayio.Group(max_size=25)
board.DISPLAY.show(numpad_group)
board.DISPLAY.rotation=90

# Make a background color fill
color_bitmap = displayio.Bitmap(240, 320, 1)
color_palette = displayio.Palette(1)
color_palette[0] = WHITE
bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
numpad_group.append(bg_sprite)

# Load the font
font = bitmap_font.load_font("/fonts/Arial-12.bdf")
buttons = []

# Some button functions
def button_grid(row, col):
    return Coords(BUTTON_MARGIN * (row + 1) + BUTTON_WIDTH * row + 15,
                  BUTTON_MARGIN * (col + 1) + BUTTON_HEIGHT * col + 60)

def add_button(row, col, label, width=1, color=ORANGE, text_color=WHITE, border_color=ORANGE, fill=LIGHT_ORANGE):
    pos = button_grid(row, col)
    new_button = Button(x=pos.x, y=pos.y,
                        width=BUTTON_WIDTH * width + BUTTON_MARGIN * (width - 1),
                        height=BUTTON_HEIGHT, outline_color=border_color, label=label, label_font=font,
                        label_color=text_color, selected_fill=fill, fill_color=color, style=Button.RECT)
    buttons.append(new_button)
    return new_button

def find_button(label):
    result = None
    for _, btn in enumerate(buttons):
        if btn.label == label:
            result = btn
    return result

border = Rect(20, 28, 200, 35, fill=WHITE, outline=BLACK, stroke=2)
number_label = Label(font, text="Getting status..", color=BLACK, max_glyphs=MAX_DIGITS)
number_label.x = 25
number_label.y = 45

send_button = add_button(0, 4, "Lock")
clear_button = add_button(2, 4, "del")
add_button(0, 0, "7")
add_button(1, 0, "8")
add_button(2, 0, "9")
add_button(0, 1, "4")
add_button(1, 1, "5")
add_button(2, 1, "6")
add_button(0, 2, "1")
add_button(1, 2, "2")
add_button(2, 2, "3")
add_button(1, 3, "0")

numpad_group.append(border)
numpad_group.append(number_label)
for b in buttons:
    numpad_group.append(b.group)

state = { "code": "", "locked": True }

def playBeep():
    print("playing")
    a.play(wav)
    while a.playing:
        pass
    print("stopped")

def sendCode(num):
    endpoint = secrets['base-api'] + "/lock"
    headers = {"x-api-key": secrets['x-api-key']}
    data = { "number": num }
    response = wifi.post(endpoint, json=data, headers=headers, timeout=30)
    data = response.json()
    print("Code received: ", data)
    response.close()
    return data

def updateState(newState):
    endpoint = secrets['base-api'] + "/state"
    headers = {"x-api-key": secrets['x-api-key']}
    response = wifi.post(endpoint, json=newState, headers=headers, timeout=30)
    data = response.json()
    print("Updated state to: ", data)
    response.close()
    return data

def lock():
    number_label.text = "Enter unlock code"
    time.sleep(1)
    btn = find_button("Lock")
    btn.selected = True
    btn.label = "Unlock"
    lock_relay.value = False
    playBeep()

def unlock():
    print("Unlocked!")
    number_label.text = "Enter Phone# to Lock"
    time.sleep(1)
    btn = find_button("Unlock")
    if btn is not None:
        btn.selected = True
        btn.label = "Lock"
    lock_relay.value = True
    playBeep()
    updateState({"locked": False, "code": ""})

def handleState(newState):
    print(state)
    state['code'] = newState['code']
    state['locked'] = newState['locked']
    print(state)
    if state['locked'] == True:
        lock()
    if state['locked'] == False:
        unlock()

def getState():
    endpoint = secrets['base-api'] + "/state"
    headers = {"x-api-key": secrets['x-api-key']}
    response = wifi.get(endpoint, headers=headers, timeout=30)
    handleState(response.json())
    response.close()

def validate(num):
    if len(num) == 10:
        number_label.text = "Sending code.."
        time.sleep(1)
        return True
    else:
        playBeep()
        number_label.text = "Try again.."
        time.sleep(1)
        number_label.text = "Enter Phone# to Lock"
        time.sleep(1)

def command(action, num):
    if action == "unlock":
        if num == state["code"]:
            unlock()
        else:
            number_label.text = "Wrong code!"
            playBeep()
    if action == "lock":
        if validate(num) == True:
            data = sendCode(num)
            handleState(data)

print("Connecting to WiFi...")
wifi.connect()
print("Connected!")
getState()

number = ""
while True:
    point = ts.touch_point
    if point is not None:
        # Button Down Events
        for _, b in enumerate(buttons):
            if b.contains(point):
                if b.label == "del":
                    number = number[:-1]
                    number_label.text = number
                if b.label == "Lock" and b.selected == False:
                    b.selected = True
                    command("lock", number)
                    number = ""
                if b.label == "Unlock" and b.selected == False:
                    command("unlock", number)
                    number = ""
                if b.label != "del" and b.label != "Lock" and b.label != "Unlock":
                    number += b.label
                    b.selected = True
                    print(number)
                    number_label.text = number
            else:
                b.selected = False
    time.sleep(0.2)
