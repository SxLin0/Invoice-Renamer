from pathlib import Path

from scripts import prepare_tesseract


def test_mac_dependencies_resolves_homebrew_rpath_dependencies(monkeypatch):
    binary = Path("/opt/homebrew/lib/libwebpmux.3.dylib")

    def fake_check_output(command, text):
        if command == ["otool", "-L", str(binary)]:
            return """
/opt/homebrew/lib/libwebpmux.3.dylib:
\t@rpath/libwebp.7.dylib (compatibility version 10.0.0, current version 10.0.0)
\t@rpath/libsharpyuv.0.dylib (compatibility version 2.0.0, current version 2.2.0)
\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1356.0.0)
"""
        if command == ["otool", "-l", str(binary)]:
            return """
          cmd LC_RPATH
      cmdsize 32
         path @loader_path/../lib (offset 12)
"""
        raise AssertionError(command)

    monkeypatch.setattr(prepare_tesseract.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(Path, "exists", lambda self: str(self).startswith("/opt/homebrew/lib/"))

    assert prepare_tesseract.mac_dependencies(binary) == [
        Path("/opt/homebrew/lib/libwebp.7.dylib"),
        Path("/opt/homebrew/lib/libsharpyuv.0.dylib"),
    ]


def test_codesign_macos_runtime_signs_libraries_before_binary(monkeypatch, tmp_path):
    binary = tmp_path / "tesseract"
    library = tmp_path / "lib" / "libtesseract.5.dylib"
    library.parent.mkdir()
    binary.write_text("", encoding="utf-8")
    library.write_text("", encoding="utf-8")

    calls = []

    def record_run(command, check):
        calls.append((command, check))

    monkeypatch.setattr(prepare_tesseract.subprocess, "run", record_run)

    prepare_tesseract.codesign_macos_runtime(binary, [library])

    assert calls == [
        (["codesign", "--force", "--sign", "-", str(library)], True),
        (["codesign", "--force", "--sign", "-", str(binary)], True),
    ]


def test_copy_mac_dependency_tree_reads_children_from_source_library(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    binary = source / "tesseract"
    parent = source / "libparent.dylib"
    child = source / "libchild.dylib"
    for path in [binary, parent, child]:
        path.write_text("", encoding="utf-8")

    calls = []

    def fake_dependencies(path):
        calls.append(path)
        if path == binary:
            return [parent]
        if path == parent:
            return [child]
        return []

    monkeypatch.setattr(prepare_tesseract, "mac_dependencies", fake_dependencies)

    copied = prepare_tesseract.copy_mac_dependency_tree(binary, tmp_path / "runtime" / "lib")

    assert tmp_path / "runtime" / "lib" / "libparent.dylib" in copied
    assert tmp_path / "runtime" / "lib" / "libchild.dylib" in copied
    assert parent in calls
