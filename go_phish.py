#!/usr/bin/env python3

import os
import subprocess
import json
import urllib.request
import zipfile
import shutil

# === USER CONFIGURABLE VARIABLES ===
DOMAIN = "phish.example.com"
EMAIL = "admin@example.com"
GOPHISH_PORT = 3333
ADMIN_PORT = 8080
GOPHISH_DIR = "/opt/gophish"
CONFIG_FILE = os.path.join(GOPHISH_DIR, "config.json")

USE_DDNS = True
NAMECHEAP_API_USER = "yournamecheapusername"
NAMECHEAP_API_KEY = "yournamecheapapikey"
NAMECHEAP_DOMAIN = "example.com"
NAMECHEAP_HOST = "phish"
# ===================================

def run(command, cwd=None):
    print(f"[+] Running: {command}")
    subprocess.run(command, shell=True, check=True, cwd=cwd)

def install_dependencies():
    run("apt update && apt upgrade -y")
    run("apt install unzip curl wget jq ufw nginx certbot python3-certbot-nginx -y")

def update_dns_record():
    url = f"https://dynamicdns.park-your-domain.com/update?host={NAMECHEAP_HOST}&domain={NAMECHEAP_DOMAIN}&password={NAMECHEAP_API_KEY}"
    print(f"[+] Updating DNS via Namecheap API: {url}")
    urllib.request.urlopen(url)

def download_gophish():
    os.makedirs(GOPHISH_DIR, exist_ok=True)
    print("[+] Fetching GoPhish release URL...")
    api_url = "https://api.github.com/repos/gophish/gophish/releases/latest"
    with urllib.request.urlopen(api_url) as response:
        data = json.loads(response.read().decode())
        for asset in data["assets"]:
            if "linux-64" in asset["name"]:
                download_url = asset["browser_download_url"]
                break
        else:
            raise Exception("GoPhish Linux 64-bit release not found.")
    
    zip_path = os.path.join(GOPHISH_DIR, "gophish.zip")
    print(f"[+] Downloading GoPhish: {download_url}")
    urllib.request.urlretrieve(download_url, zip_path)

    print("[+] Extracting GoPhish...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(GOPHISH_DIR)
    os.remove(zip_path)

def modify_config():
    print("[+] Modifying config.json...")
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    config["admin_server"]["listen_url"] = f"0.0.0.0:{ADMIN_PORT}"
    config["phish_server"]["listen_url"] = f"0.0.0.0:{GOPHISH_PORT}"
    config["phish_server"]["use_tls"] = True
    config["phish_server"]["cert_path"] = f"/etc/letsencrypt/live/{DOMAIN}/fullchain.pem"
    config["phish_server"]["key_path"] = f"/etc/letsencrypt/live/{DOMAIN}/privkey.pem"

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def configure_firewall():
    run("ufw allow OpenSSH")
    run(f"ufw allow {GOPHISH_PORT}")
    run(f"ufw allow {ADMIN_PORT}")
    run("ufw --force enable")

def configure_nginx():
    print("[+] Creating NGINX reverse proxy config...")
    nginx_conf = f"""
server {{
    listen 80;
    server_name {DOMAIN};

    location / {{
        proxy_pass http://127.0.0.1:{GOPHISH_PORT};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}
"""
    with open("/etc/nginx/sites-available/gophish", "w") as f:
        f.write(nginx_conf)

    os.symlink("/etc/nginx/sites-available/gophish", "/etc/nginx/sites-enabled/gophish")
    run("nginx -t")
    run("systemctl restart nginx")

def setup_ssl():
    print("[+] Requesting SSL certificate...")
    run(f"certbot --nginx -d {DOMAIN} --non-interactive --agree-tos -m {EMAIL}")
    run("systemctl restart nginx")

def launch_gophish():
    print("[+] Launching GoPhish...")
    run(f"nohup {os.path.join(GOPHISH_DIR, 'gophish')} &>/var/log/gophish.log &")

def main():
    print("=== GoPhish Auto Deployment ===")
    if os.geteuid() != 0:
        print("[-] Please run this script as root.")
        exit(1)

    install_dependencies()

    if USE_DDNS:
        update_dns_record()

    download_gophish()
    modify_config()
    configure_firewall()
    configure_nginx()
    setup_ssl()
    launch_gophish()

    print("\n[+] GoPhish deployed successfully!")
    print(f"[+] Admin Panel: https://{DOMAIN}:{ADMIN_PORT}")
    print(f"[+] Phishing Server: https://{DOMAIN}/")

if __name__ == "__main__":
    main()
