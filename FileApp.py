import sys
import os
import re
import json
import time
import copy
from threading import Thread
import traceback
from socket import *
from past.builtins import raw_input

IP_ADDRESS_FIELD = 'ip_address'
TCP_PORT_FIELD = 'tcp_port'
UDP_PORT_FIELD = 'udp_port'
FILE_NAMES_FIELD = 'file_names'
ONLINE_STATUS_FIELD = 'online_status'
FILENAME_STRING = "FILENAME"
OWNER_STRING = "OWNER"
IP_ADDRESS_STRING = "IP ADDRESS"
TCP_PORT_STRING = "TCP PORT"

class Client(object):

    def __init__(self, name, udp_port, tcp_port):
        self.client_name = name
        self.client_udp_port = udp_port
        self.client_tcp_port = tcp_port
        self.client_udp_socket = socket(AF_INET, SOCK_DGRAM)
        self.client_udp_socket.bind(('', int(self.client_udp_port)))
        self.client_tcp_socket = socket(AF_INET, SOCK_STREAM)
        self.hostname = gethostname()
        self.ip_address = gethostbyname(self.hostname)
        self.server_ip = None
        self.server_port = None
        self.file_names = None
        self.directory = None
        self.stop_tcp_listening = False
        # dictionary of dictionaries - client_name: {IP address, TCP port, UDP port, online status, file name}
        self.client_database = {}
        self.retry_exit = False  # exit flag to kill the retry thread once ACK is received

    def set_dir(self, directory):
        if self.client_name in list(self.client_database.keys()) and not self.client_database[self.client_name][ONLINE_STATUS_FIELD]:
            print(">>> [Client not online, operation allowed.]")
        else:
            if (os.path.exists(directory)):
                self.directory = os.path.abspath(directory)
                print(f">>> [Successfully set {self.directory} as the directory for searching offered files.]")
            else:
                print(f">>> [setdir failed: {directory} does not exist.]")

    def register(self, server_ip, server_port):
        try:
            self.server_ip = server_ip
            self.server_port = server_port
            new_client_info = {IP_ADDRESS_FIELD: self.ip_address, TCP_PORT_FIELD: self.client_tcp_port,
                               UDP_PORT_FIELD: self.client_udp_port, FILE_NAMES_FIELD: self.file_names,
                               ONLINE_STATUS_FIELD: True}
            new_client = {self.client_name: new_client_info}

            self.client_udp_socket.sendto(json.dumps({"REGISTER": new_client}).encode(),
                                          (self.server_ip, int(self.server_port)))

            reply_from_server, server_address = self.client_udp_socket.recvfrom(2048)

            if reply_from_server.decode() != "ACK":
                if reply_from_server.decode() == "Invalid":
                    print(">>> [Registration rejected: Client username already in use.]")
                    sys.exit()
                else:
                    info = json.loads(reply_from_server.decode())
                    operation = list(info.keys())[0]

                    if operation == "NEW_REGISTRATION":
                        self.update_client_database(info[operation])
                        print(">>> [Welcome, You are registered.]")
                        self.client_udp_socket.sendto("ACK".encode(), (server_ip, int(server_port)))
                    elif operation == "RE_REGISTRATION":
                        self.update_client_database(info[operation])
                        print(">>> [You are already registered.]")
                        self.client_udp_socket.sendto("ACK".encode(), (server_ip, int(server_port)))
        except Exception as e:
            print(f">>> [Error in registration]: {e}")
            traceback.print_exc()
            sys.exit()

    def update_client_database(self, client_info_in_server):
        for client in client_info_in_server.keys():
            self.client_database[client] = client_info_in_server[client]

    def listen_to_broadcast(self):
        while True:
            message, server_address = self.client_udp_socket.recvfrom(2048)
            if message.decode() != "ACK" and message.decode() != "Invalid":
                info = json.loads(message.decode())
                operation = list(info.keys())[0]

                if operation == "BROADCAST":
                    for client in info[operation].keys():
                        self.client_database[client] = info[operation][client]
                    print()
                    print(">>> [Client table updated.]")
                    print(">>> ", end='', flush=True)

    def deregister(self):
        if self.client_name in list(self.client_database.keys()) and not self.client_database[self.client_name][ONLINE_STATUS_FIELD]:
            print(">>> [Client is already offline/deregistered.]")
        else:
            try:
                self.client_udp_socket.sendto(json.dumps({"DEREGISTER": self.client_name}).encode(),
                                              (server_ip, int(server_port)))
                retry_thread = Thread(target=self.retry_udp, args=(json.dumps({"DEREGISTER": self.client_name}),))
                retry_thread.start()
                reply_from_server, server_address = self.client_udp_socket.recvfrom(2048)
                if reply_from_server.decode() == "ACK":
                    self.retry_exit = True
                    retry_thread.join()
                    self.retry_exit = False
                    self.client_database[self.client_name][ONLINE_STATUS_FIELD] = False
                    self.stop_tcp_listening = True
                    print(">>> [You are Offline. Bye.]")

                if self.client_database[self.client_name][ONLINE_STATUS_FIELD] is True and self.stop_tcp_listening is False:
                    print(">>> [Server not responding]")
                    sys.exit(">>> [Exiting]")

            except Exception as e:
                print(f">>> [Error in de-registration]: {e}")
                traceback.print_exc()
                sys.exit()


    def offer(self, file_names):
        if self.client_name in list(self.client_database.keys()) and not self.client_database[self.client_name][ONLINE_STATUS_FIELD]:
            print(">>> [Client not online, operation allowed.]")
        elif self.directory is None:
            print(">>> Directory not set. Set directory using setdir command.")
        else:
            current_filenames = self.client_database[self.client_name][FILE_NAMES_FIELD]
            if current_filenames is not None:
                current_filenames_lst = list(current_filenames)
                current_filenames_lst.extend(file_names)
                current_filenames = set(current_filenames_lst)
            else:
                current_filenames = set(file_names)

            # Converting set to list of file names before sending because 'set' is not json serializable
            self.client_udp_socket.sendto(json.dumps({"SET_FILENAMES": {self.client_name: list(current_filenames)}}).encode(),
                                          (self.server_ip, int(self.server_port)))

            retry_thread = Thread(target=self.retry_udp, args=(json.dumps({"SET_FILENAMES": {self.client_name: list(current_filenames)}}),))
            retry_thread.start()
            reply_from_server, server_address = self.client_udp_socket.recvfrom(2048)
            if reply_from_server.decode() == "ACK":
                self.retry_exit = True
                retry_thread.join()
                self.retry_exit = False
                self.client_database[self.client_name][FILE_NAMES_FIELD] = current_filenames
                print(">>> [Offer Message Received By Server]")

            if self.client_database[self.client_name][FILE_NAMES_FIELD] is None:
                print(">>> [No ACK from Server, please try again later.]")

    def retry_udp(self, json_message):
        start_time = time.time()
        retries = 0
        while True:
            if round(time.time() - start_time, 1) > 1 or retries > 2:
                break

            if self.retry_exit:
                break

            if round(time.time() - start_time, 1) == 0.5 or round(time.time() - start_time, 1) == 1:
                retries += 1
                print(f"Retrying {retries} times")
                self.client_udp_socket.sendto(json_message.encode(), (self.server_ip, int(self.server_port)))

    def file_list(self):
        if self.client_name in list(self.client_database.keys()) and not self.client_database[self.client_name][ONLINE_STATUS_FIELD]:
            print(">>> [Client not online, operation allowed.]")
        else:
            if not self.check_no_files_in_db():
                print(f"{FILENAME_STRING:15} {OWNER_STRING:15} {IP_ADDRESS_STRING:15} {TCP_PORT_STRING:15}")
                for client in self.client_database.keys():
                    if self.client_database[client][FILE_NAMES_FIELD] is not None and self.client_database[client][ONLINE_STATUS_FIELD]:
                        for filename in self.client_database[client][FILE_NAMES_FIELD]:
                            print(f"{filename:15} {client:15} {self.client_database[client][IP_ADDRESS_FIELD]:15} {self.client_database[client][TCP_PORT_FIELD]:15}")
            else:
                print(">>> [No files available for download at the moment.]")

    def check_no_files_in_db(self):
        if len(self.client_database) == 0:
            return True

        no_files_in_db = True
        for client in self.client_database.keys():
            if self.client_database[client][FILE_NAMES_FIELD] is not None:
                no_files_in_db = False
        return no_files_in_db

    def listen_for_file_request(self):
        self.client_tcp_socket.bind(('', int(self.client_tcp_port)))
        self.client_tcp_socket.listen(1)
        while not self.stop_tcp_listening:
            connectionSocket, addr = self.client_tcp_socket.accept()
            print(f"< Accepting connection request from {addr[0]}. >")
            message = json.loads(connectionSocket.recv(2048).decode())
            key = list(message.keys())[0]
            if key == "REQUEST":
                try:
                    file = self.directory.strip() + "/" + message[key][0].strip()
                    print(f"< Transferring {message[key][0]}... >")
                    with open(file, 'r') as file:
                        data = file.read().replace('\n', 'NEXT')
                    connectionSocket.send(data.encode())
                    print(f"< {message[key][0]} transferred successfully! >")
                except Exception as e:
                    print(f"< Error {e} in sending file >")
                    traceback.print_exc()
                    print(">>> ", end='', flush=True)
                    connectionSocket.send("ERROR".encode())
            print(f"< Connection with client {message[key][1]} closed>")
            print(">>> ", end='', flush=True)
            connectionSocket.close()

    def file_transfer(self, filename, client_with_file):
        if self.client_name in list(self.client_database.keys()) and not self.client_database[self.client_name][ONLINE_STATUS_FIELD]:
            print(">>> [Client not online, operation allowed.]")
        else:
            if client_with_file != self.client_name and filename in self.client_database[client_with_file][FILE_NAMES_FIELD] and self.client_database[client_with_file][ONLINE_STATUS_FIELD] is True:
                # if I use TCP socket of client, I get "OSError: [Errno 102] Operation not supported on socket"
                tcp_send_socket = socket(AF_INET, SOCK_STREAM)
                tcp_send_socket.connect((self.client_database[client_with_file][IP_ADDRESS_FIELD], int(self.client_database[client_with_file][TCP_PORT_FIELD])))
                print(f"< Connection with client {client_with_file} established. >")
                tcp_send_socket.send(json.dumps({"REQUEST": [filename, self.client_name]}).encode())
                print(f"< Downloading {filename}... >")
                file = tcp_send_socket.recv(2048).decode()
                if file != "ERROR":
                    for word in file.split():
                        if word == 'NEXT':
                            print('\n')
                        else:
                            print(word, end=' ')
                    print()
                    print(f"< {filename} downloaded successfully! >")
                else:
                    print("<Error in downloading file.>")
                print(f"< Connection with client {client_with_file} closed >")
                tcp_send_socket.close()
            else:
                print(">>> [Invalid Request]")


