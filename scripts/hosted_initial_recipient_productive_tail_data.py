"""Closed productive K DATA; no live owner, I/O, lease or acceptance factory.

The distinct flat cut is deliberately not PC's fixed30 archive or legacy P0.
Supplied bytes/hashes never restore R, K, a Recipient, a native close or a Step.
"""
from __future__ import annotations

import base64
import hashlib
import re

import hosted_initial_recipient_productive_custody_data as CD
import hosted_initial_recipient_productive_receiver_data as RD
import hosted_initial_recipient_stages as S
import hosted_initial_artifact_zip as Z


O = CD.O
NS = O.NS
LIMIT = CD.LIMIT
PUBLIC_LIMIT = CD.PUBLIC_LIMIT
MAX_ZIP_BYTES = 512 * 1024 * 1024
MAX_CIPHERTEXT_BYTES = 576 * 1024 * 1024
MAP_NAME = "custody-tail-map.json"
ARTIFACT_MEMBER = "custody-tail.tar.gz.gpg"
MANIFEST_MEMBER = "custody-tail-manifest.json"
CARRIER_MEMBERS = Z.MEMBERS
GROUPS = (
    "final-late-returned", "post-export-authority", "final-copy-references", "final-export-diagnostics",
    "final-public-home-late", "seal-authority", "seal-record", "before-authority", "before-return-originals",
    "tail-recipient-validation",
)
FIXED_COUNTS = {GROUPS[0]: 11, GROUPS[1]: 279, GROUPS[2]: 2, GROUPS[5]: 280,
    GROUPS[6]: 1, GROUPS[7]: 280, GROUPS[8]: 5}
INPUT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_MANIFEST_INPUTS_V1"
SCOPE = "ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_PRODUCTIVE_CUSTODY_TAIL_V1"
MAP_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_PRIVATE_FLAT_CUT_V1"
CONTEXT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_CHILD_CONTEXT_V1"
START_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_NATIVE_START_V1"
CHILD_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_PENDING_CHILD_CLOSE_V1"
ACK_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_POST_OWNER_CLOSE_ACK_V1"
PENDING_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_BEFORE_UPLOAD_PENDING_V1"
CARRIER_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_CARRIER_KNOWN_CLOSE_V1"
FILE = "before-upload-pending.json"
DIRECTORY = "tail-returned"
PRIVATE_CARRIER_CLOSE = "carrier-close.json"
OUTPUT = "initialProductiveBeforeSha256"
HASH_ENV = "P2PKIT_INITIAL_PRODUCTIVE_BEFORE_SHA256"
OUTCOME_ENV = "P2PKIT_INITIAL_PRODUCTIVE_BEFORE_OUTCOME"
DEADLINE_HASH_ENV = "P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_SHA256"
DEADLINE_BASE64_ENV = "P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_BASE64"
SEAL_OUTCOME_ENV = "P2PKIT_INITIAL_PRODUCTIVE_SEAL_OUTCOME"
CAP_FIELDS = ("startedNs", "workEndNs", "finalEndNs")
PHASE_NAMES = ("start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log")
PREDECESSOR_FIELDS = ("collectCloseSha256", "sealSha256", "beforeAuthoritySha256", "beforeIndexSha256", "deadlineSha256")
CUT_FIELDS = ("mapName", "mapSha256", "mapBytes", "memberCount", "totalBytes", "groups")
COMMON_FIELDS = tuple("schema scope kind selection source github policy initialRecipient productive final predecessors cut "
    "transport finalPrivateOriginals".split())
PUBLIC_EXTRA = tuple("recipient artifact testAcceptance productiveAuthority cacheAuthority exportSaveAuthority budgetAcceptance".split())
FINAL_FIELDS = tuple("manifestSha256 artifact archiveFiles archiveNativeNodes plaintextBytes".split())
TRANSPORT = {"artifactMember": ARTIFACT_MEMBER, "manifestMember": MANIFEST_MEMBER,
    "backendArtifact": "evidence.tar.gz.gpg", "backendManifest": "manifest.json"}
EXCLUDED = {"disposition": "NOT_DELIVERED", "coverage": "EXCLUDED_FROM_K_AND_R",
    "requiredEvidence": "NOT_USED_AS_QUALIFICATION_ORIGINALS"}
CONTEXT_FIELDS = tuple("schema scope kind root session job observed deadline originalProposal caps parentFirstNs "
    "parentFirstLocal beforeClosedNs originalServiceJob predecessors filesSha256 directories inheritedContext "
    "budgetAcceptance exportSaveAuthority".split())
TIME_FIELDS = ("beforeClosedNs", "tailChildClosedNs", "carrierClosedNs", "pendingPreparedNs")
PENDING_FIELDS = tuple("schema scope kind selection source github originalProposal deadline originals predecessors "
    "manifests cutMapSha256 members totalBytes zipBytes knownCloses times writerReturn originalStepOutcome upload "
    "testAcceptance productiveAuthority cacheAuthority exportSaveAuthority budgetAcceptance".split())
