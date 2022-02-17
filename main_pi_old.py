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
import numpy as np
import paho.mqtt.client as mqtt
import requests
from cryptography.fernet import Fernet
import sys

path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

serverBaseURL = "http://nea-env.eba-6tgviyyc.eu-west-2.elasticbeanstalk.com/"  # base URL to access AWS elastic beanstalk environment

haarCascade = cv.CascadeClassifier(join(path,"haar_face.xml")) # reads in the xml haar cascade file

windowSize_mobile = (640, 1136)

if not os.path.isfile(join(path,"features.npy")):
    featuresNp = np.empty(0, int) # arrays are saved as integers
    np.save(join(path,'features.npy'), featuresNp)
if not os.path.isfile(join(path,"labels.npy")):
    labelsNp = np.empty(0, int)
    np.save(join(path,'labels.npy'), labelsNp)


    
class buttonPressed():
    def __init__(self):
        with open(join(path,'data.json'), 'r') as jsonFile: # ensures up-to-date value for accountID is used
            time.sleep(0.5) # resolves issue with reading file immediately after it is written to (json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0))
            data = json.load(jsonFile)
            self.accountID = str(data['accountID'])
        self.visitID = self.create_visitID()
        self.publish_message_ring()
        with open(join(path,'data.json')) as jsonFile:
            self.data = json.load(jsonFile)
        if self.accountID not in self.data: # if data for account not yet stored
            self.data.update({self.accountID:{"faceIDs":[]}}) # updates json file to create empty parameter to store names of known visitors associated with a specific accountID
            with open(join(path,'data.json'),'w') as jsonFile:
                json.dump(self.data, jsonFile)


    def captureImage(self):
        self.camera = PiCamera()
        self.rawCapture = PiRGBArray(self.camera) # using PiRGBArray increases efficiency when accessing camera stream 
        self.trainingImages = []
        blurFactors = []
        self.faceDetected = False
        time.sleep(0.155) # delay to allow camera to warm up
        self.rawCapture.truncate(0)
        self.camera.capture(self.rawCapture, format="bgr") # captures camera stream in 'bgr' format (opencv array requires this)    
        attempts = 1
        while attempts <= 2: # time consuming to capture images and analyse for presence of face, so only attempt process of capturing images twice
            visitorImages = []
            for i in range(2): # at least two photos are required for successful training of the algorithm
                self.rawCapture.truncate(0)
                self.camera.capture(self.rawCapture, format="bgr") # captures camera stream in 'bgr' format (opencv array requires this)
                img = cv.flip(self.rawCapture.array,0) # 'img' stores matrix array of the capture image
                rgb = cv.cvtColor(img, cv.COLOR_BGR2RGB)
                if i == 0:
                    cv.imwrite((join(path,"Photos/Visitor/visitorImage.png")), rgb) #save first image captured as most likely to be looking at doorbell camera
                gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
                visitorImages.append(gray)
            faceDetected = haarCascade.detectMultiScale(gray, scaleFactor=1.01, minNeighbors=6)  # returns rectangular coordinates of a face.
            # scaleFactor is the percentage by which the image is resized on each iteration of the algorithm to attempt to detect a face in the image, as the face size used in the haar cascade xml is constant, but face sizes in the test image may vary. A small percentage value (i.e. 1.05 which would reduce image size by 5% on each iteration) would mean there is a small step for each resizing, so there is a greater chance of correctly detecting all the faces in the image, although it will be slower than using a larger scale factor
            # minNeighbours specifies how many neighbours each candidate rectangle should have to retain it. In other words, the minimum number of positive rectangles (detect facial features) that need to be adjacent to a positive rectangle in order for it to be considered actually positive. A higher value of minNeighbours will result in less detections but with high quality - somewhere between 3-4
            blurFactor = cv.Laplacian(gray, cv.CV_64F).var()# Laplacian operator calculates the gradient change values in an image (i.e. transitions from black to white in greyscale image), so it is used for edge detection. Here, the variance of this operator on each image is returned; if an image contains high variance then there is a wide spread of responses, both edge-like and non-edge like, which is representative of a normal, in-focus image. But if there is very low variance, then there is a tiny spread of responses, indicating there are very little edges in the image, which is typical of a blurry image
            num_faceDetected = len(faceDetected) # finds number of faces detected in image
            print("Blur factor = ",blurFactor)
            if num_faceDetected >= 1 and blurFactor >= 20: # if at least 1 face has been detected and image isn't blurry, save the image
                self.trainingImages.extend(visitorImages) # ensures at least two images of visitor are stored for training
                self.faceDetected = True
                break # two satisfactury images are captured so do not attempt capturing images again
            else:
                os.rename(join(path,"Photos/Visitor/visitorImage.png"), join(path,"Photos/Visitor/frame{}.png".format(str(attempts))))
                blurFactors.append((attempts, blurFactor))
                attempts +=1
        if self.faceDetected == True:
            print('Face detected')
            self.path_visitorImage = join(path,"Photos/Visitor/visitorImage.png")
        else:
            print('No face detected')
            self.img_num = max(blurFactors, key=lambda image: image[1])[0] # lambda function is an anonymous/nameless function which returns the second element in the tuple for each element in the list, as the second element is the variance of the gradient changes (i.e. number of edges) in each image. Therefore, the max operator is used to find the image with the highest variance of gradient changes as this will be the least blurry image and so most suitable to apply facial recognition to.
            self.path_visitorImage = join(path,"Photos/Visitor/frame{}.png".format(str(self.img_num)))
        print('Image path: ', self.path_visitorImage)
        self.formatImage()
        self.uploadAWS_image(Bucket="nea-visitor-log", Key = self.visitID)
        if self.faceDetected == True: # if a viable image of the visitor has been captured
            self.facialRecognition() # run facial recognition algorithm
        else:
            self.confidence = "NO_FACE"
            self.faceID = "NO_FACE"
            self.update_visitorLog()
            self.camera.close()
            print("Quit")
            quit()

    def facialRecognition(self):
        self.gray = self.imgReserve = self.trainingImages[0].copy()
        #cv.imshow('face', self.gray)
        #cv.waitKey(0)
        faceRectangle = haarCascade.detectMultiScale(self.gray, scaleFactor=1.01, minNeighbors=6)
        for (x, y, w, h) in faceRectangle:
            cv.rectangle(self.gray, (x, y), (x+w, y+h), (255, 0, 0), 2)
        #cv.imshow('face', self.gray)
        #cv.waitKey(0)
        self.faceIDs = []
        with open(join(path,'data.json')) as jsonFile:
            self.data = json.load(jsonFile)
            for faceID in self.data[self.accountID]["faceIDs"]:
                self.faceIDs.append(faceID)
        try: # try except needed as block of code will break if no previous file called 'face_trained.yml' (i.e. first time running the program) or if no acceptable images found that facial recognition can be performed on
            self.faceRecognizer = cv.face.LBPHFaceRecognizer_create(radius = 2, neighbors = 16, grid_x = 8, grid_y = 8)
            self.faceRecognizer.read(join(path,'face_trained.yml'))
            faceData = [] # list used to store confidence values for all faces detected
            for (x, y, w, h) in faceRectangle:
                print(w/self.gray.shape[1])
                if w/self.gray.shape[1] > 0.15: # ensures only trained on image of entire face
                    self.faceROI = self.gray[y:y + h,x:x + w]  # crops the image to store only the region containing a detected face, which reduces the chance of noise interfering with the face recognition
                    #cv.imwrite('Photos/Visitor/test{}.png'.format(str(counter)), self.faceROI)
                    label, confidence = self.faceRecognizer.predict(self.faceROI)  # runs facial recognition algorithm, returning the name of the faceID identified and the confidence of this identification
                    print("Confidence = ",confidence)
                    faceData.append((label, confidence))
                   # cv.imwrite((join(path,f"Photos/Visitor/{confidence}.png")), self.faceROI) #save first image captured as most likely to be looking at doorbell camera
            self.label, self.confidence = min(faceData, key=lambda x:x[1]) # lambda function used to select lowest confidence value and associated label (as this is the actual face in the photo - ignores false faces identified such as my nose)
            print('Final confidence =', self.confidence)
            #cv.imshow('faceROI',self.faceROI)
            #cv.waitKey(0)
            if self.confidence <= 30:
                self.faceID = self.faceIDs[self.label]
                self.faceRecognised = True
            else:
                self.faceID = self.create_faceID()
                self.faceRecognised = False

        except:
            self.confidence = 1000 # if the file face_trained.yml doesn't exist yet
            self.faceID = self.create_faceID()
            self.faceRecognised = False
        self.update_visitorLog()
        #self.publish_message_visitor()
        #client.publish("confidence/{}".format(self.accountID), "{}".format(faceData))
        client.publish("confidence/{}".format(self.accountID), "{}".format(str(self.confidence)))
        if self.faceID not in self.faceIDs:
            self.faceIDs.append(self.faceID)
            self.update_knownFaces()
        self.label = self.faceIDs.index(self.faceID) # create new label if face doesn't currently exist
        self.data[self.accountID]["faceIDs"] = self.faceIDs
        with open(join(path,'data.json'), 'w') as f:
            json.dump(self.data, f)
        print("Training") 
        self.thread_updateTraining = threading.Thread(target=self.updateTraining, args=(), daemon=False)
        self.thread_updateTraining.start()  # starts the thread which will run in pseudo-parallel to the rest of the program
           
            
    def updateTraining(self):
        featuresNp = np.load(join(path,'features.npy'),allow_pickle = True) # opens numpy file storing the tagged data for the known faces as list
        labelsNp = np.load(join(path,"labels.npy"), allow_pickle=True)
        features = []
        attempts = 0
        while attempts < 5: # camera captures more images to aid facial recognition training algorithm
            self.rawCapture.truncate(0) # clear the stream in preparation for the next frame
            self.camera.capture(self.rawCapture, format="bgr") # captures camera stream in 'bgr' format (opencv arr$                img = cv.flip(self.rawCapture.array,0) # 'img' stores matrix array of the capture image
            img = cv.flip(self.rawCapture.array,0) # 'img' stores matrix array of the capture image
            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            faceDetected = haarCascade.detectMultiScale(gray, scaleFactor=1.01, minNeighbors=6)  # returns rectangular coordinates of a face.
            # scaleFactor is the percentage by which the image is resized on each iteration of the algorithm to attempt to detect a face in the image, as the face size used in the haar cascade xml is constant, but face sizes in the test image may vary. A small percentage value (i.e. 1.05 which would reduce image size by 5% on each iteration) would mean there is a small step for each resizing, so there is a greater chance of correctly detecting all the faces in the image, although it will be slower than using a larger scale factor
            # minNeighbours specifies how many neighbours each candidate rectangle should have to retain it. In other words, the minimum number of positive rectangles (detect facial features) that need to be adjacent to a positive rectangle in order for it to be considered actually positive. A higher value of minNeighbours will result in less detections but with high quality - somewhere between 3-4
            blurFactor = cv.Laplacian(gray, cv.CV_64F).var()# Laplacian operator calculates the gradient change values in an image (i.e. transitions from black to white in greyscale image), so it is used for edge detection. Here, the variance of this operator on each image is returned; if an image contains high variance then there is a wide spread of responses, both edge-like and non-edge like, which is representative of a normal, in-focus image. But if there is very low variance, then there is a tiny spread of responses, indicating there are very little edges in the image, which is typical of a blurry image
            num_faceDetected = len(faceDetected) # finds number of faces detected in image
            if num_faceDetected >=1 and blurFactor >= 20: # if at least 1 face has been detected and image isn't blurry, save the image as it will contribute to the facial recognition training data set
                self.trainingImages.append(gray)
                print("Added image to training images array")
            attempts +=1
            
        print("Previous number of training images:", len(labelsNp))
        for gray in self.trainingImages:
            trainingData = []
            faces_rect = haarCascade.detectMultiScale(gray, scaleFactor=1.01, minNeighbors=6)
            for (x, y, w, h) in faces_rect:
                if w/gray.shape[1] > 0.15: # ensures only trained on image of entire face
                    faceROI = gray[y:y + h, x:x + w]  # crops image to just the face in the image, which reduces the chance of noise interfering with the face recognition
                    if self.faceRecognised == True:
                        label, confidence = self.faceRecognizer.predict(faceROI)  # runs facial recognition algorithm, returning the name of the faceID identified and the confidence of this identification
                        print("Training image confidence = ",confidence)
                        trainingData.append((label, confidence,faceROI, w))
                    elif self.faceRecognised == False:
                        trainingData.append((self.label, 10000, faceROI, w)) # as determined that face does not match a known face, train images as a new face
                        print('Training image is new face')
            if len(trainingData) > 0:
                label, confidence, faceROI, width = min(trainingData, key=lambda x:x[1])
                if confidence <=30 and label == self.label and self.faceRecognised == True:
                    print("Training image added with confidence:", confidence)
                    features.append(faceROI)
                    labelsNp = np.append(labelsNp, self.label)
                elif self.faceRecognised == False: # if there is no image which has a close match to an existing face
                    print("New face trained")
                    label, confidence, faceROI, width = max(trainingData, key=lambda x:x[3]) # choose face detected with largest value for width as this is likley to be the actual face in the image (from observation)
                    features.append(faceROI)
                    labelsNp = np.append(labelsNp, self.label)
                cv.imwrite((join(path,f"Photos/Visitor/{confidence}.png")),faceROI) #save first image captured as most likely to be looking at doorbell camera
        if len(features) == 1: # error when training on just one new image. Resolve by adding a duplicate of the image used to do the facial recognition
            faces_rect = haarCascade.detectMultiScale(self.imgReserve, scaleFactor=1.01, minNeighbors=6)
            for (x, y, w, h) in faces_rect:
                if w/gray.shape[1] > 0.15: # ensures only trained on image of entire face
                    faceROI = self.imgReserve[y:y + h, x:x + w]  # crops image to just the face in the image, which reduces the chance of noise interfering with the face recognition
                    features.append(faceROI)
                    labelsNp = np.append(labelsNp, self.label)
                    print('Error prevention used')

        print('Number of new images: ', len(features))
        if len(features) > 1:
            try:
                face_recognizer = cv.face.LBPHFaceRecognizer_create()
                featuresNp = np.append(featuresNp, features)
                face_recognizer.train(featuresNp, labelsNp)
                face_recognizer.save(join(path,"face_trained.yml"))  # saves the trained model
                print('Label: ',self.label)
                np.save(join(path,'features.npy'), featuresNp)
                np.save(join(path,"labels.npy"), labelsNp)
                print('New number of training images: ',len(featuresNp))
                print('Trained')
            except:
                print('Training error')
        self.camera.close()
        print("Quit")
        quit()



    def create_visitID(self):
        # creates a unique visitID for each visit
        self.data_vistID = {"field": "visitID"}
        visitID = requests.post(serverBaseURL + "/create_ID", self.data_vistID).text
        return visitID


    def create_faceID(self):
        # creates a unique faceID for the face captured
        self.data_faceID = {"field": "faceID"}
        faceID = requests.post(serverBaseURL + "/create_ID", self.data_faceID).text
        return faceID


    def update_visitorLog(self):
        self.data_visitorLog = {"visitID": self.visitID, "imageTimestamp": time.time(), "faceID": self.faceID, "confidence": str(self.confidence), "accountID": self.accountID}
        requests.post(serverBaseURL + "/update_visitorLog", self.data_visitorLog)
        return

    def update_knownFaces(self):
        self.data_knownFaces = {"faceID": self.faceID, "faceName": "", "accountID": self.accountID}
        requests.post(serverBaseURL + "/update_knownFaces", self.data_knownFaces)
        return

    def formatImage(self):
        visitorImage = cv.imread(self.path_visitorImage)
        visitorImage_cropped_w = round(int(windowSize_mobile[0]) * 0.93)
        visitorImage_cropped_h = round(int(windowSize_mobile[1]) * 0.54)
        scaleFactor = visitorImage_cropped_h / visitorImage.shape[0] # scaleFactor is factor by which height of image must be scale down to fit screen
        visitorImage = cv.resize(visitorImage,
                                 (int(visitorImage.shape[1] * scaleFactor), int(visitorImage.shape[0] * scaleFactor)),
                                 interpolation=cv.INTER_AREA) # scales down width and height of image to match required image height
        visitorImage_centre_x = visitorImage.shape[1]//2
        visitorImage_x = visitorImage_centre_x - visitorImage_cropped_w // 2  # floored division for pixels as must be integer
        if visitorImage_x < 0:
            visitorImage_x = 0
        visitorImage_cropped = visitorImage[0:visitorImage.shape[0],
                               visitorImage_x:visitorImage_x + visitorImage_cropped_w] # crops image width to fit screen (with centre of image the face of the visitor, if a face can be detected)
        cv.imwrite(self.path_visitorImage, visitorImage_cropped)
        return

    def uploadAWS_image(self, **kwargs):
        fernet = Fernet(self.accountID.encode()) # instantiate Fernet class with users accountID as the key
        self.data_S3Key = {"accountID": self.accountID}
        hashedKeys = requests.post(serverBaseURL + "/get_S3Key", self.data_S3Key).json() # returns json object with encoded keys
        accessKey = fernet.decrypt(hashedKeys["accessKey_encoded"].encode()).decode() # encoded byte string returned so must use 'decode()' to decode it
        secretKey = fernet.decrypt(hashedKeys["secretKey_encoded"].encode()).decode()
        s3 = boto3.client("s3", aws_access_key_id=accessKey, aws_secret_access_key=secretKey)  # initialises a connection to the S3 client on AWS using the 'accessKey' and 'secretKey' sent to the API
        s3.upload_file(Filename=self.path_visitorImage, Bucket=kwargs["Bucket"], Key=kwargs["Key"])  # uploads the txt file to the S3 bucket called 'nea-audio-messages'. The name of the txt file when it is stored on S3 is the 'messageID' of the audio message which is being stored as a txt file.
        print("Uploaded")
        for img in os.listdir(join(path,"Photos/Visitor/")):
            #os.remove(os.path.join((join(path,"Photos/Visitor")),img))
            pass
        return
    
    def publish_message_ring(self):
        client.publish("ring/{}".format(self.accountID), "{}".format(str(self.visitID)))
        return

    def publish_message_visitor(self):
        client.publish("visit/{}".format(self.accountID), "{}".format(str(self.visitID)))
        return


def on_connect(client, userdata, flags, rc):
    if rc == 0: # if connection is successful
        client.publish('connected','')
    else:
        # attempts to reconnect
        client.on_connect = on_connect
        client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
        client.connect("hairdresser.cloudmqtt.com", 18973)
        
def run():
    client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
    client.on_connect = on_connect # creates callback for successful connection with broker
    client.connect("hairdresser.cloudmqtt.com", 18973) # parameters for broker web address and port number
    buttonPressed().captureImage()
    
client = mqtt.Client()


        
