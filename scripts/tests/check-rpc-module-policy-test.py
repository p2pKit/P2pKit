#!/usr/bin/env python3
"""Offline source-inventory tripwires, not compilation, security or capacity evidence."""

import ast
import copy
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
RPC = "library/p2p-rpc/build.gradle.kts"
SAMPLE = "samples/p2p-sample-rpc/build.gradle.kts"
POLICY = "gradle/platform-test-policy.json"
RUNNER = "scripts/run-platform-tests.py"
PREREQUISITES = [
    "library/p2p-core/build.gradle.kts",
    "library/p2p-transport-lan/build.gradle.kts",
    "library/p2p-network-provisioning-android/build.gradle.kts",
    "library/p2p-network-provisioning-desktop/build.gradle.kts",
]
TARGETS = {
    "android": "androidJvm", "iosArm64": "native", "iosSimulatorArm64": "native",
    "iosX64": "native", "jvm": "jvm", "metadata": "common",
}
SUFFIXES = ["iosSimulatorArm64Test", "iosX64Test", "jvmTest", "testAndroidHostTest"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def project_dependencies(source):
    return set(re.findall(r'\b(?:api|implementation)\(project\("(:[^"\s]+)"\)\)', source))


def check(files):
    require(project_dependencies(files[RPC]) == {
        ":p2p-core", ":p2p-transport-lan", ":p2p-network-provisioning-android",
        ":p2p-network-provisioning-desktop",
    }, "RPC dependency direction changed")
    require(project_dependencies(files[SAMPLE]) == {":p2p-rpc", ":p2p-core", ":p2p-transport-lan"},
            "RPC sample dependency inventory changed")
    for name in PREREQUISITES:
        require(":p2p-rpc" not in project_dependencies(files[name]), "Prerequisite depends on optional RPC")

    policy = json.loads(files[POLICY])["model"]
    for module in (":p2p-rpc", ":p2p-sample-rpc"):
        require(policy.get(module) == {
            "targets": TARGETS, "tests": [module + ":" + suffix for suffix in SUFFIXES],
        }, "RPC platform inventory is incomplete")
    # Read literals only. Never import or invoke the platform execution driver here.
    assignments = [node for node in ast.parse(files[RUNNER]).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "PROFILES" for target in node.targets)]
    require(len(assignments) == 1, "Platform profile declaration changed")
    profiles = ast.literal_eval(assignments[0].value)
    for profile, suffix in (("ios-arm64", "iosSimulatorArm64Test"), ("ios-x64", "iosX64Test")):
        require(all(module + ":" + suffix in profiles[profile] for module in (":p2p-rpc", ":p2p-sample-rpc")),
                "Broad Apple profile omits RPC")

    require(files[SAMPLE].count('"runRpcCapacity"') == 1 and
            'tasks.register<JavaExec>("runRpcCapacity")' in files[SAMPLE],
            "Capacity driver must remain a single explicit opt-in task")
    for name, source in files.items():
        if name.endswith((".gradle.kts", ".yml", ".yaml")) and name != SAMPLE:
            require("runRpcCapacity" not in source, "Capacity execution wired into another build/workflow")


def main():
    paths = {RPC, SAMPLE, POLICY, RUNNER, *PREREQUISITES}
    paths.add("build.gradle.kts")
    for directory in ("library", "samples"):
        paths.update(str(path.relative_to(ROOT)) for path in (ROOT / directory).glob("*/build.gradle.kts"))
    paths.update(str(path.relative_to(ROOT)) for path in (ROOT / ".github/workflows").glob("*.y*ml"))
    files = {name: (ROOT / name).read_text(encoding="utf-8") for name in paths}
    check(files)
    mutations = [
        (RPC, 'api(project(":p2p-core"))', 'api(project(":p2p-rpc"))', "RPC dependency"),
        (SAMPLE, 'api(project(":p2p-rpc"))', '', "sample dependency"),
        (PREREQUISITES[0], '\n', '\nimplementation(project(":p2p-rpc"))\n', "Prerequisite"),
        (POLICY, '":p2p-rpc:jvmTest"', '":p2p-rpc:skippedTest"', "platform inventory"),
        (RUNNER, '":p2p-rpc:iosX64Test"', '":p2p-core:iosX64Test"', "Apple profile"),
        (SAMPLE, 'tasks.register<JavaExec>("runRpcCapacity")',
         'tasks.register<JavaExec>("runRpcCapacity")\ntasks.named("check") { dependsOn("runRpcCapacity") }',
         "single explicit"),
        ("build.gradle.kts", '\n', '\ntasks.named("check") { dependsOn(":p2p-sample-rpc:runRpcCapacity") }\n',
         "another build/workflow"),
    ]
    for name, before, after, expected in mutations:
        candidate = copy.copy(files)
        require(before in candidate[name], "Missing mutation anchor")
        candidate[name] = candidate[name].replace(before, after, 1)
        try:
            check(candidate)
        except ValueError as failure:
            require(expected in str(failure), "Mutation failed for the wrong reason")
        else:
            raise ValueError("Unsafe RPC source policy accepted")
    print(f"RESULT: PASS — RPC source inventories and opt-in capacity task; {len(mutations)} negative controls; "
          "no Kotlin/runtime qualification")


if __name__ == "__main__":
    main()