ORIGINAL_FIELDS = ("eventSha256", "policySha256", "matchSha256")
MANIFEST_FIELDS = ("finalSha256", "tailSha256")
CLOSE_FIELDS = ("beforeIndexSha256", "beforeWriterCloseSha256", "tailChildCloseSha256", "carrierCloseSha256")
SEAL_OUTPUT_FIELDS = ("initialProductiveSealSha256", "initialProductiveSealEndNs", "initialProductiveSealClockRole",
    "initialProductiveSealClockDomain", "initialProductiveSealClockTicksPerSecond", "initialProductiveSealBootSha256")
OUTPUT_FIELDS = (*SEAL_OUTPUT_FIELDS, OUTPUT, "initialProductiveDeadlineSha256", "initialProductiveDeadlineBase64")


def require(value, code):
    CD.require(value, "TAIL_" + code)


def fields(value, names):
    return CD.fields(value, names)


def integer(value, minimum=0, maximum=None):
    return CD.integer(value, minimum, maximum)


def sha(raw):
    require(type(raw) is bytes, "RAW_BYTES")
    return hashlib.sha256(raw).hexdigest()


def hashes(value, names):
    fields(value, names)
    for item in value.values():
        CD.sha(item)
    return value


def canonical(raw, maximum=LIMIT):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "RAW_BOUND")
    return CD.canonical(raw, maximum)


def encoded(value, maximum=LIMIT):
    raw = O.encoded(value)
    require(0 < len(raw) <= maximum, "ENCODED_BOUND")
    return raw


def _artifact(value):
    fields(value, "name sha256 size")
    require(value["name"] == "evidence.tar.gz.gpg", "ARTIFACT_NAME")
    CD.sha(value["sha256"])
    integer(value["size"], 33, MAX_CIPHERTEXT_BYTES)
    return value


def _final(value):
    fields(value, FINAL_FIELDS)
    CD.sha(value["manifestSha256"])
    _artifact(value["artifact"])
    integer(value["archiveFiles"], 32, CD.MAX_NODES)
    integer(value["archiveNativeNodes"], 63, CD.MAX_NODES)
    require(value["archiveNativeNodes"] == value["archiveFiles"] + 31, "FINAL_FIXED30_ROOTS")
    integer(value["plaintextBytes"], 1, CD.MAX_BYTES)
    return value


def final_reference(final_raw):
    value = CD.public_manifest(final_raw)
    return {"manifestSha256": sha(final_raw), "artifact": value["artifact"],
        **{name: value["copy"][name] for name in ("archiveFiles", "archiveNativeNodes", "plaintextBytes")}}


def cut(value, final_reference, native_windows):
    require(type(native_windows) is bool, "PLATFORM_TYPE")
    _final(final_reference)
    fields(value, CUT_FIELDS)
    require(value["mapName"] == MAP_NAME, "FIXED_MAP_NAME")
    CD.sha(value["mapSha256"])
    integer(value["mapBytes"], 1, LIMIT)
    fields(value["groups"], GROUPS)
    count = size = 0
    for name in GROUPS:
        row = fields(value["groups"][name], "memberCount totalBytes")
        optional = name == GROUPS[4]
        number = integer(row["memberCount"], 0 if optional else 1, CD.MAX_NODES)
        amount = integer(row["totalBytes"], 0 if optional else 1, CD.MAX_BYTES)
        if name in FIXED_COUNTS:
            require(number == FIXED_COUNTS[name], "FIXED_GROUP_COUNT")
        elif name == GROUPS[3]:
            require(number == (4 if native_windows else 7), "DIAGNOSTIC_COUNT")
        elif optional:
            require((number == 0 if native_windows else number <= 64) and
                ((number == 0) == (amount == 0)) and amount <= number * LIMIT, "PUBLIC_HOME_COUNT")
        else:
            require(name == GROUPS[9] and (number == 12 if native_windows else 13 <= number <= 77),
                "VALIDATION_COUNT")
        count += number
        size += amount
    require(type(value["memberCount"]) is int and value["memberCount"] == count + 1 and
        type(value["totalBytes"]) is int and value["totalBytes"] == size + value["mapBytes"], "CUT_ACCOUNTING")
    require(final_reference["archiveNativeNodes"] + count + 2 <= CD.MAX_NODES and
        final_reference["plaintextBytes"] + size + value["mapBytes"] <= CD.MAX_BYTES, "SHARED_CUT_BOUND")
    return value


