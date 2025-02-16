from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.search import async_search
import asyncio
import socket
import time
from urllib.parse import urlparse
import logging
import aiohttp
import xml.etree.ElementTree as ET

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_device_info(session, location):
    """Gets detailed device information from a Sonos device."""
    try:
        async with session.get(location) as response:
            if response.status == 200:
                text = await response.text()
                root = ET.fromstring(text)
                device = root.find('.//{urn:schemas-upnp-org:device-1-0}device')
                if device is not None:
                    friendly_name = device.find('.//{urn:schemas-upnp-org:device-1-0}friendlyName')
                    room_name = device.find('.//{urn:schemas-upnp-org:device-1-0}roomName')
                    model_name = device.find('.//{urn:schemas-upnp-org:device-1-0}modelName')
                    zone_name = device.find('.//{urn:schemas-upnp-org:device-1-0}zoneName')

                    info = {
                        'name': friendly_name.text if friendly_name is not None else 'Unknown',
                        'room': room_name.text if room_name is not None else None,
                        'model': model_name.text if model_name is not None else 'Unknown',
                        'zone': zone_name.text if zone_name is not None else None
                    }
                    return info
    except Exception as e:
        logger.error(str(e))
    return None

async def get_zone_group_state(session, ip):
    """Gets the zone group state from a Sonos device."""
    try:
        soap_body = """<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:GetZoneGroupState xmlns:u="urn:schemas-upnp-org:service:ZoneGroupTopology:1"/>
            </s:Body>
        </s:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': '"urn:schemas-upnp-org:service:ZoneGroupTopology:1#GetZoneGroupState"'
        }

        async with session.post(
            f'http://{ip}:1400/ZoneGroupTopology/Control',
            data=soap_body,
            headers=headers
        ) as response:
            if response.status == 200:
                text = await response.text()
                root = ET.fromstring(text)
                state = root.find(".//ZoneGroupState")
                if state is not None and state.text:
                    return state.text
    except Exception as e:
        logger.error(str(e))
    return None

async def get_volume(session, ip):
    """Gets the current volume level from a Sonos device."""
    try:
        soap_body = """<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:GetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
                    <InstanceID>0</InstanceID>
                    <Channel>Master</Channel>
                </u:GetVolume>
            </s:Body>
        </s:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': '"urn:schemas-upnp-org:service:RenderingControl:1#GetVolume"'
        }

        async with session.post(
            f'http://{ip}:1400/MediaRenderer/RenderingControl/Control',
            data=soap_body,
            headers=headers
        ) as response:
            if response.status == 200:
                text = await response.text()
                root = ET.fromstring(text)
                namespaces = {
                    's': 'http://schemas.xmlsoap.org/soap/envelope/',
                    'u': 'urn:schemas-upnp-org:service:RenderingControl:1'
                }

                volume = root.find('.//u:GetVolumeResponse/CurrentVolume', namespaces)
                if volume is None:
                    volume = root.find('.//{*}CurrentVolume')
                if volume is None:
                    volume = root.find('.//CurrentVolume')

                if volume is not None:
                    return int(volume.text)
    except Exception as e:
        logger.error(str(e))
    return None

