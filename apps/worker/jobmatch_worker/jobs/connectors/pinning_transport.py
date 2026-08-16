"""HTTPS transport that pins every connection to a DNS-validated public IP.

The career-page fetcher must never connect to an address that was not
validated: a hostname can resolve to a public address at validation time
and to a private address at connect time (DNS rebinding). This transport
resolves the hostname exactly once, validates every resolved address,
connects to a validated address, and completes TLS with SNI pinned to the
original hostname, so the checked address is the address that is
connected. A fresh connection is used per request (no keep-alive reuse),
and response headers are capped before anything is returned.
"""

import asyncio
import ipaddress
import ssl
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

import httpx

_MAX_STATUS_LINE = 16 * 1024
_MAX_HEADER_BYTES = 64 * 1024
_READ_CHUNK = 64 * 1024
_NAT64_NETWORK = ipaddress.ip_network("64:ff9b::/96")

Address = ipaddress.IPv4Address | ipaddress.IPv6Address

Resolver = Callable[[str], Awaitable[Sequence[Address]]]

ConnectionFactory = Callable[
    [str, int, ssl.SSLContext | None, str | None],
    Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]],
]


class NoDnsError(httpx.ConnectError):
    """The hostname produced no usable DNS records."""


class NonPublicAddressError(httpx.ConnectError):
    """The hostname resolved to an address that must not be contacted."""


def is_public_address(address: Address) -> bool:
    """True when an address may be contacted by the fetcher.

    Globally routable addresses only. NAT64 (``64:ff9b::/96``) is rejected
    because it can embed a private IPv4 address that is not visible to
    ``is_global``.
    """
    if not address.is_global:
        return False
    return not (
        isinstance(address, ipaddress.IPv6Address) and address in _NAT64_NETWORK
    )


async def resolve_public_addresses(host: str, resolver: Resolver) -> list[Address]:
    """Resolve once and keep only validated public addresses.

    Raises ``NoDnsError`` when the host has no usable records and
    ``NonPublicAddressError`` when any resolved address is not public.
    """
    try:
        addresses = list(await resolver(host))
    except Exception as exc:  # any resolution failure is a no-DNS outcome
        raise NoDnsError(f"no DNS records for {host}") from exc
    if not addresses:
        raise NoDnsError(f"no DNS records for {host}")
    for address in addresses:
        if not is_public_address(address):
            raise NonPublicAddressError(
                f"{host} resolves to non-public address {address}"
            )
    return addresses


async def _open_connection(
    host: str,
    port: int,
    ssl_context: ssl.SSLContext | None,
    server_hostname: str | None,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    return await asyncio.open_connection(
        host, port, ssl=ssl_context, server_hostname=server_hostname
    )


class PinnedHttpsTransport(httpx.AsyncBaseTransport):
    """Resolve once, validate, and connect to the validated address."""

    def __init__(
        self,
        *,
        resolver: Resolver,
        timeout: float = 10.0,
        connection_factory: ConnectionFactory = _open_connection,
    ) -> None:
        self._resolver = resolver
        self._timeout = timeout
        self._connection_factory = connection_factory
        self._ssl_context = ssl.create_default_context()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.scheme != "https":
            raise httpx.UnsupportedProtocol("only https requests are supported")
        hostname = request.url.host
        if not hostname:
            raise NoDnsError("URL has no host")
        port = request.url.port or 443
        addresses = await resolve_public_addresses(hostname, self._resolver)
        last_error: Exception | None = None
        for address in addresses[:4]:
            try:
                reader, writer = await asyncio.wait_for(
                    self._connection_factory(
                        str(address), port, self._ssl_context, hostname
                    ),
                    self._timeout,
                )
            except (TimeoutError, OSError, ssl.SSLError) as exc:
                last_error = exc
                continue
            try:
                return await self._exchange(request, reader, writer)
            except (TimeoutError, OSError, ssl.SSLError) as exc:
                last_error = exc
                writer.close()
                continue
        raise httpx.ConnectError(f"could not connect to {hostname}: {last_error}")

    async def _exchange(
        self,
        request: httpx.Request,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> httpx.Response:
        request_bytes = _build_request_bytes(request)
        try:
            writer.write(request_bytes)
            await asyncio.wait_for(writer.drain(), self._timeout)
            status_line = await asyncio.wait_for(reader.readuntil(b"\r\n"), self._timeout)
            if len(status_line) > _MAX_STATUS_LINE:
                raise httpx.ProtocolError("status line too large")
            header_bytes = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), self._timeout)
            if len(header_bytes) > _MAX_HEADER_BYTES:
                raise httpx.ProtocolError("response headers too large")
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
            writer.close()
            raise httpx.ProtocolError("malformed HTTP response") from exc
        except httpx.ProtocolError:
            writer.close()
            raise
        status_code = _parse_status_code(status_line)
        headers = httpx.Headers(_parse_header_block(header_bytes))
        stream = _ResponseStream(reader, writer, headers, self._timeout)
        return httpx.Response(
            status_code, headers=headers, stream=stream, request=request
        )


