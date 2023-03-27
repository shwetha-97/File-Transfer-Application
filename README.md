# File-Transfer-Application
A File Transfer Application developed in Python consisting of a server and multiple clients that can transfer files among each other

**A.	Introduction**
The project is a file transfer application which can work with multiple clients and a server. The server tracks and maintains a database of all registered clients, the files they offer, their connection ports and IP addresses and their online/offline status. Every client maintains its own database but the server acts as the source of truth. The clients use the information in the database to initiate file transfer and communicate with each other directly. All client-server interactions happen over UDP and all client-client interactions happen over TCP.

**B.	Implementation**
The project is written in Python. The client and server working, and functionalities are distributed among 2 classes – Client and Server respectively. 

The server continuously listens to the client and processes the incoming messages based on the operation – REGISTER, SET_FILENAMES and DEREGISTER. It updates its database for every operation, accepts acknowledgements (ACK) from client and handles retries for registration. It broadcasts the client database to all online clients whenever there is a change in the database. The server fields are – port, UDP socket, IP address on which it runs and client database.

The client class contains methods for each of the functionalities allowed in the file transfer application. The methods are called from the ‘main’ section whenever the user calls the respective command. Each client object has its own set of fields – name, UDP and TCP ports and sockets, IP address, server IP address and port, files offered, directory where files are located and database of clients.

The ‘main’ section of the code where execution starts has a while True loop to continuously accept inputs from the user. Every time the user calls a command, a thread is opened, the respective command is called and then the thread is joined. If a command is not one among the allowed commands, a message – “Invalid operation” is displayed. Additionally, if the client is not online, it cannot perform any operations like list, offer, etc.

The 2 daemon threads that are continuously running in the background for the client are the one that listens for broadcasts from the server and the one that listens for TCP file requests from other clients.

The server and client databases are maintained as dictionaries and are passed around in messages using JSON. The ports are passed on registration and the IP addresses are picked up dynamically from the host. 

**C.	Assumptions and Callouts:**
*	The client assumes that the server is always on.
*	The client is assumed to know the correct server IP address and port on which the server runs.
*	Since the server does not create a new thread for every new client, it might lose messages when multiple clients try to contact it simultaneously, especially since we use UDP.
*	Although not mentioned in the instructions, we are also printing the file contents during file transfer to ensure that the contents are not modified during transfer.
*	To reregister after deregistration, the client has to exit the program using CTRL+C and register using the command given in the next section.

**D. Libraries used:**
* sys
* os
* re
* json
* time
* copy
* threading
* traceback
* socket
* past.builtins

**E.	Functionalities**

I.	Registration:

Server: 
Command: `python FileApp.py -s <server-port>`
Replace `<server-port>` by a chosen port number between 1024 and 65535. This check occurs within the program and if not met, an error message is displayed.  In the happy case path, on running the command, the server IP address is displayed which the clients can use to connect with the server. Also, clients cannot register with a name that is already taken by an online client.

_Examples:_
1.	Happy case:
```
(base) shwethasubbu@Shwethas-Air-2 HW1 % python FileApp.py -s 12000
Server host name: Shwethas-Air-2 IP address: 192.168.1.155
```
2.	Invalid port:
```
(base) shwethasubbu@Shwethas-Air-2 HW1 % python FileApp.py -s 1000
[Invalid server port]
```

Client:
Command: ` python FileApp.py -c B <server-ip> <server-port> <udp-port> <tcp-port>`
Replace the arguments with their respective port numbers and IP addresses. Whenever another client registers, the server broadcasts the message and other clients display the message that their table has been updated once they receive the broadcast.

_Examples:_
1.	Happy case:
```
(base) shwethasubbu@Shwethas-Air-2 HW1 % python FileApp.py -c B 192.168.1.155 12000 1301 1401
>>> [Welcome, You are registered.]
>>>
```

2.	Invalid port:
```
(base) shwethasubbu@Shwethas-MacBook-Air-2 HW1 % python FileApp.py -c C 192.168.1.155 12000 1302 66000
[Invalid client TCP port]
```

3.	Another client registers:
```
(base) shwethasubbu@Shwethas-Air-2 HW1 % python FileApp.py -c B 192.168.1.155 12000 1301 1401
>>> [Welcome, You are registered.]
>>>
>>> [Client table updated.]
>>>
```

4.	Client name already in use by an online client:
```
(base) shwethasubbu@Shwethas-Air-2 HW1 % python FileApp.py -c B 192.168.1.155 12000 1301 1401
>>> [Registration rejected: Client username already in use.]
>>>
```

II.	Setting file directory in client:

Command: `setdir <dir>` where <dir> should be a valid directory. If invalid, an error message is printed.

_Examples:_
1.	Happy case:
```
>>> setdir files
>>> [Successfully set /Users/shwethasubbu/Documents/Sem_2/CN/Prg_HWs/HW1/files as the directory for searching offered files.]
```

2.	Invalid directory:
```
>>> setdir fileszz
>>> [setdir failed: fileszz does not exist.]
```

