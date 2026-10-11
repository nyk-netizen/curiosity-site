"""Resolve audio inputs/outputs inside a book directory, including symlinks."""

from pathlib import Path, PureWindowsPath


def resolve_book_audio(filename, book_path):
    """Unlike images, audio files may not exist yet (generation or fallback)."""
    relative = Path(filename)
    windows = PureWindowsPath(filename)
    if relative.is_absolute() or windows.drive or windows.root:
        raise ValueError("音频路径必须是书目录内的相对路径，不允许绝对路径")
    depth = 0
    for part in relative.parts:
        if part == "..":
            depth -= 1
            if depth < 0:
                raise ValueError("音频路径不能通过 ../ 越出书目录")
        elif part != ".":
            depth += 1
    try:
        directory = Path(book_path).resolve().parent
        resolved = (directory / relative).resolve()
        resolved.relative_to(directory)
    except ValueError as exc:
        raise ValueError("音频真实路径必须位于书目录内（不允许外部符号链接）") from exc
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"音频路径无法解析：{filename}") from exc
    return resolved