def _public_github(value, source, selection):
    """Closed declaration, not a current GitHub or source observation."""
    _, role, system, arch = S.bootstrap.selection(selection)
    S.joint.source(source)
    github = fields(value, "repository eventSha256 event runId runAttempt workflow workflowSha job ref profile "
        "selection runnerOS runnerArch")
    require(github["repository"] == S.identity.REPOSITORY and github["job"] == S.bootstrap.JOB and
        github["profile"] == S.bootstrap.PROFILE and github["selection"] == selection and
        github["ref"] == S.SOURCE_REF and github["event"] == "workflow_dispatch" and
        github["workflowSha"] == source["commit"] and
        (github["runnerOS"], github["runnerArch"]) == (system, arch), "PUBLIC_GITHUB")
    S.joint.run(github)
    CD.sha(github["eventSha256"])
    require(type(github["workflow"]) is str and github["workflow"] == S.bootstrap.WORKFLOW, "WORKFLOW")
    return role


def _common(value):
    require(type(value["schema"]) is int and value["schema"] == 1 and value["kind"] == "worker", "PUBLIC_SCOPE")
    role = _public_github(value["github"], value["source"], value["selection"])
    policy = fields(value["policy"], "origin commit blob path sha256 fingerprint keySha256 expiresAt retentionDays")
    require(policy["origin"] == "reviewed-head" and policy["commit"] == value["source"]["commit"] and
        policy["path"] == S.identity.POLICY_PATH and policy["sha256"] == S.POLICY_SHA256 and
        type(policy["retentionDays"]) is int and policy["retentionDays"] == 14, "PUBLIC_POLICY")
    require(type(policy["blob"]) is str and re.fullmatch(r"[0-9a-f]{40}", policy["blob"]), "POLICY_BLOB")
    CD.sha(policy["keySha256"])
    require(type(policy["fingerprint"]) is str and re.fullmatch(r"[0-9A-F]{40}", policy["fingerprint"]), "POLICY_FINGERPRINT")
    integer(policy["expiresAt"], 1, 253402300799)
    initial = fields(value["initialRecipient"], "authority environment originalBase reviewed firstUseAt notBefore expiresAt "
        "matchSha256 preExportReturnSha256 preExportIndexSha256")
    require(initial["originalBase"] == S.BASE and initial["reviewed"] == value["source"], "INITIAL_SOURCE")
    S.environment(initial["environment"])
    authority = fields(initial["authority"], "id url bodySha256 owner ownerId createdAt")
    integer(authority["id"], 1, 10 ** 20 - 1)
    CD.sha(authority["bodySha256"])
    require(authority["owner"] == S.joint.OWNER_LOGIN and type(authority["ownerId"]) is int and
        authority["ownerId"] == S.joint.OWNER_ID and authority["url"] == "https://github.com/" +
        S.identity.REPOSITORY + "/issues/437#issuecomment-" + str(authority["id"]), "PUBLIC_AUTHORITY")
    for name in ("notBefore", "firstUseAt", "expiresAt"):
        integer(initial[name], 1, 253402300799)
    require(0 < S.joint.timestamp(authority["createdAt"]) <= initial["firstUseAt"] and
        initial["notBefore"] <= initial["firstUseAt"] < initial["expiresAt"] <= policy["expiresAt"] and
        initial["expiresAt"] - initial["notBefore"] <= 14 * 86400, "PUBLIC_AUTHORITY_WINDOW")
    hashes({name: initial[name] for name in ("matchSha256", "preExportReturnSha256", "preExportIndexSha256")},
        ("matchSha256", "preExportReturnSha256", "preExportIndexSha256"))
    productive = fields(value["productive"], "originalProposalSha256 producerHandoffSha256 producerReturnSha256 "
        "producerStepOutcome afterSaveSha256 afterSaveStepOutcome probeSha256 afterProbeStepOutcome prefixRetentionSha256 "
        "compatibilityInputsSha256")
    for name, item in productive.items():
        require(item == "success", "PRODUCTIVE_PRECEDING_STEP") if name.endswith("StepOutcome") else CD.sha(item)
    hashes(value["predecessors"], PREDECESSOR_FIELDS)
    cut(value["cut"], value["final"], role == "windows-x64")
    require(value["transport"] == TRANSPORT and value["finalPrivateOriginals"] == EXCLUDED,
        "FIXED_TRANSPORT_AND_SELF_TAIL")
    return value


def public_inputs(raw):
    value = canonical(raw, PUBLIC_LIMIT)
    fields(value, COMMON_FIELDS)
    require(value["scope"] == INPUT_SCOPE, "PUBLIC_INPUT_SCOPE")
    return _common(value)


