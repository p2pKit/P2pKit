"""Inert exact filename/diagnostic/clock inverses for historical source pins only.

Each inverse transforms the supplied CURRENT source, checks every reviewed hunk
and substitution count, then requires the independently retained original hash.
It never reads files, returns an embedded source substitute, or executes source.
Behavioral controls must import the current runtime, never these preimages.
"""
import hashlib

BASE_RUNTIME_SHA256 = "a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d"
BASE_WORKFLOW_SHA256 = "c88c6e69c00c0a150e0eacefbfb54e7611ec9511112dbd02c303f8ad19d7aa40"
BASE_EXPERIMENT_TEST_SHA256 = "484c4ebdd20bf5500ad9ba340f552cc15088e0c02e74759805cf693cfe290768"

# The original direct-child startup image seam must restore the complete
# e4c66097 runtime before the READY and historical inverses below.
CHILD_STARTUP_BASE_RUNTIME_SHA256 = "65fac8adb5041deeb4e1eb5425dd43dcb88a28302d3d5ed75881e670305368b7"
CHILD_STARTUP_PATCH = (
    (
        "def service(directory):\n",
        "def observe_startup_child(native, process, birth, parent, expected_account):\n"
        "    \"\"\"One original direct child's startup image, never an identity from READY.\"\"\"\n"
        "    require(process.returncode is None and type(process.pid) is int and process.pid > 0,\n"
        "            \"IDENTITY\", \"IDENTITY_CHANGED\")\n"
        "    same_identity(birth, birth)\n"
        "    require(birth[\"pid\"] == process.pid and birth[\"parentPid\"] == parent[\"pid\"] == os.getpid() and\n"
        "            birth[\"parentUniqueId\"] == parent[\"uniqueId\"], \"IDENTITY\", \"IDENTITY_CHANGED\")\n"
        "    identity_account(birth, expected_account)\n"
        "    observed = native.identity(process.pid)\n"
        "    same_identity(observed, observed)\n"
        "    # Initial exec completion is not final interpreter readiness. Birth continuity\n"
        "    # alone admits no work: READY and later checks require the full observed image,\n"
        "    # including its actual pidVersion. Neither native observation is rewritten.\n"
        "    require(all(observed[key] == birth[key] for key in IDENTITY_KEYS - {\"status\", \"pidVersion\"}),\n"
        "            \"IDENTITY\", \"IDENTITY_CHANGED\")\n"
        "    identity_account(observed, expected_account)\n"
        "    return observed\n"
        "\n"
        "\n"
        "def service(directory):\n",
    ),
    (
        "    native, channel, probe_channel, process, pipes, producer_identity = None, None, None, None, None, None\n",
        "    native, channel, probe_channel, process, pipes, producer_identity = None, None, None, None, None, None\n"
        "    producer_birth = None\n",
    ),
    (
        "                producer_identity = native.identity(process.pid)\n"
        "                require(producer_identity[\"parentPid\"] == os.getpid() and\n"
        "                        producer_identity[\"parentUniqueId\"] == service_identity[\"uniqueId\"], \"IDENTITY\", \"IDENTITY_CHANGED\")\n",
        "                birth = native.identity(process.pid)\n"
        "                same_identity(birth, birth)\n"
        "                require(birth[\"pid\"] == process.pid and birth[\"parentPid\"] == os.getpid() and\n"
        "                        birth[\"parentUniqueId\"] == service_identity[\"uniqueId\"], \"IDENTITY\", \"IDENTITY_CHANGED\")\n"
        "                identity_account(birth, prepared[\"account\"])\n"
        "                producer_birth = birth\n",
    ),
    (
        "            startup_site = \"CHILD_READY_VALIDATE\"\n"
        "            validate_ready(ready, prepared, service_identity, producer_identity)\n",
        "            startup_site = \"CHILD_READY_VALIDATE\"\n"
        "            producer_identity = observe_startup_child(native, process, producer_birth, service_identity, prepared[\"account\"])\n"
        "            validate_ready(ready, prepared, service_identity, producer_identity)\n",
    ),
    (
        "        if process is not None and process.poll() is None and native is not None and producer_identity is not None:\n"
        "            with contextlib.suppress(BaseException):\n"
        "                native.signal(producer_identity, signal.SIGTERM, end_ns)\n",
        "        cleanup_identity = producer_identity if producer_identity is not None else producer_birth\n"
        "        if process is not None and process.poll() is None and native is not None and cleanup_identity is not None:\n"
        "            with contextlib.suppress(BaseException):\n"
        "                native.signal(cleanup_identity, signal.SIGTERM, end_ns)\n",
    ),
)

