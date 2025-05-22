import socket
import re
import sys
import os

SERVER_IP = "172.20.50.3"
SERVER_PORT = 65432
LOGGING = True

def find_remote_calls(command):
    calls = []
    i = 0
    while i < len(command):
        if command.startswith("FUN.", i) or \
           command.startswith("set_shared_variable(", i) or \
           command.startswith("get_shared_variable(", i):
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


def execute_remote_function(sock, remote_call_str):
    if LOGGING:
        print(f"Client sending: {remote_call_str}")
    sock.sendall(remote_call_str.encode('utf-8'))
    response_data = sock.recv(8192)
    decoded_response = response_data.decode('utf-8')
    if LOGGING:
        print(f"Client received: {decoded_response}")
    if decoded_response.startswith("ERROR executing command:"):
        raise ConnectionAbortedError(f"Server error: {decoded_response}")
    return decoded_response

def substitute_remote_functions(sock, command, local_namespace_for_args=None):
    while True:
        current_calls = find_remote_calls(command)
        if not current_calls:
            break

        call_to_process = current_calls[0]

        try:
            result_str = execute_remote_function(sock, call_to_process)
            command = command.replace(call_to_process, result_str.strip(), 1)
        except SyntaxError as e:
            if LOGGING:
                print(f"Client: Syntax error in remote call structure: {e} in command '{command}'")
            raise  
        except ConnectionAbortedError: 
            raise

    return command


def get_indentation_level(line):
    """Get the indentation level of a line (number of spaces/tabs at the beginning)"""
    stripped = line.lstrip()
    if not stripped:
        return 0
    return len(line) - len(stripped)


def parse_block(lines, start_idx):
    """
    Parse a block of code starting from start_idx.
    Returns (block_lines, next_idx) where block_lines contains the indented block
    and next_idx is the index after the block ends.
    """
    if start_idx >= len(lines):
        return [], start_idx
    
    # Get the base indentation level (the line with the block keyword)
    base_indent = get_indentation_level(lines[start_idx])
    block_lines = []
    
    i = start_idx + 1
    while i < len(lines):
        line = lines[i]
        stripped_line = line.strip()
        
        # Skip empty lines and comments
        if not stripped_line or stripped_line.startswith("#"):
            i += 1
            continue
            
        current_indent = get_indentation_level(line)
        
        # If indentation is less than or equal to base, we've reached the end of the block
        if current_indent <= base_indent:
            break
            
        block_lines.append(line)
        i += 1
    
    return block_lines, i


def is_block_keyword(line):
    """Check if a line starts with a block keyword"""
    stripped = line.strip()
    block_keywords = ['if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except ', 'finally:', 'with ']
    return any(stripped.startswith(keyword) for keyword in block_keywords)


def parse_if_elif_else_chain(lines, start_idx, sock, local_namespace):
    """
    Parse and execute an if/elif/else chain.
    Returns the index after the entire chain.
    """
    current_idx = start_idx
    executed_branch = False
    
    while current_idx < len(lines):
        line = lines[current_idx].strip()
        
        if line.startswith('if ') or line.startswith('elif '):
            # Extract condition
            if line.startswith('if '):
                condition = line[3:].rstrip(':').strip()
            else:  # elif
                condition = line[5:].rstrip(':').strip()
            
            # Get the block for this condition
            block_lines, next_idx = parse_block(lines, current_idx)
            
            if not executed_branch:
                # Evaluate condition with remote substitution
                try:
                    condition_with_subs = substitute_remote_functions(sock, condition, local_namespace)
                    condition_result = eval(condition_with_subs, globals(), local_namespace)
                    
                    if condition_result:
                        if LOGGING:
                            print(f"Executing {'if' if line.startswith('if') else 'elif'} block (condition: {condition} -> {condition_result})")
                        execute_script(block_lines, sock, local_namespace)
                        executed_branch = True
                except Exception as e:
                    if LOGGING:
                        print(f"Error evaluating condition '{condition}': {e}")
            
            current_idx = next_idx
            
        elif line == 'else:':
            # Get the else block
            block_lines, next_idx = parse_block(lines, current_idx)
            
            if not executed_branch:
                if LOGGING:
                    print(f"Executing else block")
                execute_script(block_lines, sock, local_namespace)
            
            return next_idx
            
        else:
            # Not part of the if/elif/else chain
            break
    
    return current_idx


