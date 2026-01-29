import os
import requests
import json
import subprocess

# --- CONFIGURATION ---
SHELLY_IP = "192.168.1.50"
DISCORD_WEBHOOK_URL = "VOTRE_URL"
MSG_ID_FILE = "./discord_msg_id.txt"
TEMP_THRESHOLD = 75  # Alerte si la température dépasse 75°C

# --- LOGIQUE DE TEMPÉRATURE ---
def get_temperature():
    # Lit la température système (divisée par 1000 pour avoir des Celsius)
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
        temp = int(f.read()) / 1000
    return round(temp, 1)

# --- LOGIQUE DE BATTERIE ---
def get_battery_info():
    cmd = "upower -i $(upower -e | grep 'BAT') | grep percentage | awk '{print $2}' | tr -d '%'"
    percent = int(subprocess.check_output(cmd, shell=True).decode().strip())
    return percent

def get_logic(percent):
    if percent >= 60:
        return None, 0, "OK (Pleine)"
    elif 50 <= percent <= 59:
        return [0, 100, 0], 15, "VERT"
    elif 40 <= percent <= 49:
        return [100, 100, 0], 30, "JAUNE"
    elif 30 <= percent <= 39:
        return [100, 50, 0], 45, "ORANGE"
    else:
        return [100, 0, 0], 60, "ROUGE (Critique)"

# --- ACTIONS ---
def control_shelly(color_rgb, minutes):
    if color_rgb is None:
        requests.get(f"http://{SHELLY_IP}/rpc/Switch.Set?id=0&on=false")
    else:
        payload = {
            "id": 0,
            "config": {"leds": {"mode": "switch", "colors": {"switch:0": {"on": {"rgb": color_rgb}, "off": {"rgb": [0,0,0]}}}}}
        }
        requests.post(f"http://{SHELLY_IP}/rpc/PLUGS_UI.SetConfig", json=payload)
        seconds = minutes * 60
        requests.get(f"http://{SHELLY_IP}/rpc/Switch.Set?id=0&on=true&toggle_after={seconds}")

def update_discord(percent, status, minutes, temp):
    # Gestion de l'ancien message
    if os.path.exists(MSG_ID_FILE):
        try:
            with open(MSG_ID_FILE, "r") as f:
                old_id = f.read().strip()
                requests.delete(f"{DISCORD_WEBHOOK_URL}/messages/{old_id}")
        except: pass

    # Alertes visuelles
    batt_emoji = "🔋" if percent > 30 else "🪫"
    temp_emoji = "🔥" if temp > TEMP_THRESHOLD else "🌡️"
    
    content = (
        f"**Rapport Système Serveur**\n"
        f"{batt_emoji} Batterie : `{percent}%` ({status})\n"
        f"{temp_emoji} Température CPU : `{temp}°C`\n"
        f"⏳ Recharge Shelly : `{minutes} min`"
    )
    
    res = requests.post(f"{DISCORD_WEBHOOK_URL}?wait=true", json={"content": content})
    if res.status_code == 200:
        with open(MSG_ID_FILE, "w") as f:
            f.write(res.json()['id'])

# --- EXECUTION ---
if __name__ == "__main__":
    p = get_battery_info()
    t = get_temperature()
    rgb, mins, label = get_logic(p)
    
    control_shelly(rgb, mins)
    update_discord(p, label, mins, t)