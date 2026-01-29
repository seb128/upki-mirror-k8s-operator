#!/usr/bin/env python3
# Copyright Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for upki-mirror; a service for fetching and serving crlite filters."""

import logging
import os

import ops
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer

logger = logging.getLogger(__name__)


class UpkiMirrorCharm(ops.CharmBase):
    """Charmed Operator for upki-mirror; a service for fetching and serving crlite filters."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.nginx_pebble_ready, self._on_nginx_pebble_ready)

        self._container = self.unit.get_container("nginx")

        # Enable log forwarding for Loki and other charms that implement loki_push_api
        self._logging = LogProxyConsumer(
            self,
            relation_name="log-proxy",
            log_files=["/var/log/nginx/access.log", "/var/log/nginx/error.log"],
        )

        # Set up the ingress relation
        self._ingress = IngressPerAppRequirer(
            self,
            host=f"{self.app.name}.{self.model.name}.svc.cluster.local",
            port=80,
            strip_prefix=True,
        )

    def _on_nginx_pebble_ready(self, event: ops.WorkloadEvent):
        """Define and start a workload using the Pebble API."""
        self._container.add_layer("nginx", self.pebble_layer(), combine=True)
        self._container.exec(["/bin/upki-mirror", "/var/www/html"])
        self._container.replan()

        self.unit.open_port(protocol="tcp", port=80)
        self.unit.status = ops.ActiveStatus()

    def pebble_layer(self) -> ops.pebble.Layer:
        """Return a Pebble layer for managing UpkiMirror."""
        return ops.pebble.Layer(
            {
                "services": {
                    "upki-mirror": {
                        "override": "replace",
                        "summary": "nginx",
                        "command": "nginx -g 'daemon off;'",
                        "startup": "enabled",
                    }
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
                                "HTTP_PROXY": os.environ.get("JUJU_CHARM_HTTP_PROXY", ""),
                                "HTTPS_PROXY": os.environ.get("JUJU_CHARM_HTTPS_PROXY", ""),
                            },
                        },
                        "startup": "enabled",
                    },
                },
            }
        )


if __name__ == "__main__":  # pragma: nocover
    ops.main(UpkiMirrorCharm)
