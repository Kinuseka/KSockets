# KSockets
Make sockets super simple!

## KSockets
KSockets is a super simple socket integration on python. It ensures reliable TCP communication without having to do many specific setups.

## Installation
`pip install KSockets`

## Usage
Client:
```py
from KSockets import SimpleClient
client = SimpleClient(("127.0.0.1",3001))
client.connect()
```
Server: 
```py
from KSockets import SimpleServer
server = SimpleServer(chunks=8196)
server.create_server()
server.listen()
```

## Support
Contact support@kinuseka.us for any queries

## License
/* Copyright (C) Kinuseka, - All Rights Reserved
 * Unauthorized copying of this file, via any medium is strictly prohibited
 * Proprietary and confidential
 * Written by Milbert Jr. Macarambon <mmacarambon@kinuseka.us>, January 2024
 */

