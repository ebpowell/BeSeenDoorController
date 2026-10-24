import os
import environs

import socket
import struct

def set_controller_network(serial_no: int, new_ip: str, subnet_mask: str, gateway: str):
    """
    Constructs and broadcasts a 64-byte Uhppote/Weigeng Function 0x96 frame.
    """
    packet = bytearray(64)
    
    # Header & Command
    packet[0] = 0x17        # Protocol Start of Frame / Type
    packet[1] = 0x96        # Function Code: Set Network Configuration
    
    # Serial Number (Bytes 4-7, Little-Endian unsigned 32-bit integer)
    struct.pack_into("<I", packet, 4, serial_no)
    
    # New IP Address (Bytes 8-11, 4 octets)
    packet[8:12] = socket.inet_aton(new_ip)
    
    # Subnet Mask (Bytes 12-15, 4 octets)
    packet[12:16] = socket.inet_aton(subnet_mask)
    
    # Default Gateway (Bytes 16-19, 4 octets)
    packet[16:20] = socket.inet_aton(gateway)
    
    # Magic Confirmation / Authorization Code (Bytes 20-23)
    # 0x55AAAA55 is the standard guard code required to commit network writes
    struct.pack_into("<I", packet, 20, 0x55AAAA55)

    # Broadcast on port 60000
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(3.0)
    
    print(f"Sending network configuration to SN {serial_no}...")
    sock.sendto(packet, ("255.255.255.255", 60000))
    
    try:
        response, addr = sock.recvfrom(1024)
        if len(response) == 64 and response[1] == 0x96:
            ack_sn = struct.unpack_from("<I", response, 4)[0]
            ack_ip = socket.inet_ntoa(response[8:12])
            ack_mask = socket.inet_ntoa(response[12:16])
            ack_gw = socket.inet_ntoa(response[16:20])
            status = response[20]  # 1 = Success, 0 = Failed / Rejected
            
            if status == 1 and ack_sn == serial_no:
                print(f"[SUCCESS] Controller {ack_sn} updated successfully!")
                print(f"  IP:      {ack_ip}")
                print(f"  Subnet:  {ack_mask}")
                print(f"  Gateway: {ack_gw}")
                return True
            else:
                print(f"[ERROR] Controller rejected configuration. Status code: {status}")
        else:
            print("[WARN] Received malformed or unexpected response.")
    except socket.timeout:
        print("[TIMEOUT] No confirmation received. Verify serial number and physical connection.")
    finally:
        sock.close()
    
    return False

if __name__ == "__main__":
    # Replace with the Serial Number retrieved from your discovery scan or the board label
    x = 5
    for value in os.getenv("serial_numbers", "").split(","):
        CONTROLLER_SERIAL = int(value.strip())
        
        # Define the new network configuration
        NEW_IP      = f"192.168.1.{x}"
        x += 1

    CONTROLLER_SERIAL = 423170127 
    
    # NEW_IP      = "192.168.1.6"
    NEW_SUBNET  = "255.255.255.0"
    NEW_GATEWAY = "192.168.1.1"
    
    set_controller_network(CONTROLLER_SERIAL, NEW_IP, NEW_SUBNET, NEW_GATEWAY)