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
import logging
import logging.handlers
import sys
import Queue
import datetime
from ConfigParser import SafeConfigParser
from lib.fona import fona
from lib.relay import relay
import RPi.GPIO as GPIO

#read in configuration settings
parser = SafeConfigParser()
parser.read('/home/pi/Desktop/piWarmer.config')
 
SERIAL_PORT = parser.get('SETTINGS','SERIAL_PORT')
BAUDRATE = parser.get('SETTINGS','BAUDRATE')
HEATER_GPIO_PIN = parser.getint('SETTINGS','HEATER_GPIO_PIN')
MQ2 = parser.getboolean('SETTINGS','MQ2')
MQ2_GPIO_PIN = parser.getint('SETTINGS','MQ2_GPIO_PIN')
ALLOWED_NUMBERS = parser.get('SETTINGS','ALLOWED_PHONE_NUMBERS')
ALLOWED_NUMBERS = ALLOWED_NUMBERS.split(',')
MAX_TIME = parser.getint('SETTINGS','MAX_HEATER_TIME')
MAX_TIME = MAX_TIME * 60 #convert from minutes to seconds for sleep
LOG_FILENAME = parser.get('SETTINGS','LOGFILE')
LOG_LEVEL = logging.INFO


def MQ2Status():
	input_state = GPIO.input(MQ2_GPIO_PIN)
	if input_state == 1:
		return "off"
	if input_state == 0:
		return "on"

def process_message(message,phone_number=False):
	global last_number
	status = heater.status()
	message = message.lower()
	turn_on = True
	print message
	#check to see if this is an allowed phone number
	if phone_number:
		phone_number = phone_number.replace('"','')
		phone_number = phone_number.replace("+",'')
		if phone_number not in ALLOWED_NUMBERS:
			logger.warning("Received unauthorized SMS from " + phone_number)
			response = "Received unauthorized SMS from " + phone_number
			return response
	if "on" in message:
		print "Received ON request"
		logger.info("Received ON request from " + phone_number)
		if status == "1":
			response = "Heater is already ON"
			turn_on = False
		if MQ2:
			if MQ2Status() == "on":
				response = "Gas warning. Not turning heater on"
				turn_on = False
		if turn_on:
			try:
				heater.switchHigh()
				response = "Heater turned ON"
				print "Heater turned ON"
				queue.put("On")
				if phone_number:
					last_number = '"+'+ phone_number +'"'
			except:
				print "Issues turning heater ON"
				logger.warning("Issues turning heater ON")
				response = "Issue turning on Heater"
	elif "off" in message:
		print "Turn OFF heater"
		logger.info("Received OFF request from " + phone_number)
		if status == "1":
			try:
				heater.switchLow()
				response = "Heater turned OFF"
				queue.put("Off")
			except:
				print "Issues turning heater OFF"
				logger.warning("Issues turning heater OFF")
				response = "Issue turning Heater OFF"
		else:
			response = "Heater is already OFF"
	elif "status" in message:
		logger.info("Received STATUS request from " + phone_number)
		if status == "1":
			print "Heater is ON"
			response = "Heater is ON"
		elif status == "0":
			print "Heater is OFF"
			response = "Heater is OFF"
	elif "shutdown" in message:
		logger.info("Received SHUTDOWN request from " + phone_number)
		response = "Shutting system down now"
		logger.info("Shutting down Raspberry Pi request from " + phone_number)
		try:
			print "Shutting down Raspberry Pi"
			shutdown()
		except:
			logger.warning("Issue shutting down Raspberry Pi")
			response = "Issue shutting down Raspberry Pi"
	else:
		logger.info("Received something other than On,Off,Status,Shutdown request from " + phone_number)
		print "Please text ON,OFF,STATUS or SHUTDOWN to control heater"
		response = "Please text ON,OFF,STATUS or SHUTDOWN to control heater"
	if phone_number:
		fona.sendMessage('"+'+ phone_number +'"',response)
		logger.info("Sent message: " + response + " to " + phone_number)
		return response
	else:
		client.publish(FEED_STATUS,response)

