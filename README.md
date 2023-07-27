# alfred-hubitat
Alfred  Workflow for Hubitat hubs
## Install

* Download .workflow file from [Releases](https://github.com/schwark/alfred-hubitat/releases)
* Can also be downloaded from github as a zip file, unzip the downloaded zip, cd into the zip directory, and create a new zip with all the files in that folder, and then renamed to Smartthings.alfredworkflow
* Or you can use the workflow-build script in the folder, using
```
chmod +x workflow-build
./workflow-build . 
```
* You will need a personal access token from the SmartThings Developer Portal at https://account.smartthings.com/tokens

## API Key

```
hb apikey <access-token>
```
This should only be needed once per install or after a reinit

## Device/Scene Update

```
hb update
```
This should be needed once at the install, and everytime you add or delete new devices and/or scenes

## Show Status Control

```
hb showstatus <on|off>
```
This setting controls whether or not the first line item of a single device search is the status of the device. Since querying the status adds latency, setting this to on takes a little longer for the command list for that device to populate. When this setting is off, a command called 'status' is added to the command list for the device that lets you query the status of the device on-demand. This 'off' setting is recommended for lower latency, but turning it on gives you status of the device simply by searching for the device


## Global Device Commands

```
hb <device-name> status
```
Queries the hub and provides key status elements for the device - can take a couple of seconds to populate due to live query. Non-actionable, for read only information


## Switch Commands

```
hb <switch-name> on|off|toggle
```
Turns the Switch on or off - clicking switch name autocompletes switch name and waits for command. If both name and command are provided, executes command and notifies upon success

## Dimmer Commands

```
hb <switch-name> dim <dim-level [0-100]>
```
Turns the dimmer to dim level specified - clicking light name autocompletes light name and waits for command. If both name and command are provided, executes command and notifies upon success

## Color Commands

```
hb <switch-name> color <rgbhex or color-name>
```
Turns the light to color specified - clicking light name autocompletes light name and waits for command. If both name and command are provided, executes command and notifies upon success


## Lock Commands

```
hb <lock-name> lock|unlock
```
Causes the lock to lock or unlock  - clicking lock name autocompletes lock name and waits for command. If both name and command are provided, executes command and notifies upon success

## Shade Commands

```
hb <shade-name> open|close
```
Causes the shade to open or close  - clicking shade name autocompletes shade name and waits for command. If both name and command are provided, executes command and notifies upon success


```
hb <shade-name> slevel <number - %age open>
```
Causes the shade to open to specified %age open (0 is closed, 100 is open)  - clicking shade name autocompletes shade name and waits for command. If both name and command and value are provided, executes command and notifies upon success


## Thermostat Commands

```
hb <thermostat-name> mode auto|heat|cool|off
```
```
hb <thermostat-name> heat <temp>
```
```
hb <thermostat-name> cool <temp>
```
Sets the thermostat mode, and heat setpoint and cool setpoints - clicking thermostat name autocompletes and waits for command. If both name and command and params are provided, executes command and notifies upon success


## Reinitialize

```
hb reinit
```
This should only be needed if you ever want to start again for whatever reason - removes all API keys, devices, scenes, etc.

## Update

```
hb workflow:update
```
An update notification should show up when an update is available, but if not invoking this should update the workflow to latest version on github

## Acknowledgements

Icons made by [Freepik](https://www.flaticon.com/authors/freepik) from [www.flaticon.com](https://www.flaticon.com)  
Icons also from [IconFinder](https://www.iconfinder.com/)