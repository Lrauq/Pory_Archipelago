var server = new Server();

function startServer() {
    console.log("Starting server...");
    server.listen(1337, "127.0.0.1");

    server.on('connection', function(c) {
        console.log("Client connected");

        // Flag to track if the connection is alive
        var isConnected = true;

        c.on('data', function(data) {
            if (!isConnected) return;

            var message = data.toString().trim();
            // console.log("Received data: " + message);

            if (message.startsWith("read")) {
                var parts = message.split(" ");
                if (parts.length === 4) {
                    var type = parts[1];
                    var address = parseInt(parts[2], 16);
                    var size = parseInt(parts[3], 10);
                    if (!isNaN(address) && !isNaN(size) && size > 0) {
                        var result = [];

                        if (type === "u8") {
                            for (var i = 0; i < size; i++) {
                                result.push(mem.u8[address + i]);
                            }
                        } else if (type === "u16") {
                            for (var i = 0; i < size; i += 2) {
                                result.push(mem.u16[address + i]);
                            }
                        } else if (type === "u32") {
                            for (var i = 0; i < size; i += 4) {
                                result.push(mem.u32[address + i]);
                            }
                        } else {
                            c.write("Invalid type, use: read u8, read u16, read u32");
                            return;
                        }

                        c.write(result.join(","));
                    } else {
                        c.write("Invalid read parameters");
                    }
                } else {
                    c.write("Usage: read u8/u16/u32 0xADDRESS SIZE");
                }
            }

            else if (message.startsWith("write")) {
                var parts = message.split(" ");
                var type = parts[1];
                var address = parseInt(parts[2], 16);
                var value = parts.slice(3).join(" ");
                if (type === "bytestring") {
                    var byteArray = [];

                    for (var i = 0; i < value.length; i++) {
                        byteArray.push(value.charCodeAt(i));
                    }
                    for (var i = 0; i < byteArray.length; i++) {
                        mem.u8[address + i] = byteArray[i];
                    }
                    c.write("Bytestring write successful");
                    return;
                }
        
                try {
                    value = JSON.parse(value);
                } catch (e) {
                    c.write("Invalid JSON format for value");
                    return;
                }
        
                if (!Array.isArray(value)) {
                    c.write("Value must be an array of bytes");
                    return;
                }
        
                if (!isNaN(address) && !isNaN(value)) {
                    if (type === "u8") {
                        for (var i = 0; i < value.length; i++) {
                            mem.u8[address + i] = value[i];
                        }
                    } else if (type === "u16") {
                        for (var i = 0; i < value.length; i += 2) {
                            mem.u16[address + i] = value[i / 2];
                        }
                    } else if (type === "u32") {
                        for (var i = 0; i < value.length; i += 4) {
                            mem.u32[address + i] = value[i / 4];
                        }
                    } else {
                        c.write("Invalid type, use: write u8, write u16, write u32, write bytestring");
                        return;
                    }
        
                    c.write("Write successful");
                } else {
                    c.write("Invalid write parameters");
                }
            }
            else if (message === "romInfo"){
                c.write(JSON.stringify(pj64.romInfo));
            }
        }
        );

        c.on('end', function() {
            console.log("Client ended connection");
            isConnected = false;
        });

        c.on('close', function() {
            console.log("Client disconnected unexpectedly");
            isConnected = false;
        });

        c.on('error', function(err) {
            if (isConnected === false) return;
            console.log("Connection error: " + err.message);
            isConnected = false;
            c.close();
            restartServer();
        });
    });

    console.log("Server listening on 127.0.0.1:1337");
}

function restartServer() {
    console.log("Restarting server...");
    server.close()
    server = new Server();
    setTimeout(startServer, 5000);
}

startServer();
