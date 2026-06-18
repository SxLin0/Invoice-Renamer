import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


LANG_URLS = {
    "eng": "https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata",
    "chi_sim": "https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata",
}


def find_tesseract(explicit_root: str | None) -> Path:
    if explicit_root:
        root = Path(explicit_root)
        binary = root / ("tesseract.exe" if sys.platform == "win32" else "bin/tesseract")
        if binary.exists():
            return binary

    if path := shutil.which("tesseract"):
        return Path(path)

    raise SystemExit("Could not find a Tesseract binary. Install Tesseract before packaging.")


def copy_language_data(source_root: Path, output_tessdata: Path) -> None:
    output_tessdata.mkdir(parents=True, exist_ok=True)
    source_tessdata = source_root / "tessdata"

    for lang, url in LANG_URLS.items():
        target = output_tessdata / f"{lang}.traineddata"
        source = source_tessdata / target.name
        if source.exists():
            shutil.copy2(source, target)
            continue
        urllib.request.urlretrieve(url, target)


def copy_windows_runtime(binary: Path, output_dir: Path) -> None:
    source_root = binary.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    for entry in source_root.iterdir():
        if entry.is_file() and entry.suffix.lower() in {".exe", ".dll"}:
            shutil.copy2(entry, output_dir / entry.name)

    copy_language_data(source_root, output_dir / "tessdata")


def mac_rpaths(binary: Path) -> list[Path]:
    output = subprocess.check_output(["otool", "-l", str(binary)], text=True)
    rpaths = []
    lines = output.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "cmd LC_RPATH":
            continue
        for child in lines[index + 1 : index + 5]:
            stripped = child.strip()
            if not stripped.startswith("path "):
                continue
            raw_path = stripped.split(" ", 2)[1]
            if raw_path.startswith("@loader_path"):
                rpaths.append(Path(str(raw_path).replace("@loader_path", str(binary.parent), 1)))
            else:
                rpaths.append(Path(raw_path))
    return rpaths


def resolve_macos_dependency(dep: str, binary: Path) -> Path | None:
    if dep.startswith(("/System/", "/usr/lib/")):
        return None
    if dep.startswith("@loader_path"):
        return Path(dep.replace("@loader_path", str(binary.parent), 1))
    if dep.startswith("@rpath/"):
        relative = dep.removeprefix("@rpath/")
        for rpath in mac_rpaths(binary):
            candidate = Path(os.path.normpath(rpath / relative))
            if candidate.exists():
                return candidate
        fallback = Path(os.path.normpath(binary.parent / relative))
        return fallback if fallback.exists() else None
    if dep.startswith("@"):
        return None
    return Path(dep)


def mac_dependencies(binary: Path) -> list[Path]:
    return [resolved for _, resolved in mac_dependency_refs(binary)]


def mac_dependency_refs(binary: Path) -> list[tuple[str, Path]]:
    output = subprocess.check_output(["otool", "-L", str(binary)], text=True)
    refs = []
    for line in output.splitlines():
        dep = line.strip().split(" ", 1)[0]
        if not dep or dep.endswith(":"):
            continue
        resolved = resolve_macos_dependency(dep, binary)
        if resolved is not None:
            refs.append((dep, resolved))
    return refs


def copy_mac_dependency_tree(binary: Path, lib_dir: Path) -> list[Path]:
    lib_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    queue = mac_dependencies(binary)
    seen = set()

    while queue:
        dep = queue.pop(0)
        if dep in seen or not dep.exists():
            continue
        seen.add(dep)

        target = lib_dir / dep.name
        if not target.exists():
            shutil.copy2(dep, target)
            target.chmod(0o755)
        copied.append(target)

        for child in mac_dependencies(dep):
            if child not in seen:
                queue.append(child)

    return copied


def rewrite_mac_library_paths(binary: Path, libraries: list[Path]) -> None:
    for lib in libraries:
        subprocess.run(
            ["install_name_tool", "-id", f"@loader_path/{lib.name}", str(lib)],
            check=False,
        )

    targets = [binary, *libraries]
    copied_names = {lib.name for lib in libraries}
    for target in targets:
        for raw_dep, dep in mac_dependency_refs(target):
            if dep.name in copied_names:
                subprocess.run(
                    [
                        "install_name_tool",
                        "-change",
                        raw_dep,
                        f"@loader_path/lib/{dep.name}" if target == binary else f"@loader_path/{dep.name}",
                        str(target),
                    ],
                    check=False,
                )


def codesign_macos_runtime(binary: Path, libraries: list[Path]) -> None:
    for target in [*libraries, binary]:
        subprocess.run(["codesign", "--force", "--sign", "-", str(target)], check=True)


def copy_macos_runtime(binary: Path, output_dir: Path) -> None:
    source_root = binary.parent.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    target_binary = output_dir / "tesseract"
    shutil.copy2(binary, target_binary)
    target_binary.chmod(0o755)

    libraries = copy_mac_dependency_tree(binary, output_dir / "lib")
    rewrite_mac_library_paths(target_binary, libraries)
    codesign_macos_runtime(target_binary, libraries)
    copy_language_data(source_root, output_dir / "tessdata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="runtime/tesseract")
    parser.add_argument("--tesseract-root", default=os.environ.get("TESSERACT_ROOT"))
    args = parser.parse_args()

    output_dir = Path(args.output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)

    binary = find_tesseract(args.tesseract_root)
    if sys.platform == "win32":
        copy_windows_runtime(binary, output_dir)
    elif sys.platform == "darwin":
        copy_macos_runtime(binary, output_dir)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, output_dir / "tesseract")
        copy_language_data(binary.parent.parent, output_dir / "tessdata")

    print(f"Prepared Tesseract runtime at {output_dir}")


if __name__ == "__main__":
    main()
