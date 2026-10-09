"""Download/check the exact public base snapshot used by the V3 experiment.

Standard library only. Hashes pin bytes observed in the completed experiment;
they are checksum expectations, not a Hugging Face publisher signature.
No model code is imported or executed and no revision is selected dynamically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import ssl
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


REPOSITORY = "HuggingFaceTB/SmolLM2-135M-Instruct"
REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
SOURCE = "https://huggingface.co/" + REPOSITORY
EXPECTED_FILES = {
    "config.json": {"sha256": "8eb740e8bbe4cff95ea7b4588d17a2432deb16e8075bc5828ff7ba9be94d982a", "bytes": 861},
    "generation_config.json": {"sha256": "87b916edaaab66b3899b9d0dd0752727dff6666686da0504d89ae0a6e055a013", "bytes": 132},
    "model.safetensors": {"sha256": "5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c", "bytes": 269060552},
    "tokenizer.json": {"sha256": "9ca9acddb6525a194ec8ac7a87f24fbba7232a9a15ffa1af0c1224fcd888e47c", "bytes": 2104556},
    "tokenizer_config.json": {"sha256": "4ec77d44f62efeb38d7e044a1db318f6a939438425312dfa333b8382dbad98df", "bytes": 3764},
    "special_tokens_map.json": {"sha256": "2b7379f3ae813529281a5c602bc5a11c1d4e0a99107aaa597fe936c1e813ca52", "bytes": 655},
    "README.md": {"sha256": "4f97533ad95b1b2fea15fbc075c01b94578ebdd7c8138888fa43fa3abd530dc4", "bytes": 6772},
}
DEFAULT_OUTPUT = Path(".deps/models/SmolLM2-135M-Instruct") / REVISION


def file_metadata(path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return {"sha256": digest.hexdigest(), "bytes": size}


def check_file(path: Path, expected: dict) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("missing regular snapshot file: " + path.name)
    actual = file_metadata(path)
    if actual != expected:
        raise ValueError("snapshot checksum/size mismatch: " + path.name)
    return actual


def download_file(output: Path, filename: str, expected: dict) -> None:
    # Fixed filename and fixed immutable revision; TLS verification is enabled.
    url = SOURCE + "/resolve/" + REVISION + "/" + filename
    request = Request(url, headers={"User-Agent": "byte-agent-eval-fixed-snapshot/1"})
    last_error = None
    for attempt in range(3):
        temporary = None
        try:
            with urlopen(request, timeout=60, context=ssl.create_default_context()) as response:
                if not response.geturl().startswith("https://"):
                    raise ValueError("refusing a non-HTTPS model redirect")
                with tempfile.NamedTemporaryFile(prefix=filename + ".", suffix=".part", dir=output, delete=False) as handle:
                    temporary = Path(handle.name)
                    size = 0
                    while block := response.read(1024 * 1024):
                        size += len(block)
                        if size > expected["bytes"]:
                            raise ValueError("download exceeded pinned file size: " + filename)
                        handle.write(block)
                    handle.flush()
                    os.fsync(handle.fileno())
            check_file(temporary, expected)
            # Never replace an unexpected existing file, even after a download.
            target = output / filename
            if target.exists():
                check_file(target, expected)
            else:
                os.replace(temporary, target)
                temporary = None
            return
        except (URLError, OSError, ValueError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(attempt + 1)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    raise RuntimeError("could not download verified " + filename) from last_error


def check_receipt(path: Path, actual_files: dict) -> dict:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("repository") != REPOSITORY or receipt.get("revision") != REVISION:
        raise ValueError("download receipt repository/revision mismatch")
    if receipt.get("files") != actual_files:
        raise ValueError("download receipt must describe the seven pinned files exactly")
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="local snapshot directory; default is relative to the eval repository")
    parser.add_argument("--verify-only", action="store_true", help="read and verify all seven files and an existing receipt; no network or writes")
    args = parser.parse_args(argv)
    output = args.output
    if output.is_symlink():
        raise ValueError("snapshot directory must not be a symlink")
    if args.verify_only and not output.is_dir():
        raise ValueError("snapshot directory does not exist")
    if not args.verify_only:
        output.mkdir(parents=True, exist_ok=True)
    actual_files = {}
    for filename, expected in EXPECTED_FILES.items():
        path = output / filename
        if not path.exists() and not args.verify_only:
            print("Downloading fixed snapshot file: " + filename, flush=True)
            download_file(output, filename, expected)
        actual_files[filename] = check_file(path, expected)
        print("Verified " + filename, flush=True)
    receipt_path = output / "download-manifest.json"
    if receipt_path.exists():
        check_receipt(receipt_path, actual_files)
    elif args.verify_only:
        raise ValueError("download-manifest.json is missing; run without --verify-only to create it")
    else:
        receipt = {"repository": REPOSITORY, "revision": REVISION, "source": SOURCE,
                   "files": actual_files,
                   "verification": "fixed experiment byte checksums; not a publisher signature"}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="download-manifest.", suffix=".part", dir=output, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(receipt, handle, indent=2)
            handle.write("\n")
        try:
            os.replace(temporary, receipt_path)
        finally:
            temporary.unlink(missing_ok=True)
    print(json.dumps({"repository": REPOSITORY, "revision": REVISION,
                      "verified_files": len(actual_files), "receipt_sha256": file_metadata(receipt_path)["sha256"],
                      "status": "pinned file checksums and local receipt verified; not a publisher signature"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
