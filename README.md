# SimpleSocket
Make sockets super simple!

## SimpleSocket
Simple socket is a super simple socket integration on python. It ensures reliable TCP communication without having to do many specific setups.

## Installation
As it had not been published yet to PYPi installation is not possible

## Usage
Client:
```py
client = SimpleClient(("127.0.0.1",3001))
```
Server: 
```py
server = SimpleServer(chunks=8196)
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