def manifest_inputs(final_manifest_raw, predecessors, cut_value):
    final = CD.public_manifest(final_manifest_raw)
    value = {name: final[name] for name in ("schema", "kind", "selection", "source", "github", "policy",
        "initialRecipient", "productive")}
    value.update(scope=INPUT_SCOPE, final=final_reference(final_manifest_raw), predecessors=predecessors,
        cut=cut_value, transport=dict(TRANSPORT), finalPrivateOriginals=dict(EXCLUDED))
    raw = encoded(value, PUBLIC_LIMIT)
    public_inputs(raw)
    return raw


def public_manifest(raw):
    value = canonical(raw, PUBLIC_LIMIT)
    fields(value, (*COMMON_FIELDS, *PUBLIC_EXTRA))
    require(value["scope"] == SCOPE and value["testAcceptance"] == "NOT_PERFORMED" and
        value["productiveAuthority"] is value["cacheAuthority"] is value["exportSaveAuthority"] is False and
        value["budgetAcceptance"] == "NOT_ADMITTED", "PUBLIC_NONACCEPTANCE")
    _common(value)
    recipient = fields(value["recipient"], "fingerprint encryptionFingerprint keySha256 expiresAt")
    for name in ("fingerprint", "encryptionFingerprint"):
        require(type(recipient[name]) is str and re.fullmatch(r"[0-9A-F]{40}", recipient[name]), "RECIPIENT_FINGERPRINT")
    CD.sha(recipient["keySha256"])
    integer(recipient["expiresAt"], value["policy"]["expiresAt"], 253402300799)
    require(recipient["fingerprint"] == value["policy"]["fingerprint"] and
        recipient["keySha256"] == value["policy"]["keySha256"], "RECIPIENT_SAME_POLICY")
    _artifact(value["artifact"])
    return value


def join_manifests(final_raw, tail_raw):
    final, tail = CD.public_manifest(final_raw), public_manifest(tail_raw)
    expected = public_inputs(manifest_inputs(final_raw, tail["predecessors"], tail["cut"]))
    require({**{name: tail[name] for name in COMMON_FIELDS}, "scope": INPUT_SCOPE} == expected and
        tail["recipient"] == final["recipient"], "COMPLETE_FINAL_TAIL_JOIN")
    return final, tail


def caps(deadline, values):
    RD.deadline(encoded(deadline, PUBLIC_LIMIT))
    require(type(values) is tuple and len(values) == 3, "K_CAPS")
    start, work, final = tuple(integer(value) for value in values)
    require(start < work and work == min(start + 210 * NS, deadline["sealEndNs"] - 45 * NS) and
        final == work + 45 * NS <= deadline["sealEndNs"], "ORIGINAL_K_CAPS")
    return values


def deadline_environment(environment):
    require(type(environment) is dict and environment.get(OUTCOME_ENV) == "success" and
        environment.get(SEAL_OUTCOME_ENV) == "success", "ORIGINAL_PRECEDING_OUTCOMES")
    CD.sha(environment.get(HASH_ENV))
    CD.sha(environment.get(DEADLINE_HASH_ENV))
    return decoded_deadline(environment.get(DEADLINE_BASE64_ENV), environment[DEADLINE_HASH_ENV])


def decoded_deadline(value, checksum):
    """Decode only DATA; do not invent enclosing Step outcomes for this seam."""
    CD.sha(checksum)
    require(type(value) is str and 0 < len(value) <= 16384, "DEADLINE_ENV_BOUND")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        require(False, "DEADLINE_BASE64")
    require(base64.b64encode(raw).decode("ascii") == value and sha(raw) == checksum,
        "DEADLINE_ORIGINAL_HASH")
    return RD.deadline(raw)


def carrier_bytes(members):
    # Z is the unchanged four-member512MiB serializer, including all framing.
    zipped = Z.zip_bytes(members)
    return sum(row["bytes"] for row in members), zipped


def _identity(value):
    require(value["kind"] == "worker", "WORKER_ONLY")
    _, role, _, _ = S.bootstrap.selection(value["selection"])
    S.joint.source(value["source"])
    github = fields(value["github"], "repository runId runAttempt job jobId role")
    S.joint.run(github)
    integer(github["jobId"], 1, 10 ** 20 - 1)
    require(github["repository"] == S.identity.REPOSITORY and github["job"] == S.bootstrap.JOB and
        github["role"] == role, "PENDING_IDENTITY")
    deadline = RD.deadline(encoded(value["deadline"], PUBLIC_LIMIT))
    require(deadline["source"] == value["source"] and deadline["selection"] == value["selection"] and
        all(deadline["github"][name] == github[name] for name in ("repository", "runId", "runAttempt", "job")),
        "DEADLINE_IDENTITY")
    require(sha(encoded(value["originalProposal"])) == deadline["originalProposalSha256"], "ORIGINAL_PROPOSAL_HASH")
    proposal_deadline(value["originalProposal"], deadline)
    require(value["originalProposal"]["serviceTimeBasis"]["service"]["numericJobId"] == github["jobId"],
        "ORIGINAL_SERVICE_JOB_ID")
    return role, deadline


