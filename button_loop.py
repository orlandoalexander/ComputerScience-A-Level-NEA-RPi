#!/usr/bin/python3
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import time
import main_pi
import threading 
import paho.mqtt.client as mqtt
import urllib.request as url
import os
from os.path import join
import json

path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

GPIO.setwarnings(False) # ignore warnings
GPIO.setmode(GPIO.BOARD) # use physical pin numbering
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # set pin 10 to be an input pin and set initial value to be pulled low (off)

def runThread():
    main_pi.run()

def detect_buttonPressed():
    # detect when visitor presses doorbell 'ring' button
    while True:
        if GPIO.input(10) == GPIO.HIGH and os.path.isfile(join(path, 'data.json')) == True: # if doorbell 'ring' button is pressed and 'data.json' file exists (indicates doorbell has been set up)
            with open(join(path,'data.json')) as jsonFile:
                data = json.load(jsonFile)
                training = data['training'] # store training status
            if (threading.active_count() == 1 or training == 'True') and 'accountID' in data: # to avoid concurrent camera access issues, doorbell can be rung in new thread if there is currently no doorbell thread OR when the doorbell thread is in training state, AND the doorbell is paired with a user's account ID
                thread_run = threading.Thread(target=runThread)
                thread_run.start()

while True: # block program until doorbell is connected to internet
    try:
        url.urlopen('http://google.com') # attempts to open 'google.com'
        detect_buttonPressed()
        break
    except: # if no internet connection is established yet, then wait 5 secs
        time.sleep(5)

