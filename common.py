from workflow import web
import json
import subprocess
from urllib.parse import quote_plus
from math import log, pow
from colorsys import rgb_to_hls, hls_to_rgb
import subprocess

def get_mode(wf, ip):
    if not ip: return 'cloud'
    ip = ip.strip()
    output = (subprocess.check_output("ping -o -c 3 -W 3000 "+ip, shell=True)).decode('utf-8')
    wf.logger.debug(output)
    return 'local' if (output and "bytes from "+ip in output) else 'cloud'

'''
import socket
import struct
import dpkt, dpkt.dns

def mdns_query(name):
    ip = None
    UDP_IP="0.0.0.0"
    UDP_PORT=5353
    MCAST_GRP = '224.0.0.251'
    sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind( (UDP_IP,UDP_PORT) )
    #join the multicast group
    mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    for host in [name][::-1]:
        # the string in the following statement is an empty query packet
        dns = dpkt.dns.DNS(bytes('\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01','utf-8'))
        dns.qd[0].name=host+'.local'
        sock.sendto(dns.pack(),(MCAST_GRP,UDP_PORT))
    sock.settimeout(0.05)
    while True:
        try:
            m=sock.recvfrom( 1024 );#print '%r'%m[0],m[1]
            try:
                dns = dpkt.dns.DNS(m[0])
                if len(dns.an)>0 and dns.an[0].type == dpkt.dns.DNS_A:
                    ip = socket.inet_ntoa(dns.an[0].rdata)
            except dpkt.UnpackError:
                pass
        except socket.timeout:
            break
    return ip
'''

def mdns_query_shell(name):
    return subprocess.check_output(['dig','-p','5353', '+answer', '@224.0.0.251', name+'.local', '+short']).decode('utf-8')
 
def discover_hub():
    return mdns_query_shell('hubitat')
 
def qnotify(title, text):
    print(text)

def error(text):
    print(text)
    exit(0)

def get_device(wf, device_uid):
    devices = wf.stored_data('devices')
    return next((x for x in devices if device_uid == x['id']), None)

def hubitat_api(wf, api_key, hub_id, hub_ip, url, data=None):
    mode = get_mode(wf, hub_ip)
    wf.logger.debug("using mode "+mode)
    base_url = 'https://cloud.hubitat.com/api/'+hub_id+'/apps/5/' if ('cloud' == mode and hub_id) else 'http://'+hub_ip+'/apps/api/5/'
    url = base_url+url
    headers = {'Accept':"application/json"}
    params = {'access_token': api_key}
    r = None
    args = ','.join(map(lambda x: quote_plus(json.dumps(x) if isinstance(x, dict) else str(x)), data)) if data else ''
    url = url+('/' if args else '')+args
    r = web.get(url, params, headers)

    wf.logger.debug("hubitat_api: url:"+url+", headers: "+str(headers)+", params: "+str(params))
    # throw an error if request failed
    # Workflow will catch this and show it to the user
    r.raise_for_status()

    # Parse the JSON returned by pinboard and extract the posts
    result = r.json()
    wf.logger.debug(str(result))
    return result    

def get_device_capabilities(device):
    return device['capabilities'] if 'capabilities' in device else []

def get_stored_data(wf, name):
    data = {}
    try:
        data = wf.stored_data(name)
    except ValueError:
        pass
    return data

# From http://www.tannerhelland.com/4435/convert-temperature-rgb-algorithm-code/
def colorTemperatureToRGB(kelvin):
    temp = kelvin / 100

    if( temp <= 66 ):
        red = 255
        
        green = temp
        green = 99.4708025861 * log(green) - 161.1195681661
        
        if( temp <= 19):
            blue = 0
        else:
            blue = temp-10
            blue = 138.5177312231 * log(blue) - 305.0447927307
    else:
        red = temp - 60
        red = 329.698727446 * pow(red, -0.1332047592)
        
        green = temp - 60
        green = 288.1221695283 * pow(green, -0.0755148492 )

        blue = 255

    return "%x%x%x" % (
        clamp(red,   0, 255),
        clamp(green, 0, 255),
        clamp(blue,  0, 255))
    
def clamp( x, min, max ):
    if(x<min):
        return min
    if(x>max):
        return max

    return int(x)

def get_attributes(device):
    attributes = {}
    if 'id' in device and 'attributes' in device:
        for attribute in device['attributes']:
            attributes[attribute['name']] = attribute['currentValue']
    return attributes     

def device_color(attributes, colors):
    rgb = None
    if 'RGB' in attributes and attributes['RGB']:
        rgb = attributes['RGB']
    if not rgb and 'colorName' in attributes and attributes['colorName']:
        return attributes['colorName']
    if not rgb and 'hue' in attributes and attributes['hue'] and 'saturation' in attributes and attributes['saturation'] and 'level' in attributes and attributes['level']:
        (r, g, b) = hls_to_rgb(attributes['hue'], attributes['level'], attributes['saturation'])
        rgb = "%x%x%x" % int(r), int(g), int(b)
    if not rgb and 'colorTemperature' in attributes and attributes['colorTemperature']:
        rgb = colorTemperatureToRGB(attributes['colorTemperature'])
    if rgb:
        inv_colors = {v: k for k, v in colors.items()}
        if rgb in inv_colors:
            return inv_colors['#'+rgb]
    return rgb
        
def device_status(wf, api_key, hub_id, hub_ip, id):
    result = hubitat_api(wf, api_key, hub_id, hub_ip, '/devices/'+id)
    result = get_attributes(result) if result else None
    return result
