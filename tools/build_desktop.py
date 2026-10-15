"""Build and smoke-test a Python-free desktop ZIP on the current OS."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform not in {"win32", "darwin"}:
        raise SystemExit("Build on Windows or macOS; PyInstaller does not cross-compile.")
    build, dist, release = ROOT / "build", ROOT / "dist", ROOT / "release"
    for folder in (build, dist, release):
        folder.mkdir(exist_ok=True)
    os.environ.setdefault("PYINSTALLER_CONFIG_DIR", str(ROOT / ".build-cache"))
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
               "--name", "OpenGeneLiterature", "--distpath", str(dist),
               "--workpath", str(build / "pyinstaller"), "--specpath", str(build)]
    if sys.platform == "darwin":
        command += ["--osx-bundle-identifier", "org.open-gene-literature.desktop"]
    subprocess.run(command + [str(ROOT / "gene_literature_gui.py")], check=True, cwd=ROOT)
    if sys.platform == "darwin":
        app = dist / "OpenGeneLiterature.app"
        executable = app / "Contents" / "MacOS" / "OpenGeneLiterature"
        docs = app / "Contents" / "Resources" / "Documentation"
        suffix = "macos-" + ("arm64" if platform.machine() == "arm64" else "x64")
    else:
        app = dist / "OpenGeneLiterature"
        executable = app / "OpenGeneLiterature.exe"
        docs = app / "Documentation"
        suffix = "windows-x64"
    # Include dependency licenses and attribution with the executable.
    docs.mkdir(parents=True, exist_ok=True)
    for filename in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(ROOT / filename, docs / filename)
    for name in ("requests", "urllib3", "certifi", "charset-normalizer", "idna"):
        distribution = importlib.metadata.distribution(name)
        for path in distribution.files or []:
            if "license" in path.name.lower() or "copying" in path.name.lower():
                destination = docs / "licenses" / name / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(distribution.locate_file(path), destination)
    for candidate in (Path(sys.base_prefix) / "LICENSE.txt",
                      Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"):
        if candidate.is_file():
            shutil.copyfile(candidate, docs / "PYTHON-LICENSE.txt")
            break
    # Re-sign the modified macOS bundle with an ad-hoc signature for local execution.
    if sys.platform == "darwin":
        # Finder metadata copied from frameworks can prevent signing. Remove only
        # those metadata attributes from our generated bundle; retain quarantine.
        for attribute in ("com.apple.FinderInfo", "com.apple.ResourceFork"):
            subprocess.run(["xattr", "-r", "-d", attribute, str(app)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    smoke = build / f"smoke-{suffix}.json"
    smoke.unlink(missing_ok=True)
    subprocess.run([str(executable), "--smoke-test", "--smoke-output", str(smoke)], check=True, timeout=60)
    assert json.loads(smoke.read_text())["ok"], "Packaged GUI smoke test failed"
    archive = release / f"OpenGeneLiterature-{suffix}.zip"
    if sys.platform == "darwin":
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)], check=True)
    else:
        shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=dist, base_dir=app.name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (release / f"SHA256SUMS-{suffix}.txt").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)


if __name__ == "__main__":
    main()