# The finite READY-producer diagnostic must restore the complete accepted
# 7274b0e7 runtime before the startup and historical inverses below.
READY_PRODUCER_BASE_RUNTIME_SHA256 = "db90735880ff020f027a91c695221963bbebce07a3ee7e7e624622692931c852"
READY_PRODUCER_PATCH = (
    (
        "def validate_ready(frame, prepared, service_identity, producer_identity):\n",
        "READY_PRODUCER_FIELDS = (\n"
        "    (\"pid\", \"PID\"), (\"parentPid\", \"PARENT_PID\"), (\"uniqueId\", \"UNIQUE_ID\"),\n"
        "    (\"parentUniqueId\", \"PARENT_UNIQUE_ID\"), (\"pidVersion\", \"PID_VERSION\"),\n"
        "    (\"startSeconds\", \"START_SECONDS\"), (\"startMicroseconds\", \"START_MICROSECONDS\"),\n"
        "    (\"uid\", \"UID\"), (\"realUid\", \"REAL_UID\"), (\"gid\", \"GID\"), (\"realGid\", \"REAL_GID\"), (\"status\", \"STATUS\"),\n"
        ")\n"
        "READY_PRODUCER_DETAIL_KEYS = frozenset((\"operand\", \"predicate\", \"fields\"))\n"
        "\n"
        "\n"
        "def _ready_producer_detail(value):\n"
        "    \"\"\"Finite diagnostic DATA only; never a process identity or guard result.\"\"\"\n"
        "    if (type(value) is not dict or len(value) != 3 or not all(type(key) is str for key in value) or\n"
        "            set(value) != READY_PRODUCER_DETAIL_KEYS):\n"
        "        return False\n"
        "    operand, predicate, fields = value[\"operand\"], value[\"predicate\"], value[\"fields\"]\n"
        "    if (type(operand) is not str or operand not in (\"REPORTED\", \"OBSERVED\", \"PAIR\") or type(predicate) is not str or\n"
        "            type(fields) is not list or len(fields) > len(READY_PRODUCER_FIELDS) or\n"
        "            not all(type(field) is str for field in fields)):\n"
        "        return False\n"
        "    if fields != [token for _key, token in READY_PRODUCER_FIELDS if token in fields]:\n"
        "        return False\n"
        "    if operand == \"PAIR\":\n"
        "        return predicate == \"EQUALITY\" and bool(fields) and \"STATUS\" not in fields\n"
        "    if predicate in (\"TYPE\", \"KEYS\"):\n"
        "        return not fields\n"
        "    if predicate == \"VALUES\":\n"
        "        return bool(fields)\n"
        "    return predicate in (\"PID\", \"UNIQUE_ID\", \"STATUS\") and fields == [predicate]\n"
        "\n"
        "\n"
        "def classify_ready_producer(reported, observed):\n"
        "    \"\"\"After refusal: classify held DATA, not the original evaluated field or native cause.\"\"\"\n"
        "    try:\n"
        "        for operand, value in ((\"REPORTED\", reported), (\"OBSERVED\", observed)):\n"
        "            if type(value) is not dict:\n"
        "                return {\"operand\": operand, \"predicate\": \"TYPE\", \"fields\": []}\n"
        "            if (len(value) != len(IDENTITY_KEYS) or not all(type(key) is str for key in value) or\n"
        "                    set(value) != IDENTITY_KEYS):\n"
        "                return {\"operand\": operand, \"predicate\": \"KEYS\", \"fields\": []}\n"
        "            invalid = [token for key, token in READY_PRODUCER_FIELDS if type(value[key]) is not int or value[key] < 0]\n"
        "            if invalid:\n"
        "                return {\"operand\": operand, \"predicate\": \"VALUES\", \"fields\": invalid}\n"
        "            if value[\"pid\"] <= 0:\n"
        "                return {\"operand\": operand, \"predicate\": \"PID\", \"fields\": [\"PID\"]}\n"
        "            if value[\"uniqueId\"] <= 0:\n"
        "                return {\"operand\": operand, \"predicate\": \"UNIQUE_ID\", \"fields\": [\"UNIQUE_ID\"]}\n"
        "            if value[\"status\"] not in (1, 2, 3, 4):\n"
        "                return {\"operand\": operand, \"predicate\": \"STATUS\", \"fields\": [\"STATUS\"]}\n"
        "        fields = [token for key, token in READY_PRODUCER_FIELDS if key != \"status\" and reported[key] != observed[key]]\n"
        "        return {\"operand\": \"PAIR\", \"predicate\": \"EQUALITY\", \"fields\": fields} if fields else None\n"
        "    except BaseException:\n"
        "        return None  # Optional classification cannot replace the original refusal.\n"
        "\n"
        "\n"
        "def validate_ready(frame, prepared, service_identity, producer_identity):\n",
    ),
    (
        "    except ExperimentError as error:\n"
        "        with contextlib.suppress(BaseException):\n"
        "            error.ready_site = ready_site\n"
        "        raise\n",
        "    except ExperimentError as error:\n"
        "        with contextlib.suppress(BaseException):\n"
        "            error.ready_site = ready_site\n"
        "        with contextlib.suppress(BaseException):\n"
        "            if (ready_site == \"READY_PRODUCER\" and type(error) is ExperimentError and\n"
        "                    type(error.stage) is str and error.stage == \"IDENTITY\" and\n"
        "                    type(error.reason) is str and error.reason == \"IDENTITY_CHANGED\" and\n"
        "                    type(error.errno_name) is str and error.errno_name == \"NONE\" and type(payload) is dict):\n"
        "                detail = classify_ready_producer(payload[\"producer\"], producer_identity)\n"
        "                if _ready_producer_detail(detail):\n"
        "                    error.ready_producer = detail\n"
        "        raise\n",
    ),
    (
        "        value = parsed(body, STARTUP_BYTES)\n"
        "        if (type(value) is not dict or set(value) != STARTUP_KEYS or body != encoded(value) or\n"
        "                type(value[\"schema\"]) is not int or value[\"schema\"] != 1 or\n",
        "        value = parsed(body, STARTUP_BYTES)\n"
        "        if (type(value) is not dict or len(value) not in (len(STARTUP_KEYS), len(STARTUP_KEYS) + 1) or\n"
        "                not all(type(key) is str for key in value)):\n"
        "            return ()\n"
        "        schema = value.get(\"schema\")\n"
        "        if (type(schema) is not int or schema not in (1, 2) or\n"
        "                set(value) != (STARTUP_KEYS if schema == 1 else STARTUP_KEYS | {\"readyProducer\"}) or\n"
        "                body != encoded(value) or\n",
    ),
    (
        "        result = [\"P2PKIT_CONTEXT_SERVICE_FAILURE|\" + \"|\".join((case, value[\"site\"], value[\"ready\"], *failure))]\n"
        "        if timeout is not None:\n",
        "        detail = None\n"
        "        if schema == 2:\n"
        "            detail = value[\"readyProducer\"]\n"
        "            if (value[\"site\"] != \"CHILD_READY_VALIDATE\" or value[\"ready\"] != \"READY_PRODUCER\" or\n"
        "                    failure != [\"IDENTITY\", \"IDENTITY_CHANGED\", \"NONE\"] or timeout is not None or eof is not None or\n"
        "                    not _ready_producer_detail(detail)):\n"
        "                return ()\n"
        "        result = [\"P2PKIT_CONTEXT_SERVICE_FAILURE|\" + \"|\".join((case, value[\"site\"], value[\"ready\"], *failure))]\n"
        "        if detail is not None:\n"
        "            result.append(\"P2PKIT_CONTEXT_SERVICE_READY_PRODUCER|\" + \"|\".join(\n"
        "                (case, detail[\"operand\"], detail[\"predicate\"], \",\".join(detail[\"fields\"]) or \"NONE\")))\n"
        "        if timeout is not None:\n",
    ),
    (
        "        value = {\"schema\": 1, \"case\": case, \"binding\": binding, \"site\": site, \"ready\": ready, \"failure\": failure,\n"
        "                 \"timeout\": timeout, \"eof\": eof, \"producerFailure\": producer_failure}\n"
        "        companion = STARTUP_PREFIX + encoded(value)\n",
        "        value = {\"schema\": 1, \"case\": case, \"binding\": binding, \"site\": site, \"ready\": ready, \"failure\": failure,\n"
        "                 \"timeout\": timeout, \"eof\": eof, \"producerFailure\": producer_failure}\n"
        "        with contextlib.suppress(BaseException):\n"
        "            if (site == \"CHILD_READY_VALIDATE\" and type(ready) is str and ready == \"READY_PRODUCER\" and\n"
        "                    failure == [\"IDENTITY\", \"IDENTITY_CHANGED\", \"NONE\"] and timeout is None and eof is None):\n"
        "                detail = getattr(error, \"ready_producer\", None)\n"
        "                if _ready_producer_detail(detail):\n"
        "                    # Build independently before replacing the schema1 fallback.\n"
        "                    value = {**value, \"schema\": 2, \"readyProducer\": {\n"
        "                        \"operand\": detail[\"operand\"], \"predicate\": detail[\"predicate\"], \"fields\": list(detail[\"fields\"])}}\n"
        "        companion = STARTUP_PREFIX + encoded(value)\n",
    ),
)

