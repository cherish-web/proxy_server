import asyncio
from server import Server


if __name__ == '__main__':
    server = Server('127.0.0.1', 8000)
    server.run()
