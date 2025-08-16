"""Terminal utilities for querying terminal capabilities."""


def query_terminal_cell_size() -> tuple[float, float]:  # noqa: C901, PLR0912, PLR0915
    """Query terminal cell size before starting TUI."""
    try:
        import array  # noqa: PLC0415
        import fcntl  # noqa: PLC0415
        import sys  # noqa: PLC0415
        import termios  # noqa: PLC0415

        buf = array.array("H", [0, 0, 0, 0])
        fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, buf)
        rows, cols, width_px, height_px = buf
    except (OSError, ImportError):
        import os  # noqa: PLC0415
        import platform  # noqa: PLC0415
        import sys  # noqa: PLC0415

        rows, cols = os.get_terminal_size()

        try:
            if platform.system() == "Windows":
                import msvcrt  # noqa: PLC0415

                sys.stdout.write("\x1b[16t")
                sys.stdout.flush()

                response = ""
                while True:
                    if msvcrt.kbhit():
                        char = msvcrt.getch().decode("utf-8")
                        response += char
                        if char == "t":
                            break
            else:
                import termios  # noqa: PLC0415
                import tty  # noqa: PLC0415

                fd = sys.stdin.fileno()
                original_attributes = termios.tcgetattr(fd)

                try:
                    tty.setraw(sys.stdin.fileno())
                    print("\x1b[16t", end="", flush=True)  # noqa: T201

                    response = ""
                    while True:
                        char = sys.stdin.read(1)
                        response += char
                        if char == "t":
                            break
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, original_attributes)

            parts = response[:-1].split(";")
            if len(parts) >= 3 and parts[0] == "\x1b[6":  # noqa: PLR2004
                cell_height_px = int(parts[1])
                cell_width_px = int(parts[2])
                width_px = cols * cell_width_px
                height_px = rows * cell_height_px
            else:
                width_px = height_px = 0

        except Exception:
            width_px = height_px = 0

    if width_px == 0 or height_px == 0:
        msg = "Terminal does not report pixel dimensions"
        raise RuntimeError(msg)

    return width_px / cols, height_px / rows