def proposal_deadline(proposal, deadline):
    """Closed original arithmetic, NOT service provenance or a live worker.

    U additionally rejoins RD.original_proposal to its actual closed final-input
    bytes/history/worker record, before any R, payload, demand or Create.
    """
    allocation = CD.D.allocation
    public_role = _public_github(deadline["github"], deadline["source"], deadline["selection"])
    require(public_role == deadline["clock"]["role"] and deadline["policySha256"] == S.POLICY_SHA256,
        "ORIGINAL_DEADLINE_PUBLIC_IDENTITY")
    fields(proposal, "schema scope profile selection cacheCohort source github workerIdentitySha256 clock firstUseAt "
        "budgetAcceptance testAcceptance exportSaveAuthority serviceTimeBasis serviceTimeBasisSha256 policy "
        "allocationStartBasisNs proposedJobEndNs phaseFencesNs productiveOwner")
    require(type(proposal["schema"]) is int and proposal["schema"] == 1 and proposal["scope"] ==
        "INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1" and proposal["profile"] == S.bootstrap.PROFILE and
        proposal["selection"] == deadline["selection"] and proposal["source"] == deadline["source"] and
        proposal["clock"] == deadline["clock"] and proposal["budgetAcceptance"] == "NOT_ADMITTED" and
        proposal["testAcceptance"] == "NOT_PERFORMED" and proposal["exportSaveAuthority"] is False and
        proposal["productiveOwner"] == "NOT_CREATED", "ORIGINAL_PROPOSAL_SCOPE")
    CD.sha(proposal["workerIdentitySha256"])
    CD.sha(proposal["serviceTimeBasisSha256"])
    integer(proposal["firstUseAt"], 1, 253402300799)
    cohort, role, _system, _arch = S.bootstrap.selection(proposal["selection"])
    require(proposal["cacheCohort"] == {"profile": cohort, "role": role}, "ORIGINAL_CACHE_COHORT")
    github = fields(proposal["github"], "repository eventSha256 event runId runAttempt workflow workflowSha job ref "
        "runnerOS runnerArch eventBinding")
    require(all(github[name] == deadline["github"][name] for name in github if name != "eventBinding") and
        github["eventBinding"] == {"originalMain": S.BASE["commit"], "policyHead": proposal["source"]["commit"],
            "selection": proposal["selection"], "expectedCommit": proposal["source"]["commit"],
            "expectedTree": proposal["source"]["tree"]}, "ORIGINAL_PROPOSAL_GITHUB")
    basis = proposal["serviceTimeBasis"]
    fields(basis, "schema scope profile selection cacheCohort source github workerIdentitySha256 clock firstUseAt "
        "budgetAcceptance testAcceptance exportSaveAuthority invocation service policy jobsRequestStartedNs "
        "jobStartedEpochSeconds serviceAgeSeconds chargedAgeNs jobStartBasisNs")
    CD.job(basis["invocation"])
    require(basis["scope"] == "INITIAL_RECIPIENT_BOOTSTRAP_SERVICE_TIME_BASIS_V1" and
        all(encoded(basis[name]) == encoded(proposal[name]) for name in ("schema", "profile", "selection", "cacheCohort",
            "source", "github", "workerIdentitySha256", "clock", "firstUseAt", "budgetAcceptance", "testAcceptance",
            "exportSaveAuthority")) and sha(encoded(basis)) == proposal["serviceTimeBasisSha256"], "ORIGINAL_BASIS_BINDING")
    service = fields(basis["service"], "firstNs lastNs numericJobId runnerName selector jobStartedAt originDateEpochSeconds "
        "jobsRequestStartedNs originalsSha256 budgetAcceptance exportSaveAuthority")
    require(type(service["runnerName"]) is str and 0 < len(service["runnerName"]) <= 256 and
        not any(ord(char) < 32 or ord(char) == 127 for char in service["runnerName"]) and
        service["selector"] == O.SERVICE_SELECTORS[deadline["clock"]["role"]] and
        service["budgetAcceptance"] == "NOT_ADMITTED" and service["exportSaveAuthority"] is False and
        integer(service["firstNs"]) <= integer(service["jobsRequestStartedNs"]) <= integer(service["lastNs"]),
        "ORIGINAL_SERVICE_DATA")
    integer(service["numericJobId"], 1, (1 << 63) - 1)
    hashes(service["originalsSha256"], ("attempt", "jobs", "approvals", "comment", "environment", "branches", "main", "reviewed_ref"))
    arithmetic = allocation.service_time.basis_arithmetic(service["jobsRequestStartedNs"],
        O.wire.utc_epoch(service["jobStartedAt"]), service["originDateEpochSeconds"])
    require(basis["policy"] == allocation.service_time.policy() and
        all(type(basis[name]) is int and basis[name] == item for name, item in arithmetic.items()) and
        basis["jobStartBasisNs"] == deadline["originalJobBasisNs"], "ORIGINAL_SERVICE_ARITHMETIC")
    fences = allocation.fence_arithmetic(basis["jobStartBasisNs"])
    job_end = allocation.service_time.job_end_arithmetic(basis["jobStartBasisNs"])
    require(encoded(proposal["policy"]) == encoded(allocation.policy()) and
        proposal["proposedJobEndNs"] == job_end and
        all(encoded(proposal[name]) == encoded(item) for name, item in fences.items()), "ORIGINAL_PHASE_ARITHMETIC")
    require(deadline["sealFirstNs"] < deadline["sealEndNs"] <= min(deadline["sealFirstNs"] + 120 * NS,
        proposal["phaseFencesNs"]["separate-seal"], job_end) and
        all(deadline[name] == proposal["phaseFencesNs"][phase] for name, phase in (
            ("uploadStartByNs", "upload-transition"), ("uploadEndNs", "evidence-upload"),
            ("afterEndNs", "upload-after-guard"), ("returnEndNs", "delivery-return"))), "ORIGINAL_PHASE_ENDS")
    return proposal