# The startup-only diagnostic must recover the complete accepted d2ab10b0
# runtime before the existing timeout and historical inverses below.
STARTUP_DIAGNOSTIC_BASE_RUNTIME_SHA256 = "fac1691819a7a201851fa4c6062f2f9d272d6ab7635c4b613746a88f58e50754"
STARTUP_DIAGNOSTIC_PATCH = (
    (
        "def validate_ready(frame, prepared, service_identity, producer_identity):\n"
        "    payload = validate_frame(frame, 3, prepared[\"binding\"])\n"
        "    require(set(payload) == {\"producer\", \"parent\", \"account\", \"sigtermDefault\", \"sigtermBlocked\", \"sourceSha256\",\n"
        "                             \"boot\", \"interpreter\"} and payload[\"sigtermDefault\"] is True and\n"
        "            payload[\"sigtermBlocked\"] is False, \"IDENTITY\", \"REFUSED\")\n"
        "    validate_account(payload[\"account\"], prepared[\"account\"])\n"
        "    same_identity(payload[\"parent\"], service_identity)\n"
        "    same_identity(payload[\"producer\"], producer_identity)\n"
        "    identity_account(producer_identity, prepared[\"account\"])\n"
        "    require(producer_identity[\"parentPid\"] == service_identity[\"pid\"] and\n"
        "            producer_identity[\"parentUniqueId\"] == service_identity[\"uniqueId\"] and\n"
        "            payload[\"sourceSha256\"] == prepared[\"source\"][\"files\"][SCRIPT] and payload[\"boot\"] == prepared[\"boot\"] and\n"
        "            payload[\"interpreter\"] == prepared[\"interpreter\"][\"path\"], \"IDENTITY\", \"IDENTITY_CHANGED\")\n"
        "    return payload\n",
        "def validate_ready(frame, prepared, service_identity, producer_identity):\n"
        "    ready_site = \"READY_SHAPE\"\n"
        "    try:\n"
        "        payload = validate_frame(frame, 3, prepared[\"binding\"])\n"
        "        require(set(payload) == {\"producer\", \"parent\", \"account\", \"sigtermDefault\", \"sigtermBlocked\", \"sourceSha256\",\n"
        "                                 \"boot\", \"interpreter\"} and payload[\"sigtermDefault\"] is True and\n"
        "                payload[\"sigtermBlocked\"] is False, \"IDENTITY\", \"REFUSED\")\n"
        "        ready_site = \"READY_ACCOUNT\"\n"
        "        validate_account(payload[\"account\"], prepared[\"account\"])\n"
        "        ready_site = \"READY_PARENT\"\n"
        "        same_identity(payload[\"parent\"], service_identity)\n"
        "        ready_site = \"READY_PRODUCER\"\n"
        "        same_identity(payload[\"producer\"], producer_identity)\n"
        "        ready_site = \"READY_ACCOUNT\"\n"
        "        identity_account(producer_identity, prepared[\"account\"])\n"
        "        ready_site = \"READY_BINDINGS\"\n"
        "        require(producer_identity[\"parentPid\"] == service_identity[\"pid\"] and\n"
        "                producer_identity[\"parentUniqueId\"] == service_identity[\"uniqueId\"] and\n"
        "                payload[\"sourceSha256\"] == prepared[\"source\"][\"files\"][SCRIPT] and payload[\"boot\"] == prepared[\"boot\"] and\n"
        "                payload[\"interpreter\"] == prepared[\"interpreter\"][\"path\"], \"IDENTITY\", \"IDENTITY_CHANGED\")\n"
        "        return payload\n"
        "    except ExperimentError as error:\n"
        "        with contextlib.suppress(BaseException):\n"
        "            error.ready_site = ready_site\n"
        "        raise\n",
    ),
    (
        "def service(directory):\n",
        "STARTUP_BYTES = 2048\n"
        "STARTUP_PREFIX = b\"P2PKIT_CONTEXT_STARTUP_RECORD|\"\n"
        "STARTUP_SITES = frozenset((\"PREPARE_READ\", \"PREPARE_VALIDATE\", \"CHILD_CHANNEL\", \"CHILD_ENVIRONMENT\", \"CHILD_SPAWN\",\n"
        "                           \"CHILD_IDENTITY\", \"CHILD_PIPES\", \"CHILD_READY_READ\", \"CHILD_READY_VALIDATE\",\n"
        "                           \"CHILD_RECHECK\", \"CHILD_READY_FORWARD\"))\n"
        "READY_SITES = frozenset((\"READY_SHAPE\", \"READY_ACCOUNT\", \"READY_PARENT\", \"READY_PRODUCER\", \"READY_BINDINGS\"))\n"
        "STARTUP_TIMEOUT_SITES = frozenset((\"NATIVE_ENTRY\", \"CASE_ENTRY\", \"SEND_PRE\", \"SEND_SELECT\", \"SEND_RETURN\",\n"
        "                                   \"READ_WAIT\", \"READ_RETURN\", \"FORWARD_TIME\", \"UNKNOWN\"))\n"
        "STARTUP_FRAMES = frozenset((\"F1\", \"F2\", \"F3\", \"F4\", \"F5\", \"F6\", \"F7\", \"F8\", \"UNKNOWN\"))\n"
        "STARTUP_KEYS = frozenset((\"schema\", \"case\", \"binding\", \"site\", \"ready\", \"failure\", \"timeout\", \"eof\", \"producerFailure\"))\n"
        "\n"
        "\n"
        "def _startup_failure_fields(value):\n"
        "    return (type(value) is list and len(value) == 3 and all(type(item) is str for item in value) and\n"
        "            value[0] in STAGES and value[1] in REASONS and value[2] in ERRNOS)\n"
        "\n"
        "\n"
        "def _startup_timeout_fields(value):\n"
        "    return (type(value) is list and len(value) == 3 and all(type(item) is str for item in value) and\n"
        "            value[0] in STARTUP_TIMEOUT_SITES and value[1] in STARTUP_FRAMES | {\"NONE\"} and\n"
        "            value[2] in (\"HEADER\", \"BODY\", \"FRAME\", \"NONE\", \"UNKNOWN\"))\n"
        "\n"
        "\n"
        "def _startup_eof_fields(value):\n"
        "    return (type(value) is list and len(value) == 3 and all(type(item) is str for item in value) and\n"
        "            value[0] in STARTUP_FRAMES and value[1] in (\"HEADER\", \"BODY\", \"UNKNOWN\") and\n"
        "            value[2] in (\"EMPTY\", \"PARTIAL\", \"UNKNOWN\"))\n"
        "\n"
        "\n"
        "def _startup_buffered_failure(pipes, case):\n"
        "    \"\"\"A finite D-reported snapshot, never a P status or complete stream claim.\"\"\"\n"
        "    if type(pipes) is not ProbePipes or type(pipes.data) is not dict:\n"
        "        return None\n"
        "    raw = pipes.data.get(\"stdout\")\n"
        "    if type(raw) not in (bytes, bytearray) or not 0 < len(raw) <= STARTUP_BYTES:\n"
        "        return None\n"
        "    raw = bytes(raw)\n"
        "    if not raw.endswith(b\"\\n\"):\n"
        "        return None\n"
        "    lines = raw.decode(\"ascii\").split(\"\\n\")[:-1]\n"
        "    if not 1 <= len(lines) <= 4:\n"
        "        return None\n"
        "    first = lines[0].split(\"|\")\n"
        "    if len(first) != 4 or first[0] != \"P2PKIT_CONTEXT_FAILURE\" or not _startup_failure_fields(first[1:]):\n"
        "        return None\n"
        "    failure, previous = first[1:], 0\n"
        "    for line in lines[1:]:\n"
        "        fields = line.split(\"|\")\n"
        "        if fields[0] == \"P2PKIT_CONTEXT_SOURCE_SITE\":\n"
        "            if (len(fields) != 3 or failure[:2] != [\"SOURCE\", \"IDENTITY_CHANGED\"] or\n"
        "                    fields[1] not in SOURCE_SITES | {\"UNKNOWN\"} or\n"
        "                    (fields[2] not in {*SOURCE_OS_ITEMS.values(), \"NONE\"} if fields[1] in SOURCE_OS_SITES\n"
        "                     else fields[2] != \"NONE\")):\n"
        "                return None\n"
        "            ordinal = 1\n"
        "        elif fields[0] == \"P2PKIT_CONTEXT_TIMEOUT_SITE\":\n"
        "            if (len(fields) != 5 or failure != [\"START\", \"TIMEOUT\", \"NONE\"] or\n"
        "                    fields[1] not in (case, \"UNKNOWN\") or not _startup_timeout_fields(fields[2:])):\n"
        "                return None\n"
        "            ordinal = 2\n"
        "        elif fields[0] == \"P2PKIT_CONTEXT_PROTOCOL_EOF\":\n"
        "            if (len(fields) != 5 or failure[:2] != [\"START\", \"STATUS_MISSING\"] or\n"
        "                    fields[1] not in (case, \"UNKNOWN\") or not _startup_eof_fields(fields[2:])):\n"
        "                return None\n"
        "            ordinal = 3\n"
        "        else:\n"
        "            return None\n"
        "        if ordinal <= previous:\n"
        "            return None\n"
        "        previous = ordinal\n"
        "    return failure\n"
        "\n"
        "\n"
        "def parse_startup_record(raw, case, binding):\n"
        "    \"\"\"Whole-record finite grammar; no input byte is echoed or accepted as custody.\"\"\"\n"
        "    try:\n"
        "        if (type(raw) is not bytes or not 0 < len(raw) <= STARTUP_BYTES or type(case) is not str or case not in CASES or\n"
        "                type(binding) is not str or not HASH.fullmatch(binding)):\n"
        "            return ()\n"
        "        lines = raw.split(b\"\\n\")\n"
        "        if len(lines) != 3 or lines[-1] != b\"\" or not lines[1].startswith(STARTUP_PREFIX):\n"
        "            return ()\n"
        "        body = lines[1][len(STARTUP_PREFIX):] + b\"\\n\"\n"
        "        value = parsed(body, STARTUP_BYTES)\n"
        "        if (type(value) is not dict or set(value) != STARTUP_KEYS or body != encoded(value) or\n"
        "                type(value[\"schema\"]) is not int or value[\"schema\"] != 1 or\n"
        "                type(value[\"case\"]) is not str or value[\"case\"] != case or\n"
        "                type(value[\"binding\"]) is not str or value[\"binding\"] != binding or\n"
        "                type(value[\"site\"]) is not str or value[\"site\"] not in STARTUP_SITES or\n"
        "                type(value[\"ready\"]) is not str or value[\"ready\"] not in READY_SITES | {\"NONE\"} or\n"
        "                (value[\"ready\"] != \"NONE\" and value[\"site\"] != \"CHILD_READY_VALIDATE\") or\n"
        "                not _startup_failure_fields(value[\"failure\"])):\n"
        "            return ()\n"
        "        failure = value[\"failure\"]\n"
        "        if lines[0] != (\"P2PKIT_CONTEXT_FAILURE|\" + \"|\".join(failure)).encode(\"ascii\"):\n"
        "            return ()\n"
        "        timeout, eof, producer_failure = value[\"timeout\"], value[\"eof\"], value[\"producerFailure\"]\n"
        "        if ((timeout is not None and (failure != [\"START\", \"TIMEOUT\", \"NONE\"] or not _startup_timeout_fields(timeout))) or\n"
        "                (eof is not None and (failure[:2] != [\"START\", \"STATUS_MISSING\"] or not _startup_eof_fields(eof))) or\n"
        "                (producer_failure is not None and not _startup_failure_fields(producer_failure))):\n"
        "            return ()\n"
        "        result = [\"P2PKIT_CONTEXT_SERVICE_FAILURE|\" + \"|\".join((case, value[\"site\"], value[\"ready\"], *failure))]\n"
        "        if timeout is not None:\n"
        "            result.append(\"P2PKIT_CONTEXT_SERVICE_TIMEOUT_SITE|\" + \"|\".join((case, *timeout)))\n"
        "        if eof is not None:\n"
        "            result.append(\"P2PKIT_CONTEXT_SERVICE_PROTOCOL_EOF|\" + \"|\".join((case, *eof)))\n"
        "        if producer_failure is not None:\n"
        "            result.append(\"P2PKIT_CONTEXT_SERVICE_REPORTED_P_FAILURE|\" + \"|\".join((case, *producer_failure)))\n"
        "        return tuple(result)\n"
        "    except BaseException:\n"
        "        return ()\n"
        "\n"
        "\n"
        "def startup_failure_record(error, case, binding, site, pipes):\n"
        "    \"\"\"Snapshot only the held refusal and existing P buffer, before D cleanup.\"\"\"\n"
        "    try:\n"
        "        if (type(error) is not ExperimentError or type(site) is not str or site not in STARTUP_SITES or\n"
        "                type(case) is not str or case not in CASES or type(binding) is not str or not HASH.fullmatch(binding)):\n"
        "            return b\"\"\n"
        "        failure = [error.stage, error.reason, error.errno_name]\n"
        "        if not _startup_failure_fields(failure):\n"
        "            return b\"\"\n"
        "        ready = getattr(error, \"ready_site\", \"NONE\")\n"
        "        timeout_line, eof_line = public_timeout_site(error), public_protocol_eof(error)\n"
        "        for line, prefix in ((timeout_line, \"P2PKIT_CONTEXT_TIMEOUT_SITE\"), (eof_line, \"P2PKIT_CONTEXT_PROTOCOL_EOF\")):\n"
        "            if line is not None and (type(line) is not str or len(line.split(\"|\")) != 5 or\n"
        "                                     line.split(\"|\")[0] != prefix or line.split(\"|\")[1] not in (case, \"UNKNOWN\")):\n"
        "                return b\"\"\n"
        "        timeout = None if timeout_line is None else timeout_line.split(\"|\")[2:]\n"
        "        eof = None if eof_line is None else eof_line.split(\"|\")[2:]\n"
        "        # An unavailable/malformed P snapshot does not suppress D's own refusal.\n"
        "        producer_failure = None\n"
        "        with contextlib.suppress(BaseException):\n"
        "            producer_failure = _startup_buffered_failure(pipes, case)\n"
        "        value = {\"schema\": 1, \"case\": case, \"binding\": binding, \"site\": site, \"ready\": ready, \"failure\": failure,\n"
        "                 \"timeout\": timeout, \"eof\": eof, \"producerFailure\": producer_failure}\n"
        "        companion = STARTUP_PREFIX + encoded(value)\n"
        "        primary = (\"P2PKIT_CONTEXT_FAILURE|\" + \"|\".join(failure) + \"\\n\").encode(\"ascii\")\n"
        "        return companion if parse_startup_record(primary + companion, case, binding) else b\"\"\n"
        "    except BaseException:\n"
        "        return b\"\"\n"
        "\n"
        "\n"
        "def emit_startup_diagnostic(context, state):\n"
        "    \"\"\"Failure only: one D-terminal-gated read, no new native observation or wait.\"\"\"\n"
        "    try:\n"
        "        if type(state) is not dict or context.current is not state:\n"
        "            return\n"
        "        case, binding, directory = state.get(\"case\"), state.get(\"binding\"), state.get(\"directory\")\n"
        "        directory_identity = state.get(\"directoryIdentity\")\n"
        "        if (type(case) is not str or case not in CASES or type(binding) is not str or not HASH.fullmatch(binding) or\n"
        "                directory != context.evidence / case or type(directory_identity) is not list or len(directory_identity) != 2 or\n"
        "                not all(type(value) is int and value >= 0 for value in directory_identity)):\n"
        "            return\n"
        "        service, native = state.get(\"service\"), context.native\n"
        "        if type(service) is not dict or type(service.get(\"pid\")) is not int:\n"
        "            return\n"
        "        pid = service[\"pid\"]\n"
        "        watched, registration, terminal = native.watched.get(pid), native.registrations.get(pid), native.events.get(pid)\n"
        "        same_identity(service, watched)\n"
        "        if (type(registration) is not dict or set(registration) != {\n"
        "                \"identity\", \"startedMonotonicNs\", \"returnedMonotonicNs\", \"requested\", \"receipts\", \"recheckedMonotonicNs\"} or\n"
        "                not any(item is registration for item in native.attach_attempts)):\n"
        "            return\n"
        "        same_identity(service, registration[\"identity\"])\n"
        "        times = [registration[key] for key in (\"startedMonotonicNs\", \"returnedMonotonicNs\", \"recheckedMonotonicNs\")]\n"
        "        requested, receipts = registration[\"requested\"], registration[\"receipts\"]\n"
        "        if (not all(type(value) is int and value >= 0 for value in times) or not times[0] <= times[1] <= times[2] or\n"
        "                type(requested) is not dict or set(requested) != {\"ident\", \"filter\", \"flags\", \"fflags\"} or\n"
        "                not all(type(value) is int for value in requested.values()) or\n"
        "                requested != {\"ident\": pid, \"filter\": EVFILT_PROC, \"flags\": EV_ADD | EV_ENABLE | EV_RECEIPT,\n"
        "                              \"fflags\": NOTE_EXIT | NOTE_EXITSTATUS} or type(receipts) is not list or len(receipts) != 1):\n"
        "            return\n"
        "        receipt = receipts[0]\n"
        "        if (type(receipt) is not dict or set(receipt) != {\"ident\", \"filter\", \"flags\", \"fflags\", \"data\"} or\n"
        "                not all(type(value) is int for value in receipt.values()) or receipt[\"ident\"] != pid or\n"
        "                receipt[\"filter\"] != EVFILT_PROC or not receipt[\"flags\"] & EV_ERROR or receipt[\"data\"] != 0 or\n"
        "                type(terminal) is not dict or set(terminal) != {\"event\", \"status\"}):\n"
        "            return\n"
        "        decoded = decode_exit_event(terminal[\"event\"], pid)  # Revalidate retained DATA, not a new native query.\n"
        "        status = terminal[\"status\"]\n"
        "        if (type(status) is not dict or set(status) != set(decoded) or type(status[\"kind\"]) is not str or\n"
        "                not all(type(status[key]) is int for key in (\"rawStatus\", \"value\", \"popenCode\")) or status != decoded):\n"
        "            return\n"
        "        # No filesystem access occurs above the original D terminal-event gate.\n"
        "        if (private_directory(context.parent) != context.parent_identity or\n"
        "                private_directory(directory) != directory_identity):\n"
        "            return\n"
        "        path = directory / \"service.stderr\"\n"
        "        before = path.lstat()\n"
        "        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or before.st_nlink != 1 or\n"
        "                stat.S_IMODE(before.st_mode) != 0o600 or not 0 < before.st_size <= STARTUP_BYTES):\n"
        "            return\n"
        "        raw = read_file(path, STARTUP_BYTES)\n"
        "        after = path.lstat()\n"
        "        fields = (\"st_dev\", \"st_ino\", \"st_mode\", \"st_uid\", \"st_gid\", \"st_nlink\", \"st_size\", \"st_mtime_ns\", \"st_ctime_ns\")\n"
        "        if (any(getattr(before, key) != getattr(after, key) for key in fields) or\n"
        "                private_directory(directory) != directory_identity or private_directory(context.parent) != context.parent_identity):\n"
        "            return\n"
        "        for line in parse_startup_record(raw, case, binding):\n"
        "            print(line)\n"
        "    except BaseException:\n"
        "        pass  # Never replace the original refusal or manufacture an outcome.\n"
        "\n"
        "\n"
        "def service(directory):\n",
    ),
    (
        "    prepared, trace, end_ns = None, [], None\n",
        "    prepared, trace, end_ns = None, [], None\n"
        "    startup_site = None\n",
    ),
    (
        "        received = read_frame(channel, 2, binding, trace, end_ns, captures.check)[\"payload\"]\n",
        "        startup_site = \"PREPARE_READ\"\n"
        "        received = read_frame(channel, 2, binding, trace, end_ns, captures.check)[\"payload\"]\n"
        "        startup_site = \"PREPARE_VALIDATE\"\n",
    ),
    (
        "        with at_stage(\"IDENTITY\"):\n"
        "            probe_channel, child_channel = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)\n"
        "            try:\n"
        "                child_fd = child_channel.fileno()\n"
        "                environment = child_environment(directory)\n"
        "                environment.update(P2PKIT_CONTEXT_BINDING=binding, P2PKIT_CONTEXT_CASE_END_NS=str(end_ns),\n"
        "                                   P2PKIT_CONTEXT_CLOCK_SCHEMA=str(CLOCK_SCHEMA), P2PKIT_CONTEXT_CLOCK_DOMAIN=CLOCK_DOMAIN)\n"
        "                left(end_ns, \"START\")\n"
        "                process = subprocess.Popen([interpreter[\"path\"], \"-I\", \"-B\", \"-S\", str(ROOT / SCRIPT), \"_probe\", str(child_fd)],\n"
        "                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,\n"
        "                                           close_fds=True, pass_fds=(child_fd,), cwd=ROOT, env=environment)\n"
        "                producer_identity = native.identity(process.pid)\n"
        "                require(producer_identity[\"parentPid\"] == os.getpid() and\n"
        "                        producer_identity[\"parentUniqueId\"] == service_identity[\"uniqueId\"], \"IDENTITY\", \"IDENTITY_CHANGED\")\n"
        "                pipes = ProbePipes(process)\n"
        "            finally:\n"
        "                close_socket(child_channel)\n"
        "            probe_channel.setblocking(False)\n"
        "            ready = read_frame(probe_channel, 3, binding, trace, end_ns, pipes.pump)\n"
        "            validate_ready(ready, prepared, service_identity, producer_identity)\n"
        "            native.same(producer_identity)\n"
        "        send_frame(channel, 4, binding, {\"readyFrame\": ready}, trace, end_ns)\n",
        "        with at_stage(\"IDENTITY\"):\n"
        "            startup_site = \"CHILD_CHANNEL\"\n"
        "            probe_channel, child_channel = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)\n"
        "            try:\n"
        "                child_fd = child_channel.fileno()\n"
        "                startup_site = \"CHILD_ENVIRONMENT\"\n"
        "                environment = child_environment(directory)\n"
        "                environment.update(P2PKIT_CONTEXT_BINDING=binding, P2PKIT_CONTEXT_CASE_END_NS=str(end_ns),\n"
        "                                   P2PKIT_CONTEXT_CLOCK_SCHEMA=str(CLOCK_SCHEMA), P2PKIT_CONTEXT_CLOCK_DOMAIN=CLOCK_DOMAIN)\n"
        "                startup_site = \"CHILD_SPAWN\"\n"
        "                left(end_ns, \"START\")\n"
        "                process = subprocess.Popen([interpreter[\"path\"], \"-I\", \"-B\", \"-S\", str(ROOT / SCRIPT), \"_probe\", str(child_fd)],\n"
        "                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,\n"
        "                                           close_fds=True, pass_fds=(child_fd,), cwd=ROOT, env=environment)\n"
        "                startup_site = \"CHILD_IDENTITY\"\n"
        "                producer_identity = native.identity(process.pid)\n"
        "                require(producer_identity[\"parentPid\"] == os.getpid() and\n"
        "                        producer_identity[\"parentUniqueId\"] == service_identity[\"uniqueId\"], \"IDENTITY\", \"IDENTITY_CHANGED\")\n"
        "                startup_site = \"CHILD_PIPES\"\n"
        "                pipes = ProbePipes(process)\n"
        "            finally:\n"
        "                try:\n"
        "                    close_socket(child_channel)\n"
        "                except BaseException:\n"
        "                    startup_site = \"CHILD_CHANNEL\"\n"
        "                    raise\n"
        "            startup_site = \"CHILD_CHANNEL\"\n"
        "            probe_channel.setblocking(False)\n"
        "            startup_site = \"CHILD_READY_READ\"\n"
        "            ready = read_frame(probe_channel, 3, binding, trace, end_ns, pipes.pump)\n"
        "            startup_site = \"CHILD_READY_VALIDATE\"\n"
        "            validate_ready(ready, prepared, service_identity, producer_identity)\n"
        "            startup_site = \"CHILD_RECHECK\"\n"
        "            native.same(producer_identity)\n"
        "        startup_site = \"CHILD_READY_FORWARD\"\n"
        "        send_frame(channel, 4, binding, {\"readyFrame\": ready}, trace, end_ns)\n"
        "        startup_site = None\n",
    ),
    (
        "        # budget. The original F owns the one suite-wide exceptional interval.\n",
        "        # budget. The original F owns the one suite-wide exceptional interval.\n"
        "        startup_record = b\"\"\n"
        "        if startup_site is not None:\n"
        "            with contextlib.suppress(BaseException):\n"
        "                startup_record = startup_failure_record(error, prepared[\"case\"], binding, startup_site, pipes)\n",
    ),
    (
        "                os.write(2, (public_error(error) + \"\\n\").encode(\"ascii\"))\n",
        "                os.write(2, (public_error(error) + \"\\n\").encode(\"ascii\"))\n"
        "            if startup_record:\n"
        "                with contextlib.suppress(BaseException):\n"
        "                    os.write(2, startup_record)\n",
    ),
    (
        "    state = {\"case\": case, \"directory\": directory, \"listener\": None, \"channel\": None, \"admin\": None,\n"
        "             \"service\": None, \"producer\": None, \"prepareSent\": False, \"socket\": None}\n",
        "    state = {\"case\": case, \"directory\": directory, \"listener\": None, \"channel\": None, \"admin\": None,\n"
        "             \"service\": None, \"producer\": None, \"prepareSent\": False, \"socket\": None,\n"
        "             \"binding\": binding, \"directoryIdentity\": None}\n",
    ),
    (
        "                    \"jobEndNs\": context.job_end}\n",
        "                    \"jobEndNs\": context.job_end}\n"
        "        state[\"directoryIdentity\"] = prepared[\"directoryIdentity\"]\n",
    ),
    (
        "                  \"registrationAttempts\": context.native.attach_attempts, \"signalReturns\": context.native.signals})))\n",
        "                  \"registrationAttempts\": context.native.attach_attempts, \"signalReturns\": context.native.signals})))\n"
        "    with contextlib.suppress(BaseException):\n"
        "        emit_startup_diagnostic(context, state)\n",
    ),
)

