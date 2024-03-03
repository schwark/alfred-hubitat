# encoding: utf-8

import sys
import re
import argparse
from workflow.workflow import MATCH_ATOM, MATCH_STARTSWITH, MATCH_SUBSTRING, MATCH_ALL, MATCH_INITIALS, MATCH_CAPITALS, MATCH_INITIALS_STARTSWITH, MATCH_INITIALS_CONTAIN
from workflow import Workflow, ICON_WEB, ICON_NOTE, ICON_BURN, ICON_SWITCH, ICON_HOME, ICON_COLOR, ICON_INFO, ICON_SYNC, web, PasswordNotFound
from common import hubitat_api, get_stored_data, discover_hub, get_device_capabilities, get_attributes, device_color

log = None

def get_device_icon(device):
    capabilities = get_device_capabilities(device)
    if 'Thermostat' in capabilities:
        icon = 'thermostat'
    elif 'Lock' in capabilities:
        icon = 'lock'
    elif 'ColorControl' in capabilities:
        icon = 'color-light'
    elif 'SwitchLevel' in capabilities:
        icon = 'light'
    elif 'Light' in capabilities:
        icon = 'light'
    elif 'WindowShade' in capabilities:
        icon = 'shade'
    elif 'ContactSensor' in capabilities:
        icon = 'contact'
    elif 'Scene Activator' == device['type']:
        icon = 'scene'
    else:
        icon = 'switch'
    return 'icons/'+icon+'.png'

def get_color(name, colors):
    name = name.lower().replace(' ','')
    if re.match('[0-9a-f]{6}', name):
        return '#'+name.upper()
    elif name in colors:
        return colors[name].upper()
    return ''

def search_key_for_device(wf, device, commands):
    """Generate a string search key for a switch"""
    elements = []
    supported_capabilities = set(map(lambda x: x[1]['capability'], commands.items()))
    #wf.logger.debug("supported capabilities are : "+str(supported_capabilities))
    capabilities = get_device_capabilities(device)
    #wf.logger.debug("device capabilities are : "+str(capabilities))
    if len(list(set(capabilities) & supported_capabilities)) > 0:
        elements.append(device['label'])  # label of device
    #wf.logger.debug(elements)
    return u' '.join(elements)

def add_config_commands(args, config_commands):
    word = args.query.lower().split(' ')[0] if args.query else ''
    config_command_list = wf.filter(word, config_commands.keys(), min_score=80, match_on=MATCH_SUBSTRING | MATCH_STARTSWITH | MATCH_ATOM)
    if config_command_list:
        for cmd in config_command_list:
            wf.add_item(config_commands[cmd]['title'],
                        config_commands[cmd]['subtitle'],
                        arg=config_commands[cmd]['args'],
                        autocomplete=config_commands[cmd]['autocomplete'],
                        icon=config_commands[cmd]['icon'],
                        valid=config_commands[cmd]['valid'])
    return config_command_list

def get_device_commands(wf, device, commands):
    result = []
    if device['type'] == 'Scene Activator':
        result.append('on') 
    else:
        capabilities = get_device_capabilities(device)
        if not should_show_status(wf):
            capabilities.append('global')
        for capability in capabilities:
            for command, map in commands.items():
                if capability == map['capability']:
                    result.append(command)
                    
        # start with off if available                    
        if 'off' in result: 
            result.insert(0, result.pop(result.index('off')))                
        # start with on if available       
        if 'on' in result:
            result.insert(0, result.pop(result.index('on')))                
        # start with toggle if available
        if 'toggle' in result:
            result.insert(0, result.pop(result.index('toggle'))) 
        if 'togglock' in result:      
            result.insert(0, result.pop(result.index('togglock')))       

    return result

def get_filtered_devices(wf, query, devices, commands):
    result = wf.filter(query, devices, key=lambda x: search_key_for_device(wf, x, commands), min_score=80, match_on=MATCH_SUBSTRING | MATCH_STARTSWITH | MATCH_ATOM)
    # check to see if the first one is an exact match - if yes, remove all the other results
    if result and query and 'label' in result[0] and result[0]['label'] and result[0]['label'].lower() == query.lower():
        result = result[0:1]
    return result

