#!/usr/bin/env python3
"""Step and readiness primitives used to describe screenshots in manifest.py.

Every step is a small object with an ``apply(page)`` method and a readable
``str()``. The runner reports the exact step that failed, so a broken selector
tells you which line of the manifest to fix.

Accessible-name matching is case-insensitive by default. The app applies
``text-transform: lowercase`` to its tab links (``tabStyleReactRouter.js``) and
Playwright honours ``text-transform`` when computing accessible names, so a
literal "Message Routing" would not match the rendered "message routing".
"""

import re

DEFAULT_TIMEOUT = 10_000
READY_TIMEOUT = 20_000


# Buttons that carry a keyboard shortcut render it in a <kbd> inside the label
# (ui/Kbd.tsx), and the accessible name picks that up — the "Save" button is
# really named "Save ⏎", "Discard" is "Discard esc". Those two are the only
# hints the app uses, so they are allowed as an optional tail on an anchored
# match. Passing exact=False instead would also make "Save" match "Save As".
KBD_HINTS = ("⏎", "esc")


def _name(value, exact=True):
    """Build a case-insensitive name matcher, anchored unless exact=False."""
    if isinstance(value, re.Pattern):
        return value
    if exact:
        tail = "|".join(re.escape(hint) for hint in KBD_HINTS)
        return re.compile(rf"^\s*{re.escape(value)}(?:\s*(?:{tail}))?\s*$", re.I)
    return re.compile(re.escape(value), re.I)


class Step:
    """Base class. Subclasses implement apply() and __str__()."""

    def __init__(self, timeout=DEFAULT_TIMEOUT):
        self.timeout = timeout

    def apply(self, page):
        raise NotImplementedError

    def __repr__(self):
        return str(self)


# ── Waiting / readiness ──────────────────────────────────────────────


class WaitText(Step):
    """Wait for literal text to be visible anywhere on the page."""

    def __init__(self, value, exact=False, timeout=READY_TIMEOUT):
        super().__init__(timeout)
        self.value = value
        self.exact = exact

    def apply(self, page):
        page.get_by_text(self.value, exact=self.exact).first.wait_for(
            state="visible", timeout=self.timeout
        )

    def __str__(self):
        return f'wait for text "{self.value}"'


class WaitGone(Step):
    """Wait for text to be absent or hidden. Used for loading states."""

    def __init__(self, value, timeout=READY_TIMEOUT):
        super().__init__(timeout)
        self.value = value

    def apply(self, page):
        page.get_by_text(self.value, exact=False).first.wait_for(
            state="hidden", timeout=self.timeout
        )

    def __str__(self):
        return f'wait for "{self.value}" to disappear'


class WaitRole(Step):
    def __init__(self, role, value, exact=True, timeout=READY_TIMEOUT):
        super().__init__(timeout)
        self.role = role
        self.value = value
        self.exact = exact

    def apply(self, page):
        page.get_by_role(self.role, name=_name(self.value, self.exact)).first.wait_for(
            state="visible", timeout=self.timeout
        )

    def __str__(self):
        return f'wait for {self.role} "{self.value}"'


class WaitSelector(Step):
    def __init__(self, selector, timeout=READY_TIMEOUT):
        super().__init__(timeout)
        self.selector = selector

    def apply(self, page):
        page.locator(self.selector).first.wait_for(state="visible", timeout=self.timeout)

    def __str__(self):
        return f"wait for selector {self.selector}"


class Sleep(Step):
    """Fixed pause. Use sparingly — prefer a real readiness signal."""

    def __init__(self, ms):
        super().__init__(ms)
        self.ms = ms

    def apply(self, page):
        page.wait_for_timeout(self.ms)

    def __str__(self):
        return f"sleep {self.ms}ms"


# ── Interaction ──────────────────────────────────────────────────────


