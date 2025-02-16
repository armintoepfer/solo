from flask import Flask, render_template, jsonify
from sonos import (
    discover_sonos_topology,
    get_volume,
    set_volume,
    get_zone_group_state,
    get_transport_info,
    get_track_info,
    control_playback,
    get_mute,
    set_mute
)
import aiohttp
import logging
from statistics import mean
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/")
async def index():
    try:
        topology = await discover_sonos_topology()
        return render_template("index.html", topology=topology, urlparse=urlparse)
    except Exception as e:
        logger.error(str(e))
        return "Error loading devices", 500

@app.route("/api/control/<ip>/<action>")
async def control_device(ip, action):
    """Handle device control requests."""
    try:
        async with aiohttp.ClientSession() as session:
            if action == "GetState":
                state = await get_transport_info(session, ip)
                if state:
                    return jsonify({"success": True, "state": state})
                return jsonify({"success": False, "error": "Could not get device state"})
            elif action == "GetTrackInfo":
                track = await get_track_info(session, ip)
                if track:
                    return jsonify({"success": True, "track": track})
                return jsonify({"success": False, "error": "Could not get track info"})
            elif action in ["Play", "Pause", "Next", "Previous"]:
                result = await control_playback(session, ip, action)
                if result:
                    if action in ["Next", "Previous"]:
                        new_state, track = result
                        return jsonify({"success": True, "state": new_state, "track": track})
                    else:
                        new_state = result
                        track = None
                        if new_state == "PLAYING":
                            track = await get_track_info(session, ip)
                        return jsonify({"success": True, "state": new_state, "track": track})
                return jsonify({"success": False, "error": f"Could not {action}"})
    except Exception as e:
        logger.error(str(e))
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/volume/<ip>/<action>")
async def control_volume(ip, action):
    """Handle volume control requests."""
    try:
        async with aiohttp.ClientSession() as session:
            if action == "get":
                volume = await get_volume(session, ip)
                if volume is not None:
                    return jsonify({"success": True, "volume": volume})
                return jsonify({"success": False, "error": "Could not get volume"})
            elif action == "mute":
                success = await set_mute(session, ip, True)
                if success:
                    return jsonify({"success": True})
                return jsonify({"success": False, "error": "Failed to mute"})
            elif action == "unmute":
                success = await set_mute(session, ip, False)
                if success:
                    return jsonify({"success": True})
                return jsonify({"success": False, "error": "Failed to unmute"})
            elif action.startswith("set/"):
                try:
                    volume = int(action.split("/")[-1])
                    success = await set_volume(session, ip, volume)
                    if success:
                        new_volume = await get_volume(session, ip)
                        return jsonify({"success": True, "volume": new_volume})
                    return jsonify({"success": False, "error": "Failed to set volume"})
                except ValueError:
                    return jsonify({"success": False, "error": "Invalid volume value"})
            elif action in ["up", "down"]:
                current_volume = await get_volume(session, ip)
                if current_volume is not None:
                    new_volume = current_volume + (2 if action == "up" else -2)
                    new_volume = max(0, min(100, new_volume))
                    success = await set_volume(session, ip, new_volume)
                    if success:
                        return jsonify({"success": True, "volume": new_volume})
                    return jsonify({"success": False, "error": "Failed to adjust volume"})
                return jsonify({"success": False, "error": "Could not get current volume"})
    except Exception as e:
        logger.error(str(e))
        return jsonify({"success": False, "error": str(e)})

    return jsonify({"success": False, "error": "Failed to control volume"})

@app.route("/api/group/volume/<ip>/<action>")
async def control_group_volume(ip, action):
    """Handle group volume control requests."""
    try:
        async with aiohttp.ClientSession() as session:
            current_volume = await get_volume(session, ip)
            if current_volume is None:
                return jsonify({"success": False, "error": "Could not get coordinator volume"})

            zone_state = await get_zone_group_state(session, ip)
            if not zone_state:
                return jsonify({"success": False, "error": "Could not get group state"})

            try:
                state_root = ET.fromstring(zone_state)
                coordinator_uuid = None
                group_members = []

                for group in state_root.findall(".//ZoneGroup"):
                    for member in group.findall(".//ZoneGroupMember"):
                        member_location = member.get('Location')
                        if member_location:
                            member_ip = urlparse(member_location).hostname
                            if member_ip == ip:
                                coordinator_uuid = group.get('Coordinator')
                                group_members = [m for m in group.findall(".//ZoneGroupMember")
                                              if m.get('Invisible', '0') == '0']
                                break
                    if coordinator_uuid:
                        break

                if not group_members:
                    return jsonify({"success": False, "error": "No group members found"})

                if action == "mean":
                    volumes = []
                    for member in group_members:
                        member_ip = urlparse(member.get('Location')).hostname
                        volume = await get_volume(session, member_ip)
                        if volume is not None:
                            volumes.append(volume)

                    if volumes:
                        mean_volume = round(mean(volumes))
                        results = []
                        for member in group_members:
                            member_ip = urlparse(member.get('Location')).hostname
                            success = await set_volume(session, member_ip, mean_volume)
                            if success:
                                results.append({"ip": member_ip, "volume": mean_volume})
                        return jsonify({"success": True, "results": results})

                elif action in ["up", "down"]:
                    results = []
                    for member in group_members:
                        member_ip = urlparse(member.get('Location')).hostname
                        current_volume = await get_volume(session, member_ip)
                        if current_volume is not None:
                            new_volume = current_volume + (2 if action == "up" else -2)
                            new_volume = max(0, min(100, new_volume))
                            success = await set_volume(session, member_ip, new_volume)
                            if success:
                                results.append({"ip": member_ip, "volume": new_volume})
                    return jsonify({"success": True, "results": results})

            except ET.ParseError as e:
                return jsonify({"success": False, "error": "Failed to parse group state"})

    except Exception as e:
        logger.error(str(e))
        return jsonify({"success": False, "error": str(e)})

    return jsonify({"success": False, "error": "Failed to control group volume"})

if __name__ == "__main__":
    import hypercorn.asyncio
    import asyncio

    config = hypercorn.Config()
    config.bind = ["0.0.0.0:5000"]
    asyncio.run(hypercorn.asyncio.serve(app, config))
