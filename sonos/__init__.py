"""
Sonos Control Library

This library provides functionality to discover and control Sonos speakers on a local network.
It uses UPnP/SOAP to communicate with Sonos devices and provides an async interface for all operations.
"""

import logging

from .discovery import discover_sonos_topology, get_zone_group_state
from .control import (
    get_device_info,
    get_volume,
    set_volume,
    get_mute,
    set_mute,
    get_transport_info,
    get_track_info,
    control_playback
)

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

__all__ = [
    'discover_sonos_topology',
    'get_zone_group_state',
    'get_device_info',
    'get_volume',
    'set_volume',
    'get_mute',
    'set_mute',
    'get_transport_info',
    'get_track_info',
    'control_playback'
]
