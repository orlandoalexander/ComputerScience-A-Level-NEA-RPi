import paho.mqtt.client as mqtt
import wave
import pickle
from os.path import join
import os
import requests
from gtts import gTTS
import time
import urllib.request as url
import json
import threading

serverBaseURL = "http://nea-env.eba-6tgviyyc.eu-west-2.elasticbeanstalk.com/"
path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

while True:
    if os.path.isfile(join(path,'data.json')) == False:  # cannot pair doorbell with mobile app unless 'data.json' file has been created, as 'data.json' stores doorbell's unique Smart Bell ID and user's account ID required for mobile app to pair with doorbell
        time.sleep(5)
    else:
        with open(join(path,'data.json'), 'r') as jsonFile:
            time.sleep(0.5) # resolves issue with reading file immediately after it is written to (json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0))
            data = json.load(jsonFile)
        if 'accountID' in data:
            break


def playAudio(client, userData, msg):
    # output recorded audio message through doorbell's speaker
    messageID = msg.payload.decode() # decode payload sent via MQTT from mobile app (i.e. messageID)
    downloadData = {"bucketName": "nea-audio-messages",
                                     "s3File": messageID}  # creates the dictionary which stores the metadata required to download the pkl file of the personalised audio message from AWS S3
    response = requests.post(serverBaseURL + "/downloadS3", downloadData) # send request to REST API path to download pickled audio message bytes from AWS S3 and return them
    audioData = pickle.loads(response.content) # unpickles the bytes string 
    messageFile = wave.open(join(path,"audioMessage.wav"), "wb")
    messageFile.setnchannels(1) # audio stream module is single channel
    messageFile.setsampwidth(2) # 2 bytes per audio sample (sample width)
    messageFile.setframerate(8000) # 8000 samples per second
    messageFile.writeframes(b''.join(audioData)) # write audio bytes to .wav file
    messageFile.close()    
    os.system("cvlc --play-and-exit {}".format(join(path,'audioMessage.wav'))) # play audio message directly through system using command line tool 'vlc' - ://quit used to quit the player after audio played
  
def playText(client, userData, msg):
    # output typed (text-based) audio message through doorbell's speaker
    messageText = msg.payload.decode()
    TtS(messageText) # convert message text into audio file
    os.system("cvlc --play-and-exit {}".format(join(path,'audioMessage.wav'))) # play audio message directly through system using command line tool 'cvlc'
     
def TtS(text):
    language = "en"
    TtS_obj = gTTS(text=text, lang=language, slow=False) # create text-to-speech object
    TtS_obj.save(join(path,"audioMessage.wav")) # save text to speech object as .wav file
    return
    
def checkAccountID(currentID, ):
    while True:
        with open(join(path,'data.json')) as jsonFile:
            time.sleep(0.5)
            data = json.load(jsonFile)
        newID = str(data['accountID'])
        if newID != currentID: # if account ID has been changed
            print('Alteration')
            # reconfigure topics that the Raspberry Pi is subscribed as the doorbell's ID has been updated:
            client.unsubscribe(f"message/audio/{currentID}")
            client.unsubscribe(f"message/text/{currentID}")
            client.subscribe(f"message/audio/{newID}")
            client.message_callback_add(f"message/audio/{newID}", playAudio)
            client.subscribe(f"message/text/{newID}")
            client.message_callback_add(f"message/text/{newID}", playText)
            currentID = newID # set new values for accountID and currentID for future comparisons
        time.sleep(5)
        
def on_connect(client, userdata, flags, rc):
    with open(join(path, 'data.json'), 'r') as jsonFile:
        data = json.load(jsonFile)
        accountID = data['accountID'] # load account ID
    if rc == 0: # if connection is successful
        # subscribe to necessary topics
        client.subscribe(f"message/audio/{accountID}")
        client.message_callback_add(f"message/audio/{accountID}", playAudio)
        client.subscribe(f"message/text/{accountID}")
        client.message_callback_add(f"message/text/{accountID}", playText)
        checkThread = threading.Thread(target=checkAccountID, args = (accountID,)) # thread created to check whether any changes to the account ID doorbell is paired with
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
    
        
print('Client setup')
client = mqtt.Client()
client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
client.on_connect = on_connect # creates callback for successful connection with broker
client.connect("hairdresser.cloudmqtt.com", 18973) # parameters for broker web address and port number

client.loop_forever() # indefinitely checks for messages on topics that client is subscribed to



