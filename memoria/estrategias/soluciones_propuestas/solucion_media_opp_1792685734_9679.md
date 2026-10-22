# Solution: [BOUNTY $130] Home Automation Stack — Home Assistant + Node-RED + Zigbee2MQTT + Mosquitto
- **Issue:** [illbnm/homelab-stack #7](https://github.com/illbnm/homelab-stack/issues/7)
- **Bounty:** $130 USDT
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Docker Compose Configuration (`stacks/automation/docker-compose.yml`)

```yaml
version: '3.8'

services:
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:2024.9.3
    container_name: automation-homeassistant
    restart: unless-stopped
    privileged: true
    network_mode: host # Required for UPnP/mDNS discovery and local casting
    # Alternative bridge mode (if host networking cannot be used):
    # networks:
    #   - internal
    #   - proxy
    # ports:
    #   - "8123:8123"
    environment:
      - TZ=UTC
    volumes:
      - ha-config:/config
      - /etc/localtime:/etc/localtime:ro
      - /run/dbus:/run/dbus:ro

  nodered:
    image: nodered/node-red:4.0.3
    container_name: automation-nodered
    restart: unless-stopped
    environment:
      - TZ=UTC
    volumes:
      - nodered-data:/data
    networks:
      - internal
      - proxy
    ports:
      - "1880:1880"
    depends_on:
      - mosquitto

  mosquitto:
    image: eclipse-mosquitto:2.0.19
    container_name: automation-mosquitto
    restart: unless-stopped
    volumes:
      - ../../config/mosquitto:/mosquitto/config
      - mosquitto-data:/mosquitto/data
      - mosquitto-log:/mosquitto/log
    networks:
      - internal
      - proxy
    ports:
      - "1883:1883"
      - "9001:9001"

  zigbee2mqtt:
    image: koenkk/zigbee2mqtt:1.40.2
    container_name: automation-zigbee2mqtt
    restart: unless-stopped
    volumes:
      - z2m-data:/app/data
      - /run/udev:/run/udev:ro
    environment:
      - TZ=UTC
    networks:
      - internal
      - proxy
    ports:
      - "8080:8080"
    depends_on:
      - mosquitto

  esphome:
    image: ghcr.io/esphome/esphome:2024.9.3
    container_name: automation-esphome
    restart: unless-stopped
    network_mode: host
    volumes:
      - esphome-config:/config
      - /etc/localtime:/etc/localtime:ro

volumes:
  ha-config:
  nodered-data:
  mosquitto-data:
  mosquitto-log:
  z2m-data:
  esphome-config:

networks:
  internal:
    internal: true
  proxy:
    external: true
```

---

## 2. Secure Mosquitto Configuration (`config/mosquitto/mosquitto.conf`)

```conf
listener 1883 0.0.0.0
allow_anonymous false
password_file /mosquitto/config/passwd
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
log_type error
log_type warning
log_type notice
log_type information
```
