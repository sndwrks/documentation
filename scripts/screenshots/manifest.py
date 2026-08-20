#!/usr/bin/env python3
"""Declarative list of every screenshot the documentation needs.

This is the file you edit. capture.py just executes it.

Each Shot names an output PNG in src/assets/screenshots/, the doc page it
belongs to, a route to navigate to, readiness gates to wait on, and optional
interaction steps. Selectors are written against the sndwrks Local frontend
(../sndwrks-local/local-frontend).

Naming follows the newer `<page>_<thing>.png` convention already used by
router_message-routing.png, macros_panels-layout.png and haze-watch_live-tab.png.

Entries marked CALIBRATE use a selector inferred from the docs prose rather than
read off the app's route table — expect to adjust those on the first run using
the HTML dumps in .debug/.
"""

from dataclasses import dataclass, field

from steps import (
    button,
    check,
    click,
    click_if,
    click_sel,
    click_text,
    click_node,
    dialog,
    fill,
    gone,
    heading,
    node_edit,
    open_combobox,
    row_menu,
    searchbox,
    select,
    selector,
    sleep,
    text,
    textbox,
)

# ── Show-file bindings ───────────────────────────────────────────────
# These name real objects in your screenshot show file. Rename them to match
# whatever you actually build, rather than editing every Shot below.

DEMO_MACRO = "Screenshot Demo"
OSC_TRIGGER = "Demo OSC Trigger"
SACN_TRIGGER = "Demo sACN Trigger"
CLOCK_TRIGGER = "Demo Wall Clock"
SHARED_TRIGGER = "Demo Shared Trigger"
OCA_COMMAND = "10D Chan A Mute"
RAW_TCP_COMMAND = "Demo Raw TCP"
EMAIL_COMMAND = "Demo Email"
MAP_NODE = "Map"
EDGE_DETECT_NODE = "Edge Detect"
# A chat channel that exists in the show file. "General" was a guess and no
# such channel exists — these are the names ChatChannelList actually renders.
DEMO_CHANNEL = "Automation"
# A second, disposable human user. The permission editor must not be opened on
# your own account — editing your own permissions down raises a confirmation
# dialog over the drawer.
PERMISSIONS_USER = "Cassandra"
# An address offered by the Available Networks accordion on /utility/network.
# The scan shots add it to the include list themselves — Start Scan is disabled
# until at least one include network is set. Keep it a /24: the confirm modal
# prints a duration estimate, and a /16 makes that estimate read as nonsense.
SCAN_NETWORK = "10.101.31.1/24"
# AvailableNetworks.tsx renders each address as a span + "Add to Scan" button in
# a hashed-class div, so the address text is the only stable way in.
ADD_TO_SCAN = f"div:has(> span:text-is('{SCAN_NETWORK}')) button"

# Router matrix cells (RouterMatrixCrosspoint.tsx) — state lives in the
# accessible name, not in a class or testid.
CROSSPOINT = "[aria-label^='Crosspoint from source to destination']"
CROSSPOINT_CONNECTED = "[aria-label*='Connected and enabled']"

# The PSN tab still uses the matrix pattern, with its own label prefix. sACN
# no longer does — it is an engines table now (SacnEnginesPage.tsx), so its
# shots gate on the toolbar search box and real table rows instead.
PSN_CROSSPOINT = "[aria-label^='PSN crosspoint from']"
SACN_ENGINE_ROW = "table tbody tr"

# Overview tab chiclets (Overview.tsx) — keys are camelCase, labels are not.
OVERVIEW_TAB = "[data-testid='overview-tab-%s']"

SOFTWARE = "products/sndwrks-local/software/"


@dataclass
class Shot:
    name: str
    doc: str
    alt: str
    goto: str = "/"
    ready: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    clip: str = None
    full_page: bool = False
    context: str = "app"  # "app" (signed in) | "anon" (signed out)
    app_ready: bool = True  # wait for the signed-in app shell before starting
    block: list = field(default_factory=list)  # URL globs to abort
    settle_ms: int = 400
    destructive: bool = False  # changes server state; needs --include-destructive
    needs: str = None  # what the show file must contain for this to work

    @property
    def filename(self):
        return f"{self.name}.png"


APP_SHELL_MISSING = "Server disconnected"


