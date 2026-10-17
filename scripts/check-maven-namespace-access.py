#!/usr/bin/env python3
"""Bounded, read-only Central authentication/namespace query; never a write probe."""
import base64
import datetime
import http.client
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.request

NAMESPACE = "io.github.apdelrahman1911"
URL = ("https://central.sonatype.com/api/v1/publisher/deployments?namespace="
       + NAMESPACE + "&page=0&size=1")
LIMIT = 256 * 1024
TIMEOUT = 20
REPORT = "namespace-access.json"
ROOT = Path(__file__).resolve().parents[1]


class Refusal(Exception):
    """Only fixed source-defined categories may be rendered."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def report_directory(path):
    """Hold the real directory; never traverse a symlink supplied as output."""
    path = Path(path).absolute()
    if ".." in path.parts:
        raise Refusal("REPORT_PATH_REFUSED")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def remove_old_report(fd):
    try:
        info = os.stat(REPORT, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    os.unlink(REPORT, dir_fd=fd)
    if not stat.S_ISREG(info.st_mode):
        raise Refusal("REPORT_TYPE_REFUSED")


def source_commit():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, timeout=10, check=False)
    sha = result.stdout.decode("ascii").strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise Refusal("SOURCE_IDENTITY_REFUSED")
    if "GITHUB_SHA" in os.environ and os.environ["GITHUB_SHA"] != sha:
        raise Refusal("SOURCE_IDENTITY_REFUSED")
    return sha


def credentials():
    user = os.environ.get("MAVEN_CENTRAL_USERNAME", "")
    password = os.environ.get("MAVEN_CENTRAL_PASSWORD", "")
    if (not user or not password or len(user) > 4096 or len(password) > 4096
            or ":" in user or any(not 33 <= ord(c) <= 126 for c in user + password)):
        raise Refusal("CREDENTIAL_INPUT_REFUSED")
    if os.environ.get("MAVEN_CENTRAL_NAMESPACE") != NAMESPACE:
        raise Refusal("NAMESPACE_INPUT_REFUSED")
    if any(name in os.environ for name in ("CENTRAL_NAMESPACE_API_URL", "CURL_BIN")):
        raise Refusal("ENDPOINT_OVERRIDE_REFUSED")
    return "Bearer " + base64.b64encode((user + ":" + password).encode("ascii")).decode("ascii")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Refusal("RESPONSE_JSON_REFUSED")
        result[key] = value
    return result


def invalid_constant(value):
    raise Refusal("RESPONSE_JSON_REFUSED")


def validate_response(data):
    if not isinstance(data, dict):
        raise Refusal("RESPONSE_SCHEMA_REFUSED")
    numbers = ("page", "pageSize", "pageCount", "totalResultCount")
    if any(type(data.get(k)) is not int or not 0 <= data[k] <= 2**63 - 1 for k in numbers):
        raise Refusal("RESPONSE_PAGINATION_REFUSED")
    total = data["totalResultCount"]
    rows = data.get("deployments")
    if (data["page"] != 0 or data["pageSize"] != 1
            or data["pageCount"] not in ({0, 1} if total == 0 else {total})
            or not isinstance(rows, list) or len(rows) != min(total, 1)):
        raise Refusal("RESPONSE_PAGINATION_REFUSED")
    for row in rows:
        if not isinstance(row, dict) or row.get("namespace") != NAMESPACE:
            raise Refusal("RESPONSE_NAMESPACE_REFUSED")


def query(authorization):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(URL, method="GET", headers={
        "Accept": "application/json", "Authorization": authorization,
        "User-Agent": "P2pKit-Namespace-Preflight/2"})
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            status = response.status
            if type(status) is not int or status != 200:
                raise Refusal("HTTP_STATUS_REFUSED")
            body = response.read(LIMIT + 1)
        if len(body) > LIMIT:
            raise Refusal("RESPONSE_LIMIT_REFUSED")
        data = json.loads(body.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=invalid_constant)
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        raise Refusal("HTTP_" + str(status) if type(status) is int and 100 <= status <= 599
                      else "HTTP_STATUS_REFUSED") from None
    except (urllib.error.URLError, OSError, http.client.HTTPException):
        raise Refusal("TRANSPORT_REFUSED") from None
    except (UnicodeError, ValueError, RecursionError):
        raise Refusal("RESPONSE_JSON_REFUSED") from None
    validate_response(data)


def main(argv=None):
    fd = None
    new_report = False
    result = 1
    try:
        fd = report_directory(os.environ.get("MAVEN_NAMESPACE_REPORT_DIR", "build/reports/maven-central"))
        remove_old_report(fd)
        args = argv if argv is not None else sys.argv[1:]
        if args:
            raise Refusal("ARGUMENTS_REFUSED")
        authorization = credentials()
        sha = source_commit()
        query(authorization)
        record = {"schemaVersion": 2, "namespace": NAMESPACE,
                  "tokenAuthenticated": True, "namespaceQueryAccepted": True,
                  "namespaceVerificationState": "NOT_ASSERTED",
                  "checkedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "commitSha": sha}
        output = os.open(REPORT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=fd)
        new_report = True
        with os.fdopen(output, "w", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True)
            stream.write("\n")
        new_report = False
        result = 0
    except Refusal as error:
        print("FATAL: Central namespace preflight " + str(error), file=sys.stderr)
    except (Exception, KeyboardInterrupt):
        # No arbitrary exception text, remote payload or credential-derived data.
        print("FATAL: Central namespace preflight LOCAL_OR_TRANSPORT_FAILURE", file=sys.stderr)
    finally:
        if fd is not None:
            try:
                try:
                    if new_report:
                        os.unlink(REPORT, dir_fd=fd)
                finally:
                    os.close(fd)
            except Exception:
                # Remove the new report if the original directory handle remains
                # usable. Never fall back to an unpinned path or retry close.
                try:
                    os.unlink(REPORT, dir_fd=fd)
                except OSError:
                    pass
                print("FATAL: Central namespace preflight REPORT_CLEANUP_FAILURE", file=sys.stderr)
                result = 1
    if result == 0:
        print("RESULT: PASS — Central authenticated the token and accepted the exact namespace query; "
              "namespace verification state and publication capability are not asserted")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
