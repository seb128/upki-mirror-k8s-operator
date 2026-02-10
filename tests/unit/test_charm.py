# Copyright Canonical Ltd.
# See LICENSE file for licensing details.


import pytest
from ops.pebble import ServiceStatus
from ops.testing import (
    ActiveStatus,
    BlockedStatus,
    Container,
    Context,
    Exec,
    State,
    TCPPort,
)

from charm import UpkiMirrorCharm


@pytest.fixture
def charm():
    yield UpkiMirrorCharm


@pytest.fixture
def loaded_ctx(charm):
    ctx = Context(charm)
    container = Container(
        name="nginx",
        can_connect=True,
        execs={Exec(("/bin/upki-mirror", "/var/www/html"))},
    )
    return (ctx, container)


def test_nginx_pebble_ready(loaded_ctx):
    ctx, container = loaded_ctx
    state = State(containers=[container])

    result = ctx.run(ctx.on.pebble_ready(container=container), state)

    assert result.get_container("nginx").layers["nginx"] == {
        "services": {
            "nginx": {
                "override": "replace",
                "summary": "nginx",
                "command": "nginx -g 'daemon off;'",
                "startup": "enabled",
            },
        },
        "checks": {
            "up": {
                "override": "replace",
                "level": "alive",
                "period": "30s",
                "tcp": {"port": 80},
                "startup": "enabled",
            },
            "fetch": {
                "override": "replace",
                "level": "alive",
                "period": "360m",
                "exec": {
                    "command": "/bin/upki-mirror /var/www/html",
                    "environment": {
                        "HTTP_PROXY": "",
                        "HTTPS_PROXY": "",
                    },
                },
                "startup": "enabled",
            },
        },
    }
    assert result.get_container("nginx").service_statuses == {
        "nginx": ServiceStatus.ACTIVE,
    }
    assert result.opened_ports == frozenset({TCPPort(80)})
    assert result.unit_status == ActiveStatus()


def test_nginx_pebble_ready_exec_error(charm):
    ctx = Context(charm)
    container = Container(
        name="nginx",
        can_connect=True,
        execs={
            Exec(
                ("/bin/upki-mirror", "/var/www/html"),
                return_code=1,
                stderr="Failed to fetch mirror",
            )
        },
    )
    state = State(containers=[container])

    result = ctx.run(ctx.on.pebble_ready(container=container), state)

    assert "nginx" in result.get_container("nginx").layers
    assert result.get_container("nginx").service_statuses == {}
    assert result.opened_ports == frozenset()
    assert result.unit_status == BlockedStatus("Initial mirror fetch failed")
