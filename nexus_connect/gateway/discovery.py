from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Any


LEGACY_SERVICE_NAME = "_BRAHMA._tcp.local."


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


@dataclass(slots=True)
class GatewayDiscovery:
    service_name: str = "_NEXUS._tcp.local."
    _zeroconf: Any = None
    _service_info: Any = None
    _service_infos: list[Any] = field(default_factory=list)

    def start(self, *, host: str, port: int, properties: dict[str, str] | None = None) -> bool:
        try:
            from zeroconf import IPVersion, ServiceInfo, Zeroconf
        except Exception:
            return False

        try:
            self._zeroconf = Zeroconf(ip_version=IPVersion.All)
            address = socket.inet_aton(host if host and host != "0.0.0.0" else local_ip())
            encoded_properties = {
                k.encode("utf-8"): v.encode("utf-8")
                for k, v in (properties or {}).items()
            }

            # Advertise the new Nexus service and the old service type during
            # migration so already-installed companion versions can still pair.
            service_types = [(self.service_name, "Nexus Connect")]
            if self.service_name != LEGACY_SERVICE_NAME:
                service_types.append((LEGACY_SERVICE_NAME, "Brahma Connect"))

            for service_type, label in service_types:
                info = ServiceInfo(
                    type_=service_type,
                    name=f"{label}.{service_type}",
                    addresses=[address],
                    port=int(port),
                    properties=encoded_properties,
                )
                self._zeroconf.register_service(info)
                self._service_infos.append(info)

            self._service_info = self._service_infos[0] if self._service_infos else None
            return bool(self._service_infos)
        except Exception:
            self.stop()
            return False

    def stop(self) -> None:
        for info in list(self._service_infos):
            try:
                if self._zeroconf:
                    self._zeroconf.unregister_service(info)
            except Exception:
                pass
        try:
            if self._zeroconf:
                self._zeroconf.close()
        except Exception:
            pass
        self._service_infos.clear()
        self._zeroconf = None
        self._service_info = None