def parse_try_except_finally(lines, start_idx, sock, local_namespace):
    """
    Parse and execute a try/except/finally block.
    Returns the index after the entire block.
    """
    current_idx = start_idx
    
    # Parse try block
    if not lines[current_idx].strip() == 'try:':
        raise SyntaxError(f"Expected 'try:' but got '{lines[current_idx].strip()}'")
    
    try_block, current_idx = parse_block(lines, current_idx)
    
    # Parse except and finally blocks
    except_blocks = []
    finally_block = []
    
    while current_idx < len(lines):
        line = lines[current_idx].strip()
        
        if line.startswith('except'):
            # Parse except block
            block_lines, current_idx = parse_block(lines, current_idx)
            
            # Extract exception type if specified
            if line == 'except:':
                exception_type = None
            else:
                # Extract exception type (simplified parsing)
                exception_part = line[6:].rstrip(':').strip()
                exception_type = exception_part
            
            except_blocks.append((exception_type, block_lines))
            
        elif line == 'finally:':
            # Parse finally block
            finally_block, current_idx = parse_block(lines, current_idx)
            break
        else:
            break
    
    # Execute try block
    exception_occurred = None
    try:
        if LOGGING:
            print("Executing try block")
        execute_script(try_block, sock, local_namespace)
    except Exception as e:
        exception_occurred = e
        if LOGGING:
            print(f"Exception in try block: {e}")
        
        # Handle except blocks
        handled = False
        for exception_type, except_block_lines in except_blocks:
            if exception_type is None or exception_type in str(type(e)):
                if LOGGING:
                    print(f"Executing except block for {exception_type or 'any exception'}")
                try:
                    execute_script(except_block_lines, sock, local_namespace)
                    handled = True
                    break
                except Exception as except_e:
                    if LOGGING:
                        print(f"Exception in except block: {except_e}")
        
        if not handled and except_blocks:
            # Re-raise if no except block handled it
            raise e
    
    # Execute finally block
    if finally_block:
        if LOGGING:
            print("Executing finally block")
        try:
            execute_script(finally_block, sock, local_namespace)
        except Exception as finally_e:
            if LOGGING:
                print(f"Exception in finally block: {finally_e}")
    
    return current_idx


