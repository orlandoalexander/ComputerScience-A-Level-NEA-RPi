import paho.mqtt.client as mqtt
import wave
import pickle
from os.path import join
import os
import requests
from pydub import AudioSegment
from gtts import gTTS
import time
import urllib.request as url



accountID = "MzVmXPjQXsIBouwmHM2ISwsJx0SB4UTncAVjnvnKcmI="
serverBaseURL = "http://nea-env.eba-6tgviyyc.eu-west-2.elasticbeanstalk.com/"
path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

def playAudio(client, userData, msg):
    messageID = msg.payload.decode()
    print(messageID)
    downloadData = {"bucketName": "nea-audio-messages",
                                     "s3File": messageID}  # creates the dictionary which stores the metadata required to download the pkl file of the personalised audio message from AWS S3 using the 'boto3' module on the AWS elastic beanstalk environment
    response = requests.post(serverBaseURL + "/downloadS3", downloadData)
    audioData = pickle.loads(response.content) # unpickles the bytes string 
    messageFile = wave.open(join(path,"audioMessage.wav"), "wb")
    messageFile.setnchannels(1)  # change to 1 for audio stream module
    messageFile.setsampwidth(2)
    messageFile.setframerate(8000)  # change to 8000 for audio stream module
    messageFile.writeframes(b''.join(audioData))
    messageFile.close()    
    os.system("omxplayer {}".format(join(path,'audioMessage.wav')))
  
def playText(client, userData, msg):
    messageText = msg.payload.decode()
    TtS(messageText)
    os.system("omxplayer {}".format(join(path,'audioMessage.wav')))
     
def TtS(text):
    language = "en"
    TtS_obj = gTTS(text=text, lang=language, slow=False)
    TtS_obj.save(join(path,"audioMessage.wav"))
    return
    
def on_connect(client, userdata, flags, rc):
    if rc == 0: # if connection is successful
        client.publish("audio", "ready")
        client.subscribe(f"message/audio/{accountID}")
        client.message_callback_add(f"message/audio/{accountID}", playAudio)
        client.subscribe(f"message/text/{accountID}")
        client.message_callback_add(f"message/text/{accountID}", playText)
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
