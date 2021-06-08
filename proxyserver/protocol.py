import asyncio
from asyncio import Transport, Protocol


class FlowControl:
    def __init__(self, transport):
        self._transport = transport
        self.read_paused = False
        self.write_paused = False
        self._is_writable_event = asyncio.Event()
        self._is_writable_event.set()

    async def drain(self):
        await self._is_writable_event.wait()

    def pause_reading(self):
        if not self.read_paused:
            self.read_paused = True
            self._transport.pause_reading()

    def resume_reading(self):
        if self.read_paused:
            self.read_paused = False
            self._transport.resume_reading()

    def pause_writing(self):
        if not self.write_paused:
            self.write_paused = True
            self._is_writable_event.clear()

    def resume_writing(self):
        if self.write_paused:
            self.write_paused = False
            self._is_writable_event.set()


class ClientProtocol(Protocol):
    def __init__(self, on_con_lost):
        self.on_con_lost = on_con_lost
        self.disconnected = True
        self.transport = None
        self.flow = None
        self.response_data = bytes()

    def connection_made(self, transport: Transport) -> None:
        self.disconnected = False
        self.transport = transport
        self.flow = FlowControl(transport=transport)

    def data_received(self, data: bytes) -> None:
        print(''.join(["%02X" % b for b in data]))
        self.response_data += data

    def connection_lost(self, exc):
        print('服务器连接断开')
        self.disconnected = True
        self.on_con_lost.set_result(True)


class ServerProtocol(Protocol):
    def __init__(self, server_state, on_con_lost):
        self.on_con_lost = on_con_lost
        self.disconnected = True
        self.transport = None
        self.flow = None
        self.response_data = bytes()

    def connection_made(self, transport: Transport) -> None:
        self.disconnected = False
        self.transport = transport
        self.flow = FlowControl(transport=transport)

    def data_received(self, data: bytes) -> None:
        print(''.join(["%02X" % b for b in data]))
        self.response_data += data

    def connection_lost(self, exc):
        print('服务器连接断开')
        self.disconnected = True
        self.on_con_lost.set_result(True)