def pending_value(value):
    fields(value, PENDING_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == PENDING_SCOPE, "PENDING_SCOPE")
    _role, deadline = _identity(value)
    hashes(value["originals"], ORIGINAL_FIELDS)
    hashes(value["predecessors"], PREDECESSOR_FIELDS)
    hashes(value["manifests"], MANIFEST_FIELDS)
    hashes(value["knownCloses"], CLOSE_FIELDS)
    CD.sha(value["cutMapSha256"])
    require(value["originals"]["policySha256"] == S.POLICY_SHA256 == deadline["policySha256"] and
        value["originals"]["eventSha256"] == deadline["github"]["eventSha256"] and
        value["manifests"]["finalSha256"] == deadline["manifestSha256"] and
        value["knownCloses"]["beforeIndexSha256"] == value["predecessors"]["beforeIndexSha256"] and
        value["predecessors"]["deadlineSha256"] == sha(encoded(deadline, PUBLIC_LIMIT)) and
        all(value["predecessors"][name] == deadline[name] for name in ("collectCloseSha256", "sealSha256")),
        "PENDING_PREDECESSORS")
    total, zipped = carrier_bytes(value["members"])
    require(type(value["totalBytes"]) is int and value["totalBytes"] == total and
        type(value["zipBytes"]) is int and value["zipBytes"] == zipped and
        value["members"][1]["sha256"] == value["manifests"]["finalSha256"] and
        value["members"][3]["sha256"] == value["manifests"]["tailSha256"], "PENDING_MEMBERS")
    fields(value["times"], TIME_FIELDS)
    previous = deadline["sealFirstNs"]
    for name in TIME_FIELDS:
        previous = integer(value["times"][name], previous, deadline["sealEndNs"] - 1)
    require(value["writerReturn"] == "PENDING_OWNER_CLOSE" and value["originalStepOutcome"] == "NOT_OBSERVED" and
        value["upload"] == value["testAcceptance"] == "NOT_PERFORMED" and value["productiveAuthority"] is
        value["cacheAuthority"] is value["exportSaveAuthority"] is False and value["budgetAcceptance"] == "NOT_ADMITTED",
        "PENDING_NOT_ACCEPTANCE")
    return value


def parse_pending(raw):
    return pending_value(canonical(raw, PUBLIC_LIMIT))


def encode_pending(value):
    return encoded(pending_value(value), PUBLIC_LIMIT)


def output_values(raw):
    value = parse_pending(raw)
    deadline_raw = encoded(value["deadline"], PUBLIC_LIMIT)
    deadline = value["deadline"]
    clock = deadline["clock"]
    values = {"initialProductiveSealSha256": deadline["sealSha256"],
        "initialProductiveSealEndNs": str(deadline["sealEndNs"]),
        "initialProductiveSealClockRole": clock["role"], "initialProductiveSealClockDomain": clock["domain"],
        "initialProductiveSealClockTicksPerSecond": str(clock["ticksPerSecond"]),
        "initialProductiveSealBootSha256": deadline["originalBootDigest"], OUTPUT: sha(raw),
        "initialProductiveDeadlineSha256": sha(deadline_raw),
        "initialProductiveDeadlineBase64": base64.b64encode(deadline_raw).decode("ascii")}
    require(sum(len(name) + len(item) + 2 for name, item in values.items()) <= 4096 and
        all(type(item) is str and 0 < len(item) <= 16384 and "\n" not in item and "\r" not in item
            for item in values.values()), "EXACT_OUTPUT_BOUND")
    return tuple(values.items())


