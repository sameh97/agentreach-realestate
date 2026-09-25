"""End-to-end smoke test against the running stack (make up). Run: python3 backend/tests/smoke_test.py
Runs one real search capped at 2 results. Creates two throwaway smoke-*@test.dev users."""
import json, time, uuid, urllib.request, urllib.error
B = "http://localhost:8000"
ok = fail = 0
def req(method, path, body=None, token=None):
    r = urllib.request.Request(B + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            t = resp.read(); return resp.status, (json.loads(t) if t and resp.headers.get_content_type()=="application/json" else t)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200]
def check(name, cond, extra=""):
    global ok, fail
    ok += bool(cond); fail += (not cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))

s, b = req("GET", "/api/health"); check("health", s == 200, b)
email = f"smoke-{uuid.uuid4().hex[:6]}@test.dev"; pw = "password123"
s, b = req("POST", "/api/auth/register", {"email": email, "password": pw, "name": "Smoke"}); check("register", s == 201, b)
s, b = req("POST", "/api/auth/register", {"email": email, "password": pw}); check("duplicate email rejected", s in (400, 409), s)
s, b = req("POST", "/api/auth/register", {"email": "x@y.z", "password": "short"}); check("short password rejected", s == 422, s)
s, b = req("POST", "/api/auth/login", {"email": email, "password": "wrongpass1"}); check("wrong password rejected", s == 401, s)
s, b = req("POST", "/api/auth/login", {"email": email.upper(), "password": pw}); check("login (case-insensitive email)", s == 200, b); tok = b["token"] if s == 200 else None
s, b = req("GET", "/api/auth/me", token=tok); check("me", s == 200 and b.get("email") == email, b)
s, _ = req("GET", "/api/auth/me"); check("me without token -> 401", s == 401, s)
s, _ = req("GET", "/api/auth/me", token="garbage"); check("me bad token -> 401", s == 401, s)
s, _ = req("GET", "/api/searches"); check("searches without token -> 401", s == 401, s)
s, _ = req("POST", "/api/leads/generate", {"query": "agents in Austin TX"}); check("generate without token -> 401", s == 401, s)

s, b = req("POST", "/api/leads/generate", {"query": "real estate agents in Austin, TX", "max_results": 2, "max_retries": 0}, tok)
check("generate job", s == 200, b); job = b["job_id"] if s == 200 else None
st = None
for _ in range(90):
    s, st = req("GET", f"/api/leads/status/{job}", token=tok)
    if s != 200 or st.get("status") in ("completed", "failed", "done", "error"): break
    time.sleep(2)
print("     job status:", st.get("status") if isinstance(st, dict) else st, "| error:", st.get("error") if isinstance(st, dict) else "")
check("job finished", isinstance(st, dict) and st.get("status") in ("completed", "done"), st)
s, b = req("GET", "/api/searches", token=tok); check("search saved to history", s == 200 and len(b if isinstance(b, list) else b.get("searches", b.get("items", []))) >= 1, b)
s, b = req("GET", f"/api/searches/{job}", token=tok); check("get saved search", s == 200, s)
s, b = req("GET", f"/api/leads/download/{job}", token=tok); check("download CSV", s == 200, s)

s, b = req("POST", "/api/auth/register", {"email": "other-" + email, "password": pw}); tok2 = b.get("token") if s == 201 else None
s, _ = req("GET", f"/api/searches/{job}", token=tok2); check("other user can't read search", s in (403, 404), s)
s, _ = req("GET", f"/api/leads/status/{job}", token=tok2); check("other user can't read job", s in (403, 404), s)
s, _ = req("DELETE", f"/api/searches/{job}", token=tok2); check("other user can't delete", s in (403, 404), s)
s, _ = req("DELETE", f"/api/searches/{job}", token=tok); check("owner deletes search", s == 204, s)
s, _ = req("GET", f"/api/searches/{job}", token=tok); check("deleted search gone", s == 404, s)
print(f"\n{ok} passed, {fail} failed"); print("TEST_EMAILS", email, "other-" + email)