# The timeout-site diagnostic must recover the complete accepted afaff3fc
# runtime before any historical runtime entrypoint applies its older inverse.
PROTOCOL_TIMEOUT_BASE_RUNTIME_SHA256 = "17b7105e3dab4dcf865d8fda633f988b9ad78d1b286e0ecbb215da8d2828da47"
PROTOCOL_TIMEOUT_PATCH = (
    ('def public_protocol_eof(error):\n',
     'def public_timeout_site(error):\n'
     '    """Fixed refusing guard only, not elapsed-time measurement or peer cause."""\n'
     '    if (type(error) is not ExperimentError or type(error.stage) is not str or type(error.reason) is not str or\n'
     '            type(error.errno_name) is not str or error.stage != "START" or error.reason != "TIMEOUT" or\n'
     '            error.errno_name != "NONE"):\n'
     '        return None\n'
     '    fields = getattr(error, "timeout_site", None)\n'
     '    if type(fields) is not tuple or len(fields) != 3:\n'
     '        return None\n'
     '    site, serial, phase = fields\n'
     '    case = getattr(error, "timeout_case", None)\n'
     '    case = case if type(case) is str and case in CASES else "UNKNOWN"\n'
     '    site = site if type(site) is str and site in (\n'
     '        "NATIVE_ENTRY", "CASE_ENTRY", "SEND_PRE", "SEND_SELECT", "SEND_RETURN", "READ_WAIT", "READ_RETURN", "FORWARD_TIME"\n'
     '    ) else "UNKNOWN"\n'
     '    frame = "NONE" if serial is None else (\n'
     '        ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8")[serial - 1] if type(serial) is int and 1 <= serial <= 8 else "UNKNOWN")\n'
     '    phase = "NONE" if phase is None else (phase if type(phase) is str and phase in ("HEADER", "BODY", "FRAME") else "UNKNOWN")\n'
     '    return "P2PKIT_CONTEXT_TIMEOUT_SITE|" + "|".join((case, site, frame, phase))\n'
     '\n\n'
     'def public_protocol_eof(error):\n'),
    ('def load_module(name, relative):\n',
     'def timeout_left(end_ns, site, serial=None, phase=None):\n'
     '    """Annotate only the original START deadline refusal; never reread a clock."""\n'
     '    try:\n'
     '        return left(end_ns, "START")\n'
     '    except ExperimentError as error:\n'
     '        if (type(error) is ExperimentError and type(error.stage) is str and type(error.reason) is str and\n'
     '                type(error.errno_name) is str and error.stage == "START" and error.reason == "TIMEOUT" and\n'
     '                error.errno_name == "NONE"):\n'
     '            error.timeout_site = (site, serial, phase)\n'
     '        raise\n'
     '\n\n'
     'def load_module(name, relative):\n'),
    ('    while pending:\n'
     '        left(end_ns, "START")\n',
     '    while pending:\n'
     '        timeout_left(end_ns, "SEND_PRE", serial, "FRAME")\n'),
    ('        _, ready, _ = select.select([], [channel], [], min(0.05, left(end_ns, "START")))\n',
     '        _, ready, _ = select.select([], [channel], [], min(0.05, timeout_left(end_ns, "SEND_SELECT", serial, "FRAME")))\n'),
    ('            pending = pending[count:]\n'
     '    left(end_ns, "START")\n',
     '            pending = pending[count:]\n'
     '    timeout_left(end_ns, "SEND_RETURN", serial, "FRAME")\n'),
    ('            ready, _, _ = select.select([channel], [], [], min(0.05, left(end_ns, "START")))\n',
     '            ready, _, _ = select.select([channel], [], [], min(0.05, timeout_left(end_ns, "READ_WAIT", serial, phase)))\n'),
    ('    validate_frame(value, serial, binding)\n'
     '    left(end_ns, "START")\n',
     '    validate_frame(value, serial, binding)\n'
     '    timeout_left(end_ns, "READ_RETURN", serial, "FRAME")\n'),
    ('    require(type(forward) is dict and set(forward) == {"startedMonotonicNs", "returnedMonotonicNs"} and\n'
     '            all(type(value) is int and value > 0 for value in forward.values()) and\n'
     '            forward["startedMonotonicNs"] <= forward["returnedMonotonicNs"] < prepared["caseEndNs"], "START", "TIMEOUT")\n',
     '    try:\n'
     '        require(type(forward) is dict and set(forward) == {"startedMonotonicNs", "returnedMonotonicNs"} and\n'
     '                all(type(value) is int and value > 0 for value in forward.values()) and\n'
     '                forward["startedMonotonicNs"] <= forward["returnedMonotonicNs"] < prepared["caseEndNs"], "START", "TIMEOUT")\n'
     '    except ExperimentError as error:\n'
     '        if (type(error) is ExperimentError and type(error.stage) is str and type(error.reason) is str and\n'
     '                type(error.errno_name) is str and error.stage == "START" and error.reason == "TIMEOUT" and\n'
     '                error.errno_name == "NONE"):\n'
     '            error.timeout_site = ("FORWARD_TIME", 8, "FRAME")\n'
     '        raise\n'),
    ('    end_ns = min(context.limit(CASE_SECONDS), native_end)\n'
     '    left(end_ns, "START")\n',
     '    end_ns = min(context.limit(CASE_SECONDS), native_end)\n'
     '    timeout_left(end_ns, "CASE_ENTRY")\n'),
    ('def run_cases(context):\n',
     'def perform_case_with_timeout(context, case, native_end):\n'
     '    """Keep the held case even when its original entry guard precedes state."""\n'
     '    try:\n'
     '        return perform_case(context, case, native_end)\n'
     '    except ExperimentError as error:\n'
     '        if (type(error) is ExperimentError and type(error.stage) is str and type(error.reason) is str and\n'
     '                type(error.errno_name) is str and error.stage == "START" and error.reason == "TIMEOUT" and\n'
     '                error.errno_name == "NONE" and type(getattr(error, "timeout_site", None)) is tuple and\n'
     '                len(error.timeout_site) == 3):\n'
     '            error.timeout_case = case if type(case) is str and case in CASES else "UNKNOWN"\n'
     '        raise\n'
     '\n\n'
     'def run_cases(context):\n'),
    ('            left(native_end, "START")\n',
     '            timeout_left(native_end, "NATIVE_ENTRY")\n'),
    ('            perform_case(context, case, native_end)\n',
     '            perform_case_with_timeout(context, case, native_end)\n'),
    ('        protocol_diagnostic = public_protocol_eof(error)\n',
     '        timeout_diagnostic = public_timeout_site(error)\n'
     '        if timeout_diagnostic is not None:\n'
     '            print(timeout_diagnostic)\n'
     '        protocol_diagnostic = public_protocol_eof(error)\n'),
)