async def set_volume(session, ip, volume):
    """Sets the volume level for a Sonos device."""
    try:
        volume = max(0, min(100, volume))
        soap_body = f"""<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:SetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
                    <InstanceID>0</InstanceID>
                    <Channel>Master</Channel>
                    <DesiredVolume>{volume}</DesiredVolume>
                </u:SetVolume>
            </s:Body>
        </s:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': '"urn:schemas-upnp-org:service:RenderingControl:1#SetVolume"'
        }

        async with session.post(
            f'http://{ip}:1400/MediaRenderer/RenderingControl/Control',
            data=soap_body,
            headers=headers
        ) as response:
            return response.status == 200
    except Exception as e:
        logger.error(str(e))
    return False

async def get_transport_info(session, ip):
    """Gets the current transport state from a Sonos device."""
    try:
        soap_body = """<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:GetTransportInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
                    <InstanceID>0</InstanceID>
                </u:GetTransportInfo>
            </s:Body>
        </s:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': '"urn:schemas-upnp-org:service:AVTransport:1#GetTransportInfo"'
        }

        async with session.post(
            f'http://{ip}:1400/MediaRenderer/AVTransport/Control',
            data=soap_body,
            headers=headers
        ) as response:
            if response.status == 200:
                text = await response.text()
                root = ET.fromstring(text)
                namespaces = {
                    's': 'http://schemas.xmlsoap.org/soap/envelope/',
                    'u': 'urn:schemas-upnp-org:service:AVTransport:1'
                }

                state = root.find('.//u:GetTransportInfoResponse/CurrentTransportState', namespaces)
                if state is None:
                    state = root.find('.//{*}CurrentTransportState')
                if state is None:
                    state = root.find('.//CurrentTransportState')

                if state is not None:
                    return state.text
    except Exception as e:
        logger.error(str(e))
    return None

async def get_track_info(session, ip):
    """Gets the current track information from a Sonos device."""
    try:
        soap_body = """<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
                    <InstanceID>0</InstanceID>
                </u:GetPositionInfo>
            </s:Body>
        </s:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': '"urn:schemas-upnp-org:service:AVTransport:1#GetPositionInfo"'
        }

        async with session.post(
            f'http://{ip}:1400/MediaRenderer/AVTransport/Control',
            data=soap_body,
            headers=headers
        ) as response:
            if response.status == 200:
                text = await response.text()
                root = ET.fromstring(text)
                namespaces = {
                    's': 'http://schemas.xmlsoap.org/soap/envelope/',
                    'u': 'urn:schemas-upnp-org:service:AVTransport:1'
                }

                title = root.find('.//u:GetPositionInfoResponse/TrackMetaData', namespaces)
                if title is None:
                    title = root.find('.//{*}TrackMetaData')
                if title is None:
                    title = root.find('.//TrackMetaData')

                if title is not None and title.text:
                    try:
                        metadata = ET.fromstring(title.text)
                        title_elem = metadata.find('.//{*}title')
                        artist_elem = metadata.find('.//{*}creator')
                        album_elem = metadata.find('.//{*}album')

                        parts = []
                        if title_elem is not None and title_elem.text:
                            parts.append(title_elem.text)
                        if artist_elem is not None and artist_elem.text:
                            parts.append(artist_elem.text)
                        if album_elem is not None and album_elem.text:
                            parts.append(album_elem.text)

                        if parts:
                            return " - ".join(parts)
                    except ET.ParseError:
                        pass
    except Exception as e:
        logger.error(str(e))
    return None

async def get_mute(session, ip):
    """Gets the current mute state from a Sonos device."""
    try:
        soap_body = """<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:GetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
                    <InstanceID>0</InstanceID>
                    <Channel>Master</Channel>
                </u:GetMute>
            </s:Body>
        </s:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': '"urn:schemas-upnp-org:service:RenderingControl:1#GetMute"'
        }

        async with session.post(
            f'http://{ip}:1400/MediaRenderer/RenderingControl/Control',
            data=soap_body,
            headers=headers
        ) as response:
            if response.status == 200:
                text = await response.text()
                root = ET.fromstring(text)
                namespaces = {
                    's': 'http://schemas.xmlsoap.org/soap/envelope/',
                    'u': 'urn:schemas-upnp-org:service:RenderingControl:1'
                }

                mute = root.find('.//u:GetMuteResponse/CurrentMute', namespaces)
                if mute is None:
                    mute = root.find('.//{*}CurrentMute')
                if mute is None:
                    mute = root.find('.//CurrentMute')

                if mute is not None:
                    return mute.text == '1'
    except Exception as e:
        logger.error(str(e))
    return None

