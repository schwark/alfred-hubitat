# encoding: utf-8

import sys
import re
import argparse
from workflow.workflow import MATCH_ATOM, MATCH_STARTSWITH, MATCH_SUBSTRING, MATCH_ALL, MATCH_INITIALS, MATCH_CAPITALS, MATCH_INITIALS_STARTSWITH, MATCH_INITIALS_CONTAIN
from workflow import Workflow, ICON_WEB, ICON_NOTE, ICON_BURN, ICON_SWITCH, ICON_HOME, ICON_COLOR, ICON_INFO, ICON_SYNC, web, PasswordNotFound
from common import qnotify, error, hubitat_api, get_device, get_stored_data, discover_hub, get_device_capabilities, get_attributes, device_status
from time import sleep
from colorsys import rgb_to_hls, hls_to_rgb

log = None

def get_devices(wf, api_key, hub_id, hub_ip):
    """Retrieve all devices

    Returns a has of devices.

    """
    items = []
    result = hubitat_api(wf, api_key, hub_id, hub_ip, 'devices/all')
    if result and len(result) > 0:
        items.extend(result)

    return items

def get_colors():
    r = web.get('https://raw.githubusercontent.com/jonathantneal/color-names/master/color-names.json')
    flip_colors = r.json()
    colors = {v.lower().replace(' ',''): k for k, v in flip_colors.items()}
    return colors

def get_color(name, colors):
    name = name.lower().replace(' ','')
    if re.match('[0-9a-f]{6}', name):
        return name.upper()
    elif name in colors:
        return colors[name].upper()[1:]
    return ''

def get_color_hls(name, colors):
    hex = get_color(name, colors)
    r = int(hex[0:1], 16)
    g = int(hex[2:3], 16)
    b = int(hex[4:5], 16)
    (hue, level, saturation) = rgb_to_hls(r, g, b)
    return {"hue": hue, "saturation": saturation, "level": level}

def get_device_commands(device, commands):
    result = []
    capabilities = get_device_capabilities(device)
    for capability in capabilities:
        for command, map in commands.items():
            if capability == map['capability']:
                result.append(command) 
    return result

def preprocess_device_command(wf, api_key, hub_id, hub_ip, args):
    if 'toggle' == args.device_command:
        status = device_status(wf, api_key, hub_id, hub_ip, args.device_uid)
        if status and 'switch' in status:
            state = status['switch']
            log.debug("Toggle Switch state is "+state)
            if 'on' == state:
                args.device_command = 'off'
            else:
                args.device_command = 'on'
    if 'togglock' == args.device_command:
        status = device_status(wf, api_key, hub_id, hub_ip, args.device_uid)
        if status and 'lock' in status:
            state = status['lock']
            log.debug("Toggle Lock state is "+state)
            if 'locked' == state:
                args.device_command = 'unlock'
            else:
                args.device_command = 'lock'
    return args.device_command

def handle_device_commands(wf, api_key, hub_id, hub_ip, args, commands):
    if not args.device_uid or args.device_command not in commands.keys():
        return 
    args.device_command = preprocess_device_command(wf, api_key, hub_id, hub_ip, args)
    command = commands[args.device_command]

    device = get_device(wf, args.device_uid)
    device_name = device['label']
    capabilities = get_device_capabilities(device)
    if command['capability'] not in capabilities:
        error('Unsupported command for device')
        
    # eval all lambdas in arguments
    if 'arguments' in command and command['arguments']:
        for i, arg in enumerate(command['arguments']):
            if callable(arg):
                command['arguments'][i] = arg()
            elif isinstance(arg, dict):
                for key, value in arg.items():
                    if callable(value):
                        arg[key] = value()                

    data = command['arguments'] if 'arguments' in command else None
    log.debug("Executing Switch Command: "+device_name+" "+args.device_command)
    url = 'devices/'+args.device_uid+'/'+command['command']
    result = hubitat_api(wf, api_key, hub_id, hub_ip, url, data)
    success = False
    i = 0
    while(i < 2):
        if result:
            attributes = result
            if command['attribute'] in attributes:
                success = str(attributes[command['attribute']]) == str(command['arguments'][0] if 'arguments' in command and command['arguments'] else command['command'])
        if not success:
            sleep(1)
            i = i + 1
            result = device_status(wf, api_key, hub_id, hub_ip,args.device_uid)
        else:
            break
            
    if success:
        qnotify("Hubitat", device_name+" turned "+args.device_command+' '+(args.device_params[0] if args.device_params else ''))
    else:
        qnotify("Hubitat", device_name+" failed "+args.device_command+' '+(args.device_params[0] if args.device_params else ''))
    
    wf.logger.debug("Switch Command "+device_name+" "+args.device_command+" "+(args.device_params[0]+' ' if args.device_params else '')+("succeeded" if success else "failed"))
    return result

