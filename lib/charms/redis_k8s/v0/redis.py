"""Library for the redis relation.

This library contains the Requires and Provides classes for handling the
redis interface.

Import `RedisRequires` in your charm by adding the following to `src/charm.py`:
```
from charms.redis_k8s.v0.redis import RedisRequires

# In your charm's `__init__` method.
self.redis = RedisRequires(self, self._stored)
```
And then wherever you need to reference the relation data:
```
for redis_unit in self._stored.redis_relation:
    redis_host = self._stored.redis_relation[redis_unit]["hostname"]
    redis_port = self._stored.redis_relation[redis_unit]["port"]
```
"""
import logging

from ops.charm import CharmEvents
from ops.framework import EventBase, EventSource, Object

# The unique Charmhub library identifier, never change it
LIBID = "fe18a608cec5465fa5153e419abcad7b"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

logger = logging.getLogger(__name__)


class RedisRelationUpdatedEvent(EventBase):
    pass


class RedisRelationCharmEvents(CharmEvents):
    redis_relation_updated = EventSource(RedisRelationUpdatedEvent)


class RedisRequires(Object):
    def __init__(self, charm, _stored):
        # Define a constructor that takes the charm and it's StoredState
        super().__init__(charm, "redis")
        self.framework.observe(charm.on.redis_relation_changed, self._on_relation_changed)
        self.framework.observe(charm.on.redis_relation_broken, self._on_relation_broken)
        self._stored = _stored
        self.charm = charm

    def _on_relation_changed(self, event):
        if not event.unit:
            return

        hostname = event.relation.data[event.unit].get("hostname")
        port = event.relation.data[event.unit].get("port")
        # Store some data from the relation in local state
        self._stored.redis_relation[event.relation.id] = {"hostname": hostname, "port": port}

        # Trigger an event that our charm can react to.
        self.charm.on.redis_relation_updated.emit()

    def _on_relation_broken(self, event):
        # Remove the unit data from local state
        self._stored.redis_relation.pop(event.relation.id, None)

        # Trigger an event that our charm can react to.
        self.charm.on.redis_relation_updated.emit()


class RedisProvides(Object):
    def __init__(self, charm, port):
        super().__init__(charm, "redis")
        self.framework.observe(charm.on.redis_relation_changed, self._on_relation_changed)
        self._port = port

    def _on_relation_changed(self, event):
        if not self.model.unit.is_leader():
            logger.debug("Relation changes ignored by non-leader")
            return

        event.relation.data[self.model.unit]['hostname'] = str(self._bind_address(event))
        event.relation.data[self.model.unit]['port'] = str(self._port)
        # The reactive Redis charm exposes also 'password'. When tackling
        # https://github.com/canonical/redis-operator/issues/7 add 'password'
        # field so that it matches the exposed interface information from it.
        # event.relation.data[self.unit]['password'] = ''

    def _bind_address(self, event):
        relation = self.model.get_relation(event.relation.name, event.relation.id)
        if address := self.model.get_binding(relation).network.bind_address:
            return address
        return self.app.name