class Server(object):

    def __init__(self, port):
        self.port = port
        self.hostname = gethostname()
        self.ip_address = gethostbyname(self.hostname)
        print(f"Server host name: {self.hostname} IP address: {self.ip_address}")
        # dictionary of dictionaries - client_name: {IP address, TCP port, UDP port, online status, file names}
        self.client_database = {}
        self.server_socket = socket(AF_INET, SOCK_DGRAM)
        self.server_socket.bind((self.ip_address, int(port)))
        self.retry_exit = False  # exit flag to kill the retry thread once ACK is received
        self.spin_up()

    def spin_up(self):
        while True:
            message, client_address = self.server_socket.recvfrom(2048)

            if message.decode() != "ACK":
                info = json.loads(message.decode())
                operation = list(info.keys())[0]

                if operation == "REGISTER":
                    client_name = list(info[operation].keys())[0]
                    if client_name in list(self.client_database.keys()):
                        if not self.client_database[client_name][ONLINE_STATUS_FIELD]:
                            self.client_database[client_name][ONLINE_STATUS_FIELD] = True
                            database_to_send = self.convert_file_names_to_list() # JSON cannot serialize sets (filenames) so we need to convert to list
                            message_to_send = json.dumps({"RE_REGISTRATION": database_to_send})
                            self.server_socket.sendto(message_to_send.encode(), client_address)
                            self.broadcast(client_name)  # table update should not be broadcasted to client registering
                        else:
                            self.server_socket.sendto("Invalid".encode(), client_address)
                    else:
                        self.add_client_to_database(info[operation], client_name)
                        database_to_send = self.convert_file_names_to_list() # JSON cannot serialize sets (filenames) so we need to convert to list
                        message_to_send = json.dumps({"NEW_REGISTRATION": database_to_send})
                        self.server_socket.sendto(message_to_send.encode(), client_address)
                        self.broadcast(client_name)  # table update should not be broadcasted to client registering

                    retry_thread = Thread(target=self.retry_register, args=(client_address,))
                    retry_thread.start()
                    message, client_address = self.server_socket.recvfrom(2048)
                    if message.decode() == "ACK":
                        self.retry_exit = True
                        retry_thread.join()
                        self.retry_exit = False

                elif operation == "SET_FILENAMES":
                    client_name = list(info[operation].keys())[0]
                    self.set_files_for_client(client_name, info[operation][client_name])
                    self.server_socket.sendto("ACK".encode(), client_address)
                    self.broadcast(client_name) # table update should not be broadcasted to client offering files

                elif operation == "DEREGISTER":
                    client_name = info[operation]
                    self.client_database[client_name][ONLINE_STATUS_FIELD] = False
                    self.server_socket.sendto("ACK".encode(), client_address)
                    self.broadcast(client_name) # table update should not be broadcasted to client deregistering

    def convert_file_names_to_list(self):
        database_to_send = copy.deepcopy(self.client_database)
        for client in self.client_database.keys():
            if self.client_database[client][FILE_NAMES_FIELD] is not None:
                database_to_send[client][FILE_NAMES_FIELD] = list(database_to_send[client][FILE_NAMES_FIELD])
        return database_to_send

    def retry_register(self, client_address):
        start_time = time.time()
        retries = 0
        while True:
            if round(time.time() - start_time, 1) > 1 or retries > 2:
                break

            if self.retry_exit:
                break

            if round(time.time() - start_time, 1) == 0.5 or round(time.time() - start_time,
                                                                  1) == 1:
                retries += 1
                print(f"Retrying {retries} times")
                database_to_send = self.convert_file_names_to_list() # JSON cannot serialize sets (filenames) so we need to convert to list
                self.server_socket.sendto(json.dumps(database_to_send).encode(), client_address)

    def set_files_for_client(self, client_name, file_names):
        current_filenames = self.client_database[client_name][FILE_NAMES_FIELD]
        if current_filenames is not None:
            current_filenames_lst = list(current_filenames)
            current_filenames_lst.extend(file_names)
            current_filenames = set(current_filenames_lst)
        else:
            current_filenames = set(file_names)
        self.client_database[client_name][FILE_NAMES_FIELD] = current_filenames

    def add_client_to_database(self, info, client_name):
        new_client = {IP_ADDRESS_FIELD: info[client_name][IP_ADDRESS_FIELD],
                      TCP_PORT_FIELD: info[client_name][TCP_PORT_FIELD],
                      UDP_PORT_FIELD: info[client_name][UDP_PORT_FIELD], ONLINE_STATUS_FIELD: True,
                      FILE_NAMES_FIELD: info[client_name][FILE_NAMES_FIELD]}
        self.client_database[client_name] = new_client

    def broadcast(self, to_exclude):
        for client in self.client_database.keys():
            if self.client_database[client][ONLINE_STATUS_FIELD] and client != to_exclude:
                client_address = (
                    self.client_database[client][IP_ADDRESS_FIELD], int(self.client_database[client][UDP_PORT_FIELD]))
                database_to_send = self.convert_file_names_to_list() # JSON cannot serialize sets (filenames) so we need to convert to list
                self.server_socket.sendto(json.dumps({"BROADCAST": database_to_send}).encode(), client_address)


