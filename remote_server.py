# pybullet_server.py
import socket
import traceback
import io
import sys
import json
import ast

# Define destination
SERVER_IP = "127.0.0.1" 
SERVER_PORT = 65432

_shared_variables_store = {}
_shared_variables_store = {}


def _safe_parse(value_repr_str):
    try:
        return json.loads(value_repr_str)
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        return ast.literal_eval(value_repr_str)
    except (ValueError, SyntaxError): 
        pass
    except TypeError: 
        pass

    return value_repr_str

def set_shared_variable(name, value_arg):
    # Sync shared variable store on server side

    # Define the variable store globally
    global _shared_variables_store

    if not isinstance(name, str):
        raise TypeError(f"'name' must be a string, got {type(name)}")
 
    # Type safety checking
    value_repr_str_for_parse: str
    if isinstance(value_arg, str):
        value_repr_str_for_parse = value_arg
    else:
        value_repr_str_for_parse = repr(value_arg)

    # Safe parsing the value
    value = _safe_parse(value_repr_str_for_parse)

    # Set the variable name
    _shared_variables_store[name] = value

    print(f"Server: Set shared variable '{name}' = {value!r} (type: {type(value)})")
    return f"Variable '{name}' set to {value!r}"

def get_shared_variable(name):
    # Pull shared variable information
    global _shared_variables_store


    # Check type safety (shouldn't ever trigger)
    if not isinstance(name, str):
        raise TypeError(f"'name' must be a string, got {type(name)}")

    # Throw error if the variable isn't in the store
    if name not in _shared_variables_store:
        raise NameError(f"Shared variable '{name}' not found on server.")

    # Get the shared variable
    value = _shared_variables_store[name]
    print(f"Server: Get shared variable '{name}' -> {value!r} (type: {type(value)})")
    return value

def main():
    # Initialize default pybullet instance
    # physicsClientId = -1
    # try:
    #     # Start GUI
    #     physicsClientId = FUN_MODULE.connect(FUN_MODULE.GUI)
    #     if (physicsClientId < 0):
    #         print("Error: Could not connect to PyBullet simulation.")
    #         return

    #     # Add pybullet parameters
    #     FUN_MODULE.setAdditionalSearchPath(pybullet_data.getDataPath())
    #     FUN_MODULE.setGravity(0, 0, -9.81)
    #     _shared_variables_store['planeId_server_init'] = FUN_MODULE.loadURDF("plane.urdf") 
    #     print(f"Loaded plane.urdf with ID: {_shared_variables_store['planeId_server_init']}")
    #     print(f"PyBullet simulation started. Physics Client ID: {physicsClientId}")

    # except Exception as e:
    #     print(f"Error initializing PyBullet: {e}")
    #     if physicsClientId >= 0:
    #         FUN_MODULE.disconnect(physicsClientId)
    #     return

    # Open an IPv4 Socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((SERVER_IP, SERVER_PORT))
            s.listen()
            print(f"Server listening on {SERVER_IP}:{SERVER_PORT}")

            # Wait for clients to connect and handle connections
            while True:
                print("Waiting for a client connection...")
                conn, addr = s.accept()
                with conn:
                    print(f"Connected by {addr}")
                    try:
                        while True:
                            # Buffer size of 8k bytes
                            data = conn.recv(8192)
                            if not data:
                                print(f"Client {addr} disconnected gracefully.")
                                break

                            command_str = data.decode('utf-8')
                            print(f"Server Received command from {addr}: {command_str}") # Log raw command

                            response_message = ""
                            try:
                                # Global variables
                                exec_globals = {
                                    'set_shared_variable': set_shared_variable,
                                    'get_shared_variable': get_shared_variable,
                                    **_shared_variables_store 
                                }

                                # 
                                if command_str.strip().startswith(("set_shared_variable(", "get_shared_variable(")) or \
                                   command_str.strip().startswith("FUN.") :
                                    actual_result_for_client = eval(command_str, exec_globals, _shared_variables_store)
                                    response_message = repr(actual_result_for_client)
                                
                                print("\n")
                            except Exception as e:
                                print(f"Server Error executing command '{command_str}': {e}")
                                response_message = f"ERROR executing command:\n{traceback.format_exc()}"
                            conn.sendall(response_message.encode('utf-8'))

                    except socket.error as se:
                        print(f"Socket error with client {addr}: {se}")
                    except Exception as client_e:
                        print(f"Error during client {addr} communication: {client_e}")
                    finally:
                        print(f"Client {addr} session ended.")
        except socket.error as e:
            print(f"Socket error: {e}")
        except KeyboardInterrupt:
            print("Server shutting down due to KeyboardInterrupt.")
        except Exception as e:
            print(f"An unexpected server error occurred: {e}")
        finally:
            print("Shutting down PyBullet simulation.")

            print("Server shutdown.")

if __name__ == "__main__":
    main()