def execute_script(lines, sock, local_namespace=None):
    """
    Execute a sequence of Python lines with remote function substitution and block support.
    
    Args:
        lines (list): List of strings containing Python code lines
        sock: Socket connection to the remote server
        local_namespace (dict): Local variable namespace (created if None)
    """
    if local_namespace is None:
        local_namespace = {}

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped_line = line.strip()
        
        if not stripped_line or stripped_line.startswith("#"):
            i += 1
            continue

        try:
            if LOGGING:
                print(f"\n[Line {i+1}] Original: {stripped_line}")

            # Handle block keywords
            if stripped_line.startswith('if '):
                i = parse_if_elif_else_chain(lines, i, sock, local_namespace)
                continue
                
            elif stripped_line.startswith('for '):
                # Parse for loop
                block_lines, next_i = parse_block(lines, i)
                
                # Extract for loop components
                for_statement = stripped_line[4:].rstrip(':').strip()
                
                # Handle remote substitutions in for statement
                for_statement_with_subs = substitute_remote_functions(sock, for_statement, local_namespace)
                
                if LOGGING:
                    print(f"[Line {i+1}] For loop: {for_statement_with_subs}")
                
                # Execute for loop
                try:
                    # Parse the for statement: "var in iterable"
                    if ' in ' in for_statement_with_subs:
                        var_part, iterable_part = for_statement_with_subs.split(' in ', 1)
                        var_name = var_part.strip()
                        
                        # Evaluate the iterable
                        iterable = eval(iterable_part, globals(), local_namespace)
                        
                        for item in iterable:
                            local_namespace[var_name] = item
                            # Sync variable to server
                            server_set_command = f"set_shared_variable('{var_name}', {repr(item)})"
                            try:
                                execute_remote_function(sock, server_set_command)
                            except ConnectionAbortedError:
                                pass  # Continue even if sync fails
                            
                            if LOGGING:
                                print(f"For loop iteration: {var_name} = {item}")
                            execute_script(block_lines, sock, local_namespace)
                            
                except Exception as e:
                    if LOGGING:
                        print(f"Error in for loop: {e}")
                
                i = next_i
                continue
                
            elif stripped_line.startswith('while '):
                # Parse while loop
                block_lines, next_i = parse_block(lines, i)
                
                # Extract condition
                condition = stripped_line[6:].rstrip(':').strip()
                
                if LOGGING:
                    print(f"[Line {i+1}] While loop condition: {condition}")
                

                
                while True:
                    try:
                        # Evaluate condition with remote substitutions
                        condition_with_subs = substitute_remote_functions(sock, condition, local_namespace)
                        condition_result = eval(condition_with_subs, globals(), local_namespace)
                        
                        if not condition_result:
                            break
                            
                        if LOGGING:
                            print(f"While loop iteration {iteration_count + 1}")
                        execute_script(block_lines, sock, local_namespace)
                        iteration_count += 1
                        
                    except Exception as e:
                        if LOGGING:
                            print(f"Error in while loop iteration {iteration_count + 1}: {e}")
                        break
                

                i = next_i
                continue
                
            elif stripped_line == 'try:':
                i = parse_try_except_finally(lines, i, sock, local_namespace)
                continue
                
            elif stripped_line.startswith('with '):
                # Parse with statement
                block_lines, next_i = parse_block(lines, i)
                
                # Extract with statement
                with_statement = stripped_line[5:].rstrip(':').strip()
                
                if LOGGING:
                    print(f"[Line {i+1}] With statement: {with_statement}")
                
                # Execute with statement (simplified - doesn't handle context managers properly)
                try:
                    with_statement_with_subs = substitute_remote_functions(sock, with_statement, local_namespace)
                    
                    # For simplicity, we'll execute the block without proper context manager support
                    # In a full implementation, you'd need to handle __enter__ and __exit__ methods
                    if LOGGING:
                        print("Executing with block (simplified - no context manager support)")
                    execute_script(block_lines, sock, local_namespace)
                    
                except Exception as e:
                    if LOGGING:
                        print(f"Error in with statement: {e}")
                
                i = next_i
                continue

            # Handle regular statements (non-block)
            command_after_remote_subs = substitute_remote_functions(sock, stripped_line, local_namespace)
            if LOGGING:
                print(f"[Line {i+1}] Substituted: {command_after_remote_subs}")

            if '=' in command_after_remote_subs and command_after_remote_subs.count('=') == 1:
                parts = command_after_remote_subs.split('=', 1)
                var_name = parts[0].strip()
                expression_str_to_eval = parts[1].strip()

                evaluated_rhs = eval(expression_str_to_eval, globals(), local_namespace)
                local_namespace[var_name] = evaluated_rhs 
                if LOGGING:
                    print(f"[Line {i+1}] Client var set: {var_name} = {evaluated_rhs!r}")

                server_set_command = f"set_shared_variable('{var_name}', {repr(evaluated_rhs)})"
                if LOGGING:
                    print(f"[Line {i+1}] Syncing to server: {server_set_command}")
                try:
                    execute_remote_function(sock, server_set_command) 
                except ConnectionAbortedError as e_sync:
                    if LOGGING:
                        print(f"[Line {i+1}] Server error during sync of '{var_name}': {e_sync}")
                        
            else:
                try:
                    result = eval(command_after_remote_subs, globals(), local_namespace)
                    if LOGGING:
                        if result is not None:
                            print(f"[Line {i+1}] Client eval result: {result!r}")
                except SyntaxError: 
                    exec(command_after_remote_subs, globals(), local_namespace)
                    if LOGGING:
                        print(f"[Line {i+1}] Client executed as statement.")

        except ConnectionAbortedError as e_server:
            if LOGGING:
                print(f"[Line {i+1}] SERVER EXECUTION FAILED for line: {stripped_line}")
                print(f"  Error details: {e_server}")
        except Exception as e_client:
            if LOGGING:
                print(f"[Line {i+1}] Client error processing line: {e_client}")
                print(f"  Original line: {stripped_line}")
                print(f"  Line after substitutions (if any): {command_after_remote_subs if 'command_after_remote_subs' in locals() else 'N/A'}")
        
        i += 1


def main():
    if len(sys.argv) != 2:
        print("Usage: python pybullet_client.py <script_file.py>")
        sys.exit(1)

    script_path = sys.argv[1]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            print(f"Connecting to PyBullet server at {SERVER_IP}:{SERVER_PORT}...")
            s.connect((SERVER_IP, SERVER_PORT))
            print("Connected to server.")
            if os.path.isfile(script_path):
                with open(script_path, 'r') as f:
                    lines = f.readlines()
                execute_script(lines, s)
            else:
                print(f"Error: File '{script_path}' does not exist.")

        except socket.gaierror:
            print(f"Error: Cannot resolve IP address {SERVER_IP}.")
        except socket.error as e:
            print(f"Socket error: {e}. Is the server running?")
        finally:
            print("Closing connection to server.")

if __name__ == "__main__":
    main()