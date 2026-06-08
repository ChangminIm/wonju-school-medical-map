"""gh api 로 파일 직접 배포 (로컬 git write 불안정 우회)"""
import base64, json, os, subprocess, tempfile, sys

REPO = "ChangminIm/wonju-school-medical-map"
BRANCH = "master"
BASE = os.path.dirname(os.path.abspath(__file__))

FILES = {
    "index.html": "결과 지도 파일 크기 갱신",
    "maps/wonju_elem_obesity.png": "초등 단계구분도 노스애로우/박스 스케일바(10km) 수정",
    "maps/wonju_mid_obesity.png": "중학교 단계구분도 노스애로우/박스 스케일바(10km) 수정",
}


def gh(args, input_path=None):
    cmd = ["gh", "api"] + args
    if input_path:
        cmd += ["--input", input_path]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def get_sha(path):
    r = gh(["repos/%s/contents/%s?ref=%s" % (REPO, path, BRANCH)])
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)["sha"]
    except Exception:
        return None


for path, msg in FILES.items():
    local = os.path.join(BASE, path.replace("/", os.sep))
    with open(local, "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")
    payload = {"message": msg, "content": content, "branch": BRANCH}
    sha = get_sha(path)
    if sha:
        payload["sha"] = sha
    tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(payload, tf)
    tf.close()
    r = gh(["--method", "PUT", "repos/%s/contents/%s" % (REPO, path)], input_path=tf.name)
    os.unlink(tf.name)
    if r.returncode == 0:
        new_sha = json.loads(r.stdout)["content"]["sha"]
        print("OK   %-22s sha=%s (%s)" % (path, new_sha[:8], "update" if sha else "new"))
    else:
        print("FAIL %-22s %s" % (path, r.stderr.strip()[:200]))
        sys.exit(1)
print("배포 완료")