def extract_commands(wf, args, devices, commands):
    words = args.query.split() if args.query else []
    args.device_command = ''
    args.device_params = []
    if devices:
        full_devices = get_filtered_devices(wf, args.query,  devices, commands)
        minusone_devices = get_filtered_devices(wf, ' '.join(words[0:-1]),  devices, commands)
        minustwo_devices = get_filtered_devices(wf, ' '.join(words[0:-2]),  devices, commands)

        if 1 == len(minusone_devices) and (0 == len(full_devices) or (1 == len(full_devices) and full_devices[0]['id'] == minusone_devices[0]['id'])):
            extra_words = args.query.replace(minusone_devices[0]['label'],'').split()
            if extra_words:
                wf.logger.debug("extract_commands: setting command to "+extra_words[0])
                args.device_command = extra_words[0]
                args.query = minusone_devices[0]['label']
        if 1 == len(minustwo_devices) and 0 == len(full_devices) and 0 == len(minusone_devices):
            extra_words = args.query.replace(minustwo_devices[0]['label'],'').split()
            if extra_words:
                args.device_command = extra_words[0]
                args.query = minustwo_devices[0]['label']
                args.device_params = extra_words[1:]
        wf.logger.debug("extract_commands: "+str(args))
    return args

def device_status(wf, api_key, hub_id, hub_ip, device, colors):
    caps = {
        'switch': {
            'tag': 'switch',
            'icon': u'🎚'
        },
        'level': {
            'tag': 'level',
            'icon': u'💡'
        },
        'lock': {
            'tag': 'lock',
            'icon': u'🔒'
        },
        'battery': {
            'tag': 'battery',
            'icon': u'🔋'
        },
        'colorTemperature': {
            'tag': 'colorTemperature',
            'icon': u'🎨'
        },
        'windowShade': {
            'tag': 'windowShade',
            'icon': u'🪟'
        },
        'windowShadeLevel': {
            'tag': 'shadeLevel',
            'icon': u'🌒'
        },
        'contactSensor': {
            'tag': 'contact',
            'icon': u'🔓'
        },
        'thermostat': [
        {
            'tag': 'heatingSetpoint',
            'icon': u'🔥'
        },
        {
            'tag': 'coolingSetpoint',
            'icon': u'❄️'
        },
        {
            'tag': 'thermostatOperatingState',
            'icon': u'🏃🏻‍♀️'
        },
        {
            'tag': 'temperature',
            'icon': u'🌡'
        },
        {
            'tag': 'thermostatFanMode',
            'icon': u'💨'
        },
        {
            'tag': 'thermostatMode',
            'icon': u'😰'
        }
        ]
    }
    subtitle = ''
    status = get_attributes(hubitat_api(wf, api_key, hub_id, hub_ip, '/devices/'+device['id']))
    if status:
        detail = status
        for cap in caps:
            if not cap in detail: continue
            metas = caps[cap]
            if not isinstance(metas, list):
                metas = [metas]
            for meta in metas:
                tag = meta['tag']
                if not tag in detail: continue
                value = detail[tag]
                if 'colorTemperature' == tag:
                    value = device_color(detail, colors)
                wf.logger.debug(device['label']+' '+cap+' '+tag+' '+str(value))
                subtitle += u'  '+meta['icon']+' '+str(value)
    return subtitle

def should_show_status(wf):
    return ('on' == wf.settings['showstatus']) if 'showstatus' in wf.settings else False

