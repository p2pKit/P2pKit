"""One source of current-host executor test selection, without running fixtures."""


def class_names(host):
    native = {"macos-arm64": "DarwinNativeTests", "macos-x64": "DarwinNativeTests",
              "linux-x64": "LinuxNativeTests", "windows-x64": "WindowsNativeTests"}
    if host not in native:
        raise ValueError("Unsupported native control host")
    names = ["PurePolicyTests", "CapturePolicyTests", "DeadlinePolicyTests", "DarwinObservationTests", native[host]]
    if host != "windows-x64":
        names.append("ReportRetentionPosixTests")
    if host == "linux-x64":
        names.append("LinuxObservationTests")
    return (*names, "SupervisorMergeTests")