# The required-frame EOF diagnostic must recover the complete accepted 85392b0d
# runtime before every historical runtime inverse, including direct plist calls.
PROTOCOL_EOF_BASE_RUNTIME_SHA256 = "e92c291407c4b1f6f000a675c07190b34c340cd6b17648e5d73fd8a610e9acac"
PROTOCOL_EOF_PATCH = (
    ('def annotate_admin_return(error, return_site, case, result, *, ledger=False):\n',
     'def public_protocol_eof(error):\n'
     '    """Fixed required-frame EOF boundary only, not peer cause or acceptance."""\n'
     '    if (type(error) is not ExperimentError or type(error.stage) is not str or type(error.reason) is not str or\n'
     '            error.stage != "START" or error.reason != "STATUS_MISSING"):\n'
     '        return None\n'
     '    fields = getattr(error, "protocol_eof", None)\n'
     '    if type(fields) is not tuple or len(fields) != 3:\n'
     '        return None\n'
     '    serial, phase, progress = fields\n'
     '    case = getattr(error, "protocol_eof_case", None)\n'
     '    case = case if type(case) is str and case in CASES else "UNKNOWN"\n'
     '    frame = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8")[serial - 1] if type(serial) is int and 1 <= serial <= 8 else "UNKNOWN"\n'
     '    phase = phase if type(phase) is str and phase in ("HEADER", "BODY") else "UNKNOWN"\n'
     '    progress = progress if type(progress) is str and progress in ("EMPTY", "PARTIAL") else "UNKNOWN"\n'
     '    return "P2PKIT_CONTEXT_PROTOCOL_EOF|" + "|".join((case, frame, phase, progress))\n'
     '\n\n'
     'def annotate_admin_return(error, return_site, case, result, *, ledger=False):\n'),
    ('    def exact(size):\n', '    def exact(size, phase):\n'),
    ('                require(part, "START", "STATUS_MISSING")\n',
     '                try:\n'
     '                    require(part, "START", "STATUS_MISSING")\n'
     '                except ExperimentError as error:\n'
     '                    error.protocol_eof = (serial, phase, "EMPTY" if len(data) == 0 else "PARTIAL")\n'
     '                    raise\n'),
    ('    size = struct.unpack("!I", exact(4))[0]\n',
     '    size = struct.unpack("!I", exact(4, "HEADER"))[0]\n'),
    ('    raw = exact(size)\n', '    raw = exact(size, "BODY")\n'),
    ('    except BaseException:\n'
     '        abort_suite(context)\n'
     '        raise\n',
     '    except BaseException as error:\n'
     '        if (type(error) is ExperimentError and type(error.stage) is str and type(error.reason) is str and\n'
     '                error.stage == "START" and error.reason == "STATUS_MISSING" and\n'
     '                type(getattr(error, "protocol_eof", None)) is tuple and len(error.protocol_eof) == 3):\n'
     '            current = context.current\n'
     '            case = current.get("case") if type(current) is dict else None\n'
     '            error.protocol_eof_case = case if type(case) is str and case in CASES else "UNKNOWN"\n'
     '        abort_suite(context)\n'
     '        raise\n'),
    ('        admin_diagnostic = public_admin_site(error)\n',
     '        protocol_diagnostic = public_protocol_eof(error)\n'
     '        if protocol_diagnostic is not None:\n'
     '            print(protocol_diagnostic)\n'
     '        admin_diagnostic = public_admin_site(error)\n'),
)

