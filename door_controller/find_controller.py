import socket

# Standard Uhppote/Weigeng 64-byte get-controller command (Function 0x94)
msg = bytearray(64)
msg[0] = 0x17
msg[1] = 0x94

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.settimeout(3.0)
sock.sendto(msg, ("255.255.255.255", 60000))

try:
    data, addr = sock.recvfrom(1024)
    sn = int.from_bytes(data[4:8], byteorder="little")
    ip = ".".join(str(b) for b in data[8:12])
    mask = ".".join(str(b) for b in data[12:16])
    gateway = ".".join(str(b) for b in data[16:20])
    print(f"Found Controller: SN={sn} | IP={ip} | Subnet={mask} | Gateway={gateway}")
except socket.timeout:
    print("No controller responded. Check physical link or power supply.")