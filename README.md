#Twitch plays Spot Robot

## Purpose
This code is meant as an example on how to use the python client provided by Boston Dynamic.  
We use their client to communicate with the Spot and send the commands we receive via Twitch chat to Spot.

## Prerequisites
- Have a Yaml file called config.yaml in your assets folder
- Have python 3.7 installed

## Configuration

### assets/config.yaml
```yaml
connection:
  host: <spot-ip>
  name: <app-name>
payload:
  guid: <payload-guid>
  secret: <payload-secret>
twitch:
  token: <twitch oauth token>
```

### install the requirements
```shell
pip install -r requirements.txt
```

## Three Parts

### 1. Spot Handler
The spot handler is used to manage the connection with the Spot.

### 2. Twitch Bot
Twitch bot connects to our channel and interprets the relevant commands, these commands are then send to the Spot Handler

### 3. Message server
We have to run a server in order to show status information about the Spot to the twitch stream. These pages are used by OBS to populate the stream.