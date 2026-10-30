import asyncio
from pathlib import Path

from nexus_connect.gateway.command_router import CommandRouter
from nexus_connect.gateway.device_manager import DeviceManager
from nexus_connect.gateway.capability_manager import CapabilityManager
from nexus_connect.gateway.models import DeviceRecord
from nexus_connect.gateway.pairing import PairingManager
from nexus_connect.gateway.protocol import ProtocolTypes, build_message, validate_message
from nexus_connect.gateway.websocket import ConnectionHub


def test_protocol_message_has_required_fields():
    message = build_message(ProtocolTypes.HELLO, {"hello": True})

    assert message["type"] == ProtocolTypes.HELLO
    assert message["request_id"]
    assert message["timestamp"]
    assert message["payload"] == {"hello": True}
    assert validate_message(message) == (True, "")


def test_device_manager_persists_and_authenticates(tmp_path: Path):
    registry_path = tmp_path / "devices.json"
    manager = DeviceManager(registry_path)

    record, secret = manager.create_from_pairing(
        name="Galaxy S24",
        platform="android",
        os_version="14",
        agent_version="1.0.0",
        ip="192.168.1.12",
        capabilities=["camera", "screen_capture"],
        permissions=["camera"],
    )

    assert record.device_id
    assert secret
    assert registry_path.exists()

    loaded = DeviceManager(registry_path)
    fetched = loaded.get(record.device_id)
    assert fetched is not None
    assert fetched.name == "Galaxy S24"

    authenticated = loaded.authenticate(record.device_id, secret, ip="192.168.1.13")
    assert authenticated is not None
    assert authenticated.online is True
    assert authenticated.ip == "192.168.1.13"


def test_pairing_manager_returns_expiring_offer():
    pairing = PairingManager(ttl_seconds=120)
    offer = pairing.create_offer("192.168.1.20", 8765)

    assert offer.service == "_NEXUS._tcp.local."
    assert offer.host == "192.168.1.20"
    assert len(offer.pairing_code) == 6
    assert pairing.get_offer(offer.pairing_token) is not None
    assert pairing.get_offer_by_code(offer.pairing_code) is not None


def test_command_router_reports_offline_device(tmp_path: Path):
    registry_path = tmp_path / "devices.json"
    manager = DeviceManager(registry_path)
    record = DeviceRecord(
        device_id="android_001",
        name="Galaxy S24",
        platform="android",
        online=False,
        capabilities=["camera"],
    )
    manager._devices[record.device_id] = record
    manager.save()

    router = CommandRouter(manager, ConnectionHub(), CapabilityManager())
    result = asyncio.run(router.route("Galaxy S24", "launch_app", {"package": "com.spotify.music"}))

    assert result["success"] is False
    assert "offline" in result["error"].lower()


def test_legacy_connect_config_migrates_to_nexus_user_data(tmp_path, monkeypatch):
    import json
    from nexus_connect.gateway.server import NexusGatewayConfig

    user_data = tmp_path / "user-data"
    config_dir = user_data / "config"
    config_dir.mkdir(parents=True)
    legacy_config = config_dir / "brahma_connect.json"
    legacy_config.write_text(json.dumps({
        "host": "127.0.0.1",
        "port": 9876,
        "service_name": "_BRAHMA._tcp.local.",
    }), encoding="utf-8")

    monkeypatch.setattr(
        "nexus_connect.gateway.server.get_user_data_dir",
        lambda: user_data,
    )
    config = NexusGatewayConfig.load(tmp_path / "bundle")

    assert config.port == 9876
    assert config.service_name == "_NEXUS._tcp.local."
    assert (config_dir / "nexus_connect.json").exists()
    assert config.registry_path == config_dir / "nexus_connect" / "devices.json"


def test_gateway_discovery_advertises_nexus_and_legacy_service(monkeypatch):
    import sys
    from types import SimpleNamespace
    from nexus_connect.gateway.discovery import GatewayDiscovery

    class FakeServiceInfo:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeZeroconf:
        def __init__(self, **kwargs):
            self.registered = []
            self.unregistered = []
            self.closed = False

        def register_service(self, info):
            self.registered.append(info)

        def unregister_service(self, info):
            self.unregistered.append(info)

        def close(self):
            self.closed = True

    fake_module = SimpleNamespace(
        IPVersion=SimpleNamespace(All=object()),
        ServiceInfo=FakeServiceInfo,
        Zeroconf=FakeZeroconf,
    )
    monkeypatch.setitem(sys.modules, "zeroconf", fake_module)

    discovery = GatewayDiscovery()
    assert discovery.start(host="127.0.0.1", port=8765)
    service_types = {item.type_ for item in discovery._service_infos}
    assert service_types == {"_NEXUS._tcp.local.", "_BRAHMA._tcp.local."}

    zeroconf = discovery._zeroconf
    discovery.stop()
    assert len(zeroconf.unregistered) == 2
    assert zeroconf.closed is True