if __name__ == "__main__":
    # client -> client : TCP
    # client -> server : UDP
    try:
        mode = sys.argv[1]
        if mode == '-s':
            server_port = sys.argv[2]
            if int(server_port) < 1024 or int(server_port) > 65535:
                sys.exit("[Invalid server port]")
            server = Server(server_port)

        elif mode == '-c':
            client_name = sys.argv[2]
            server_ip = sys.argv[3]
            server_port = sys.argv[4]
            client_udp_port = sys.argv[5]
            client_tcp_port = sys.argv[6]

            if re.search("^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$", server_ip) is None:
                sys.exit("[Invalid server IP address]")

            if int(server_port) < 1024 or int(server_port) > 65535:
                sys.exit("[Invalid server port]")

            if int(client_udp_port) < 1024 or int(client_udp_port) > 65535:
                sys.exit("[Invalid client UDP port]")

            if int(client_tcp_port) < 1024 or int(client_tcp_port) > 65535:
                sys.exit("[Invalid client TCP port]")

            client = Client(client_name, client_udp_port, client_tcp_port)
            register_thread = Thread(target=client.register, args=(server_ip, server_port))
            register_thread.start()
            register_thread.join()
            broadcast_thread = Thread(target=client.listen_to_broadcast, args=(), daemon=True)
            broadcast_thread.start()
            listen_for_file_request = Thread(target=client.listen_for_file_request, args=(), daemon=True)
            listen_for_file_request.start()
            while True:
                user_input = raw_input(">>> ")
                input_split = user_input.split(" ")
                if input_split[0] == "setdir":
                    setdir_thread = Thread(target=client.set_dir, args=(input_split[1],))
                    setdir_thread.start()
                    setdir_thread.join()
                elif input_split[0] == "offer":
                    if len(input_split) > 1:
                        offer_files_thread = Thread(target=client.offer, args=(input_split[1:],))
                        offer_files_thread.start()
                        offer_files_thread.join()
                elif input_split[0] == "list":
                    list_files_thread = Thread(target=client.file_list, args=())
                    list_files_thread.start()
                    list_files_thread.join()
                elif input_split[0] == "request":
                    request_files_thread = Thread(target=client.file_transfer(input_split[1], input_split[2]))
                    request_files_thread.start()
                    request_files_thread.join()
                elif input_split[0] == "dereg":
                    dereg_thread = Thread(target=client.deregister, args=())
                    dereg_thread.start()
                    dereg_thread.join()
                elif input_split[0] == "rereg":
                    rereg_thread = Thread(target=client.register, args=(server_ip, server_port))
                    rereg_thread.start()
                    rereg_thread.join()
                else:
                    print(">>> Invalid operation.")
            broadcast_thread.join()
            listen_for_file_request.join()
    except Exception as e:
        print(f">>> [Error occurred]: {e}")
        traceback.print_exc()
        sys.exit(">>> [Exiting]")
