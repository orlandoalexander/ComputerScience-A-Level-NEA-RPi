#!/usr/bin/python3
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import time
import main_pi
import threading 
import paho.mqtt.client as mqtt
import urllib.request as url


GPIO.setwarnings(False) # Ignore warning for now
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)

def runThread():
    main_pi.run()

def run():
    while True: # Run forever
        if GPIO.input(10) == GPIO.HIGH and threading.active_count() == 1:
                print("Button pressed")
                thread_run = threading.Thread(target =runThread)
                thread_run.start()

def on_connect(client, userdata, flags, rc):
    if rc == 0: # if connection is successful
        client.publish("button", "ready")
        run()
    else:
        # attempts to reconnect
        client.on_connect = on_connect
        client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
        client.connect("hairdresser.cloudmqtt.com", 18973)

while True:
    try:
        url.urlopen('http://google.com')
        break
    except:
        time.sleep(5)

client = mqtt.Client()
client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
client.on_connect = on_connect # creates callback for successful connection with broker
client.connect("hairdresser.cloudmqtt.com", 18973) # parameters for broker web address and port number

client.loop_forever()
