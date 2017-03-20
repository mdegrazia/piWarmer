# piWarmer
This is a Python scipt that controls an AC/DC relay attached to a Raspberry Pi with a space heater plugged in. There is an adafruit GSM Board that receives text messages using a Ting SIM card connected to the Raspberry Pi. When the Pi receives a text messgae it will turn the AC/DC relay on or off accordingly, thus powering the heater on or off. The following are a list of commands that can be sent to the Pi that will control the heater:

SMS Message | Action
------------ | -------------
ON | Turn the Relay/Heater on
OFF | Turn the Relay/Heater off
STATUS | Return status of the Relay/Heater (on or off)
SHUTDOWN | Shutdown the Pi


There is a configuration file, piWarmer.config that must be edited that contains phone numbers that are allowed to control the heater and a maximum time that the heater can run for if a "off" text messages is not received. Text messages can be upper or lowercase.

Use the piWarmer image (https://github.com/mdegrazia/piWarmer/releases)  for easy installation. See the Wiki (https://github.com/mdegrazia/piWarmer/wiki) for parts needed, assembly instructions and software installation instructions.