# The filename-only increment must recover the complete accepted 372bf615
# runtime before either historical runtime entrypoint applies its older inverse.
PLIST_NAME_BASE_RUNTIME_SHA256 = "c2726e3b3e43544f813f567f674473f52636fa165f70766a1f0f7cd1e18dc1bf"
PLIST_NAME_PATCH = (
    ('            exact.append(["/usr/bin/mktemp", self.root + "/job.XXXXXXXXXX"])\n',
     '            exact.append(["/usr/bin/mktemp", self.root + "/job.plist"])\n'),
    ('        raw = self._run(["/usr/bin/mktemp", self.root + "/job.XXXXXXXXXX"], "ADMIN_CREATE")["stdout"]\n',
     '        raw = self._run(["/usr/bin/mktemp", self.root + "/job.plist"], "ADMIN_CREATE")["stdout"]\n'),
    ('        require(re.fullmatch(re.escape(self.root.encode("ascii")) + rb"/job\\.[A-Za-z0-9]{10}\\n", raw),\n'
     '                "ADMIN_CREATE", "UNSUPPORTED")\n',
     '        require(raw == self.root.encode("ascii") + b"/job.plist\\n", "ADMIN_CREATE", "UNSUPPORTED")\n'),
)

# The diagnostic-only increment must first recover the complete accepted
# c61acffd runtime. The original clock hunks/counts/hashes below stay unchanged.
ADMIN_RETURN_BASE_RUNTIME_SHA256 = "5224a331a6570a913aa3c34ac1785d2ae744688fbfe9e4329ba587e36586ba1b"
ADMIN_RETURN_PATCH = (
    ('ADMIN_ITEMS = frozenset((*SOURCE_OS_ITEMS.values(), "PRIVATE_DIRECTORY", "PRIVATE_FILE"))\n',
     'ADMIN_ITEMS = frozenset((*SOURCE_OS_ITEMS.values(), "PRIVATE_DIRECTORY", "PRIVATE_FILE"))\n'
     'ADMIN_RETURN_SITES = frozenset(("BOOTSTRAP_PRECHECK_PRINT", "BOOTSTRAP_COMMAND",\n'
     '                                "INSPECT_RUNNING_PRINT", "INSPECT_STOPPED_PRINT"))\n'
     'ADMIN_RETURN_GUARDS = frozenset(("LEDGER_WRITE", "RETURN_CODE", "STDERR"))\n'),
    ('@contextlib.contextmanager\ndef at_stage(stage):\n',
     'def annotate_admin_return(error, return_site, case, result, *, ledger=False):\n'
     '    """Describe an already-failed guard using only held, bounded primitives."""\n'
     '    site = return_site if type(return_site) is str and return_site in ADMIN_RETURN_SITES else "UNKNOWN"\n'
     '    case = case if type(case) is str and case in CASES else "UNKNOWN"\n'
     '    code = result.get("code") if type(result) is dict else None\n'
     '    stderr = result.get("stderr") if type(result) is dict else None\n'
     '    code = code if type(code) is int and -127 <= code <= 255 else "UNKNOWN"\n'
     '    stderr = ("EMPTY" if len(stderr) == 0 else "NONEMPTY") if type(stderr) is bytes else "UNKNOWN"\n'
     '    guard = "UNKNOWN"\n'
     '    if ledger is True:\n'
     '        guard = "LEDGER_WRITE"\n'
     '    elif type(code) is int and code != 0:\n'
     '        guard = "RETURN_CODE"\n'
     '    elif type(code) is int and code == 0 and stderr == "NONEMPTY":\n'
     '        guard = "STDERR"\n'
     '    error.admin_return = (site, case, guard, code, stderr)\n'
     '\n\n'
     'def public_admin_return(error):\n'
     '    """Fixed failing-return facts only; neither an OS cause nor acceptance."""\n'
     '    if (not isinstance(error, ExperimentError) or type(error.stage) is not str or type(error.reason) is not str or\n'
     '            error.stage != "BOOTSTRAP" or error.reason != "RETURN_FAILED"):\n'
     '        return None\n'
     '    fields = getattr(error, "admin_return", None)\n'
     '    if type(fields) is not tuple or len(fields) != 5:\n'
     '        return None\n'
     '    site, case, guard, code, stderr = fields\n'
     '    site = site if type(site) is str and site in ADMIN_RETURN_SITES else "UNKNOWN"\n'
     '    case = case if type(case) is str and case in CASES else "UNKNOWN"\n'
     '    guard = guard if type(guard) is str and guard in ADMIN_RETURN_GUARDS else "UNKNOWN"\n'
     '    code = str(code) if type(code) is int and -127 <= code <= 255 else "UNKNOWN"\n'
     '    stderr = stderr if type(stderr) is str and stderr in ("EMPTY", "NONEMPTY", "UNKNOWN") else "UNKNOWN"\n'
     '    return "P2PKIT_CONTEXT_ADMIN_RETURN|" + "|".join((site, case, guard, code, stderr))\n'
     '\n\n'
     '@contextlib.contextmanager\ndef at_stage(stage):\n'),
    ('    def _run(self, argv, stage, *, input_raw=b"", success=True):\n',
     '    def _run(self, argv, stage, *, input_raw=b"", success=True, return_site=None):\n'),
    ('        require(self.record.write(raw) == len(raw), stage, "RETURN_FAILED")\n',
     '        try:\n'
     '            require(self.record.write(raw) == len(raw), stage, "RETURN_FAILED")\n'
     '        except ExperimentError as error:\n'
     '            annotate_admin_return(error, return_site, self.directory.name, result, ledger=True)\n'
     '            raise\n'),
    ('        if success:\n'
     '            require(result["code"] == 0 and result["stderr"] == b"", stage, "RETURN_FAILED")\n'
     '        return result\n',
     '        if success:\n'
     '            try:\n'
     '                require(result["code"] == 0 and result["stderr"] == b"", stage, "RETURN_FAILED")\n'
     '            except ExperimentError as error:\n'
     '                annotate_admin_return(error, return_site, self.directory.name, result)\n'
     '                raise\n'
     '        return result\n'),
    ('        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP", success=False), self.label)\n'
     '        self._run(["/bin/launchctl", "bootstrap", "system", self.path], "BOOTSTRAP")\n',
     '        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP", success=False,\n'
     '                                 return_site="BOOTSTRAP_PRECHECK_PRINT"), self.label)\n'
     '        self._run(["/bin/launchctl", "bootstrap", "system", self.path], "BOOTSTRAP", return_site="BOOTSTRAP_COMMAND")\n'),
    ('        raw = self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP")["stdout"]\n',
     '        raw = self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP",\n'
     '                        return_site="INSPECT_RUNNING_PRINT" if running else "INSPECT_STOPPED_PRINT")["stdout"]\n'),
    ('        if admin_diagnostic is not None:\n'
     '            print(admin_diagnostic)\n'
     '        return 2  # No qualifying exclusive outcome/seal tuple on this route.\n',
     '        if admin_diagnostic is not None:\n'
     '            print(admin_diagnostic)\n'
     '        return_diagnostic = public_admin_return(error)\n'
     '        if return_diagnostic is not None:\n'
     '            print(return_diagnostic)\n'
     '        return 2  # No qualifying exclusive outcome/seal tuple on this route.\n'),
)

