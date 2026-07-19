#!./.venv/bin/python
import argparse, uuid,struct,json,time, hashlib, shutil,tempfile
from pathlib import Path
from tracking import Tracking
from commit import Commit
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime

today = datetime.now()
ym = today.strftime("%Y-%m")
day = today.strftime("%d")

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

def restore_snapshot(zip_path, repo_path="."):
    repo = Path(repo_path).resolve()
    zip_path = Path(zip_path).resolve()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)

        with ZipFile(zip_path, "r") as zipf:
            for member in zipf.infolist():
                member_path = Path(member.filename)

                # Prevent zip-slip attacks like ../../somefile
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError(f"Unsafe zip path: {member.filename}")

                zipf.extract(member, temp)

        # Delete current repo contents except .svcs
        for path in repo.iterdir():
            if path.name == ".svcs":
                continue

            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

        # Copy extracted contents into repo
        for path in temp.iterdir():
            destination = repo / path.name

            if path.is_dir():
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)



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
parser.add_argument("--restore", action="store_true")

args = parser.parse_args()

if args.commit:
    localtime = time.localtime(time.time())
    timestamp = f"{localtime.tm_hour}:{localtime.tm_min}"
    print(f"Commit message: {args.commit}")
    commitf = commitsfolder / f"{ym}/{day}"

    if not commitf.exists():
        commitf.mkdir()

    filename = f"{str(uuid.uuid7())}-{str(uuid.uuid7())}-{int(time.time())}"
    zip_folder("./", f"{commitf.resolve()}/{filename}.zip")
    zipfile = commitf / f"{filename}.zip"

    sha512 = sha512_file(f"./.svcs/commits/{ym}/{day}/{filename}.zip")
    filename = filename + f"-{sha512}"

    clist[f"{filename.split("-")[0]}-{filename.split("-")[1]}-{int(time.time())}-{filename.split("-")[2]}-{filename.split("-")[3]}"] = {
        "filename": filename,
        "sha512": sha512,
        "msg": args.commit,
        "stamp": time.time(),
        "ym": ym,
        "day": day
    }
    commitlist.write_text(json.dumps(clist, indent=4))

    newzip = Path(f"{commitf.resolve()}/{filename}.zip")
    newzip.touch()
    newzip.write_bytes(zipfile.read_bytes())

    zipfile.unlink(missing_ok=True)

    print(f"Done. commit {args.commit} ({filename.split("-")[0]}-{filename.split("-")[1]}) on {ym}-{day} @ {timestamp}")
elif args.list:
    for uid, (dat) in clist.items():
        print(f"{uid}: '{dat["msg"]}' : {dat["ym"]} on {dat["day"]} | Timestamp: {dat["stamp"]}")
elif args.restore:
    for num, uid in enumerate(clist):
        dat = clist[uid]
        print(f"[{num}] {uid}: '{dat["msg"]}' : {dat["ym"]} on {dat["day"]} | Timestamp: {dat["stamp"]}")
    print("Please select a option or type 'exit' to exit. Any uncommited changes will be lost.\n the above goes from Old -> New")
    answer = input("Warning > ")
    if answer.lower() == "exit":
        exit("User exit")
    else:
        print("Are you sure? All uncommited changes will be lost (y/n)")
        ans = input("Confirm Y/N > ")
        if ans.lower() == "y":
            for num, uid in enumerate(clist):
                dat = clist[uid]
                if num == int(answer):
                    restore_snapshot(f"{commitsfolder.resolve()}/{dat["ym"]}/{dat["day"]}/{dat["filename"]}.zip")
                else:
                    continue