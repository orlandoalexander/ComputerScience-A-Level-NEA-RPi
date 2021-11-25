import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import time
import main_pi
import threading 

GPIO.setwarnings(False) # Ignore warning for now
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)

def runThread():
    main_pi.run()

while True: # Run forever
    if GPIO.input(10) == GPIO.HIGH and threading.active_count() == 1:
        thread_run = threading.Thread(target =runThread)
        thread_run.start()
