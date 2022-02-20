import paho.mqtt.client as mqtt
import urllib.request as url
from os.path import join
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import os
import json
import time
import threading
import requests

path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

serverBaseURL = "http://nea-env.eba-6tgviyyc.eu-west-2.elasticbeanstalk.com/"  # base URL to access AWS elastic beanstalk environment

GPIO.setwarnings(False) # Ignore warning for now
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setup(37, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 37 to be an input pin and set initial value to be pulled low (off)

while True:
    if os.path.isfile(join(path, 'data.json')) == False: # cannot pair doorbell with mobile app unless 'data.json' file has been created, as 'data.json' stores doorbell's unique Smart Bell ID and user's account ID required for mobile app to pair with doorbell
        time.sleep(5)
    else:
        break

def on_message(client, userData, msg):
    # callback function called when pairing request sent via MQTT by mobile app
    time_start = time.time()
    while True:
        if GPIO.input(37) == GPIO.HIGH: # if user presses 'Pair' button on doorbell
            print("Button pressed")
            connectDoorbell(msg) # pair the doorbell with the user's account
            break
        elif time.time() - time_start > 60: # pairing request expires 60 seconds after it is initiated by user through mobile app
            break
        
        
def connectDoorbell(msg):
    # pair doorbell with user's account
    with open(join(path,'data.json')) as jsonFile:
        data = json.load(jsonFile)
    SmartBellID = str(data['id'])
    accountID = msg.payload.decode() # decode payload sent by user from mobile app (i.e. users' account ID)
    data['accountID'] = accountID # store the user's account ID in the 'data.json' file as now paired with that account
    with open(join(path,'data.json'), 'w') as jsonFile:
        json.dump(data, jsonFile)
    data_accountID = {"accountID": accountID, 'id': SmartBellID}
    paired = requests.post(serverBaseURL + "/update_SmartBellIDs", data_accountID).text # store pairing details in MySQL table
    client.publish(f'pair/{accountID}', paired)

    
def checkID(currentID):
    # check whether doorbell's unique SmartBell ID has been updated
    while True:
        with open(join(path,'data.json')) as jsonFile:
            data = json.load(jsonFile)
        newID = str(data['id'])
        if newID != currentID: # if the doorbell's SmartBell ID has been changed
            print('Alteration')
            client.unsubscribe(f"id/{currentID}") # unsubscribe from the topic for the old SmartBell ID
            client.subscribe(f"id/{newID}") # subscribe to the new topic for the updated SmartBell ID
            client.message_callback_add(f"id/{newID}", on_message)
            currentID = newID
        time.sleep(5)
        

def on_connect(client, userdata, flags, rc):
    # called when connection to MQTT broker established
    if rc == 0: # if connection is successful
        with open(join(path,'data.json')) as jsonFile:
            data = json.load(jsonFile)
        SmartBellID = str(data['id'])
        client.publish(f"connected/{SmartBellID}")
        client.subscribe(f"id/{SmartBellID}") # mobile app publishes to topic when it wishes to pair a user's account with the doorbell
        client.message_callback_add(f"id/{SmartBellID}", on_message) # add callback when message received to the topic to indicate pairing request
        checkThread = threading.Thread(target=checkID, args = (SmartBellID,)) # thread created to persistently verify whether the doorbell's unique SmartBell ID has been altered, and act accordingly if it has been changed
        checkThread.start()
    else:
        # attempts to reconnect
        client.on_connect = on_connect
        client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
        client.connect("hairdresser.cloudmqtt.com", 18973)

# check if Raspberry Pi is connected to the internet before running program
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