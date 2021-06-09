import asyncio
import click
import logging
import functools
import os
import sys
import signal
from protocol import ServerProtocol
import time
logger = logging.getLogger("server.error")
logger.level = logging.INFO


HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


class ServerState:
    """
    Shared servers state that is available between all protocol instances.
    """

    def __init__(self):
        self.total_requests = 0
        self.connections = set()
        self.tasks = set()


class Server:
    def __init__(self, host, port):
        self.server_state = ServerState()
        self.host = host
        self.port = port
        self.started = False
        self.should_exit = False
        self.force_exit = False
        self.last_notified = 0
        self.servers = []

    def run(self, sockets=None):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.serve(sockets=sockets))

    async def serve(self, sockets=None):
        process_id = os.getpid()

        self.install_signal_handlers()

        message = "Started server process [%d]"
        color_message = "Started server process [" + click.style("%d", fg="cyan") + "]"
        logger.info(message, process_id, extra={"color_message": color_message})

        await self.startup(sockets=sockets)
        if self.should_exit:
            return
        await self.main_loop()
        await self.shutdown(sockets=sockets)

        message = "Finished server process [%d]"
        color_message = "Finished server process [" + click.style("%d", fg="cyan") + "]"
        logger.info(
            "Finished server process [%d]",
            process_id,
            extra={"color_message": color_message},
        )

    async def startup(self, sockets=None):

        create_protocol = functools.partial(
            ServerProtocol, server_state=self.server_state
        )

        loop = asyncio.get_event_loop()

        try:
            server = await loop.create_server(
                create_protocol,
                host=self.host,
                port=self.port,
                # ssl=config.ssl,
                # backlog=config.backlog,
            )
        except OSError as exc:
            logger.error(exc)
            sys.exit(1)

        message = f"Server running on {self.host + ':' + str(self.port)} (Press CTRL+C to quit)"
        color_message = (
            "Server running on "
            + click.style(self.host + ':' + str(self.port), bold=True)
            + " (Press CTRL+C to quit)"
        )
        print(message)
        logger.info(
            message,
            'ProxyServer',
            self.host,
            self.port,
            extra={"color_message": color_message},
        )
        self.servers = [server]

        self.started = True

    async def main_loop(self):
        counter = 0
        should_exit = await self.on_tick(counter)
        while not should_exit:
            counter += 1
            counter = counter % 864000
            await asyncio.sleep(0.1)
            should_exit = await self.on_tick(counter)

    async def on_tick(self, counter) -> bool:
        if self.should_exit:
            return True
        return False

    async def shutdown(self, sockets=None):
        logger.info("Shutting down")

        # Stop accepting new connections.
        for server in self.servers:
            server.close()
        for sock in sockets or []:
            sock.close()
        for server in self.servers:
            await server.wait_closed()

        # Request shutdown on all existing connections.
        for connection in list(self.server_state.connections):
            connection.shutdown()
        await asyncio.sleep(0.1)

        # Wait for existing connections to finish sending responses.
        if self.server_state.connections and not self.force_exit:
            msg = "Waiting for connections to close. (CTRL+C to force quit)"
            logger.info(msg)
            while self.server_state.connections and not self.force_exit:
                await asyncio.sleep(0.1)

        # Wait for existing tasks to complete.
        if self.server_state.tasks and not self.force_exit:
            msg = "Waiting for background tasks to complete. (CTRL+C to force quit)"
            logger.info(msg)
            while self.server_state.tasks and not self.force_exit:
                await asyncio.sleep(0.1)

    def install_signal_handlers(self):
        loop = asyncio.get_event_loop()

        try:
            for sig in HANDLED_SIGNALS:
                loop.add_signal_handler(sig, self.handle_exit, sig, None)
        except NotImplementedError:
            # Windows
            for sig in HANDLED_SIGNALS:
                signal.signal(sig, self.handle_exit)

    def handle_exit(self, sig, frame):
        if self.should_exit:
            self.force_exit = True
        else:
            self.should_exit = True


