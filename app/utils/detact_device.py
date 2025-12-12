import platform
import user_agents
from datetime import datetime
from user_agents import parse
import subprocess


def get_device_info(request):
    ua = user_agents.parse(request.headers.get('User-Agent'))
    device = {
        "ip": request.remote_addr,
        "browser": ua.browser.family,
        "browser_version": ua.browser.version_string,
        "os": ua.os.family,
        "os_version": ua.os.version_string,
        "device_type": "Mobile" if ua.is_mobile else "Tablet" if ua.is_tablet else "PC",
        "login_time": datetime.utcnow()
    }
    return device


def get_readable_device(user_agent_string: str, saved_name=None):
    ua = parse(user_agent_string)

    # If user saved custom model (HP, Dell, etc)
    if saved_name:
        return {
            "device_type": "Desktop" if ua.is_pc else "Mobile Phone" if ua.is_mobile else "Tablet",
            "device_name": saved_name,
            "os": ua.os.family,
            "browser": ua.browser.family
        }

    # Detect type
    if ua.is_mobile:
        device_type = "Mobile Phone"
    elif ua.is_tablet:
        device_type = "Tablet"
    elif ua.is_pc:
        device_type = "Desktop"
    else:
        device_type = "Unknown Device"

    # Mobile devices usually have brand + model
    if ua.device.brand or ua.device.model:
        device_name = f"{ua.device.brand} {ua.device.model}".strip()
    else:
        # Desktop fallback
        if ua.is_pc:
            device_name = f"{ua.os.family} PC"  # Windows PC, Mac PC
        else:
            device_name = "Unknown Model"

    return {
        "device_type": device_type,
        "device_name": device_name,
        "os": ua.os.family,
        "browser": ua.browser.family
    }

