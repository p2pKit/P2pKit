#!/usr/bin/env python3
"""Two read-only Central token probes; no publication or qualification authority.

Only finite status/shape results are printed. Credentials come from environment
secrets, never arguments; response bodies and exception text are never retained.
"""
import base64
import http.client
import json
import os
import sys
import urllib.error
import urllib.request


HOST = "https://central.sonatype.com"
NAMESPACE = "io.github.apdelrahman1911"
ROUTES = (
    "/api/v1/publisher/deployments?namespace=" + NAMESPACE + "&page=0&size=1",
    "/api/internal/publisher/namespace",
)
LIMIT = 262144
TIMEOUT = 20
SCOPE = "READ_ONLY_AUTH_DIAGNOSTIC_NOT_RELEASE_QUALIFICATION_OR_APPROVAL"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def read_only_probe(opener, route, authorization):
    request = urllib.request.Request(HOST + route, method="GET", headers={
        "Accept": "application/json", "Authorization": authorization,
        "User-Agent": "P2pKit-read-only-auth-diagnostic",
    })
    result = {"httpStatus": None, "boundedJson": False, "transportError": False}
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            result["httpStatus"] = response.status
            raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                return result, None
            try:
                data = json.loads(raw)
            except (UnicodeError, ValueError, RecursionError):
                return result, None
            result["boundedJson"] = True
            return result, data
    except urllib.error.HTTPError as error:
        result["httpStatus"] = error.code
        error.close()  # Do not read private error bodies or follow Location.
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException):
        result["transportError"] = True
    return result, None


def main():
    username = os.environ.get("MAVEN_CENTRAL_USERNAME", "")
    password = os.environ.get("MAVEN_CENTRAL_PASSWORD", "")
    if (not username or not password or len(username) > 4096 or len(password) > 4096
            or ":" in username or any(ord(c) < 33 or ord(c) > 126 for c in username + password)):
        print(json.dumps({"scope": SCOPE, "validCredentialInput": False}, sort_keys=True))
        return 1
    authorization = "Bearer " + base64.b64encode((username + ":" + password).encode()).decode()
    # Default HTTPS certificate/hostname checks; no ambient proxy or redirects.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    public, data = read_only_probe(opener, ROUTES[0], authorization)
    public["expectedResponseShape"] = (
        isinstance(data, dict) and isinstance(data.get("deployments"), list)
        and len(data["deployments"]) <= 1 and type(data.get("page")) is int and data["page"] == 0
        and type(data.get("pageSize")) is int and data["pageSize"] == 1)
    internal, data = read_only_probe(opener, ROUTES[1], authorization)
    internal["expectedResponseShape"] = isinstance(data, list) and all(isinstance(x, dict) for x in data)
    matches = [x for x in data if x.get("name") == NAMESPACE] if internal["expectedResponseShape"] else []
    internal["exactVerifiedNamespaceVisible"] = len(matches) == 1 and matches[0].get("state") == "VERIFIED"
    print(json.dumps({"scope": SCOPE, "namespace": NAMESPACE,
                      "documentedPublicApi": public, "currentInternalGate": internal,
                      "credentialsAndBodiesRetained": False, "uploadPerformed": False}, sort_keys=True))
    return 0 if (public["httpStatus"] == internal["httpStatus"] == 200
                 and public["expectedResponseShape"] and internal["expectedResponseShape"]
                 and internal["exactVerifiedNamespaceVisible"]) else 1


if __name__ == "__main__":
    if len(sys.argv) != 1:
        print("AUTH_DIAGNOSTIC_ARGUMENTS_REFUSED")
        sys.exit(1)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("AUTH_DIAGNOSTIC_INTERRUPTED")
        sys.exit(1)