class ClickRole(Step):
    def __init__(self, role, value, exact=True, nth=None, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.role = role
        self.value = value
        self.exact = exact
        self.nth = nth

    def _locator(self, page):
        # Icon-only buttons here carry a `title` and no aria-label, and a title
        # only becomes the accessible name when the element has no text content.
        # The sidebar toggle renders "≡", so it is named "≡" and get_by_role
        # never matches "open sidebar" — hence the title fallback.
        loc = page.get_by_role(self.role, name=_name(self.value, self.exact))
        loc = loc.or_(page.get_by_title(self.value, exact=self.exact))
        return loc.first if self.nth is None else loc.nth(self.nth)

    def apply(self, page):
        self._locator(page).click(timeout=self.timeout)

    def __str__(self):
        suffix = "" if self.nth is None else f" [{self.nth}]"
        return f'click {self.role} "{self.value}"{suffix}'


class ClickRoleIfPresent(ClickRole):
    """Click only if the target exists. For toggles whose label flips state."""

    def apply(self, page):
        loc = self._locator(page)
        if loc.count() and loc.is_visible():
            loc.click(timeout=self.timeout)

    def __str__(self):
        return f'click {self.role} "{self.value}" if present'


class ClickSelector(Step):
    def __init__(self, selector, nth=0, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.selector = selector
        self.nth = nth

    def apply(self, page):
        page.locator(self.selector).nth(self.nth).click(timeout=self.timeout)

    def __str__(self):
        return f"click {self.selector} [{self.nth}]"


class ClickText(Step):
    def __init__(self, value, exact=False, nth=0, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.value = value
        self.exact = exact
        self.nth = nth

    def apply(self, page):
        page.get_by_text(self.value, exact=self.exact).nth(self.nth).click(
            timeout=self.timeout
        )

    def __str__(self):
        return f'click text "{self.value}"'


class ClickRowMenu(Step):
    """Click the trailing icon button of a row identified by its text.

    The chat channel row menu (ChatChannelList.tsx) is an icon-only button with
    no accessible name and no stable class, and it is only revealed on hover or
    when its row is selected — hence hover-then-click-last-button.
    """

    def __init__(self, row_selector, row_text, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.row_selector = row_selector
        self.row_text = row_text

    def apply(self, page):
        row = page.locator(self.row_selector).filter(has_text=self.row_text).first
        row.hover(timeout=self.timeout)
        row.get_by_role("button").last.click(timeout=self.timeout)

    def __str__(self):
        return f'open row menu for "{self.row_text}"'


class ClickNode(Step):
    """Click an @xyflow canvas node by its visible label."""

    def __init__(self, label, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.label = label

    def apply(self, page):
        page.locator(".react-flow__node").filter(has_text=self.label).first.click(
            timeout=self.timeout
        )

    def __str__(self):
        return f'click canvas node "{self.label}"'


class ClickNodeEdit(Step):
    """Open a canvas node's editor.

    Clicking the node body only selects it — every node carries its own
    title="edit" button, and there is one per node, so it has to be scoped to
    the node rather than matched globally.
    """

    def __init__(self, label, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.label = label

    def apply(self, page):
        node = page.locator(".react-flow__node").filter(has_text=self.label).first
        node.locator("button[title='edit']").first.click(timeout=self.timeout)

    def __str__(self):
        return f'edit node "{self.label}"'


class Hover(Step):
    def __init__(self, selector, nth=0, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.selector = selector
        self.nth = nth

    def apply(self, page):
        page.locator(self.selector).nth(self.nth).hover(timeout=self.timeout)

    def __str__(self):
        return f"hover {self.selector}"


class Fill(Step):
    def __init__(self, label, value, exact=True, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.label = label
        self.value = value
        self.exact = exact

    def apply(self, page):
        page.get_by_role("textbox", name=_name(self.label, self.exact)).first.fill(
            self.value, timeout=self.timeout
        )

    def __str__(self):
        return f'fill "{self.label}"'


class Check(Step):
    def __init__(self, label, exact=True, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.label = label
        self.exact = exact

    def apply(self, page):
        target = page.get_by_role("checkbox", name=_name(self.label, self.exact)).first
        if not target.count():
            target = page.get_by_role("switch", name=_name(self.label, self.exact)).first
        target.check(timeout=self.timeout)

    def __str__(self):
        return f'check "{self.label}"'


class SelectOption(Step):
    """Open a Radix Select trigger and pick an option by its label."""

    def __init__(self, trigger, option, exact=True, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.trigger = trigger
        self.option = option
        self.exact = exact

    def apply(self, page):
        page.get_by_role("combobox", name=_name(self.trigger, self.exact)).first.click(
            timeout=self.timeout
        )
        page.get_by_role("option", name=_name(self.option, self.exact)).first.click(
            timeout=self.timeout
        )

    def __str__(self):
        return f'select "{self.option}" from "{self.trigger}"'


class Press(Step):
    def __init__(self, key):
        super().__init__()
        self.key = key

    def apply(self, page):
        page.keyboard.press(self.key)

    def __str__(self):
        return f"press {self.key}"


class ScrollTo(Step):
    def __init__(self, selector, nth=0, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout)
        self.selector = selector
        self.nth = nth

    def apply(self, page):
        page.locator(self.selector).nth(self.nth).scroll_into_view_if_needed(
            timeout=self.timeout
        )

    def __str__(self):
        return f"scroll to {self.selector}"


# ── Short constructors, for a readable manifest ──────────────────────

text = WaitText
gone = WaitGone
selector = WaitSelector
sleep = Sleep
hover = Hover
fill = Fill
check = Check
press = Press
scroll_to = ScrollTo
select = SelectOption
click_sel = ClickSelector
click_text = ClickText
click_node = ClickNode
node_edit = ClickNodeEdit
row_menu = ClickRowMenu


def heading(value, exact=True, timeout=READY_TIMEOUT):
    return WaitRole("heading", value, exact=exact, timeout=timeout)


def link(value, exact=True, timeout=READY_TIMEOUT):
    return WaitRole("link", value, exact=exact, timeout=timeout)


def button(value, exact=True, timeout=READY_TIMEOUT):
    return WaitRole("button", value, exact=exact, timeout=timeout)


def searchbox(value, exact=True, timeout=READY_TIMEOUT):
    """Wait for a search field.

    The kit's SearchInput renders ``<input type="search">`` (ui/kit/SearchInput.tsx),
    whose implicit ARIA role is ``searchbox``, not ``textbox`` — every
    "search ..." field in the app needs this rather than textbox().
    """
    return WaitRole("searchbox", value, exact=exact, timeout=timeout)


def textbox(value, exact=True, timeout=READY_TIMEOUT):
    return WaitRole("textbox", value, exact=exact, timeout=timeout)


def dialog(value, exact=False, timeout=READY_TIMEOUT):
    return WaitRole("dialog", value, exact=exact, timeout=timeout)


def click(value, exact=True, nth=None):
    """Click a button by accessible name.

    Note the app frequently uses the HTML ``title`` attribute rather than
    ``aria-label`` on icon-only buttons (e.g. "edit macro buttons",
    "new trigger"). Playwright falls back to ``title``, so those work here.
    """
    return ClickRole("button", value, exact=exact, nth=nth)


def open_combobox(value, exact=True, nth=None):
    """Open a Radix Select without picking anything, so the options show."""
    return ClickRole("combobox", value, exact=exact, nth=nth)


def click_if(value, exact=True):
    return ClickRoleIfPresent("button", value, exact=exact)


def click_link(value, exact=True, nth=None):
    return ClickRole("link", value, exact=exact, nth=nth)