# Independently transcribed from the reviewed aef82967 -> shared-clock delta.
# The 33 runtime call replacements are separately counted, not arbitrary AST
# erasure; existing diagnostic/directory inverses run only AFTER this inverse.
RUNTIME_PATCH = (
    ('NS = 1_000_000_000\n',
     'NS = 1_000_000_000\n'
     'UINT64 = (1 << 64) - 1\n'
     'CLOCK_SCHEMA = 2\n'
     'CLOCK_DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"\n'),
    ('def errno_name(value):\n',
     'def shared_raw_ns():\n'
     '    """Only this guarded same-boot kernel clock crosses interpreter boundaries."""\n'
     '    require(sys.platform == "darwin" and callable(getattr(time, "clock_gettime_ns", None)) and\n'
     '            type(getattr(time, "CLOCK_MONOTONIC_RAW", None)) is int, "PREPARE", "UNSUPPORTED")\n'
     '    value = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)\n'
     '    require(type(value) is int and 0 <= value <= UINT64, "PREPARE", "BOUND")\n'
     '    return value\n'
     '\n'
     '\n'
     'def errno_name(value):\n'),
    ('def validate_allocation(allocation, request, github, now_ns, wall_ns):\n'
     '    keys = {"schema", "source", "sourceTree", "runId", "runAttempt", "startedMonotonicNs", "startedEpochNs"}\n'
     '    require(type(allocation) is dict and set(allocation) == keys and type(allocation["schema"]) is int and\n'
     '            allocation["schema"] == 1 and allocation["source"] == request["source_sha"] and\n',
     'def validate_allocation_clock(allocation, stage):\n'
     '    keys = {"schema", "clockDomain", "source", "sourceTree", "runId", "runAttempt", "startedMonotonicNs", "startedEpochNs"}\n'
     '    require(type(allocation) is dict and set(allocation) == keys and type(allocation["schema"]) is int and\n'
     '            allocation["schema"] == CLOCK_SCHEMA and type(allocation["clockDomain"]) is str and\n'
     '            allocation["clockDomain"] == CLOCK_DOMAIN, stage, "IDENTITY_CHANGED")\n'
     '\n'
     '\n'
     'def validate_allocation(allocation, request, github, now_ns, wall_ns):\n'
     '    validate_allocation_clock(allocation, "PREPARE")\n'
     '    require(allocation["source"] == request["source_sha"] and\n'),
    ('def producer(fd):\n'
     '    """Only the original D-created inherited FD and fixed START can select work."""\n',
     'def producer(fd):\n'
     '    """Only the original D-created inherited FD and fixed START can select work."""\n'
     '    require(os.environ.get("P2PKIT_CONTEXT_CLOCK_SCHEMA") == str(CLOCK_SCHEMA) and\n'
     '            os.environ.get("P2PKIT_CONTEXT_CLOCK_DOMAIN") == CLOCK_DOMAIN, "START", "IDENTITY_CHANGED")\n'),
    ('            directory.name == value["case"] and directory.parent.name == "evidence", "IDENTITY", "REFUSED")\n'
     '    validate_account(account(), value["account"])\n',
     '            directory.name == value["case"] and directory.parent.name == "evidence", "IDENTITY", "REFUSED")\n'
     '    validate_allocation_clock(value["allocation"], "START")\n'
     '    validate_account(account(), value["account"])\n'),
    ('            require(type(prepared) is dict and type(prepared.get("caseEndNs")) is int, "START", "TIMEOUT")\n'
     '            end_ns = prepared["caseEndNs"]\n',
     '            require(type(prepared) is dict and type(prepared.get("caseEndNs")) is int, "START", "TIMEOUT")\n'
     '            validate_allocation_clock(prepared.get("allocation"), "START")\n'
     '            end_ns = prepared["caseEndNs"]\n'),
    ('                environment.update(P2PKIT_CONTEXT_BINDING=binding, P2PKIT_CONTEXT_CASE_END_NS=str(end_ns))\n',
     '                environment.update(P2PKIT_CONTEXT_BINDING=binding, P2PKIT_CONTEXT_CASE_END_NS=str(end_ns),\n'
     '                                   P2PKIT_CONTEXT_CLOCK_SCHEMA=str(CLOCK_SCHEMA), P2PKIT_CONTEXT_CLOCK_DOMAIN=CLOCK_DOMAIN)\n'),
    ('def validate_seal(seal, github, allocation, identity, now_ns):\n',
     'def validate_seal(seal, github, allocation, identity, now_ns):\n'
     '    validate_allocation_clock(allocation, "UPLOAD")\n'),
)

