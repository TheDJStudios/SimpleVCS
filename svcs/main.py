#!./.venv/bin/python
import argparse, uuid,struct,json,time, hashlib
from pathlib import Path
from tracking import Tracking
from commit import Commit
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime

today = datetime.now()
ym = today.strftime("%Y-%m")

def zip_folder(folder_path, output_zip):
    folder = Path(folder_path)

    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as zipf:
        for path in folder.rglob("*"):
            if ".svcs" in path.parts:
                continue
            if path.is_file():
                zipf.write(path, path.relative_to(folder.parent))

def hash_folder(folder_path):
    folder = Path(folder_path)
    h = hashlib.sha512()

    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue

        if ".svcs" in path.parts:
            continue

        relative_path = path.relative_to(folder).as_posix()

        h.update(relative_path.encode("utf-8"))
        h.update(b"\0")

        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)

        h.update(b"\0")

    return h.hexdigest()
def sha512_file(path):
    h = hashlib.sha512()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            h.update(chunk)

    return h.hexdigest()


folder = Path("./.svcs")
if not folder.exists():
    folder.mkdir()

core = folder / "core.svcs"
core.touch()

commitsfolder = folder / "commits"
if not commitsfolder.exists():
    commitsfolder.mkdir()

commitlist = folder / "commits.json"
commitlist.touch()

if len(commitlist.read_text()) < 2:
    commitlist.write_text("{}")

clist = json.loads(commitlist.read_text())




cmagic = b"SVCS"
version = 1
cstruct = struct.Struct("<32sIx")
commitstruct = struct.Struct("<36sxQ")

parser = argparse.ArgumentParser(description="SimpleVCS CLI")

commit = Commit()
tracking = Tracking()

if len(core.read_bytes()) < cstruct.size:
    print("It doesnt look like theres a repository here. if there is its file is corrupted.\n Please enter a name below to create / repair this repository")
    reponame = input("SimpleVCS | New repo > ")
    core.write_bytes(cstruct.pack(str(reponame).encode(), version))

if len(core.read_bytes()) >= cstruct.size:
    repoexists = True
else:
    repoexists = False

parser.add_argument("--commit", type=str)
parser.add_argument("--list", "-l", action="store_true")

args = parser.parse_args()

if args.commit:
    print(f"Commit message: {args.commit}")
    commitf = commitsfolder / f"{ym}"

    if not commitf.exists():
        commitf.mkdir()

    filename = f"{str(uuid.uuid7())}-{str(uuid.uuid7())}-{time.time()}"
    zip_folder("./", f"{commitf.resolve()}/{filename}.zip")
    zipfile = commitf / f"{filename}.zip"

    sha512 = sha512_file(f"./.svcs/commits/{ym}/{filename}.zip")
    filename = filename + f"-{sha512}"

    clist[f"{filename.split("-")[0]}-{filename.split("-")[1]}-{time.time()}"] = {
        "filename": filename,
        "sha512": sha512,
        "msg": args.commit,
        "stamp": time.time(),
        "ym": ym
    }
    commitlist.write_text(json.dumps(clist, indent=4))

    newzip = Path(f"{commitf.resolve()}/{filename}.zip")
    newzip.touch()
    newzip.write_bytes(zipfile.read_bytes())

    zipfile.unlink(missing_ok=True)

    print(f"Done. commit {args.commit} ({filename.split("-")[0]}-{filename.split("-")[1]}) @ {ym}")
elif args.list:
    for uid, (dat) in clist.items():
        print(f"{uid}:{dat["msg"]}:{dat["ym"]} | Timestamp: {dat["stamp"]}")