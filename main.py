import threading
from queue import Queue
import paramiko
import socket

url = ''
which_command = input("Which mode? set-inform, info, or set-default [info]: ")
if which_command == "set-inform":
    url = input("Enter your set-inform URL [http://unifi.fxbgtech.com:8080/inform]: ")
username_ = input("Enter device username [ubnt]: ")
password_ = input("Enter device password [ubnt]: ")
subnet_ = input("Enter subnet [192.168.1.0]: ")
#TODO: Accept CIDR notation to enable different subnet sizes
#TODO: Attempt to read the primary network adapter's current subnet to default to that

if url == '':
    url = "http://unifi.fxbgtech.com:8080/inform"
if which_command == '':
    which_command = 'info'
if username_ == '':
    USERNAME = 'ubnt'
else:
    USERNAME = username_
if password_ == '':
    PASSWORD = 'ubnt'
else:
    PASSWORD = password_
if subnet_ == '':
    SUBNET = '192.168.1.0'
else:
    SUBNET = subnet_

SUBNET = SUBNET[:-1]
PORT = 22
COMMAND = url
hostnames = [SUBNET + str(i) for i in range(1, 254)]
responsive_ips = []

def is_port_open(hostname):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)  # Set timeout to 1 second
    result = sock.connect_ex((hostname, PORT))
    sock.close()
    if result == 0:
        responsive_ips.append(hostname)

def execute_command(hostname, command, output_q):
    print(f"Starting... {hostname}")
    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname, port=PORT, username=USERNAME, password=PASSWORD)
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode('utf-8')
        output_q.put((hostname, output))
    except Exception as e:
        output_q.put((hostname, str(e)))
    finally:
        client.close()

def info(hostname, output_q):
    execute_command(hostname, "mca-cli <<EOF\ninfo\nquit\nEOF", output_q)

def set_default(hostname, output_q):
    execute_command(hostname, "mca-cli <<EOF\nset-default\nquit\nEOF", output_q)

def set_inform(hostname, output_q):
    execute_command(hostname, f"mca-cli <<EOF\nset-inform {COMMAND}\nquit\nEOF", output_q)

if __name__ == "__main__":
    output_q = Queue()
    scan_threads = []

    print("Scanning subnet for IPs that respond on port 22...")
    for hostname in hostnames:
        scan_thread = threading.Thread(target=is_port_open, args=(hostname,))
        scan_threads.append(scan_thread)
        scan_thread.start()

    for thread in scan_threads:
        thread.join()

    print("Beginning SSH connections to responsive IPs...")
    ssh_threads = []
    for hostname in responsive_ips:
        if which_command == "set-inform":
            my_thread = threading.Thread(target=set_inform, args=(hostname, output_q))
        elif which_command == "info":
            my_thread = threading.Thread(target=info, args=(hostname, output_q))
        elif which_command == "set-default":
            my_thread = threading.Thread(target=set_default, args=(hostname, output_q))
        ssh_threads.append(my_thread)
        my_thread.start()

    for thread in ssh_threads:
        thread.join()

    while not output_q.empty():
        hostname, output = output_q.get()
        print(f"{hostname}:\n{output}")

    input("Press any key to exit...")