WORKFLOW_PATCH = (
    ('          import time\n\n',
     '          import time\n\n'
     '          UINT64 = (1 << 64) - 1\n'
     '          CLOCK_SCHEMA = 2\n'
     "          CLOCK_DOMAIN = 'darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)'\n\n"),
    ('          def unique(pairs):\n',
     '          def shared_raw_ns():\n'
     "              require(sys.platform == 'darwin' and callable(getattr(time, 'clock_gettime_ns', None)) and\n"
     "                      type(getattr(time, 'CLOCK_MONOTONIC_RAW', None)) is int)\n"
     '              value = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)\n'
     '              require(type(value) is int and 0 <= value <= UINT64)\n'
     '              return value\n\n'
     '          def unique(pairs):\n'),
    ("              allocation = dict(schema=1, source=request['source_sha'], sourceTree=request['source_tree'],\n",
     '              allocation = dict(schema=CLOCK_SCHEMA, clockDomain=CLOCK_DOMAIN,\n'
     "                                source=request['source_sha'], sourceTree=request['source_tree'],\n"),
)

EXPERIMENT_TEST_PATCH = (
    ('class Focused(unittest.TestCase):\n',
     'class Focused(unittest.TestCase):\n'
     '    def setUp(self):\n'
     '        # Synthetic shared-clock readings only; these legacy models never\n'
     '        # qualify a host clock. The dedicated clock controls test its reader.\n'
     '        clock = patch.object(M, "shared_raw_ns", return_value=M.NS)\n'
     '        clock.start()\n'
     '        self.addCleanup(clock.stop)\n\n'),
    ('        context.allocation = dict(schema=1, source=SHA, sourceTree=TREE, runId="123", runAttempt="1",\n',
     '        context.allocation = dict(schema=2, clockDomain=M.CLOCK_DOMAIN, source=SHA, sourceTree=TREE,\n'
     '                                  runId="123", runAttempt="1",\n'),
    ('        allocation = dict(schema=1, source=SHA, sourceTree=TREE, runId="123", runAttempt="1",\n',
     '        allocation = dict(schema=2, clockDomain=M.CLOCK_DOMAIN, source=SHA, sourceTree=TREE,\n'
     '                          runId="123", runAttempt="1",\n'),
)


def _restore(source, patches, count, before_call, after_call, expected):
    if type(source) is not str:
        raise AssertionError("CLOCK_INVERSE_REQUIRES_CURRENT_SOURCE_TEXT")
    for before, after in reversed(patches):
        if source.count(after) != 1:
            raise AssertionError("EXACT_REVIEWED_CLOCK_HUNK_REQUIRED")
        source = source.replace(after, before, 1)
    if source.count(after_call) != count or before_call in source:
        raise AssertionError("EXACT_REVIEWED_CLOCK_SUBSTITUTIONS_REQUIRED")
    source = source.replace(after_call, before_call)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != expected:
        raise AssertionError("OUTSIDE_REVIEWED_CLOCK_DELTA_CHANGED")
    return source


def restore_child_startup_runtime(source):
    if type(source) is not str or len(CHILD_STARTUP_PATCH) != 5:
        raise AssertionError("EXACT_FIVE_CHILD_STARTUP_HUNKS_REQUIRED")
    for before, after in reversed(CHILD_STARTUP_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_CHILD_STARTUP_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != CHILD_STARTUP_BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_CHILD_STARTUP_DELTA_CHANGED")
    return source


def restore_ready_producer_runtime(source):
    source = restore_child_startup_runtime(source)
    if type(source) is not str or len(READY_PRODUCER_PATCH) != 5:
        raise AssertionError("EXACT_FIVE_READY_PRODUCER_HUNKS_REQUIRED")
    for before, after in reversed(READY_PRODUCER_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_READY_PRODUCER_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != READY_PRODUCER_BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_READY_PRODUCER_DELTA_CHANGED")
    return source


def restore_startup_diagnostic_runtime(source):
    source = restore_ready_producer_runtime(source)
    if type(source) is not str or len(STARTUP_DIAGNOSTIC_PATCH) != 10:
        raise AssertionError("EXACT_TEN_STARTUP_DIAGNOSTIC_HUNKS_REQUIRED")
    for before, after in reversed(STARTUP_DIAGNOSTIC_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_STARTUP_DIAGNOSTIC_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != STARTUP_DIAGNOSTIC_BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_STARTUP_DIAGNOSTIC_DELTA_CHANGED")
    return source


def restore_protocol_timeout_runtime(source):
    source = restore_startup_diagnostic_runtime(source)
    if type(source) is not str or len(PROTOCOL_TIMEOUT_PATCH) != 13:
        raise AssertionError("EXACT_THIRTEEN_PROTOCOL_TIMEOUT_HUNKS_REQUIRED")
    for before, after in reversed(PROTOCOL_TIMEOUT_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_PROTOCOL_TIMEOUT_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != PROTOCOL_TIMEOUT_BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_PROTOCOL_TIMEOUT_DELTA_CHANGED")
    return source


def restore_protocol_eof_runtime(source):
    source = restore_protocol_timeout_runtime(source)
    if type(source) is not str or len(PROTOCOL_EOF_PATCH) != 7:
        raise AssertionError("EXACT_SEVEN_PROTOCOL_EOF_HUNKS_REQUIRED")
    for before, after in reversed(PROTOCOL_EOF_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_PROTOCOL_EOF_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != PROTOCOL_EOF_BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_PROTOCOL_EOF_DELTA_CHANGED")
    return source


def restore_plist_name_runtime(source):
    source = restore_protocol_eof_runtime(source)
    if type(source) is not str or len(PLIST_NAME_PATCH) != 3:
        raise AssertionError("EXACT_THREE_PLIST_NAME_HUNKS_REQUIRED")
    for before, after in reversed(PLIST_NAME_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_PLIST_NAME_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != PLIST_NAME_BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_PLIST_NAME_DELTA_CHANGED")
    return source


def restore_admin_return_runtime(source):
    source = restore_plist_name_runtime(source)
    if type(source) is not str or len(ADMIN_RETURN_PATCH) != 8:
        raise AssertionError("EXACT_EIGHT_ADMIN_RETURN_HUNKS_REQUIRED")
    for before, after in reversed(ADMIN_RETURN_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_ADMIN_RETURN_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != ADMIN_RETURN_BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_ADMIN_RETURN_DELTA_CHANGED")
    return source


def restore_runtime(source):
    source = restore_admin_return_runtime(source)
    return _restore(source, RUNTIME_PATCH, 33, "time.monotonic_ns()", "shared_raw_ns()", BASE_RUNTIME_SHA256)


def restore_workflow(source):
    return _restore(source, WORKFLOW_PATCH, 3, "time.monotonic_ns()", "shared_raw_ns()", BASE_WORKFLOW_SHA256)


def restore_experiment_test(source):
    return _restore(source, EXPERIMENT_TEST_PATCH, 6, 'patch.object(M.time, "monotonic_ns"',
                    'patch.object(M, "shared_raw_ns"', BASE_EXPERIMENT_TEST_SHA256)
