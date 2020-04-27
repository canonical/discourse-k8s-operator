import sys
sys.path.append('lib')  # noqa: E402

from ops.charm import CharmBase, CharmEvents  # NoQA: E402
from ops.main import main  # NoQA: E402
from ops.framework import EventBase, EventSource, StoredState  # NoQA: E402
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus  # NoQA: E402


class MyCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self.on_start)

    def on_start(self, event):
        # Handle the start event here.
        return


if __name__ == "__main__":
    main(MyCharm)