def seal_outputs(deadline):
    RD.deadline(encoded(deadline, PUBLIC_LIMIT))
    clock = deadline["clock"]
    return dict(zip(SEAL_OUTPUT_FIELDS, (deadline["sealSha256"], str(deadline["sealEndNs"]), clock["role"],
        clock["domain"], str(clock["ticksPerSecond"]), deadline["originalBootDigest"])))


def identity(value, role):
    require(type(value) is list and len(value) == 2, "IDENTITY")
    integer(value[0], 0, O.clocks.UINT64)
    if role == "windows-x64":
        require(type(value[1]) is str and re.fullmatch(r"[0-9a-f]{32}", value[1]) is not None, "WINDOWS_IDENTITY")
    else:
        require(role in O.clocks.DOMAINS, "ROLE")
        integer(value[1], 1, O.clocks.UINT64)
    return tuple(value)


def metadata(value, role, count):
    """Actual supplied observation grammar, never an open/verify/close action."""
    integer(count, 0, MAX_ZIP_BYTES)
    windows = role == "windows-x64"
    names = {"identity", "is_directory", "size", "links", "attributes", "creation_100ns", "modified_100ns",
        "change_100ns", "owner_sid", "protected_dacl"} if windows else {"device", "inode", "size", "mtime_ns", "ctime_ns"}
    fields(value, names)
    require(type(value["size"]) is int and value["size"] == count, "METADATA_SIZE")
    if windows:
        pin = identity(value["identity"], role)
        integer(value["attributes"], 0, O.clocks.UINT64)
        require(value["is_directory"] is False and type(value["links"]) is int and value["links"] == 1 and
            type(value["owner_sid"]) is str and re.fullmatch(r"S-1-[0-9-]{1,180}", value["owner_sid"]) is not None and
            value["protected_dacl"] is True and not value["attributes"] & (0x400 | 0x10), "WINDOWS_PRIVATE_FILE")
        integers = ("attributes", "creation_100ns", "modified_100ns", "change_100ns")
    else:
        pin = identity([value["device"], value["inode"]], role)
        integers = ("mtime_ns", "ctime_ns")
    for name in integers:
        integer(value[name], 0, O.clocks.UINT64)
    return pin


def write_close_metadata(role, before, after, count):
    """Same strict per-reader lifetime, only the known write-close seam differs."""
    require(metadata(before, role, count) == metadata(after, role, count), "WRITE_CLOSE_IDENTITY")
    allowed = {"modified_100ns", "change_100ns"} if role == "windows-x64" else set()
    require(encoded({name: value for name, value in before.items() if name not in allowed}) ==
        encoded({name: value for name, value in after.items() if name not in allowed}),
        "WRITE_CLOSE_METADATA_CHANGED")
    return "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY" if allowed else "POSIX_FULL_METADATA_EQUAL"


SOURCE_NAMES = ("productive-final/export-output/evidence.tar.gz.gpg", "productive-final/export-output/manifest.json",
    "productive-tail/tail-export-output/evidence.tar.gz.gpg", "productive-tail/tail-export-output/manifest.json")
FILE_FIELDS = {"name", "bytes", "sha256", "sourceRelative", "sourceDirectoryIdentity", "sourceRead", "write",
    "readback", "metadataPolicy"}
CARRIER_FIELDS = {"schema", "scope", "kind", "selection", "source", "github", "originalProposal", "deadline",
    "predecessors", "manifests", "cutMapSha256", "carrier", "files", "totalBytes", "zipBytes", "nativeClose",
    "ownerCloses", "times", "writerReturn", "originalStepOutcome", "upload", "testAcceptance",
    "productiveAuthority", "cacheAuthority", "exportSaveAuthority", "budgetAcceptance"}


def _resources(value, *, carrier):
    require(type(value) is list and 0 < len(value) <= CD.MAX_NODES, "RESOURCE_ROWS")
    labels = ("directory",) * 4 + ("reader", "writer", "reader") * 4 if carrier else None
    require(not carrier or len(value) == len(labels), "CARRIER_RESOURCE_COUNT")
    for ordinal, row in enumerate(value):
        fields(row, {"ordinal", "label", "closeAttempted", "closed"})
        require(type(row["ordinal"]) is int and row["ordinal"] == ordinal and type(row["label"]) is str and
            row["label"] in ("directory", "writer", "native-scope", "stdout", "stderr", "reader") and
            row["closeAttempted"] is True and row["closed"] is True and
            (not carrier or row["label"] == labels[ordinal]), "KNOWN_RESOURCE_CLOSE")