class _ResponseStream(httpx.AsyncByteStream):
    """Streams the body from the socket and closes the connection at EOF."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        headers: httpx.Headers,
        timeout: float,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._timeout = timeout
        self._closed = False
        transfer_encoding = headers.get("transfer-encoding", "").casefold()
        self._chunked = "chunked" in transfer_encoding
        content_length = headers.get("content-length", "")
        self._remaining = int(content_length) if content_length.isdigit() else None

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self.aiter_bytes()

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        try:
            while True:
                if self._chunked:
                    chunk = await self._next_chunk()
                elif self._remaining is not None:
                    if self._remaining <= 0:
                        break
                    size = min(_READ_CHUNK, self._remaining)
                    chunk = await self._read(size)
                    self._remaining -= len(chunk)
                else:
                    chunk = await self._read(_READ_CHUNK)
                if not chunk:
                    break
                yield chunk
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
            raise httpx.ProtocolError("truncated HTTP response body") from exc
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:  # noqa: BLE001, S110 - best-effort teardown
            pass

    async def _read(self, size: int) -> bytes:
        return await asyncio.wait_for(self._reader.read(size), self._timeout)

    async def _read_exact(self, size: int) -> bytes:
        """Read exactly ``size`` bytes, tolerating partial reader fills.

        ``asyncio.StreamReader.read(n)`` returns at most what is currently
        buffered, so large chunks must be accumulated across reads until the
        full chunk size is collected or the connection ends.
        """
        parts: list[bytes] = []
        remaining = size
        while remaining > 0:
            part = await self._read(remaining)
            if not part:
                raise httpx.ProtocolError("truncated chunk")
            parts.append(part)
            remaining -= len(part)
        return b"".join(parts)

    async def _read_until(self, sep: bytes) -> bytes:
        return await asyncio.wait_for(self._reader.readuntil(sep), self._timeout)

    async def _next_chunk(self) -> bytes:
        size_line = await self._read_until(b"\r\n")
        try:
            size = int(size_line.split(b";", 1)[0].strip(), 16)
        except ValueError as exc:
            raise httpx.ProtocolError("malformed chunked encoding") from exc
        if size == 0:
            trailer_bytes = 0
            while trailer_bytes <= _MAX_HEADER_BYTES:
                line = await self._read_until(b"\r\n")
                trailer_bytes += len(line)
                if line in (b"\r\n", b""):
                    return b""
            raise httpx.ProtocolError("chunked trailers too large")
        data = await self._read_exact(size)
        await self._read_until(b"\r\n")
        return data


def _build_request_bytes(request: httpx.Request) -> bytes:
    target = request.url.raw_path.decode("latin-1")
    port = request.url.port
    netloc = f"{request.url.host}:{port}" if port else request.url.host
    headers = [
        f"{request.method} {target} HTTP/1.1",
        f"Host: {netloc}",
    ]
    for name, value in request.headers.items():
        lower = name.casefold()
        if lower in ("host", "accept-encoding", "connection", "content-length"):
            continue
        headers.append(f"{name}: {value}")
    headers.append("Accept-Encoding: identity")
    body = request.content
    if body:
        headers.append(f"Content-Length: {len(body)}")
    return ("\r\n".join(headers) + "\r\n\r\n").encode("latin-1") + body


def _parse_status_code(status_line: bytes) -> int:
    try:
        status_code = int(status_line.split(b" ", 2)[1])
    except (IndexError, ValueError) as exc:
        raise httpx.ProtocolError("malformed status line") from exc
    if not 100 <= status_code <= 599:
        raise httpx.ProtocolError("invalid status code")
    return status_code


def _parse_header_block(header_bytes: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in header_bytes.split(b"\r\n"):
        if not line:
            continue
        name, sep, value = line.partition(b":")
        if not sep or not name:
            raise httpx.ProtocolError("malformed response header")
        headers[name.decode("latin-1").strip().casefold()] = value.decode("latin-1").strip()
    return headers


__all__ = [
    "Address",
    "ConnectionFactory",
    "NoDnsError",
    "NonPublicAddressError",
    "PinnedHttpsTransport",
    "Resolver",
    "is_public_address",
    "resolve_public_addresses",
]