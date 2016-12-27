#!/usr/bin/env python
#
#
#Author: Mari DeGrazia
#http://az4n6.blogspot.com/
#arizona4n6@gmail.com
#This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You can view the GNU General Public License at <http://www.gnu.org/licenses/>

import serial
import time
import subprocess
from multiprocessing import Queue as MPQueue
from multiprocessing import Process
import RPi.GPIO as GPIO
import logging
import logging.handlers
import sys
import Queue
from ConfigParser import SafeConfigParser

#read in configuration settings
parser = SafeConfigParser()
parser.read('/home/pi/Desktop/piWarmer.config')
 
SERIAL_PORT = parser.get('SETTINGS','serial_port')
BAUDRATE = parser.get('SETTINGS','baudrate')
GPIO_PIN = parser.getint('SETTINGS','bcm_gpio_pin')
ALLOWED_NUMBERS = parser.get('SETTINGS','allowed_phone_numbers')
ALLOWED_NUMBERS = ALLOWED_NUMBERS.split(',')
MAX_TIME = parser.getint('SETTINGS','max_heater_time')
MAX_TIME = MAX_TIME * 60 #convert from minutes to seconds for sleep
LOG_FILENAME = parser.get('SETTINGS','logfile')
LOG_LEVEL = logging.INFO

#setup GPIO Pin
GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_PIN, GPIO.OUT)

