# Nexus Browser Control (Chrome extension)

Pairs Chrome with Nexus Core through Nexus Connect, so Nexus can open, read and drive tabs.
It appears in Nexus as a device with platform `browser`.

## Install and pair
1. `chrome://extensions` → Developer mode → **Load unpacked** → pick this folder.
2. Ask Nexus to "pair a browser" (or use the Nexus Connect setup screen) and enter the 6-digit code in the popup.
3. That's it. The extension stores its own credentials and reconnects after browser start, a Nexus Core restart or a dropped connection. Badge `ON` = connected.

## What Nexus can do
`browser_list_tabs`, `browser_open_url`, `browser_navigate`, `browser_back/forward/reload`, `browser_activate_tab`, `browser_close_tab`,
`browser_snapshot` (page text + clickable elements with refs), `browser_get_text`, `browser_click`, `browser_type`, `browser_press_key`,
`browser_scroll`, `browser_wait_for`, `browser_screenshot`, `browser_eval`, `browser_upload_file`, `browser_drag`.

## You stay in control
- **Its own tab group.** Nexus works in a purple **Nexus** tab group. Your other tabs are invisible to it and untouchable unless you share them
  (popup → *Let Nexus use this tab*, or right-click → *Let Nexus use this tab*). Dragging a tab out of the group takes access back.
  A setting lets you give it all tabs instead.
- **Site rules.** A block list (default: common banks, payment and crypto sites; edit it) or an allow list. Enforced on every action,
  including redirects, tab listings and *Send to Nexus*.
- **Confirmation for risky actions.** Clicking or submitting things that pay, send/post or delete, typing into card fields, running scripts, and
  uploading files each open a prompt in a window owned by the extension (a web page can't fake or click it). It denies itself after 60 s, and closing it means no.
  Uploads always ask. The check looks at the button label and the form, so it is a safety net, not a guarantee.
- **Activity log** in the popup: what Nexus did, where, and the outcome. It never records typed text, page content or script source.
- **Pause** with the popup switch or **Alt+Shift+P** (change at `chrome://extensions/shortcuts`). Pausing refuses all commands, closes open prompts and
  releases the debugger. Pressing *Cancel* on Chrome's "debugging this browser" bar also pauses.

## Real input events
Clicks, typing, keys and scrolling are sent through Chrome's debugger API, so pages see trusted input and file uploads work.
Chrome shows its "…is debugging this browser" bar while a tab is attached; the extension lets go after ~20 s idle.
Turn it off in the popup to use simulated page events instead (no bar, but some sites ignore them). If Chrome refuses to attach,
the action falls back to simulated events and the result says `input: "synthetic"`.

## Send to Nexus
Right-click a selection, page or link → **Send … to Nexus**, use the popup (with an optional instruction), or press **Alt+Shift+N** for the selection.
The text arrives in Nexus chat, fenced and labelled as untrusted page content so instructions hidden in a page aren't treated as yours.

## Limits
- Only the top-level page, not iframes or shadow DOM.
- `chrome://` pages and the Web Store can't be controlled. Strict-CSP pages block `browser_eval`.
- Tested in Chromium only. Edge and Brave should work but are untested; Firefox would need a separate build.

## Tests
`NEXUS_E2E=1 xvfb-run -a python -m pytest tests/e2e_browser_extension -v` drives the extension in real Chromium against the real gateway.

## What the agent can see

- Snapshots include elements inside open shadow DOM and inside iframes (iframe elements are marked `in_frame`
  and are driven with synthetic events, since their coordinates aren't known to the top page).
- `browser_screenshot` returns a downscaled JPEG (max 1024 px wide by default) plus the page viewport size,
  so the model can turn image coordinates into click coordinates. Nexus Core hands the image to the live
  model as a real image (or has a vision model describe it in text-only chats); it is never pasted as base64 text.
- `browser_drag` presses, moves along a path and releases the mouse with real input events (drawing on canvases,
  sliders). It needs real input to be switched on.