III.	File Offering:

Command: `offer <filename1>….` 
Zero or more space-delimited file names can be provided. If the directory is not set using the command in previous section, offer is rejected with an error message. If there is no ACK received from server despite retrying 3 times with 500ms gap, the appropriate error message is displayed. Whenever a client successfully offers a file, the server broadcasts it to all online clients and they then display that their table has been updated.

_Examples:_
1.	Happy case 1: multiple files offered at once
```
>>> offer foo bar
Retrying 1 times
Retrying 2 times
Retrying 3 times
>>> [Offer Message Received By Server]
>>>
```

2.	Happy case 2: one file offered at a time
```
>>> offer baz
Retrying 1 times
Retrying 2 times
Retrying 3 times
>>> [Offer Message Received By Server]
>>>
```

3.	Directory not set
```
>>> offer foo
>>> Directory not set. Set directory using setdir command.
>>>
```

IV.	File Listing:

Command: `list`
When called from any client, it displays a table of files offers by all online clients along with their respective IP address and TCP port. If there are no files available, it should mention it.

_Examples:_
1.	Happy case 1: Files existing
```
>>> list
FILENAME        OWNER           IP ADDRESS       TCP PORT
bar             	B                       192.168.1.155   1401
foo                     B                       192.168.1.155   1401
>>>
```

2.	Happy case 2: No files existing
```
>>> list
>>> [No files available for download at the moment.]
>>>
```

V.	File Transfer:

Command: `request <filename> <client-name>`
Replace <filename> with the name of the file that the client wants to request and <client-name> with the name of the client it wants to request from. Client can get this info by performing the `list` operation as described in the previous section. If the file is not offered by the given client or filename is incorrect, an error message is displayed.

_Examples:_
1.	Happy case – client C requesting a file from client B
Client C – requester’s terminal:
```
>>> request foo B
< Connection with client B established. >
< Downloading foo... >
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Viverra orci sagittis eu volutpat. Eu turpis egestas pretium aenean pharetra magna ac placerat. Sit amet venenatis urna cursus. Sed lectus vestibulum mattis ullamcorper velit sed ullamcorper morbi tincidunt. Lobortis mattis aliquam faucibus purus. Sem fringilla ut morbi tincidunt augue interdum velit. Tincidunt nunc pulvinar sapien et ligula. Libero justo laoreet sit amet. Cras tincidunt lobortis feugiat vivamus at augue eget arcu. Venenatis urna cursus eget nunc scelerisque viverra mauris in. Id eu nisl nunc mi ipsum faucibus vitae aliquet nec. Ac turpis egestas sed tempus urna et pharetra. Vulputate eu scelerisque felis imperdiet proin fermentum leo. Vel orci porta non pulvinar neque. Nascetur ridiculus mus mauris vitae ultricies leo integer malesuada nunc. Quis risus sed vulputate odio ut enim blandit volutpat maecenas. Arcu vitae elementum curabitur vitae nunc sed.NEXTNEXTNisl pretium fusce id velit ut tortor. Vitae purus faucibus ornare suspendisse sed nisi lacus sed. Blandit massa enim nec dui nunc mattis enim ut tellus. Magna eget est lorem ipsum dolor sit amet. Nullam non nisi est sit amet facilisis. Fermentum odio eu feugiat pretium nibh ipsum consequat. Nunc sed blandit libero volutpat sed cras ornare arcu. Quisque egestas diam in arcu cursus. Euismod nisi porta lorem mollis aliquam ut porttitor. Nascetur ridiculus mus mauris vitae ultricies. Semper risus in hendrerit gravida. Pulvinar sapien et ligula ullamcorper malesuada. In ornare quam viverra orci sagittis eu volutpat odio. Amet nisl suscipit adipiscing bibendum. Neque viverra justo nec ultrices dui sapien eget mi proin. Turpis egestas maecenas pharetra convallis. Velit euismod in pellentesque massa placerat duis ultricies. Pretium vulputate sapien nec sagittis aliquam malesuada. Pharetra et ultrices neque ornare.NEXTNEXTId aliquet risus feugiat in ante. Risus quis varius quam quisque id. Nulla aliquet porttitor lacus luctus a
< foo downloaded successfully! >
< Connection with client B closed >
>>>
```
Client B – provider’s terminal:
```
>>> < Accepting connection request from 192.168.1.155. >
< Transferring foo... >
< foo transferred successfully! >
< Connection with client C closed>
>>>
```

2.	Invalid file – file not owned by given client
```
>>> request baz B
>>> [Invalid Request]
>>>
```

VI.	De-Registration:

Command: `dereg` or `dereg <client-name>`
After successful deregistration (when client gets an ACK from server that it has updated its table), it notifies the client that it is offline. If it does not get an ACK from server, it displays the message that server is not responding and exits/terminates the program.

_Examples:_
1.	Happy case:
```
>>> dereg B
Retrying 1 times
Retrying 2 times
Retrying 3 times
>>> [You are Offline. Bye.]
>>>
```