def main(wf):
    # retrieve cached devices and scenes
    devices = get_stored_data(wf ,'devices')
    colors = get_stored_data(wf, 'colors')

    # build argument parser to parse script args and collect their
    # values
    parser = argparse.ArgumentParser()
    # add an optional (nargs='?') --apikey argument and save its
    # value to 'apikey' (dest). This will be called from a separate "Run Script"
    # action with the API key
    parser.add_argument('--apikey', dest='apikey', nargs='?', default=None)
    parser.add_argument('--hubid', dest='hubid', nargs='?', default=None)
    parser.add_argument('--hubip', dest='hubip', nargs='?', default=None)
    parser.add_argument('--mode', dest='mode', nargs='?', default=None)
    parser.add_argument('--showstatus', dest='showstatus', nargs='?', default=None)
    # add an optional (nargs='?') --update argument and save its
    # value to 'apikey' (dest). This will be called from a separate "Run Script"
    # action with the API key
    parser.add_argument('--update', dest='update', action='store_true', default=False)
    # reinitialize 
    parser.add_argument('--reinit', dest='reinit', action='store_true', default=False)
    # device name, uid, command and any command params
    parser.add_argument('--device-uid', dest='device_uid', default=None)
    parser.add_argument('--device-command', dest='device_command', default='')
    parser.add_argument('--device-params', dest='device_params', nargs='*', default=[])
    # scene name, uid, command and any command params
    parser.add_argument('--scene-uid', dest='scene_uid', default=None)

    # add an optional query and save it to 'query'
    parser.add_argument('query', nargs='?', default=None)
    # parse the script's arguments
    args = parser.parse_args(wf.args)

    log.debug("args are "+str(args))

    words = args.query.split(' ') if args.query else []

    # list of commands
    commands = {
        'status': {
            'capability': 'global'
        },
        'on': {
                'component': 'main',
                'capability': 'Switch',
                'command': 'on',
                'attribute': 'switch'
        }, 
        'toggle': {
                'component': 'main',
                'capability': 'Switch',
                'command': 'on',
                'attribute': 'switch'
        }, 
        'off': {
                'component': 'main',
                'capability': 'Switch',
                'command': 'off',
                'attribute': 'switch'
        },
        'dim': {
                'component': 'main',
                'capability': 'SwitchLevel',
                'command': 'setLevel',
                'arguments': [
                    lambda: int(args.device_params[0]),
                ],
                'attribute': 'level'
        },
        'slevel': {
                'component': 'main',
                'capability': 'WindowShadeLevel',
                'command': 'setShadeLevel',
                'arguments': [
                    lambda: int(args.device_params[0]),
                ],
                'attribute': 'shadeLevel'
        },
        'open': {
                'component': 'main',
                'capability': 'WindowShade',
                'command': 'open',
                'attribute': 'windowShade'                
        },
        'close': {
                'component': 'main',
                'capability': 'WindowShade',
                'command': 'close',
                'attribute': 'windowShade'                
        },
        'lock': {
                'component': 'main',
                'capability': 'Lock',
                'command': 'lock',
                'attribute': 'lock'                
        }, 
        'unlock': {
                'component': 'main',
                'capability': 'Lock',
                'command': 'unlock',
                'attribute': 'lock'                
        },
        'togglock': {
                'component': 'main',
                'capability': 'Lock',
                'command': 'unlock',
                'attribute': 'lock'                
        },
        'color': {
                'component': 'main',
                'capability': 'ColorControl',
                'command': 'setColor',
                'arguments': [
                    {
                        'hex':lambda: get_color(args.device_params[0], colors)
                    }
                ],
                'attribute': 'colorTemperature'                
        },
        'mode': {
            'component': 'main',
            'capability': 'ThermostatMode',
            'command': 'setThermostatMode',
            'arguments': [
                lambda: str(args.device_params[0])
            ],
            'attribute': 'thermostatMode'
        },
        'heat': {
                'component': 'main',
                'capability': 'ThermostatHeatingSetpoint',
                'command': 'setHeatingSetpoint',
                'arguments': [
                    lambda: int(args.device_params[0]),
                ],
                'attribute': 'thermostatHeatingSetpoint'                
        },
        'cool': {
                'component': 'main',
                'capability': 'ThermostatCoolingSetpoint',
                'command': 'setCoolingSetpoint',
                'arguments': [
                    lambda: int(args.device_params[0]),
                ],
                'attribute': 'thermostatCoolingSetpoint'                
        }
    }

    # Reinitialize if necessary
    if args.reinit:
        wf.reset()
        wf.delete_password('hubitat_api_key')
        wf.delete_password('hubitat_hub_id')
        wf.delete_password('hubitat_hub_ip')
        qnotify('Hubitat', 'Workflow reinitialized')
        return 0

    if args.showstatus:
        if args.showstatus in ['on', 'off']:
            wf.settings['showstatus'] = args.showstatus
            wf.settings.save()
            qnotify('Hubitat', 'Show Status '+args.showstatus)
        return 0

    ####################################################################
    # Save the provided API key
    ####################################################################

    # save mode if that is passed in
    if args.mode:  # Script was passed a mode
        log.debug("saving mode "+args.mode)
        # save the mode
        wf.save_password('hubitat_mode', args.mode)
        qnotify('Hubitat', 'Mode '+args.mode+' Saved')
        return 0  # 0 means script exited cleanly

    # save API key if that is passed in
    if args.apikey:  # Script was passed an API key
        log.debug("saving api key "+args.apikey)
        # save the key
        wf.save_password('hubitat_api_key', args.apikey)
        qnotify('Hubitat', 'API Key Saved')
        return 0  # 0 means script exited cleanly

    # save Hub ID if that is passed in
    if args.hubid:  # Script was passed an Hub ID
        log.debug("saving hub id "+args.hubid)
        # save the key
        wf.save_password('hubitat_hub_id', args.hubid)
        qnotify('Hubitat', 'Hub ID Saved')
        return 0  # 0 means script exited cleanly

    # save Hub IP if that is passed in
    if args.hubip:  # Script was passed an Hub IP
        log.debug("saving hub IP "+args.hubip)
        # save the key
        wf.save_password('hubitat_hub_ip', args.hubip)
        qnotify('Hubitat', 'Hub IP Saved')
        return 0  # 0 means script exited cleanly

    ####################################################################
    # Check that we have an API key saved
    ####################################################################

    try:
        api_key = wf.get_password('hubitat_api_key')
    except PasswordNotFound:  # API key has not yet been set
        error('API Key not found')
        return 0

    try:
        mode = wf.get_password('hubitat_mode')
    except PasswordNotFound:  # Mode has not yet been set
        mode = 'auto'

    try:
        hub_id = wf.get_password('hubitat_hub_id')
    except PasswordNotFound:  # Hub ID has not yet been set
        error('Hub ID not found')
        return 0
    try:
        hub_ip = wf.get_password('hubitat_hub_ip')
    except PasswordNotFound:  # Hub IP has not yet been set
        hub_ip = discover_hub()
        if not hub_ip:
            error('Hub IP not found')
            return 0
        
    if 'cloud' == mode:
        hub_ip = None
    elif 'local' == mode:
        hub_id = None
        
    # Update devices if that is passed in
    if args.update:  
        # update devices and scenes
        devices = get_devices(wf, api_key, hub_id, hub_ip)
        colors = get_colors()
        wf.store_data('devices', devices)
        wf.store_data('colors', colors)
        qnotify('Hubitat', 'Devices and Scenes updated')
        return 0  # 0 means script exited cleanly

   # handle any device or scene commands there may be
    handle_device_commands(wf, api_key, hub_id, hub_ip, args, commands)


if __name__ == u"__main__":
    wf = Workflow(update_settings={
        'github_slug': 'schwark/alfred-hubitat'
    })
    log = wf.logger
    sys.exit(wf.run(main))
    