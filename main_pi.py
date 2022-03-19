#!/usr/bin/python3
import cv2 as cv
from picamera.array import PiRGBArray
from picamera import PiCamera
import time
import json
import boto3
from os.path import join
import os
import threading
import paho.mqtt.client as mqtt
import requests
from cryptography.fernet import Fernet
import face_recognition
import pickle

path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

serverBaseURL = "http://nea-env.eba-6tgviyyc.eu-west-2.elasticbeanstalk.com/"  # base URL to access AWS elastic beanstalk environment

haarCascade = cv.CascadeClassifier(join(path,"haar_face_alt2.xml")) # reads in the xml haar cascade file

windowSize_mobile = (640, 1136) # mobile phone screen size in pixels

class buttonPressed():
    def __init__(self):
        with open(join(path,'data.json'), 'r') as jsonFile: # ensures up-to-date value for accountID is used
            time.sleep(0.5) # avoids concurrent access errors for 'data.json' file
            self.data = json.load(jsonFile) # load json file as json object
            self.accountID = str(self.data['accountID']) # retrieve user's account ID stored under key 'accountID' in json object 'data'
        self.visitID = self.create_visitID() # create unique visit ID for the visit
        self.publish_message_ring() # transmit MQTT message to the mobile app to notify of visit
        if self.accountID not in self.data: # if data for account not stored (i.e. doorbell not paired with a user account)
            self.data.update({self.accountID:{"faceIDs":[]}}) # updates json file to create empty parameter to store names of known visitors associated with a specific accountID
            with open(join(path,'data.json'),'w') as jsonFile:
                json.dump(self.data, jsonFile) # write json object data to json file 'data.json' so stored permanently on Raspberry Pi

    def captureImage(self):
        # called when doorbell 'ring' button pressed
        self.camera = PiCamera() # create instance of Raspberry Pi camera
        self.rawCapture = PiRGBArray(self.camera) # using PiRGBArray increases efficiency when accessing camera stream 
        self.trainingImages = []
        self.faceDetected = False
        time.sleep(0.155) # delay to allow camera to warm up
        attempts = 0
        while attempts < 2: # make up to two attempts to capture high quality image of visitor
            faceRGBImages = []
            self.rawCapture.truncate(0) # clear any data from the camera stream
            self.camera.capture(self.rawCapture, format="bgr") # captures camera stream in 'bgr' format (opencv array requires this)
            self.faceBGR = cv.flip(self.rawCapture.array,0) # flip image in vertical (0) axis, as camera module is upside down when attached to Raspberry Pi
            self.faceGray = cv.cvtColor(self.faceBGR, cv.COLOR_BGR2GRAY) # change visitor image to grayscale for OpenCV operations
            self.faceRGB = cv.cvtColor(self.faceBGR, cv.COLOR_BGR2RGB) # change visitor image to rgb for face-recognition library operations
            if attempts == 0: # first image of visitor captured
                self.uploadImage = threading.Thread(target=self.formatImage, args=(self.faceBGR,), daemon=False)
                self.uploadImage.start()  # starts the thread which will run in pseudo-parallel to the rest of the program to format image for display in mobile app GUI
            faceRGBImages.append(self.faceRGB)
            # check if face exists as much quicker than doing facial recognition (so can check whether need to capture another image):
            faceDetected = haarCascade.detectMultiScale(self.faceGray, scaleFactor=1.01, minNeighbors=6)  # returns rectangular coordinates of face bounding box
            blurFactor = cv.Laplacian(self.faceGray, cv.CV_64F).var() # calculate bluriness of visitor image
            num_faceDetected = len(faceDetected) # number of faces detected in image
            if num_faceDetected >= 1 and blurFactor >= 25: # if at least 1 face has been detected and image isn't blurry, image considered suitable
                self.trainingImages.extend(faceRGBImages) # save visitor images in RGB format to train the facial recognition algorithm
                self.faceDetected = True
                break # suitable image captured so do not attempt capturing images again
            else:
                attempts +=1
        if self.faceDetected == True: # if face detected in visitor image
            self.facialRecognition() # run facial recognition algorithm
        else: # if no face detected in visitor image
            self.faceID = "NO_FACE"
            self.update_visitorLog() # update SQL database to store visit details
            self.camera.close() # terminate camera instance
            quit()
            
            
    def recognise(self, faceRGB):
        # facial recognition algorithm
        fileName = join(path,"trainingData") # load the face encodings and labels for trained image data set
        if not os.path.isfile(fileName): # training image data set doesn't exist yet
            return 'Unknown', False # face not recognised
        data = pickle.loads(open(fileName, "rb").read()) # reconstruct dictionary object 'data' from character stream stored in fileName file
        encodings = face_recognition.face_encodings(faceRGB) # create face encodings for visitor image (test image)
        for encoding in encodings: # iterate through face encodings in the visitor image as there may be multiple faces in the visitor image
            matches = face_recognition.compare_faces(data["encodings"], encoding) # compare encoding of face in visitor image with encodings in trained data set
            # matches contain array with boolean values True and False for each face encoding in 'data'
            if True in matches: # if there is at least one match for the test image in the training image data set
                matchedIndexes = [index for (index, match) in enumerate(matches) if match] # store indexes of training set face encodings which match a face encoding in visitor image
                labelCount = {}
                for index in matchedIndexes: # loop over the matched indexes and store a count for each face in training data set which matches the test image
                    label = data["labels"][index] # get the label associated with the face encoding at index 'index'
                    labelCount[label] = labelCount.get(label,0) + 1 # increment counter (value) for label (key) of face encoding stored at 'index', indicating that test image has match with this label
                label = max(labelCount, key=labelCount.get) # return key with greatest value (i.e. label of face in training image data set with greatest number of matches)
                matchCount = labelCount[label] # number of matches for label assigned to visitor image
                actualCount = 0 # stores total number of face encodings with same label as label assigned to visitor image
                for i in data['labels']: # iterate through each label in trained data set
                    if i == label: # label in trained data set is same as label assigned to visitor image
                        actualCount +=1
                if matchCount/actualCount > 0.5: # if visitor image matches more than 50% of training data set images with same label
                    return label, True
                else:
                    return 'Unknown', False
            else:
                return 'Unknown', False
        return 'Unknown', False


    def facialRecognition(self):
        # driver method for facial recognition algorithm
        self.faceIDs = []
        with open(join(path,'data.json')) as jsonFile:
            self.data = json.load(jsonFile) # load json object from 'data.json' file
            self.faceIDs = [faceID for faceID in self.data[self.accountID]["faceIDs"]] # store all face IDs associated with user's account in array

        self.label, self.faceRecognised = self.recognise(self.faceRGB) # execute facial recognition algorithm to retrieve label for captured visitor image

        if self.faceRecognised == True: # if face recognised in visitor image
            self.faceID = self.faceIDs[self.label] # retrieve face ID for face label detected in visitor image
        else: # if no face recognised in visitor image
            self.faceID = self.create_faceID() # create new face ID for face in visitor image

        self.update_visitorLog() # update SQL database to store visit details
        
        if self.faceID not in self.faceIDs: # if visitor image is new face
            self.faceIDs.append(self.faceID)
            self.label = self.faceIDs.index(self.faceID) # create new label which corresponds to index of new face ID in face IDs array
            self.update_knownFaces() # store details for new face
            
        with open(join(path,'data.json'), 'w') as jsonFile:
            json.dump(self.data, jsonFile)
        self.thread_updateTraining = threading.Thread(target=self.updateTraining, args=(), daemon=False) # create thread to train facial recognition algorithm
        self.thread_updateTraining.start()  # starts the thread which will run in pseudo-parallel to the rest of the program to train facial recognition algorithm
           
    def train(self, faceRGB, label): # train facial recognition algorithm
        boxes = face_recognition.face_locations(faceRGB,model='hog') # bounding box around face location in image
        encodings = face_recognition.face_encodings(faceRGB, boxes) # compute the facial encodings for the face
        for encoding in encodings: # loop through each face encoding in image
            self.encodings.append(encoding)
            self.labels.append(label)
        return self.encodings, self.labels
        
    
    def updateTraining(self):
        # driver method for training algorithm
        self.encodings = [] # store face encodings for trained data set
        self.labels = [] # store corresponding face labels for trained data set
        attempts = 0

        while attempts < 2: # make up to two attempts to capture high quality image of visitor
            self.rawCapture.truncate(0) # clear any data from the camera stream
            self.camera.capture(self.rawCapture, format="bgr") # captures camera stream in 'bgr' format (opencv array requires this)
            self.faceBGR = cv.flip(self.rawCapture.array,0) # flip image in vertical (0) axis, as camera module is upside down when attached to Raspberry Pi
            self.faceGray = cv.cvtColor(self.faceBGR, cv.COLOR_BGR2GRAY) # change visitor image to grayscale for OpenCV operations
            self.faceRGB = cv.cvtColor(self.faceBGR, cv.COLOR_BGR2RGB) # change visitor image to rgb for face-recognition library operations
            faceDetected = haarCascade.detectMultiScale(self.faceGray, scaleFactor=1.01, minNeighbors=6)  # returns rectangular coordinates of face bounding box
            blurFactor = cv.Laplacian(self.faceGray, cv.CV_64F).var() # calculate bluriness of visitor image
            num_faceDetected = len(faceDetected) # number of faces detected in image
            if num_faceDetected >= 1 and blurFactor >= 25: # if at least 1 face has been detected and image isn't blurry, image considered suitable
                self.trainingImages.extend(self.faceRGB) # save visitor images in RGB format to train the facial recognition algorithm
            attempts +=1
        
        self.camera.close()

        self.data[self.accountID]["faceIDs"] = self.faceIDs # update face IDs in json object
        self.data['training'] = 'True' # status message to indicate that training is complete and camera instance has been closed, so can now ring doorbell again with new camera instance (avoids concurrent camera access errors)
        
        with open(join(path,'data.json'), 'w') as jsonFile:
            json.dump(self.data, jsonFile)
            
        for faceRGB in self.trainingImages: # iterate through image arrays for each training image
            if self.faceRecognised == True: # if face identified in test visitor image
                label, faceRecognised = self.recognise(faceRGB) # get face label for training image
                if label == self.label: # if training image  has same label as label of test visitor image
                    self.encodings, self.labels = self.train(faceRGB, label) # train facial recognition algorithm and update face encodings and labels
            elif self.faceRecognised == False: # if no face identified in test visitor image
                self.encodings, self.labels = self.train(faceRGB, self.label) # train facial recognition algorithm and update face encodings and labels for new face label

        fileName = join(path, "trainingData")  # load the face encodings and labels for trained image data set
        if os.path.isfile(fileName): # training image data set exists
            trainingData = pickle.loads(open(join(path,"trainingData"), "rb").read()) # reconstruct dictionary object 'trainingData' from character stream stored in 'trainingData' file
            trainingData['encodings'].extend(self.encodings) # append latest version of visitor image face encodings to training data
            trainingData['labels'].extend(self.labels) # append latest version of visitor image labels to training data
        else: # training image data set doesn't exist
            trainingData = {'encodings': self.encodings, 'labels': self.labels} # create new dictionary storing face encodings and labels for trained data set
        
        f = open(join(path,"trainingData"), "wb")
        f.write(pickle.dumps(trainingData)) # dump training data dictionary object as character stream to 'trainingData'
        f.close()

        self.data['training'] = 'False'
        with open(join(path,'data.json'), 'w') as jsonFile:
            json.dump(self.data, jsonFile)
        client.disconnect() # disconnect client from MQTT broker
        quit()


    def create_visitID(self):
        # creates a unique visitID for each visit
        data_vistID = {"field": "visitID"} # dictionary passed to REST API path to specify that required ID is visit ID
        visitID = requests.post(serverBaseURL + "/create_ID", data_vistID).text # REST API path generate new unique visit ID
        return visitID


    def create_faceID(self):
        # creates a unique faceID for the face captured
        data_faceID = {"field": "faceID"} # dictionary passed to REST API path to specify that required ID is face ID
        faceID = requests.post(serverBaseURL + "/create_ID", data_faceID).text # REST API path generate new unique face ID
        return faceID


    def update_visitorLog(self):
        # store visit details in SQL table 'visitorLog'
        data_visitorLog = {"visitID": self.visitID, "imageTimestamp": (str(time.strftime("%H.%M"))+','+str(time.time())), "faceID": self.faceID, "accountID": self.accountID} # data to be stored in SQL table 'visitorLog'
        requests.post(serverBaseURL + "/update_visitorLog", data_visitorLog) # REST API path store data in SQL databese
        return

    def update_knownFaces(self):
        # store details for new face in SQL table 'knownFaces'
        data_knownFaces = {"faceID": self.faceID, "faceName": "", "accountID": self.accountID} # data to be stored in SQL table 'knownFaces'
        requests.post(serverBaseURL + "/update_knownFaces", data_knownFaces) # REST API path store data in SQL database
        return

    def formatImage(self, visitorImage):
        # format visitor image so suitable shape to be displayed in mobile app
        visitorImage_cropped_w = round(int(windowSize_mobile[0]) * 0.93) # target width of visitor image
        visitorImage_cropped_h = round(int(windowSize_mobile[1]) * 0.54) # target height of visitor image
        scaleFactor = visitorImage_cropped_h / visitorImage.shape[0] # factor by which height of image must be scale down to fit screen
        visitorImage = cv.resize(visitorImage,
                                 (int(visitorImage.shape[1] * scaleFactor), int(visitorImage.shape[0] * scaleFactor)),
                                 interpolation=cv.INTER_AREA) # scales down width and height of image to match required image height
        visitorImage_centre_x = visitorImage.shape[1]//2 # x-coordinate of horizontal middle of image
        visitorImage_x = visitorImage_centre_x - visitorImage_cropped_w // 2  # start x-coordinate of visitor image
        if visitorImage_x < 0: # if desired start x-coordinate of image is negative, set start x-coordinate to 0
            visitorImage_x = 0
        visitorImage_cropped = visitorImage[0:visitorImage.shape[0],
                               visitorImage_x:visitorImage_x + visitorImage_cropped_w] # crops image width to fit screen
        self.path_visitorImage = join(path, 'Photos/visitorImage.png')
        cv.imwrite(self.path_visitorImage, visitorImage_cropped) # store formatted visitor image locally on Raspnberry Pi
        self.uploadAWS_image(Bucket="nea-visitor-log", Key = self.visitID) # upload formatted visitor image to AWS S3 storage

    def uploadAWS_image(self, **kwargs):
        # uploads image to AWS S3 storage
        fernet = Fernet(self.accountID.encode()) # instantiate Fernet class with users accountID as the key
        data_S3Key = {"accountID": self.accountID} # dictionary passed to REST API path to encode AWS S3 keys
        encodedKeys = requests.post(serverBaseURL + "/get_S3Key", data_S3Key).json() # REST API path returns json object with encoded keys
        accessKey = fernet.decrypt(encodedKeys["accessKey_encrypted"].encode()).decode() # decode access key using 'accountID' encryption key
        secretKey = fernet.decrypt(encodedKeys["secretKey_encrypted"].encode()).decode() # decode secret key using 'accountID' encryption key
        s3 = boto3.client("s3", aws_access_key_id=accessKey, aws_secret_access_key=secretKey)  # initialises a connection to the S3 client on AWS using the access key and secret key
        s3.upload_file(Filename=self.path_visitorImage, Bucket=kwargs["Bucket"], Key=kwargs["Key"])  # uploads the image file to the S3 bucket called 'nea-visitor-log'.
        return
    
    def publish_message_ring(self):
        # transmit MQTT message to mobile app to notify that doorbell has been rung
        client.publish("ring/{}".format(self.accountID), "{}".format(str(self.visitID))) # publish MQTT message to 'ring/accountID' topic
        return


def on_connect(client, userdata, flags, rc):
    # callback function called if successful connection to MQTT broker
    if rc == 0: # if connection is successful
        client.publish('connected','')
    else:
        # attempts to reconnect
        client.on_connect = on_connect
        client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
        client.connect("hairdresser.cloudmqtt.com", 18973)
        
def run():
    # driver function when doorbell is rung
    client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI") # specify MQTT broker connection details
    client.on_connect = on_connect # creates callback for successful connection with broker
    client.connect("hairdresser.cloudmqtt.com", 18973) # connect to MQTT broker
    buttonPressed().captureImage()

client = mqtt.Client()



        
