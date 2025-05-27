import socket
import re
import sys
import os


class RemoteClient:
    def __init__(self, server_ip="127.0.0.1", server_port=65432, logging=True, remote_prefix="FUN."):
        self.SERVER_IP = server_ip
        self.SERVER_PORT = server_port
        self.LOGGING = logging
        self.REMOTE_PREFIX = remote_prefix
        self.local_namespace = {}
        self.socket = None

    def connect(self):
        """Establish connection to the PyBullet server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if self.LOGGING:
                print(f"Connecting to PyBullet server at {self.SERVER_IP}:{self.SERVER_PORT}...")
            self.socket.connect((self.SERVER_IP, self.SERVER_PORT))
            if self.LOGGING:
                print("Connected to server.")
            return True
        except socket.error as e:
            print(f"Connection error: {e}")
            return False

    def close(self):
        """Close the connection to the server"""
        if self.socket:
            self.socket.close()
            if self.LOGGING:
                print("Closing connection to server.")

    def find_remote_calls(self, command):
        """Find all remote function calls in the command"""
        calls = []
        i = 0
        while i < len(command):
            if (command.startswith(self.REMOTE_PREFIX, i) or
                command.startswith("set_shared_variable(", i) or
                command.startswith("get_shared_variable(", i)):
                start = i
                depth = 0
                
                temp_i = i
                while temp_i < len(command) and command[temp_i] != '(':
                    temp_i += 1
                if temp_i == len(command):
                    i += 1
                    continue

                i = temp_i
                while i < len(command):
                    if command[i] == '(':
                        depth += 1
                    elif command[i] == ')':
                        depth -= 1
                        if depth == 0:
                            i += 1
                            calls.append(command[start:i])
                            break
                    i += 1
                if depth != 0:
                    i = start + 1
                    continue
            else:
                i += 1
        return calls

    def execute_remote_function(self, remote_call_str):
        """Execute a remote function and return the result"""
        if self.LOGGING:
            print(f"Client sending: {remote_call_str}")
        self.socket.sendall(remote_call_str.encode('utf-8'))
        response_data = self.socket.recv(8192)
        decoded_response = response_data.decode('utf-8')
        if self.LOGGING:
            print(f"Client received: {decoded_response}")
        if decoded_response.startswith("ERROR executing command:"):
            raise ConnectionAbortedError(f"Server error: {decoded_response}")
        return decoded_response

    def substitute_remote_functions(self, command):
        """Substitute remote function calls with their results"""
        while True:
            current_calls = self.find_remote_calls(command)
            if not current_calls:
                break

            call_to_process = current_calls[0]
            try:
                result_str = self.execute_remote_function(call_to_process)
                command = command.replace(call_to_process, result_str.strip(), 1)
            except (SyntaxError, ConnectionAbortedError):
                raise

        return command

    def execute_line(self, line, idx=1):
        """Execute a single line of code"""
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            return

        try:
            if self.LOGGING:
                print(f"\n[Line {idx}] Original: {stripped_line}")

            command_after_subs = self.substitute_remote_functions(stripped_line)
            if self.LOGGING:
                print(f"[Line {idx}] Substituted: {command_after_subs}")

            if '=' in command_after_subs and command_after_subs.count('=') == 1:
                parts = command_after_subs.split('=', 1)
                var_name = parts[0].strip()
                expression_str_to_eval = parts[1].strip()

                evaluated_rhs = eval(expression_str_to_eval, globals(), self.local_namespace)
                self.local_namespace[var_name] = evaluated_rhs
                if self.LOGGING:
                    print(f"[Line {idx}] Client var set: {var_name} = {evaluated_rhs!r}")

                server_set_command = f"set_shared_variable('{var_name}', {repr(evaluated_rhs)})"
                if self.LOGGING:
                    print(f"[Line {idx}] Syncing to server: {server_set_command}")
                try:
                    self.execute_remote_function(server_set_command)
                except ConnectionAbortedError as e_sync:
                    if self.LOGGING:
                        print(f"[Line {idx}] Server error during sync of '{var_name}': {e_sync}")
            else:
                try:
                    result = eval(command_after_subs, globals(), self.local_namespace)
                    if self.LOGGING and result is not None:
                        print(f"[Line {idx}] Client eval result: {result!r}")
                except SyntaxError:
                    exec(command_after_subs, globals(), self.local_namespace)
                    if self.LOGGING:
                        print(f"[Line {idx}] Client executed as statement.")

        except ConnectionAbortedError as e_server:
            if self.LOGGING:
                print(f"[Line {idx}] SERVER EXECUTION FAILED for line: {stripped_line}")
                print(f"  Error details: {e_server}")
        except Exception as e_client:
            if self.LOGGING:
                print(f"[Line {idx}] Client error processing line: {e_client}")
                print(f"  Original line: {stripped_line}")
                print(f"  Line after substitutions (if any): {command_after_subs if 'command_after_subs' in locals() else 'N/A'}")

    def execute_script(self, lines):
        """Execute multiple lines of code"""
        for idx, line in enumerate(lines, 1):
            self.execute_line(line, idx)

def main():
    if len(sys.argv) != 2:
        print("Usage: python pybullet_client.py <script_file.py>")
        sys.exit(1)

    script_path = sys.argv[1]
    
    # Read the script file
    if not os.path.isfile(script_path):
        print(f"Error: File '{script_path}' does not exist.")
        sys.exit(1)
        
    with open(script_path, 'r') as f:
        script_lines = f.readlines()

    # Create client and execute script
    client = RemoteClient()
    try:
        if client.connect():
            client.execute_script(script_lines)
    finally:
        client.close()

if __name__ == "__main__":
    main()