#get status of heater. I had to use the subprocess function as using the GPIO library resets the GPIO pin
def getStatus():
	p = subprocess.Popen(["gpio -g read " + str(GPIO_PIN)],shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	message =  p.communicate(input)
	return message[0].rstrip()
	
#send a command to the modem
def sendCommand(com):
  ser.write(com+"\r\n")
  time.sleep(2)
  ret = []
  while ser.inWaiting() > 0:
    msg = ser.readline().strip()
    msg = msg.replace("\r","")
    msg = msg.replace("\n","")
    if msg!="":
      ret.append(msg)
  return ret

#send a message to the specified phone number
def sendMessage(message_num,text):
	sendCommand("AT+CMGF=1")
	sendCommand('AT+CMGS='+message_num)
	sendCommand(text + chr(26))
	time.sleep(5)
	

#reads text messages on the SIM card and returns a list of messages with three fields: id, num, message
def getMessages(confirmation=True):
        #put into SMS mode
        sendCommand("AT+CMGF=1")
        #get all text messages currently on SIM Card
        ser.write('AT+CMGL="ALL"\r')
        time.sleep(3)
        messages = []
        while ser.inWaiting() > 0:
                line =  ser.readline().strip()
                if "+CMGL:" in line:
                        message_details = []
                        metadata_list = line.split(",")
                        message_id = metadata_list[0]
                        message_id = message_id.rpartition(":")[2].strip()
                        message_num = metadata_list[2]

                        message_details.append(message_id)
                        message_details.append(message_num)
                        message_line =  ser.readline().strip()
                        message_details.append(message_line)
                        messages.append(message_details)

                        #now that we read the message,remove it from the SIM card
                        sendCommand("AT+CMGD="+str(message_id))
                        time.sleep(4)
        
        if len(messages) > 0:
            for message in messages:
                if confirmation == True:
                    logger.info("Message received from " + message[1] + ": " + message[2])
                    sendCommand('AT+CMGS='+message[1])
                    sendCommand("Message received: " + message[2] + chr(26))

        return messages

def heaterON():
	GPIO.output(GPIO_PIN,GPIO.HIGH)
 	sendMessage(message[1],"Heater successfully turned ON")
	logger.info("Heater turned ON")
	time.sleep(3)
	
def heaterOFF():
	GPIO.output(GPIO_PIN,GPIO.LOW)
	sendMessage(message[1],"Heater successfully turned OFF")
	logger.info("Heater turned OFF")
	time.sleep(3)

def shutdown():
	p = subprocess.Popen(["sudo shutdown -P now " + str(GPIO_PIN)],shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

#for safety, this thread starts a timer for when the heater was turned on
#and turns it off when reached
def heaterTimer(queue):

	 logger.info("Starting Heater Timer. Max Time is " + str(MAX_TIME/60) + " minutes")
         time.sleep(MAX_TIME)
          
         #turn off heater
         GPIO.output(GPIO_PIN,GPIO.LOW)
         queue.put("max_time")
         logger.info("Heater turned OFF. Max Time Reached")
         return


if __name__ == '__main__':
	#set up logging
	logger = logging.getLogger("heater")
	logger.setLevel(LOG_LEVEL)
	handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=1048576, backupCount=3)
	formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
	handler.setFormatter(formatter)
	logger.addHandler(handler)


	#create queue to hold heater timer.
	queue = MPQueue()
	Empty = Queue.Empty

	#connect to serial device AKA GSM Modem
	try:
		ser=serial.Serial(SERIAL_PORT, BAUDRATE, timeout=.1, rtscts=0)
	except:
		logger.warning("SERIAL DEVICE NOT LOCATED. Try changing /dev/ttyUSB0 to different USB port (like /dev/ttyUSB1) in configuration file or check to make sure device is connected correctly")
		exit()
 
	logger.info("Starting SMS monitoring and heater service")
	logger.info("Initialize heater to OFF position")
	GPIO.output(GPIO_PIN,GPIO.LOW)
	for phone_number in ALLOWED_NUMBERS:
		sendMessage('"+'+ phone_number +'"',"piWarmer powered on. Initializing. Wait to send messages...")
		logger.info("Sent starting message to " + phone_number)
	
	#clear out all the text messages currently stored on the SIM card.We don't want old messages being processed
	#dont send out a confirmation to these numbers because we are just deleting them and not processing them
	
	old_messages = True
	while old_messages is True:
		messages = getMessages(confirmation=False)
		if messages:
			for phone_number in ALLOWED_NUMBERS:
				sendMessage('"+'+ phone_number +'"',"Old or unprocessed message(s) found on SIM Card. Deleting...: ")
			for message in messages:
				logger.info("Old message cleared from SIM Card: " + message[2])
			
		else:
			old_messages = False

	print "Starting to monitor for SMS Messages..."
	logger.info("Begin monitoring for SMS messages")
	
	for phone_number in ALLOWED_NUMBERS:
		sendMessage('"+'+ phone_number +'"',"piWarmer monitoring started. Ok to send messages now")
		logger.info("Sent starting message to " + phone_number)
	
	print 'Press Ctrl-C to quit.'
	while True:
		
		#get messages on SIM Card
		messages = getMessages()
		#check the heater time queue to see if the heater was turned off due to max time being reached
		try:        
			heater_timer_q = queue.get_nowait()
			if "max_time" in heater_timer_q:
				print "Max time reached. Heater turned OFF"
				sendMessage(last_number,"Heater was turned off due to max time being reached")
		except Empty:
			pass

		for message in messages:
			phone_number = message[1].replace('"','')
			phone_number = phone_number.replace("+",'')
			sms_message = message[2].lower()
			if phone_number in ALLOWED_NUMBERS:
				status = getStatus()
				if "on" in sms_message:
					print "Turn ON heater"
					logger.info("Received ON SMS from " + phone_number)

					if status == "1":
						sendMessage(message[1],"Heater is already ON")
					else:
						try:
							#turn on the heater timer
							p = Process(target=heaterTimer,args=(queue,))
							p.start()
							heaterON()
							last_number = message[1]
						except:
							print "Issues turning heater ON"
							logger.warning("Issues turning heater ON")
							sendMessage(message[1],"Issue turning on Heater")
				elif "off" in sms_message:
					print "Turn OFF heater"
					logger.info("Received OFF SMS from " + phone_number)
					if status == "1":
						#kill the heater timer since we are turning it off
						p.terminate()
						try:
							heaterOFF()
						except:
							print "Issues turning heater OFF"
							logger.warning("Issues turning heater OFF")
							sendMessage(message[1],"Issue turning Heater OFF")
					else:
						sendMessage(message[1],"Heater is already OFF")
						
				elif "status" in sms_message:
					logger.info("Received STATUS SMS from " + phone_number)
					if status == "1":
						print "Heater is ON"
						sendMessage(message[1],"Heater is ON")
					elif status == "0":
						print "Heater is OFF"
						sendMessage(message[1],"Heater is OFF")
						
				elif "shutdown" in sms_message:
					logger.info("Received SHUTDOWN SMS from " + phone_number)
					sendMessage(message[1],"Shutting system down now")
					logger.info("Shutting down Raspberry Pi")
					try:
						print "Shutting down Raspberry Pi"
						shutdown()
					except:
						logger.warning("Issue shutting down Raspberry Pi")
						sendMessage(message[1],"Issue shutting down Raspberry Pi")
				else:
					
					logger.info("Received something other than On,Off,Status,Shutdown request from " + phone_number)
					sendMessage(message[1],"Please text ON,OFF,STATUS or SHUTDOWN to control heater")
			else:
				
				logger.warning("Received unauthorized SMS from " + phone_number)
				sendMessage(message[1],"This phone number is not on the allowed list. Contact the administrator to have the phone number " + phone_number + " added")
