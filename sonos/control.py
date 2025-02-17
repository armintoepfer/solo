import logging
import xml.etree.ElementTree as ET
import asyncio

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