def main(wf):
    # retrieve cached devices and scenes
    devices = get_stored_data(wf, 'devices')
    colors = get_stored_data(wf, 'colors')

    # build argument parser to parse script args and collect their
    # values
    parser = argparse.ArgumentParser()
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
                'command': 'on'
        }, 
        'off': {
                'component': 'main',
                'capability': 'Switch',
                'command': 'off'
        },
        'toggle': {
                'component': 'main',
                'capability': 'Switch',
                'command': 'off'
        },
        'dim': {
                'component': 'main',
                'capability': 'SwitchLevel',
                'command': 'setLevel',
                'arguments': [
                    lambda: int(args.device_params[0]),
                ]
        },
        'slevel': {
                'component': 'main',
                'capability': 'WindowShadeLevel',
                'command': 'setShadeLevel',
                'arguments': [
                    lambda: int(args.device_params[0]),
                ]
        },
        'open': {
                'component': 'main',
                'capability': 'WindowShade',
                'command': 'open'
        },
        'close': {
                'component': 'main',
                'capability': 'WindowShade',
                'command': 'close'
        },
        'lock': {
                'component': 'main',
                'capability': 'Lock',
                'command': 'lock'
        }, 
        'unlock': {
                'component': 'main',
                'capability': 'Lock',
                'command': 'unlock'
        },
        'togglock': {
                'component': 'main',
                'capability': 'Lock',
                'command': 'unlock'
        },
        'view': {
                'component': 'main',
                'capability': 'ContactSensor',
                'command': 'view'
        },
        'color': {
                'component': 'main',
                'capability': 'ColorControl',
                'command': 'setColor',
                'arguments': [
                    {
                        'hex': lambda: get_color(args.device_params[0], colors)
                    }
                ]
        },
        'mode': {
            'component': 'main',
            'capability': 'Thermostat',
            'command': 'setThermostatMode',
            'arguments': [
                lambda: str(args.device_params[0])
            ]
        },
        'heat': {
                'component': 'main',
                'capability': 'Thermostat',
                'command': 'setHeatingSetpoint',
                'arguments': [
                    lambda: int(args.device_params[0]),
                ]
        },
        'cool': {
                'component': 'main',
                'capability': 'Thermostat',
                'command': 'setCoolingSetpoint',
                'arguments': [
                    lambda: int(args.device_params[0]),
                ]
        }
    }

    command_params = {
        'color': {
            'values': colors.keys() if colors else [],
            'regex': '[0-9a-f]{6}'
        },
        'mode': {
            'values': ['auto','heat','cool','off']
        }
    }

    config_commands = {
        'update': {
            'title': 'Update Devices and Scenes',
            'subtitle': 'Update the devices and scenes from Hubitat',
            'autocomplete': 'update',
            'args': ' --update',
            'icon': ICON_SYNC,
            'valid': True
        },
        'apikey': {
            'title': 'Set API Key',
            'subtitle': 'Set api key to personal access token from Hubitat',
            'autocomplete': 'apikey',
            'args': ' --apikey '+(words[1] if len(words)>1 else ''),
            'icon': ICON_WEB,
            'valid': len(words) > 1
        },
        'hubid': {
            'title': 'Set hub ID',
            'subtitle': 'Set hub id to personal access token from Hubitat',
            'autocomplete': 'hubid',
            'args': ' --hubid '+(words[1] if len(words)>1 else ''),
            'icon': ICON_WEB,
            'valid': len(words) > 1
        },
        'ip': {
            'title': 'Set hub IP',
            'subtitle': 'Set hub ip to local IP for Hubitat hub',
            'autocomplete': 'ip',
            'args': ' --hubip '+(words[1] if len(words)>1 else ''),
            'icon': ICON_WEB,
            'valid': len(words) > 1
        },
        'mode': {
            'title': 'Set access mode',
            'subtitle': 'Set access mode to local or cloud',
            'autocomplete': 'mode',
            'args': ' --mode '+(words[1] if len(words)>1 else ''),
            'icon': ICON_WEB,
            'valid': len(words) > 1 and words[1] in ['local', 'cloud']
        },
        'showstatus': {
            'title': 'Turn on/off showing of status when single device',
            'subtitle': 'Adds latency. When off, can still get info via status command',
            'autocomplete': 'showstatus',
            'args': ' --showstatus '+(words[1] if len(words)>1 else ''),
            'icon': ICON_INFO,
            'valid': len(words) > 1 and words[1] in ['on', 'off']
        },
        'reinit': {
            'title': 'Reinitialize the workflow',
            'subtitle': 'CAUTION: this deletes all scenes, devices and apikeys...',
            'autocomplete': 'reinit',
            'args': ' --reinit',
            'icon': ICON_BURN,
            'valid': True
        },
        'workflow:update': {
            'title': 'Update the workflow',
            'subtitle': 'Updates workflow to latest github version',
            'autocomplete': 'workflow:update',
            'args': '',
            'icon': ICON_SYNC,
            'valid': True
        }
    }

    # add config commands to filter
    add_config_commands(args, config_commands)

    ####################################################################
    # Check that we have an API key saved
    ####################################################################

    try:
        api_key = wf.get_password('hubitat_api_key')
    except PasswordNotFound:  # API key has not yet been set
        wf.add_item('No API key set...',
                    'Please use hb apikey to set your Hubitat API key.',
                    valid=False,
                    icon=ICON_NOTE)
        wf.send_feedback()
        return 0

    try:
        mode = wf.get_password('hubitat_mode')
    except PasswordNotFound:  # mode has not yet been set
        mode = 'local'

    if 'cloud' == mode:
        hub_ip = None
        try:
            hub_id = wf.get_password('hubitat_hub_id')
        except PasswordNotFound:  # Hub ID has not yet been set
            wf.add_item('No Hub ID set in cloud mode...',
                        'Please use hb hubid to set your Hubitat Hub ID or revert to local mode',
                        valid=False,
                        icon=ICON_NOTE)
            wf.send_feedback()
            return 0
    else:
        hub_id = None
        try:
            hub_ip = wf.get_password('hubitat_hub_ip')
        except PasswordNotFound:  # Hub IP has not yet been set
            try:
                hub_ip = None #discover_hub()
            except:
                pass
            wf.logger.debug('discovered hub ip is '+(hub_ip or ''))
            if not hub_ip:
                wf.add_item('No Hub IP set in local mode...',
                            'Please use hb ip to set your Hubitat Hub IP or revert to cloud mode',
                            valid=False,
                            icon=ICON_NOTE)
                wf.send_feedback()
                return 0
        
    # since this i now sure to be a device/scene query, fix args if there is a device/scene command in there
    args = extract_commands(wf, args, devices, commands)
 
    # update query post extraction
    query = args.query


    ####################################################################
    # View/filter devices or scenes
    ####################################################################

    # Check for an update and if available add an item to results
    if wf.update_available:
        # Add a notification to top of Script Filter results
        wf.add_item('New version available',
            'Action this item to install the update',
            autocomplete='workflow:update',
            icon=ICON_INFO)

    if not devices or len(devices) < 1:
        wf.add_item('No Devices...',
                    'Please use hb update - to update your Hubitat devices.',
                    valid=False,
                    icon=ICON_NOTE)
        wf.send_feedback()
        return 0

    # If script was passed a query, use it to filter posts
    if query:
        devices = get_filtered_devices(wf, query, devices, commands)

        if devices:
            args.device_command = 'on' if 1 == len(devices) and devices[0]['type'] == 'Scene Activator' else args.device_command

            if 1 == len(devices) and should_show_status(wf):
                device = devices[0]
                wf.add_item(title=device['label'],
                        subtitle=device_status(wf, api_key, hub_id, hub_ip, device, colors),
                        arg=' --device-uid '+device['id']+' --device-command '+args.device_command,
                        autocomplete=device['label']+' '+args.device_command,
                        valid=False,
                        icon=get_device_icon(device))
            if 1 == len(devices) and (not args.device_command or args.device_command not in commands):
                # Single device only, no command or not complete command yet so populate with all the commands
                device = devices[0]
                device_commands = get_device_commands(wf, device, commands)
                device_commands = list(filter(lambda x: x.startswith(args.device_command), device_commands))
                log.debug('args.device_command is '+args.device_command)
                for command in device_commands:
                    wf.add_item(title=device['label'],
                            subtitle='Turn '+device['label']+' '+command+' '+(' '.join(args.device_params) if args.device_params else ''),
                            arg=' --device-uid '+device['id']+' --device-command '+command+' --device-params '+(' '.join(args.device_params)),
                            autocomplete=device['label']+' '+command,
                            valid=bool('status' != command and ('arguments' not in commands[command] or args.device_params)),
                            icon=get_device_icon(device))
            elif 1 == len(devices) and (args.device_command and args.device_command in commands and args.device_command in command_params):
                # single device and has command already - populate with params?
                device = devices[0]
                param_list = command_params[args.device_command]['values']
                param_start = args.device_params[0] if args.device_params else ''
                param_list = list(filter(lambda x: x.startswith(param_start), param_list))
                param_list.sort()
                check_regex = False
                if not param_list and command_params[args.device_command]['regex']:
                    param_list.append(args.device_params[0].lower())
                    check_regex = True
                for param in param_list:
                    wf.add_item(title=device['label'],
                            subtitle='Turn '+device['label']+' '+args.device_command+' '+param,
                            arg=' --device-uid '+device['id']+' --device-command '+args.device_command+' --device-params '+param,
                            autocomplete=device['label']+' '+args.device_command,
                            valid=bool(not check_regex or re.match(command_params[args.device_command]['regex'], param)),
                            icon=get_device_icon(device))
            elif 1 == len(devices) and ('status' == args.device_command):
                device = devices[0]
                wf.add_item(title=device['label'],
                        subtitle=device_status(wf, api_key, hub_id, hub_ip, device, colors),
                        arg=' --device-uid '+device['id']+' --device-command '+args.device_command,
                        autocomplete=device['label']+' '+args.device_command,
                        valid=False,
                        icon=get_device_icon(device))
            else:
                # Loop through the returned devices and add an item for each to
                # the list of results for Alfred
                for device in devices:
                    command = 'on' if device['type'] == 'Scene Activator' else args.device_command
                    wf.add_item(title=device['label'],
                            subtitle='Turn '+device['label']+' '+command+' '+(' '.join(args.device_params) if args.device_params else ''),
                            arg=' --device-uid '+device['id']+' --device-command '+command+' --device-params '+(' '.join(args.device_params)),
                            autocomplete=device['label'],
                            valid=bool(command in commands),
                            icon=get_device_icon(device))

        # Send the results to Alfred as XML
        wf.send_feedback()
    return 0


if __name__ == u"__main__":
    wf = Workflow(update_settings={
        'github_slug': 'schwark/alfred-hubitat'
    })
    log = wf.logger
    sys.exit(wf.run(main))
    