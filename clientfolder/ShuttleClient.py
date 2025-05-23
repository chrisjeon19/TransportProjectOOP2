import socket 
import time
import threading
import random

# !!! hello, all comments for our own reference will have "!!" and need to be deleted before submission

# Purpose: Wrapper class to handle all shuttle related movement and updates 
class ShuttleClient:
    def __init__(self, host='localhost', port=65000, xy=[40,0], canstart = False, start=False, done=False, status="Standby", current_stop="Penn Station", next_stop="JFK Airport", nextdeparture ="11:00"):
        self.host = host
        self.port = port
        self.xy = xy
        self.canstart = canstart # This is going to be updated by the server. If it hits 8AM, the Shuttle *can* start
        self.start = start          # But, the shuttle will not start until the 'start' command is sent 
        self.done = done
        self.status = status  # Will either be 'Active', 'Delayed', 'Standby'
        self.current_stop = current_stop
        self.next_stop = next_stop
        self.nextdeparture = nextdeparture
        self.waiting_at_jfk = False

    # Purpose: To log connections and commands to text file for future reference
    # Contract: writeFile(user_input: str) -> None
    def writeFile(self, input: str) -> None:
        with open("logs.txt", "a") as f:
            f.write(input + "\n")

    # Contract: getArrival(self)
    # Purpose: helper method to dynamically get accurate nextdeparture time         
    def getArrival(self):
        # Split the current time into hours and minutes
        hour, minute = map(int, self.nextdeparture.split(":"))
        # Add 50 minutes
        minute += 110
        if minute >= 60:
            hour += minute // 60
            minute = minute % 60
        # Format back to hour:minute 
        self.nextdeparture = f"{hour}:{minute:02d}"        

    # Contract: repr(self)
    # Purpose: Format for displaying location and status to server (TCP). This one is every minute 
    def __repr__(self):
        if self.status == "Standby":
            return f"[TCP] Shuttle S01 | Status: Standby | Eligible to start at 8:00 AM (awaiting command)"
        elif self.waiting_at_jfk:
            return f"[TCP] Shuttle S01 | Status: Arrived at JFK Airport | Next trip will start soon | Next arrival at JFK ~ {self.nextdeparture} AM"
        else:
            return f"[TCP] Shuttle S01 | En route to: {self.next_stop} | Status: {self.status} | Next arrival at JFK ~ {self.nextdeparture} AM"

    # Contract: ShuttleSim(self) 
    # Purpose: To simulate shuttlemovement
    def ShuttleSim(self):
        while True:     # !! we need to change this *while* to wait for the command from server controls 
            if self.status == "Active":
                time.sleep(1)
            elif self.status == "Delayed": 
                time.sleep(1.1)

            # Incrementing the coordinates by a random value between .1-.3
            random_num = random.uniform(0.1,0.3)
            self.xy[1] += random_num
        
            # if 30 minutes passed, the shuttle will reach JFK, represented by the '36'
            if self.xy[1] >= 36:
                self.current_stop = "JFK Airport"
                self.waiting_at_jfk = True  # This flag will let repr know the shuttle has arrived 

                self.getArrival() # calculate next arrival time 

                time.sleep(20) # will wait 20 minutes (or real life seconds) before a new shuttle starts
                self.waiting_at_jfk = False  # Now the shuttle is no longer waiting 

                self.xy[1] = 0 # this starts the shuttle back at penn 
                self.current_stop = "Penn Station"

    # Contract: update_statusTCP(self, client)
    # Purpose: Updates shuttle location and status via TCP to the central server every 60 seconds.
    def update_statusTCP(self, client):
        while True:
            # Display to the client along with send to server
            print(self.__repr__())
            client.send(self.__repr__().encode())
            time.sleep(60)

    # Purpose: Sends UDP beacon every 10 seconds to broadcast its latest coords for the public dashboard
    def UDP_beacon(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while True:
            client.sendto(f"[UDP] S01 -> Real-Time Location Update: Latitude: {self.xy[0]} Longitude: {round(self.xy[1], 2)} (JFK is [40,36])".encode(), (self.host, self.port))
            time.sleep(10)

    # Purpose : To receive server messages
    def receive_server_messages(self, client_socket):
        while not self.done:
            try:
                data = client_socket.recv(1024)
                if data:
                    message = data.decode()
                    print(f"[SERVER]: {message}")
                    self.command_handler(message)  # handle messages
            except:
                break

   # Purpose: To handle commands sent from the server
    def command_handler(self, message):
        parts = message.split()
        # If the message received is DELAY
        if parts[0] == "DELAY":
        
            self.status = "Delayed"
            print(f"Shuttle is now delayed.")
                
        # If the message received is REROUTE
        elif parts[0] == "REROUTE":
            print("Rerouting shuttle to alternate route")
            self.rerouted = True
        # If the message received is SHUTDOWN
        elif parts[0] == "SHUTDOWN":
            # Shutting down the simulation
            print("Shutting down shuttle simulation")
            self.done = True
        elif parts[0] == "START_ROUTE":
            # Resuming the route (bus needs server approval to start)
            print("Resuming route")
            self.justArrived = False
    
    # Purpose: handle sending messages back and forth with server 
    def send_message(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Connecting to the server
            client.connect((self.host, self.port))
            # Sending a message to indicate the shuttle is connected
            client.send('Vehicle CONNECTED: S01 (Shuttle) via TCP '.encode())

            # Start the TCP status update thread
            status_thread = threading.Thread(target=self.update_statusTCP, args=(client,))
            status_thread.start()
            self.writeFile("Vehicle S01 Shuttle is Connected via TCP")


            # Start the UDP beacon thread
            udp_thread = threading.Thread(target=self.UDP_beacon)
            udp_thread.start()
            self.writeFile("Vehicle S01 Shuttle is Connected via UDP")


            # Receiving messages from the server
            while not self.done:
                try:
                    msg = client.recv(1024).decode()
                    if msg:
                        print(f"Server: {msg}")  # Log the received message for debugging

                        if msg == "ready":
                            self.status = "Active"
                            print("[DEBUG] Shuttle status set to Active.")

                            # Start ShuttleSim thread if not already running
                            if not hasattr(self, 'shuttle_thread') or not self.shuttle_thread.is_alive():
                                self.shuttle_thread = threading.Thread(target=self.ShuttleSim)
                                self.shuttle_thread.start()
                                self.writeFile("Vehicle S01 Shuttle is [Active] via TCP")


                        elif msg == "delay":
                            self.status = "Delayed"
                        elif msg == "shutdown":
                            self.done = True
                        else:
                            print(f"Unknown command received: {msg}")
                except:
                    print("Error receiving message.")
                    break
        finally:
            print("Disconnected from the server!")
            client.close()

if __name__ == "__main__":
    client = ShuttleClient()
    threading.Thread(target=client.send_message).start()