def shutdown():
	p = subprocess.Popen(["sudo shutdown -P now " + str(HEATER_GPIO_PIN)],shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

#for safety, this thread starts a timer for when the heater was turned on
#and turns it off when reached
def heaterTimer(queue):
	print "Starting timer"
	logger.info("Starting Heater Timer. Max Time is " + str(MAX_TIME/60) + " minutes")
	time.sleep(MAX_TIME)
	queue.put("max_time")
	return
	
def monitor_LED_sensor(myLEDq,queue,client=False):
	while True:
		LED_status = MQ2Status()
		#print LED_status
		if LED_status == "on" and heater.status() == "1":
			
			#clear the queue if it has a bunch of no warnings in it
			while not myLEDq.empty():
				myLEDq.get()
			myLEDq.put("gas_warning")
			queue.put("Off")

			heater.switchLow()
			time.sleep(60)
		else:
			myLEDq.put("no_warning")
		time.sleep(2)

class MyLogger(object):
        def __init__(self, logger, level):
                """Needs a logger and a logger level."""
                self.logger = logger
                self.level = level

        def write(self, message):
                # Only log if there is a message (not just a new line)
                if message.rstrip() != "":
                        self.logger.log(self.level, message.rstrip())
							
		def flush(self):
			pass					

if __name__ == '__main__':
	#set up logging
	logger = logging.getLogger("heater")
	logger.setLevel(LOG_LEVEL)
	handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=1048576, backupCount=3)
	formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
	handler.setFormatter(formatter)
	logger.addHandler(handler)

	#create heater relay instance
	heater = relay()
	
	#create queue to hold heater timer.
	queue = MPQueue()
	p = Process(target=heaterTimer,args=(queue,))
	Empty = Queue.Empty

	try:
		ser=serial.Serial(SERIAL_PORT, BAUDRATE, timeout=.1, rtscts=0)
	except:
		logger.warning("SERIAL DEVICE NOT LOCATED. Try changing /dev/ttyUSB0 to different USB port (like /dev/ttyUSB1) in configuration file or check to make sure device is connected correctly")
		print "Serial Device not detected. Make sure fona is powered on and plugged into the Raspberry Pi. Checking again in 60 seconds"
		logger.info("Serial Device not detected. Make sure fona is powered on and plugged into the Raspberry Pi. Checking again in 60 seconds")
		
		#wait 60 seconds and check again
		time.sleep(60)
		try:
			ser=serial.Serial(SERIAL_PORT, BAUDRATE, timeout=.1, rtscts=0)
		
		except:
			print "no serial device"
			logger.warning("Serial Device not connected")
			exit()

	
	fona = fona(name="fona",ser=ser,allowednumbers=ALLOWED_NUMBERS)

	#create queue to hold heater timer.
	queue = MPQueue()
	Empty = Queue.Empty

	
	if MQ2:
		print "MQ2 Sensor enabled"
		logger.info("MQ2 Gas Sensor enabled")
		#setup MQ2 GPIO PINS
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(MQ2_GPIO_PIN, GPIO.IN)
		#create queue to hold MQ2 LED status
		myLEDq = MPQueue()
		#start sub process to monitor actual MQ2 sensor
		p_gas_monitor = Process(target=monitor_LED_sensor,args=(myLEDq,queue))
		p_gas_monitor.start()
		
	else:
		print "MQ2 Sensor not enabled"
		logger.info("MQ2 Sensor not enabled")

	#make sure and turn heater off
	heater.switchLow()
	logger.info("Starting SMS monitoring and heater service")
	for phone_number in ALLOWED_NUMBERS:
		fona.sendMessage('"+'+ phone_number +'"',"piWarmer powered on. Initializing. Wait to send messages...")
		logger.info("Sent starting message to " + phone_number)
	
	#clear out all the text messages currently stored on the SIM card.We don't want old messages being processed
	#dont send out a confirmation to these numbers because we are just deleting them and not processing them
	num_deleted = fona.deleteMessages()
	if num_deleted > 0:
		for phone_number in ALLOWED_NUMBERS:
			fona.sendMessage('"+'+ phone_number +'"',"Old or unprocessed message(s) found on SIM Card. Deleting...")
		logger.info(str(num_deleted) + " old message cleared from SIM Card")

	if MQ2:
		gas_status = MQ2Status()
		if "off" in gas_status:
			gas_status = "No gas detected"
		if "on" in gas_status:
			gas_status = "Gas detected"
		for phone_number in ALLOWED_NUMBERS:
			fona.sendMessage('"+'+ phone_number +'"',"MQ2 Gas Sensor Enabled. Status is " + gas_status)
	
	print "Starting to monitor for SMS Messages..."
	logger.info("Begin monitoring for SMS messages")

	for phone_number in ALLOWED_NUMBERS:
		fona.sendMessage('"+'+ phone_number +'"',"piWarmer monitoring started. Ok to send messages now. Text ON,OFF,STATUS or SHUTDOWN to control heater")
		logger.info("Sent starting message to " + phone_number)

	print 'Press Ctrl-C to quit.'
	flag = 0

	while True:
		if MQ2:
			try:
				myLEDqstatus = myLEDq.get_nowait()
				
				#print "QUEUE: " + myLEDqstatus
				if "gas_warning" in myLEDqstatus:
					if flag == 0:
						flag = 1
						print "Sending Warning"
						logger.warning("GAS DETECTED.HEATER TURNED OFF")
						#heater.switchLow()
						fona.sendMessage(last_number,"Gas Warning. Heater turned OFF")
						flag = 1
				if myLEDqstatus == "no_warning":
					if flag == 1:
						print "Cleared"
						logger.warning("GAS WARNING CLEARED")
						fona.sendMessage(last_number,"Gas Warning CLEARED. Send ON message to restart")
						flag = 0
							
			except Empty:
				pass

		#check the queue to deal with various issues, such as Max heater time and the gas sensor being tripped
		try:
			status_queue = queue.get_nowait()
			
			if "On" in status_queue:
				p = Process(target=heaterTimer,args=(queue,))
				p.start()
			if "Off" in status_queue:
				p.terminate()
			if "max_time" in status_queue:
				print "Max time reached. Heater turned OFF"
				logger.info("Max time reached. Heater turned OFF")
				heater.switchLow()
				fona.sendMessage(last_number,"Heater was turned off due to max time being reached")
		except Empty:
			pass
		#get messages on SIM Card
		messages = fona.getMessages()
		for message in messages:
			response = process_message(message[2],message[1])
			print response
