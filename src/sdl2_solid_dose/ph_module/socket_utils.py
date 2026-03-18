"""
Socket utility functions for file transfer and connection management.
Author: Yang Cao, Acceleration Consortium
"""

import socket
import time


def connect_socket(sock, host, port, logger, max_retries=3, retry_delay=1):
    """
    Connect socket to host:port with retries.
    
    Args:
        sock: Socket object
        host (str): Host IP address
        port (int): Port number
        logger: Logger instance
        max_retries (int): Maximum connection attempts
        retry_delay (int): Delay between retries in seconds
        
    Returns:
        socket or None: Connected socket or None if failed
    """
    for attempt in range(max_retries):
        try:
            sock.connect((host, port))
            logger.info(f"Successfully connected to {host}:{port}")
            return sock
        except socket.error as e:
            logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to connect to {host}:{port} after {max_retries} attempts")
    
    return None


def send_file_name(sock, filename, logger):
    """
    Send filename to socket with newline terminator.
    
    Args:
        sock: Socket object
        filename (str): Name of the file
        logger: Logger instance
    """
    try:
        message = f"{filename}\n"
        sock.sendall(message.encode('utf-8'))
        logger.debug(f"Sent filename: {filename}")
    except Exception as e:
        logger.error(f"Failed to send filename: {e}")
        raise


def receive_file_name(sock, logger, buffer_size=1024):
    """
    Receive filename from socket (newline terminated).
    
    Args:
        sock: Socket object
        logger: Logger instance
        buffer_size (int): Buffer size for receiving
        
    Returns:
        str or None: Received filename or None if failed
    """
    try:
        data = sock.recv(buffer_size).decode('utf-8').strip()
        if data:
            logger.debug(f"Received filename: {data}")
            return data
        else:
            logger.error("Received empty filename")
            return None
    except Exception as e:
        logger.error(f"Failed to receive filename: {e}")
        return None


def send_file_size(sock, file_size, logger):
    """
    Send file size to socket with newline terminator.
    
    Args:
        sock: Socket object
        file_size (int): Size of the file in bytes
        logger: Logger instance
    """
    try:
        message = f"{file_size}\n"
        sock.sendall(message.encode('utf-8'))
        logger.debug(f"Sent file size: {file_size}")
    except Exception as e:
        logger.error(f"Failed to send file size: {e}")
        raise


def receive_file_size(sock, logger, buffer_size=1024):
    """
    Receive file size from socket (newline terminated).
    
    Args:
        sock: Socket object
        logger: Logger instance
        buffer_size (int): Buffer size for receiving
        
    Returns:
        str or None: Received file size as string or None if failed
    """
    try:
        data = sock.recv(buffer_size).decode('utf-8').strip()
        if data:
            logger.debug(f"Received file size: {data}")
            return data
        else:
            logger.error("Received empty file size")
            return None
    except Exception as e:
        logger.error(f"Failed to receive file size: {e}")
        return None


def receive_file(sock, file_size, chunk_size, logger):
    """
    Receive file data from socket in chunks.
    
    Args:
        sock: Socket object
        file_size (int): Expected file size in bytes
        chunk_size (int): Size of each chunk to receive
        logger: Logger instance
        
    Returns:
        bytes: Received file data
    """
    try:
        received_data = b""
        bytes_received = 0
        
        while bytes_received < file_size:
            remaining = file_size - bytes_received
            chunk = sock.recv(min(chunk_size, remaining))
            
            if not chunk:
                logger.error("Connection closed before receiving complete file")
                break
                
            received_data += chunk
            bytes_received += len(chunk)
            
            # Log progress for large files
            if file_size > 1024 * 1024:  # Log for files > 1MB
                progress = (bytes_received / file_size) * 100
                if bytes_received % (chunk_size * 100) == 0:  # Log every 100 chunks
                    logger.debug(f"File transfer progress: {progress:.1f}%")
        
        logger.debug(f"File transfer complete: {bytes_received}/{file_size} bytes")
        return received_data
        
    except Exception as e:
        logger.error(f"Failed to receive file: {e}")
        return b""


def send_file(sock, file_data, chunk_size, logger):
    """
    Send file data through socket in chunks.
    
    Args:
        sock: Socket object
        file_data (bytes): File data to send
        chunk_size (int): Size of each chunk to send
        logger: Logger instance
    """
    try:
        file_size = len(file_data)
        bytes_sent = 0
        
        while bytes_sent < file_size:
            end = min(bytes_sent + chunk_size, file_size)
            chunk = file_data[bytes_sent:end]
            sock.sendall(chunk)
            bytes_sent += len(chunk)
            
            # Log progress for large files
            if file_size > 1024 * 1024:  # Log for files > 1MB
                progress = (bytes_sent / file_size) * 100
                if bytes_sent % (chunk_size * 100) == 0:  # Log every 100 chunks
                    logger.debug(f"File send progress: {progress:.1f}%")
        
        logger.debug(f"File send complete: {bytes_sent}/{file_size} bytes")
        
    except Exception as e:
        logger.error(f"Failed to send file: {e}")
        raise
