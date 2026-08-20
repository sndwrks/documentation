#!/usr/bin/env python3
"""Screenshots of the device adoption flow.

Kept out of manifest.py because these shots cannot be captured on demand.
PendingAdoptionsSection returns null unless a device is actually sitting in the
adoption queue (PendingAdoptionsSection.tsx), and approving one is a one-shot
action that empties the queue again — so the state has to be staged by hand
immediately before a run.

Run them on their own:

    uv run --group screenshots scripts/screenshots/capture_adoption.py

Everything else about a Shot works exactly as it does in manifest.py.
"""

from manifest import SOFTWARE, Shot
from steps import button, click_sel, text

# The section is a plain <section> with CSS-module classes, so the class names
# are hashed at build time and [class*='pendingAdoptions'] can never match.
# Anchor on the heading instead — it is stable text the component always renders.
PENDING_SECTION = "section:has(h2:text-is('Pending adoptions'))"

STAGED = (
    "A device parked in the adoption queue. Power on an unadopted sndwrks "
    "sensor and leave it un-approved — without a pending request the whole "
    "section renders as null and neither shot can be taken."
)

ADOPTION_SHOTS = [
    Shot(
        name="adoption_pending-section",
        doc=SOFTWARE + "device-adoption.mdx",
        alt="The pending adoptions section on the devices page",
        goto="/devices",
        ready=[text("Pending adoptions")],
        clip=PENDING_SECTION,
        needs=STAGED,
    ),
    # Opens the drawer only. Never add a step that clicks Approve — that adopts
    # a real device and clears the queue this whole file depends on.
    Shot(
        name="adoption_drawer",
        doc=SOFTWARE + "device-adoption.mdx",
        alt="The adopt device drawer",
        goto="/devices",
        ready=[text("Pending adoptions")],
        steps=[
            click_sel(f"{PENDING_SECTION} tbody tr", nth=0),
            text("Adopt device"),
            button("Approve"),
        ],
        needs=STAGED,
    ),
]
