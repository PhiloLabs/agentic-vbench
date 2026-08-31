#!/usr/bin/env python3
"""Minimal XTEST input injection via ctypes — no xdotool, no python-xlib needed.

The authentic-render path needs the real Minecraft client to join a server, and 1.16.5 ignores
`--server` (that flag only became functional with quickPlay in 1.20). The client therefore has
to be *clicked* through Multiplayer -> Direct Connection -> type address -> Join. Menu button
positions are deterministic for a given window size, so the clicks can be scripted blind.

    xtest_click.py :DISPLAY move X Y
    xtest_click.py :DISPLAY click X Y
    xtest_click.py :DISPLAY type "some text"
    xtest_click.py :DISPLAY key Return|Tab|Escape
    xtest_click.py :DISPLAY probe          # verify the display accepts synthetic input
    xtest_click.py :DISPLAY windows        # list top-level windows + geometry (blind diagnosis)
    xtest_click.py :DISPLAY focus          # give input focus to the largest mapped window

Xvfb runs with no window manager, so nothing assigns input focus and GLFW ignores synthetic
keys — `focus` does that job explicitly (XSetInputFocus + XRaiseWindow).
"""
import ctypes, ctypes.util, sys, time

X11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
XTST = ctypes.CDLL(ctypes.util.find_library("Xtst") or "libXtst.so.6")
X11.XOpenDisplay.restype = ctypes.c_void_p
X11.XStringToKeysym.restype = ctypes.c_ulong
X11.XKeysymToKeycode.restype = ctypes.c_uint

KEYSYMS = {
    "Return": "Return", "Tab": "Tab", "Escape": "Escape", "BackSpace": "BackSpace",
    "space": "space", "period": "period", "colon": "colon",
}


def open_display(name):
    d = X11.XOpenDisplay(name.encode())
    if not d:
        sys.exit(f"cannot open display {name}")
    return ctypes.c_void_p(d)


def flush(d):
    X11.XFlush(d)


def move(d, x, y):
    XTST.XTestFakeMotionEvent(d, -1, int(x), int(y), 0)
    flush(d)


def click(d, x, y, button=1):
    move(d, x, y)
    time.sleep(0.15)
    XTST.XTestFakeButtonEvent(d, button, True, 0)
    flush(d)
    time.sleep(0.08)
    XTST.XTestFakeButtonEvent(d, button, False, 0)
    flush(d)


def press_keysym(d, name):
    ks = X11.XStringToKeysym(name.encode())
    if ks == 0:
        return False
    kc = X11.XKeysymToKeycode(d, ctypes.c_ulong(ks))
    if kc == 0:
        return False
    XTST.XTestFakeKeyEvent(d, kc, True, 0)
    XTST.XTestFakeKeyEvent(d, kc, False, 0)
    flush(d)
    time.sleep(0.04)
    return True


CHAR_KEYSYM = {".": "period", ":": "colon", " ": "space", "_": "underscore", "-": "minus"}


class XWindowAttributes(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int),
                ("width", ctypes.c_int), ("height", ctypes.c_int),
                ("border_width", ctypes.c_int), ("depth", ctypes.c_int),
                ("visual", ctypes.c_void_p), ("root", ctypes.c_ulong),
                ("c_class", ctypes.c_int), ("bit_gravity", ctypes.c_int),
                ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
                ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong),
                ("save_under", ctypes.c_int), ("colormap", ctypes.c_ulong),
                ("map_installed", ctypes.c_int), ("map_state", ctypes.c_int),
                ("all_event_masks", ctypes.c_long), ("your_event_mask", ctypes.c_long),
                ("do_not_propagate_mask", ctypes.c_long), ("override_redirect", ctypes.c_int),
                ("screen", ctypes.c_void_p)]


def toplevels(d):
    """(window_id, x, y, w, h, mapped, name) for each child of the root window."""
    root = X11.XDefaultRootWindow(d)
    r = ctypes.c_ulong(); parent = ctypes.c_ulong()
    kids = ctypes.POINTER(ctypes.c_ulong)()
    n = ctypes.c_uint()
    X11.XQueryTree(d, ctypes.c_ulong(root), ctypes.byref(r), ctypes.byref(parent),
                   ctypes.byref(kids), ctypes.byref(n))
    out = []
    for i in range(n.value):
        w = kids[i]
        a = XWindowAttributes()
        if not X11.XGetWindowAttributes(d, ctypes.c_ulong(w), ctypes.byref(a)):
            continue
        name = ctypes.c_char_p()
        X11.XFetchName(d, ctypes.c_ulong(w), ctypes.byref(name))
        out.append((w, a.x, a.y, a.width, a.height, a.map_state != 0,
                    (name.value or b"").decode(errors="replace")))
    return out


def focus_largest(d):
    ws = [w for w in toplevels(d) if w[5]]
    if not ws:
        return None
    w = max(ws, key=lambda t: t[3] * t[4])
    X11.XRaiseWindow(d, ctypes.c_ulong(w[0]))
    X11.XSetInputFocus(d, ctypes.c_ulong(w[0]), 2, 0)   # RevertToParent, CurrentTime
    flush(d)
    return w


def type_text(d, text):
    for ch in text:
        name = CHAR_KEYSYM.get(ch, ch)
        if not press_keysym(d, name):
            print(f"  (could not type {ch!r})", file=sys.stderr)


def main():
    disp, action = sys.argv[1], sys.argv[2]
    d = open_display(disp)
    if action == "probe":
        major = ctypes.c_int(); minor = ctypes.c_int()
        ev = ctypes.c_int(); err = ctypes.c_int()
        ok = XTST.XTestQueryExtension(d, ctypes.byref(ev), ctypes.byref(err),
                                      ctypes.byref(major), ctypes.byref(minor))
        print(f"XTEST available={bool(ok)} version={major.value}.{minor.value}")
        move(d, 100, 100); click(d, 100, 100)
        print("synthetic motion+click accepted")
    elif action == "windows":
        for w in toplevels(d):
            print(f"  win=0x{w[0]:x} pos=({w[1]},{w[2]}) size={w[3]}x{w[4]} mapped={w[5]} name={w[6]!r}")
    elif action == "focus":
        w = focus_largest(d)
        print(f"focused 0x{w[0]:x} {w[3]}x{w[4]} at ({w[1]},{w[2]})" if w else "no mapped window")
    elif action == "move":
        move(d, sys.argv[3], sys.argv[4])
    elif action == "click":
        click(d, sys.argv[3], sys.argv[4])
    elif action == "type":
        type_text(d, sys.argv[3])
    elif action == "key":
        print("ok" if press_keysym(d, sys.argv[3]) else "failed")
    else:
        sys.exit(f"unknown action {action}")


if __name__ == "__main__":
    main()
