import socket
import time
from urllib.parse import urlparse
import logging
import aiohttp
import xml.etree.ElementTree as ET
import asyncio

from .utils import get_xml_text
from .control import get_volume, get_device_info

logger = logging.getLogger(__name__)

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
                            'zones': [],
                            'volume': None
                        })
                        device_locations.add(location)
            except socket.timeout:
                break
            except Exception as e:
                logger.error(str(e))
                continue

        await asyncio.sleep(0.1)  # Reduced sleep time

    finally:
        if sock:
            sock.close()

    if not devices:
        return []

    async with aiohttp.ClientSession() as session:
        # First, get device info in parallel for all discovered devices
        info_tasks = []
        for device in devices:
            task = asyncio.create_task(get_device_info(session, device['location']))
            info_tasks.append((device, task))

        # Process device info results
        filtered_devices = []
        for device, task in info_tasks:
            try:
                info = await task
                if info and info.get('model', '').startswith('Sonos'):
                    device.update(info)
                    filtered_devices.append(device)
            except Exception as e:
                logger.error(f"Failed to get device info for {device['ip']}: {e}")

        if not filtered_devices:
            return []

        devices = filtered_devices
        existing_devices = {d['location']: d for d in devices}

        # Get zone state from the first available device
        zone_state = None
        for device in devices:
            try:
                zone_state = await get_zone_group_state(session, device['ip'])
                if zone_state:
                    break
            except Exception:
                continue

        if not zone_state:
            logger.error("Could not get zone state from any device")
            return devices

        try:
            state_root = ET.fromstring(zone_state)
            all_members = state_root.findall(".//ZoneGroupMember")

            # Add any missing devices from the topology
            new_device_tasks = []
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
                        'zones': [],
                        'volume': None
                    }
                    task = asyncio.create_task(get_device_info(session, location))
                    new_device_tasks.append((new_device, task))
                    device_locations.add(location)

            # Process new devices in parallel
            for new_device, task in new_device_tasks:
                try:
                    info = await task
                    if info and info.get('model', '').startswith('Sonos'):
                        new_device.update(info)
                        devices.append(new_device)
                        existing_devices[new_device['location']] = new_device
                except Exception as e:
                    logger.error(f"Failed to get device info for new device {new_device['ip']}: {e}")

            # Process groups and fetch volumes
            groups_info = {}  # Store group info by ID
            volume_tasks = []
            for group in state_root.findall(".//ZoneGroup"):
                group_id = group.get('ID')
                group_info = {
                    'id': group_id,
                    'coordinator': group.get('Coordinator'),
                    'members': []
                }
                groups_info[group_id] = group_info

                for member in group.findall(".//ZoneGroupMember"):
                    if member.get('Invisible', '0') != '0':
                        continue

                    member_info = {
                        'uuid': member.get('UUID'),
                        'zone_name': member.get('ZoneName'),
                        'room_name': member.get('RoomName'),
                        'location': member.get('Location'),
                        'is_visible': True
                    }

                    member_ip = urlparse(member.get('Location')).hostname
                    if member_ip:
                        task = asyncio.create_task(get_volume(session, member_ip))
                        volume_tasks.append((member_info, member_ip, task, group_info))

            # Wait for all volume fetches to complete
            for member_info, member_ip, task, group_info in volume_tasks:
                try:
                    volume = await task
                    member_info['volume'] = volume if volume is not None else 0
                    logger.info(f"Set volume for member {member_ip} to {member_info['volume']}")

                    # Update the volume in the existing device
                    member_location = member_info['location']
                    if member_location in existing_devices:
                        existing_devices[member_location]['volume'] = member_info['volume']

                    group_info['members'].append(member_info)
                except Exception as e:
                    logger.error(f"Failed to get volume for {member_ip}: {e}")
                    member_info['volume'] = 0
                    group_info['members'].append(member_info)

            # Add group info to devices
            for device in devices:
                for group in state_root.findall(".//ZoneGroup"):
                    group_id = group.get('ID')
                    member_locations = [m.get('Location') for m in group.findall(".//ZoneGroupMember")]
                    if device['location'] in member_locations and group_id in groups_info:
                        device['groups'].append(groups_info[group_id])

        except ET.ParseError as e:
            logger.error(f"Failed to parse zone state: {e}")

        # Ensure all devices have a volume value
        for device in devices:
            if device['volume'] is None:
                device['volume'] = 0

    devices.sort(key=lambda x: x.get('room', '').lower() if x.get('room') else x.get('name', '').lower())
    return devices

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
