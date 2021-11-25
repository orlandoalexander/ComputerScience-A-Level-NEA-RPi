#! /usr/bin/env python
from subprocess import call
call(['espeak “Welcome to the world of Robots” 2>/dev/null'], shell=True)
import paho.mqtt.client as mqtt
import wave
import pickle
from os.path import join
import requests
from pydub import AudioSegment
from pydub.playback import play
from gtts import gTTS

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
    messageFile = wave.open(join(path,"audioMessage.wav", "wb"))
    messageFile.setnchannels(1)  # change to 1 for audio stream module
    messageFile.setsampwidth(2)
    messageFile.setframerate(8000)  # change to 8000 for audio stream module
    messageFile.writeframes(b''.join(audioData))
    messageFile.close()

    sound = AudioSegment.from_wav(join(path,'audioMessage.wav'))
    play(sound) 
    
def playText(client, userData, msg):
    messageText = msg.payload.decode()
    TtS(messageText)
    sound = AudioSegment.from_mp3(join(path,'audioMessage.mp3')) # only works when saved as mp3, not wav
    play(sound) 
    
    
def TtS(text):
    language = "en"
    TtS_obj = gTTS(text=text, lang=language, slow=False)
    TtS_obj.save(join(path,"audioMessage.mp3"))
    return
    
def on_connect(client, userdata, flags, rc):
    if rc == 0: # if connection is successful
        client.subscribe(f"message/audio/{accountID}")
        client.message_callback_add(f"message/audio/{accountID}", playAudio)
        client.subscribe(f"message/text/{accountID}")
        client.message_callback_add(f"message/text/{accountID}", playText)
    else:
        # attempts to reconnect
        client.on_connect = on_connect
        client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
        client.connect("hairdresser.cloudmqtt.com", 18973)

client = mqtt.Client()
client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
client.on_connect = on_connect # creates callback for successful connection with broker
client.connect("hairdresser.cloudmqtt.com", 18973) # parameters for broker web address and port number

client.loop_forever()