def close_value(value):
    encoded(value)
    fields(value, CARRIER_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CARRIER_SCOPE,
        "CARRIER_SCOPE")
    role, deadline = _identity(value)
    hashes(value["predecessors"], PREDECESSOR_FIELDS)
    require(value["predecessors"]["deadlineSha256"] == sha(encoded(deadline, PUBLIC_LIMIT)) and
        all(value["predecessors"][name] == deadline[name] for name in ("collectCloseSha256", "sealSha256")),
        "CARRIER_ORIGINAL_DEADLINE")
    hashes(value["manifests"], MANIFEST_FIELDS)
    require(value["manifests"]["finalSha256"] == deadline["manifestSha256"], "CARRIER_FINAL_MANIFEST")
    CD.sha(value["cutMapSha256"])
    fields(value["carrier"], {"relative", "identity"})
    require(value["carrier"]["relative"] == "upload-output", "FIXED_CARRIER")
    carrier_pin = identity(value["carrier"]["identity"], role)
    require(type(value["files"]) is list and len(value["files"]) == 4, "FOUR_FILES")
    file_pins, source_dirs, members = {carrier_pin}, [], []
    for number, row in enumerate(value["files"]):
        fields(row, FILE_FIELDS)
        members.append({name: row[name] for name in ("name", "bytes", "sha256")})
        require(row["sourceRelative"] == SOURCE_NAMES[number], "FIXED_SOURCE")
        source_dir = identity(row["sourceDirectoryIdentity"], role)
        source_dirs.append(source_dir)
        observations = []
        for name, label, ordinal in (("sourceRead", "reader", 4 + number * 3),
                ("write", "writer", 5 + number * 3), ("readback", "reader", 6 + number * 3)):
            observation = row[name]
            fields(observation, {"metadata", label + "Ordinal"})
            require(type(observation[label + "Ordinal"]) is int and observation[label + "Ordinal"] == ordinal,
                "EXACT_FILE_RESOURCE_ORDINAL")
            observations.append(metadata(observation["metadata"], role, row["bytes"]))
        require(observations[0] != observations[1] == observations[2] and
            observations[0] not in file_pins and observations[1] not in file_pins, "FILE_ALIAS")
        file_pins.update((observations[0], observations[1]))
        require(write_close_metadata(role, row["write"]["metadata"], row["readback"]["metadata"], row["bytes"]) ==
            row["metadataPolicy"], "WRITE_CLOSE_POLICY")
    require(source_dirs[0] == source_dirs[1] and source_dirs[2] == source_dirs[3] and
        source_dirs[0] != source_dirs[2] and not set(source_dirs).intersection(file_pins), "SOURCE_DIRECTORY_ALIAS")
    total, zipped = carrier_bytes(members)
    require(type(value["totalBytes"]) is int and value["totalBytes"] == total and type(value["zipBytes"]) is int and
        value["zipBytes"] == zipped and members[1]["sha256"] == value["manifests"]["finalSha256"] and
        members[3]["sha256"] == value["manifests"]["tailSha256"], "CARRIER_EQUATIONS")
    close = value["nativeClose"]
    fields(close, {"contextSha256", "resultSha256", "ackSha256", "phaseSha256"})
    for name in ("contextSha256", "resultSha256", "ackSha256"):
        CD.sha(close[name])
    hashes(close["phaseSha256"], PHASE_NAMES)
    require(close["ackSha256"] == close["phaseSha256"]["stdout.log"], "ACK_LINK")
    fields(value["ownerCloses"], {"native", "carrier"})
    for name, scope in (("native", "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_NATIVE_KNOWN_CLOSE_V1"),
            ("carrier", "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1")):
        observed = value["ownerCloses"][name]
        fields(observed, {"schema", "scope", "resources", "retirement", "exportSaveAuthority"})
        require(type(observed["schema"]) is int and observed["schema"] == 1 and observed["scope"] == scope and
            observed["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and observed["exportSaveAuthority"] is False,
            "OWNER_CLOSE_SCOPE")
        _resources(observed["resources"], carrier=name == "carrier")
    fields(value["times"], TIME_FIELDS[:-1])
    previous = deadline["sealFirstNs"]
    for name in TIME_FIELDS[:-1]:
        previous = integer(value["times"][name], previous, deadline["sealEndNs"] - 1)
    require(value["writerReturn"] == "PENDING_SEPARATE_RECORD_WRITER_CLOSE" and
        value["originalStepOutcome"] == "NOT_OBSERVED" and value["upload"] == value["testAcceptance"] == "NOT_PERFORMED" and
        value["productiveAuthority"] is False and value["cacheAuthority"] is False and
        value["exportSaveAuthority"] is False and value["budgetAcceptance"] == "NOT_ADMITTED", "NO_SELF_ACCEPTANCE")
    return value


def parse_close(raw):
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT, "BYTES")
    value = canonical(raw)
    require(encoded(value) == raw, "CANONICAL")
    return close_value(value)


def encode_close(value):
    raw = encoded(close_value(value))
    require(0 < len(raw) <= LIMIT, "BYTES")
    return raw