SHOTS = [
    # ── Auth & connection ────────────────────────────────────────────
    # AuthGate wraps the app outside the router, so the login screen renders at
    # whatever URL is in the bar. Nothing to navigate to.
    Shot(
        name="auth_sign-in",
        doc=SOFTWARE + "users-and-permissions.mdx",
        alt="The sndwrks sign-in screen",
        goto="/",
        context="anon",
        app_ready=False,
        ready=[heading("Sign in"), text("Sign in to access this sndwrks server.")],
    ),
    Shot(
        name="auth_register",
        doc=SOFTWARE + "users-and-permissions.mdx",
        alt="The register form with the magic code field",
        goto="/",
        context="anon",
        app_ready=False,
        ready=[text("Sign in to access this sndwrks server.")],
        steps=[
            click("Register"),
            text("Enter the magic code from your administrator to join."),
        ],
    ),
    Shot(
        name="auth_server-disconnected",
        doc=SOFTWARE + "quick-setup.mdx",
        alt="The server disconnected screen",
        goto="/",
        app_ready=False,
        # ServerDisconnectedGate swaps in the whole screen after a 1000ms grace
        # period with no socket. Blocking socket.io is the reliable way to force it.
        block=["**/socket.io/**"],
        ready=[text("Server disconnected"), text("Trying to reconnect")],
        settle_ms=800,
    ),
    # ── Overview ─────────────────────────────────────────────────────
    # The overview is a tabbed dashboard now (Overview.tsx): analytics →
    # device monitoring → macro buttons. The tabs are react-tabs, NOT routes,
    # so these click rather than navigate. Every tab is double-gated on a
    # feature flag AND a permission, and a gated-off tab is absent from the DOM
    # rather than disabled — so a missing tab here means the signed-in account
    # or the server build lacks it, not a broken selector.
    Shot(
        name="overview_analytics",
        doc=SOFTWARE + "overview.mdx",
        alt="The analytics tab on the overview page",
        goto="/",
        # analytics is the first visible tab, so it is already selected
        ready=[
            selector(OVERVIEW_TAB % "analytics"),
            selector("[data-testid='analytics-tab']"),
            selector("[data-testid='stat-tile-messages-per-second']"),
        ],
        # the analytics subscription only starts once the tab is visible, so
        # the tiles and graphs need a beat to take on real values
        settle_ms=2_000,
        needs="A server that has been passing traffic for a few minutes, so the "
        "graphs are not flat and the tiles are not all zero.",
    ),
    Shot(
        name="overview_stat-tiles",
        doc=SOFTWARE + "overview.mdx",
        alt="The analytics stat tiles row",
        goto="/",
        ready=[selector("[data-testid='stat-tile-messages-per-second']")],
        # no testid on the row itself, so it is reached through a known tile
        clip="div:has(> [data-testid='stat-tile-messages-per-second'])",
        settle_ms=2_000,
        needs="Live traffic, otherwise every tile reads zero.",
    ),
    Shot(
        name="overview_network-stats",
        doc=SOFTWARE + "overview.mdx",
        alt="The network stats section of the analytics tab",
        goto="/",
        ready=[selector("[data-testid='network-stats-section']")],
        clip="[data-testid='network-stats-section']",
        settle_ms=2_000,
        needs="The network stats feature enabled and the account holding its "
        "view permission — the section is absent otherwise.",
    ),
    Shot(
        name="overview_device-monitoring",
        doc=SOFTWARE + "overview.mdx",
        alt="The device monitoring tab on the overview page",
        goto="/",
        ready=[selector(OVERVIEW_TAB % "deviceMonitoring")],
        steps=[
            click_sel(OVERVIEW_TAB % "deviceMonitoring"),
            selector("[data-testid^='device-cell-']"),
        ],
        needs="At least three devices with monitoring enabled, ideally a mix of "
        "connected and disconnected so the cell colours differ.",
    ),
    Shot(
        name="overview_macro-buttons",
        doc=SOFTWARE + "overview.mdx",
        alt="The macro buttons tab on the overview page",
        goto="/",
        ready=[selector(OVERVIEW_TAB % "macroButtons")],
        steps=[
            click_sel(OVERVIEW_TAB % "macroButtons"),
            text("macro buttons"),
        ],
        needs="At least three macro buttons configured — the panel reads "
        "'no macro buttons configured' otherwise.",
    ),
    Shot(
        name="overview_edit-modal",
        doc=SOFTWARE + "overview.mdx",
        alt="The Edit Macro Buttons modal",
        goto="/",
        ready=[selector(OVERVIEW_TAB % "macroButtons")],
        # icon-only button, named via its title attribute
        steps=[
            click_sel(OVERVIEW_TAB % "macroButtons"),
            click("edit macro buttons"),
            text("selected buttons (drag to reorder)"),
        ],
        needs="Several macros defined so 'available macros' is not empty.",
    ),
    # ── Devices ──────────────────────────────────────────────────────
    Shot(
        name="devices_list",
        doc=SOFTWARE + "devices.mdx",
        alt="The devices page",
        goto="/devices",
        ready=[gone("Loading devices..."), button("New Device")],
        needs="A spread of device types with presentable names — they also show "
        "up in the router matrix.",
    ),
    Shot(
        name="devices_new-device",
        doc=SOFTWARE + "devices.mdx",
        alt="New device page showing device creation in progress",
        goto="/devices",
        ready=[gone("Loading devices..."), button("New Device")],
        # An untouched New Device form is entirely blank, which does not match
        # "in progress" or the numbered steps in devices.mdx.
        steps=[
            click("New Device"),
            button("Save"),
            fill("IP Address", "10.0.10.42"),
            check("Enabled"),
            sleep(300),
        ],
    ),
    Shot(
        name="devices_editor-router-enabled",
        doc=SOFTWARE + "devices.mdx",
        alt="The device editor with Router enabled, revealing transport and message type",
        goto="/devices",
        ready=[gone("Loading devices..."), button("New Device")],
        steps=[click("New Device"), button("Save"), check("Router"), sleep(300)],
    ),
    Shot(
        name="devices_monitoring-options",
        doc=SOFTWARE + "devices.mdx",
        alt="The device monitoring options",
        goto="/devices",
        ready=[gone("Loading devices..."), button("New Device")],
        # The four options only exist inside the open Radix popup, which
        # portals to <body> — so this cannot be clipped to the drawer.
        steps=[
            click("New Device"),
            button("Save"),
            check("Monitoring"),
            sleep(300),
            open_combobox("Monitor Type"),
            text("OSC Ping/Pong"),
            sleep(300),
        ],
    ),
    Shot(
        name="devices_delete-confirm",
        doc=SOFTWARE + "devices.mdx",
        alt="Confirming deletion of a device",
        goto="/devices",
        ready=[gone("Loading devices..."), button("New Device")],
        steps=[
            click_sel("table tbody tr", nth=0),
            button("Save"),
            click("Delete"),
            text("Confirm Delete"),
        ],
        needs="At least one existing device to open.",
    ),
    # ── Router ───────────────────────────────────────────────────────
    # The matrix is a div grid, not a <table> (RouterMatrix.tsx). Every cell is
    # a button carrying its state in the accessible name, which makes
    # "a crosspoint that is actually wired up" directly selectable — clicking
    # an empty cell only selects it, so the editor would open blank.
    Shot(
        name="router_message-routing",
        doc=SOFTWARE + "router.mdx",
        alt="The message routing matrix",
        goto="/router/routing",
        ready=[selector(CROSSPOINT), sleep(500)],
        needs="A populated crosspoint matrix — several routed devices with a mix "
        "of on, off and filtered crosspoints so the legend is meaningful.",
    ),
    Shot(
        name="router_crosspoint-editor",
        doc=SOFTWARE + "router.mdx",
        alt="The crosspoint editor",
        goto="/router/routing",
        ready=[selector(CROSSPOINT_CONNECTED), sleep(500)],
        steps=[click_sel(CROSSPOINT_CONNECTED), text("destination"), sleep(400)],
        needs="At least one connected, enabled crosspoint.",
    ),
    Shot(
        name="router_crosspoint-filters",
        doc=SOFTWARE + "router.mdx",
        alt="Crosspoint filters",
        goto="/router/routing",
        ready=[selector(CROSSPOINT_CONNECTED), sleep(500)],
        # Nothing in the DOM marks which crosspoint carries filters — the
        # aria-label only distinguishes connected/enabled/disabled, and the
        # "filters on" state lives purely in a styled-components class. So this
        # indexes into the connected cells. Probed 2026-08-19: index 1 is
        # "Qlab Backup In -> Qlab Backup Out", the only one with filters.
        # Re-probe if the show file's routing changes.
        steps=[
            click_sel(CROSSPOINT_CONNECTED, nth=1),
            gone("No filters configured"),
            sleep(400),
        ],
        needs="Filters configured on the SECOND connected crosspoint in the "
        "matrix (reading order top-left to bottom-right). The capture asserts "
        "the filter list is non-empty and fails loudly if it is not.",
    ),
    # sACN is an engines table, not a matrix. The drawer is non-modal, so a full
    # page shot still shows the table behind it. Never match a Combobox by
    # accessible name while its popup is open — the trigger and the filter input
    # share the label (Combobox.tsx).
    Shot(
        name="router_sacn-engines",
        doc=SOFTWARE + "router.mdx",
        alt="The sACN engines table",
        goto="/router/sacn",
        ready=[searchbox("Search engines"), selector(SACN_ENGINE_ROW), sleep(500)],
        needs="At least two sACN engines — the tab shows 'No engines yet' until "
        "one exists. Ideally one in Backup mode with two or more inputs, and two "
        "engines sharing an output so the duplicate-output warning icon shows.",
    ),
    Shot(
        name="router_sacn-engine-drawer",
        doc=SOFTWARE + "router.mdx",
        alt="The sACN engine editor",
        goto="/router/sacn",
        ready=[searchbox("Search engines"), selector(SACN_ENGINE_ROW), sleep(500)],
        steps=[click_sel(SACN_ENGINE_ROW), heading("Merge"), sleep(400)],
        needs="At least one sACN engine with several inputs, so the Inputs "
        "section is not a single row.",
    ),
    Shot(
        name="router_sacn-bulk-create",
        doc=SOFTWARE + "router.mdx",
        alt="Bulk creating sACN engines",
        goto="/router/sacn",
        # the toolbar is there whether or not any engines exist, and the modal
        # opens empty, so this one needs no staged data at all
        ready=[searchbox("Search engines"), sleep(500)],
        # The modal opens empty and shows a validation error until it is filled,
        # so the shot has to walk the same worked example the docs describe.
        # Interfaces are whatever the capture host actually has; probed
        # 2026-08-19 as utun11 / vlan0 / vlan1.
        steps=[
            click("Bulk Create"),
            text("Bulk Create Engines"),
            fill("Base Name", "Stage"),
            select("Source Interface", "vlan0"),
            fill("Source Universe Range", "1-8"),
            select("Destination Interface", "vlan1"),
            fill("Destination Universe Range", "101-108"),
            gone("Give the engines a base name."),
            sleep(400),
        ],
        needs="Nothing staged, but the capture host must expose the interfaces "
        "named in the steps above.",
    ),
    Shot(
        name="router_psn",
        doc=SOFTWARE + "router.mdx",
        alt="PSN routing",
        goto="/router/psn",
        ready=[selector(PSN_CROSSPOINT), sleep(500)],
        needs="PSN routing configured between at least two endpoints.",
    ),
    Shot(
        name="router_messages",
        doc=SOFTWARE + "router.mdx",
        alt="The router messages tab with live traffic",
        goto="/router/messages",
        ready=[searchbox("Search messages")],
        settle_ms=1500,
        needs="Live message traffic flowing so the list is not empty.",
    ),
    # ── Macros ───────────────────────────────────────────────────────
    # MacroCanvasToolbar's sidebar toggle flips its title between
    # "open sidebar" and "close sidebar", so click_if only fires when collapsed.
    Shot(
        name="macros_panels-layout",
        doc=SOFTWARE + "macros.mdx",
        alt="The macros page: controls along the top, nodes down the side, canvas in the middle",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("open sidebar"),
            select("select macro", DEMO_MACRO),
            gone("select a macro to view its canvas"),
            sleep(600),
        ],
        needs=f'A macro named "{DEMO_MACRO}" with a clean trigger to command flow.',
    ),
    Shot(
        name="macros_canvas-example",
        doc=SOFTWARE + "macros.mdx",
        alt="A completed macro on the canvas",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("close sidebar"),
            select("select macro", DEMO_MACRO),
            gone("select a macro to view its canvas"),
            sleep(600),
        ],
        needs=f'A macro named "{DEMO_MACRO}".',
    ),
    Shot(
        name="macros_trigger-editor-osc",
        doc=SOFTWARE + "macros.mdx",
        alt="The OSC trigger editor showing match type",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        # clicking the sidebar row only selects it — the editor is behind the
        # row's "actions" dropdown (MacroCanvasSidebarItem.tsx:67)
        steps=[
            click_if("open sidebar"),
            row_menu("[draggable='true']", OSC_TRIGGER),
            click_text("Edit"),
            text("Match Type"),
            sleep(400),
        ],
        needs=f'A custom OSC trigger named "{OSC_TRIGGER}".',
    ),
    Shot(
        name="macros_trigger-editor-sacn",
        doc=SOFTWARE + "macros.mdx",
        alt="The sACN trigger editor",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("open sidebar"),
            row_menu("[draggable='true']", SACN_TRIGGER),
            click_text("Edit"),
            text("Universe"),
            sleep(400),
        ],
        needs=f'An sACN trigger named "{SACN_TRIGGER}".',
    ),
    Shot(
        name="macros_trigger-editor-wall-clock",
        doc=SOFTWARE + "macros.mdx",
        alt="The wall clock trigger editor",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("open sidebar"),
            row_menu("[draggable='true']", CLOCK_TRIGGER),
            click_text("Edit"),
            text("Timezone"),
            sleep(400),
        ],
        needs=f'A wall clock trigger named "{CLOCK_TRIGGER}".',
    ),
    Shot(
        name="macros_macros-using-this-trigger",
        doc=SOFTWARE + "macros.mdx",
        alt="The Macros using this trigger section of the trigger editor",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("open sidebar"),
            row_menu("[draggable='true']", SHARED_TRIGGER),
            click_text("Edit"),
            text("macros using this trigger"),
            sleep(400),
        ],
        # the box is a plain div whose heading is an h3 — the CSS-module class
        # is hashed, so anchor on the heading text instead
        clip="div:has(> h3:text-is('Macros using this trigger'))",
        needs=f'A trigger named "{SHARED_TRIGGER}" used by two or more macros.',
    ),
    Shot(
        name="macros_command-device-oca",
        doc=SOFTWARE + "macros.mdx",
        # Not the object tree: a d&b target renders DnbCommandConfig's channel
        # picker (Channel -> Ch D -> Mute/Unmute, with the resolved OcaMute -
        # Config / Mute path underneath). macros.mdx:145 describes browsing the
        # object tree itself, which needs a non-d&b AES70 device to illustrate.
        alt="A d&b device command muting an OCA channel",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("open sidebar"),
            # This one sits far enough down the sidebar list that hovering it
            # times out, unlike the shorter-named commands above. The sidebar's
            # filter box narrows the list to a single row first; it is cleared
            # again once the editor is open so the sidebar looks normal in the
            # shot.
            fill("filter...", OCA_COMMAND),
            row_menu("[draggable='true']", OCA_COMMAND),
            click_text("Edit"),
            fill("filter...", ""),
            text("Command Type"),
            sleep(1200),
        ],
        needs=f'A device command named "{OCA_COMMAND}" pointing at a reachable '
        "AES70/OCA device, so the object tree actually populates. The command "
        "cannot even be saved without one — a target is required, the target "
        "picker only fills from a live device, and the server rejects the save "
        "with 'Please fix validation errors before saving.' Note the Device "
        "picker lists only macro-enabled devices, and a d&b device renders "
        "DnbCommandConfig's target picker rather than the AES70 object tree.",
    ),
    Shot(
        name="macros_command-raw-tcp",
        doc=SOFTWARE + "macros.mdx",
        alt="The raw TCP command editor",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("open sidebar"),
            row_menu("[draggable='true']", RAW_TCP_COMMAND),
            click_text("Edit"),
            text("Framing Type"),
            sleep(400),
        ],
        needs=f'A raw TCP command named "{RAW_TCP_COMMAND}".',
    ),
    Shot(
        name="macros_command-email",
        doc=SOFTWARE + "macros.mdx",
        alt="The email command editor",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("open sidebar"),
            row_menu("[draggable='true']", EMAIL_COMMAND),
            click_text("Edit"),
            text("Subject"),
            sleep(400),
        ],
        needs=f'An email command named "{EMAIL_COMMAND}".',
    ),
    Shot(
        name="macros_transformer-map",
        doc=SOFTWARE + "macros.mdx",
        alt="The Map transformer editor",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("close sidebar"),
            select("select macro", DEMO_MACRO),
            gone("select a macro to view its canvas"),
            node_edit(MAP_NODE),
            sleep(600),
        ],
        needs=f'The "{DEMO_MACRO}" macro must contain a Map transformer node.',
    ),
    Shot(
        name="macros_transformer-edge-detect",
        doc=SOFTWARE + "macros.mdx",
        alt="The Edge Detect transformer editor",
        goto="/macros",
        ready=[
            gone("loading canvas..."),
            # "loading canvas..." detaches before the toolbar and the
            # sidebar list actually mount, so steps that reach for a
            # sidebar row race the render without these
            selector("button[title='new macro']"),
            selector(".react-flow__pane"),
            sleep(400),
        ],
        steps=[
            click_if("close sidebar"),
            select("select macro", DEMO_MACRO),
            gone("select a macro to view its canvas"),
            node_edit(EDGE_DETECT_NODE),
            sleep(600),
        ],
        needs=f'The "{DEMO_MACRO}" macro must contain an Edge Detect transformer node.',
    ),
    # ── Haze Watch ───────────────────────────────────────────────────
    Shot(
        name="haze-watch_live-tab",
        doc=SOFTWARE + "haze-watch.mdx",
        alt="The Haze Watch live tab",
        goto="/haze-watch/live",
        ready=[text("Current Average")],
        settle_ms=1500,
        needs="Sensors reporting, with enough history for the moving average "
        "graph to draw a real line.",
    ),
    Shot(
        name="haze-watch_triggers",
        doc=SOFTWARE + "haze-watch.mdx",
        alt="The Haze Watch triggers tab",
        goto="/haze-watch/triggers",
        ready=[gone("Loading triggers...")],
        needs="At least two configured haze triggers.",
    ),
    Shot(
        name="haze-watch_trigger-editor",
        doc=SOFTWARE + "haze-watch.mdx",
        alt="The Haze Watch trigger editor",
        goto="/haze-watch/triggers",
        ready=[gone("Loading triggers...")],
        steps=[click_sel("table tbody tr", nth=0), sleep(400)],
        needs="At least one configured haze trigger.",
    ),
    Shot(
        name="haze-watch_commands",
        doc=SOFTWARE + "haze-watch.mdx",
        alt="The Haze Watch commands tab",
        goto="/haze-watch/commands",
        ready=[gone("Loading commands...")],
        needs="At least two configured haze commands.",
    ),
    Shot(
        name="haze-watch_command-editor",
        doc=SOFTWARE + "haze-watch.mdx",
        alt="The Haze Watch command editor with above, below and E-Stop messages",
        goto="/haze-watch/commands",
        ready=[gone("Loading commands...")],
        steps=[click_sel("table tbody tr", nth=0), sleep(400)],
        needs="At least one haze command with above, below and E-Stop messages set.",
    ),
    # ── Chat ─────────────────────────────────────────────────────────
    Shot(
        name="chat_overview",
        doc=SOFTWARE + "chat.mdx",
        alt="The chat page",
        goto="/chat",
        ready=[button("new channel")],
        settle_ms=800,
        needs="Three or four channels with message history at mixed priorities "
        "(info, attention, urgent) so the styling differences are visible.",
    ),
    Shot(
        name="chat_channel-row-menu",
        doc=SOFTWARE + "chat.mdx",
        alt="The channel list with the row menu open",
        goto="/chat",
        ready=[button("new channel")],
        steps=[
            row_menu("[class*='channelRow']", DEMO_CHANNEL),
            text("OSC API"),
        ],
        needs=f'A channel named "{DEMO_CHANNEL}".',
    ),
    Shot(
        name="chat_speed-buttons-dialog",
        doc=SOFTWARE + "chat.mdx",
        alt="The speed buttons dialog",
        goto="/chat",
        ready=[button("new channel")],
        steps=[click("Manage speed buttons"), dialog("Speed Buttons")],
        needs="A few speed buttons already configured, at least one with confetti.",
    ),
    Shot(
        name="chat_osc-api-dialog",
        doc=SOFTWARE + "chat.mdx",
        alt="The OSC API dialog for a chat channel",
        goto="/chat",
        ready=[button("new channel")],
        steps=[
            row_menu("[class*='channelRow']", DEMO_CHANNEL),
            # SndwrksDropdownMenu items are role="menuitem", not buttons.
            click_text("OSC API"),
            dialog("OSC API"),
        ],
        needs=f'A channel named "{DEMO_CHANNEL}".',
    ),
    # ── Utility ──────────────────────────────────────────────────────
    Shot(
        name="utility_network-scan-config",
        doc=SOFTWARE + "utility.mdx",
        alt="The network scan configuration panel",
        goto="/utility/network",
        ready=[text("Scan Speeds")],
        needs="Interfaces configured so the available networks accordion has "
        "real subnets in it.",
    ),
    Shot(
        name="utility_scan-confirm",
        doc=SOFTWARE + "utility.mdx",
        alt="The Start Network Scan confirmation summary",
        goto="/utility/network",
        ready=[text("Scan Speeds")],
        steps=[
            click_sel(ADD_TO_SCAN),
            click("Start Scan"),
            text("Start Network Scan?"),
        ],
        needs="A small include range preloaded so the estimate reads sensibly. "
        "Start Scan stays disabled until at least one valid include network is "
        "set. If a previous scan's results are still on screen, press New Scan "
        "first — ScanResults renders in place of the config form.",
    ),
    Shot(
        name="utility_scan-progress",
        doc=SOFTWARE + "utility.mdx",
        alt="A network scan in progress",
        goto="/utility/network",
        ready=[text("Scan Speeds")],
        steps=[
            click_sel(ADD_TO_SCAN),
            click("Start Scan"),
            text("Start Network Scan?"),
            # ScanConfirmModal's primary action is "Confirm", and its label
            # wraps a <Kbd>, so the accessible name is "Confirm \u23ce".
            click("Confirm", exact=False),
            button("Cancel Scan"),
        ],
        # Do NOT raise settle_ms here. The confirm modal estimates ~13s for a
        # /24 at cruise, but the mocked scanner ignores speed and returns in
        # about a second — a 4s settle lands on ScanResults with the
        # "Network scan complete" toast still up. The default 400ms is the only
        # window ScanRunning is actually on screen, so this shot reads
        # "0% — 0 devices found — Elapsed: 0s". That is the honest running
        # state; against a real scanner it will fill in on its own.
        destructive=True,
        needs="Nothing preloaded — the shot scans SCAN_NETWORK itself.",
    ),
    Shot(
        name="utility_scan-results",
        doc=SOFTWARE + "utility.mdx",
        alt="Network scan results",
        goto="/utility/network",
        ready=[text("Scan Speeds")],
        # scanStatus and currentNetworkScan live in the frontend store, and
        # NetworkScan only renders ScanResults while hasResults is true. Nothing
        # rehydrates that on load, so a scan run in an earlier session is gone by
        # the time this navigates — the shot has to run its own scan and sit
        # through it. "New Scan" is ScanResults' action bar, i.e. the completion
        # signal; the timeout covers the scan itself, not just a render.
        steps=[
            click_sel(ADD_TO_SCAN),
            click("Start Scan"),
            text("Start Network Scan?"),
            click("Confirm", exact=False),
            button("New Scan", timeout=120_000),
        ],
        destructive=True,
        needs="Nothing preloaded — the shot scans SCAN_NETWORK itself. Keep that "
        "a /24 at cruise speed so the wait stays inside the timeout.",
    ),
    Shot(
        name="utility_events",
        doc=SOFTWARE + "utility.mdx",
        alt="The events tab",
        goto="/utility/events",
        ready=[gone("Loading events...")],
        needs="Enough server history that the events list is full.",
    ),
    Shot(
        name="utility_syslog",
        doc=SOFTWARE + "utility.mdx",
        alt="The syslog tab",
        goto="/utility/syslog",
        ready=[gone("Loading syslog messages...")],
        needs="A device shipping syslog to the server on UDP 1514.",
    ),
    Shot(
        name="utility_psn-monitor",
        doc=SOFTWARE + "utility.mdx",
        alt="The PSN monitor",
        goto="/utility/psn",
        settle_ms=1500,
        needs="A PSN source sending trackers, otherwise this shows the "
        "'No PSN trackers are currently being received.' empty state. The tab "
        "only exists when features.router.psn.base is on.",
    ),
    Shot(
        name="utility_sacn-monitor",
        doc=SOFTWARE + "utility.mdx",
        alt="The sACN monitor with a universe selected",
        goto="/utility/sacn",
        ready=[selector("[data-testid^='universe-row-']")],
        steps=[
            click_sel("[data-testid^='universe-row-']", nth=0),
            click_sel("[data-testid^='source-button-']", nth=0),
            selector("[data-testid='sacn-dmx-grid']"),
        ],
        needs="A live sACN source transmitting on at least one universe.",
    ),
    # ── Settings ─────────────────────────────────────────────────────
    # Every panel is a real route. Note hazeWatch and backupRestore are
    # camelCase while the top-level routes are kebab-case.
    Shot(
        name="settings_global",
        doc=SOFTWARE + "settings.mdx",
        alt="The global settings panel",
        goto="/settings/global",
        ready=[heading("Global")],
    ),
    Shot(
        name="settings_server",
        doc=SOFTWARE + "settings.mdx",
        alt="The Server settings panel with its interface list and network parameters",
        goto="/settings/server",
        ready=[heading("Server")],
        needs="Interfaces configured with at least one VLAN, so the panel is not bare.",
    ),
    Shot(
        name="settings_profile",
        doc=SOFTWARE + "settings.mdx",
        alt="The profile settings panel",
        goto="/settings/profile",
        ready=[heading("Profile")],
    ),
    Shot(
        name="settings_users",
        doc=SOFTWARE + "settings.mdx",
        alt="The users settings panel",
        goto="/settings/users",
        ready=[heading("Users"), gone("No users yet.")],
        needs="Two or more users, so the list is not a single row.",
    ),
    Shot(
        name="settings_users-add",
        doc=SOFTWARE + "users-and-permissions.mdx",
        alt="The add user form",
        goto="/settings/users",
        ready=[heading("Users")],
        steps=[click("Add user"), sleep(400)],
    ),
    Shot(
        name="settings_users-permissions",
        doc=SOFTWARE + "users-and-permissions.mdx",
        alt="The permission editor for a user",
        goto="/settings/users",
        # UserSettings.tsx renders a div list of UserRow cards, not a table, and
        # the section heading carries a count ("Users (7)") so it will not match
        # exactly. The "New user defaults" title is the one fixed string here.
        ready=[text("New user defaults")],
        steps=[
            # UserRow's only named control is its dropdown trigger.
            click_sel(f"[aria-label='Actions for {PERMISSIONS_USER}']"),
            click_text("Permissions"),
            text(f"Permissions \u2014 {PERMISSIONS_USER}"),
            sleep(400),
        ],
        needs=f'A second human user named "{PERMISSIONS_USER}" to open, so you '
        "are not editing your own permissions. It must not be an isSndwrks "
        "user — their permissions are locked to full and the Permissions menu "
        "item renders disabled.",
    ),
    Shot(
        name="settings_chat",
        doc=SOFTWARE + "settings.mdx",
        alt="The chat notification settings panel",
        goto="/settings/chat",
        ready=[heading("Chat")],
    ),
    Shot(
        name="settings_router",
        doc=SOFTWARE + "settings.mdx",
        alt="The router settings panel",
        goto="/settings/router",
        ready=[heading("Router")],
    ),
    Shot(
        name="settings_sacn",
        doc=SOFTWARE + "settings.mdx",
        alt="The sACN settings panel",
        goto="/settings/sacn",
        ready=[heading("sACN")],
    ),
    Shot(
        name="settings_psn",
        doc=SOFTWARE + "settings.mdx",
        alt="The PSN settings panel",
        goto="/settings/psn",
        ready=[heading("PSN")],
    ),
    Shot(
        name="settings_syslog",
        doc=SOFTWARE + "settings.mdx",
        alt="The syslog settings panel",
        goto="/settings/syslog",
        ready=[heading("Syslog")],
    ),
    Shot(
        name="settings_backup-restore",
        doc=SOFTWARE + "settings.mdx",
        alt="The backup and restore settings panel",
        goto="/settings/backupRestore",
        ready=[heading("Backup & Restore")],
    ),
]


# Screenshots the docs reference that this harness deliberately does not take:
#
#   quick-setup.mdx — the browser's certificate-untrusted warning. That is
#   browser chrome, not page content, and page.screenshot() cannot reach it.


def by_name(name):
    for shot in SHOTS:
        if shot.name == name:
            return shot
    return None