async def set_mute(session, ip, mute):
    """Sets the mute state for a Sonos device."""
    try:
        soap_body = f"""<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:SetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
                    <InstanceID>0</InstanceID>
                    <Channel>Master</Channel>
                    <DesiredMute>{1 if mute else 0}</DesiredMute>
                </u:SetMute>
            </s:Body>
        </s:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': '"urn:schemas-upnp-org:service:RenderingControl:1#SetMute"'
        }

        async with session.post(
            f'http://{ip}:1400/MediaRenderer/RenderingControl/Control',
            data=soap_body,
            headers=headers
        ) as response:
            return response.status == 200
    except Exception as e:
        logger.error(str(e))
    return False

async def discover_sonos_topology():
    """Discover Sonos devices and their organization using UPnP."""
    devices = []
    device_locations = set()
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.bind(('0.0.0.0', 0))

        SSDP_ADDR = "239.255.255.250"
        SSDP_PORT = 1900
        search_target = "urn:schemas-upnp-org:device:ZonePlayer:1"

        msearch_request = (
            'M-SEARCH * HTTP/1.1\r\n'
            f'HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n'
            'MAN: "ssdp:discover"\r\n'
            f'ST: {search_target}\r\n'
            'MX: 3\r\n'
            '\r\n'
        )

        sock.sendto(msearch_request.encode(), (SSDP_ADDR, SSDP_PORT))
        sock.settimeout(3)

        start_time = time.time()
        while time.time() - start_time < 1:
            try:
                data, addr = sock.recvfrom(1024)
                response = data.decode('utf-8')
                headers = dict(line.split(':', 1) for line in response.split('\r\n') if ':' in line)
                headers = {k.strip().lower(): v.strip() for k, v in headers.items()}

                if 'location' in headers:
                    location = headers['location']
                    if location not in device_locations:
                        parsed_url = urlparse(location)
                        ip = parsed_url.hostname
                        devices.append({
                            'name': 'Unknown',
                            'location': location,
                            'type': 'Unknown',
                            'ip': ip,
                            'groups': [],
                            'zones': []
                        })
                        device_locations.add(location)
            except socket.timeout:
                break
            except Exception as e:
                logger.error(str(e))
                continue

        await asyncio.sleep(0.5)

    finally:
        if sock:
            sock.close()

    if devices:
        async with aiohttp.ClientSession() as session:
            # First, get basic device info and volume for discovered devices
            filtered_devices = []
            for device in devices:
                info = await get_device_info(session, device['location'])
                if info and info.get('model', '').startswith('Sonos'):
                    device.update(info)
                    volume = await get_volume(session, device['ip'])
                    device['volume'] = volume if volume is not None else 0
                    filtered_devices.append(device)

            devices = filtered_devices

            # Then, get group information and additional devices from topology
            for device in devices:
                zone_state = await get_zone_group_state(session, device['ip'])
                if zone_state:
                    try:
                        state_root = ET.fromstring(zone_state)
                        all_members = state_root.findall(".//ZoneGroupMember")

                        # Create a map of existing devices by location for quick lookup
                        existing_devices = {d['location']: d for d in devices}

                        # Add any missing devices from the topology
                        for member in all_members:
                            location = member.get('Location')
                            if location and location not in device_locations:
                                parsed_url = urlparse(location)
                                ip = parsed_url.hostname
                                zone_name = member.get('ZoneName')
                                new_device = {
                                    'name': zone_name or 'Unknown',
                                    'location': location,
                                    'type': 'Unknown',
                                    'ip': ip,
                                    'room': zone_name,
                                    'groups': [],
                                    'zones': []
                                }
                                info = await get_device_info(session, location)
                                if info and info.get('model', '').startswith('Sonos'):
                                    new_device.update(info)
                                    volume = await get_volume(session, ip)
                                    new_device['volume'] = volume if volume is not None else 0
                                    devices.append(new_device)
                                    existing_devices[location] = new_device
                                    device_locations.add(location)

                        # Process group information
                        for group in state_root.findall(".//ZoneGroup"):
                            group_info = {
                                'id': group.get('ID'),
                                'coordinator': group.get('Coordinator'),
                                'members': []
                            }

                            for member in group.findall(".//ZoneGroupMember"):
                                member_info = {
                                    'uuid': member.get('UUID'),
                                    'zone_name': member.get('ZoneName'),
                                    'room_name': member.get('RoomName'),
                                    'location': member.get('Location'),
                                    'is_visible': member.get('Invisible', '0') == '0'
                                }

                                # Get volume for the member
                                member_ip = urlparse(member.get('Location')).hostname
                                if member_ip:
                                    # Always fetch the volume directly for each member
                                    volume = await get_volume(session, member_ip)
                                    member_info['volume'] = volume if volume is not None else 0
                                    logger.info(f"Set volume for member {member_ip} to {member_info['volume']}")

                                    # Update the volume in the existing device if we have one
                                    member_location = member.get('Location')
                                    if member_location in existing_devices:
                                        existing_devices[member_location]['volume'] = member_info['volume']

                                group_info['members'].append(member_info)

                            # Add group info to all member devices
                            for d in devices:
                                member_locations = [m['location'] for m in group_info['members']]
                                if d['location'] in member_locations:
                                    d['groups'].append(group_info)
                        break
                    except ET.ParseError:
                        pass

    devices.sort(key=lambda x: x.get('room', '').lower() if x.get('room') else x.get('name', '').lower())
    return devices

async def control_playback(session, ip, action):
    """Controls playback (Play, Pause, Next, Previous) on a Sonos device."""
    try:
        # First get current transport info to check the state
        current_state = await get_transport_info(session, ip)
        logger.info(f"Current transport state for {ip}: {current_state}")

        # Send the playback command
        soap_action = action
        if action in ["Next", "Previous"]:
            soap_action = f"{'Next' if action == 'Next' else 'Previous'}"  # Remove "Track" suffix
            soap_body = f"""<?xml version="1.0"?>
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                <s:Body>
                    <u:{soap_action} xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
                        <InstanceID>0</InstanceID>
                    </u:{soap_action}>
                </s:Body>
            </s:Envelope>"""
        elif action == "Play":
            soap_body = """<?xml version="1.0"?>
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                <s:Body>
                    <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
                        <InstanceID>0</InstanceID>
                        <Speed>1</Speed>
                    </u:Play>
                </s:Body>
            </s:Envelope>"""
        else:  # Pause
            soap_body = """<?xml version="1.0"?>
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                <s:Body>
                    <u:Pause xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
                        <InstanceID>0</InstanceID>
                    </u:Pause>
                </s:Body>
            </s:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': f'"urn:schemas-upnp-org:service:AVTransport:1#{soap_action}"'
        }

        async with session.post(
            f'http://{ip}:1400/MediaRenderer/AVTransport/Control',
            data=soap_body,
            headers=headers
        ) as response:
            text = await response.text()
            logger.info(f"Playback command response for {ip}: {text}")

            if response.status == 200 and '<s:Fault>' not in text:
                # For Next/Previous, wait a moment for the track to change and get track info
                if action in ["Next", "Previous"]:
                    await asyncio.sleep(0.5)  # Give the device a moment to update
                    track = await get_track_info(session, ip)
                    new_state = await get_transport_info(session, ip)
                    logger.info(f"New transport state for {ip}: {new_state}")
                    return new_state, track
                else:
                    # For Play/Pause, just get the new state
                    new_state = await get_transport_info(session, ip)
                    logger.info(f"New transport state for {ip}: {new_state}")
                    return new_state
            else:
                error_code = None
                try:
                    error_root = ET.fromstring(text)
                    error_code = error_root.find('.//{*}errorCode')
                    if error_code is not None:
                        error_code = error_code.text
                except:
                    pass
                logger.error(f"Playback command failed for {ip} with error code: {error_code}")
                return None
    except Exception as e:
        logger.error(f"Error controlling playback for {ip}: {str(e)}")
        return None
