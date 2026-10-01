#!/usr/bin/env python3
"""Read-only Linux KVM prerequisite observations, never emulator/test admission.

No device open, identity/ACL change, module loading or virtualization workaround.
Only closed categories and numeric/Boolean metadata are printed, not host IDs,
user/group names, processor models or raw kernel files.
"""
import errno
import json
import os
from pathlib import Path
import re
import stat

SCOPE = 'READ_ONLY_KVM_ENVIRONMENT_NOT_EMULATOR_OR_ART_QUALIFICATION'


def error_kind(error):
    return {errno.ENOENT: 'MISSING', errno.EACCES: 'DENIED', errno.EPERM: 'DENIED'}.get(error.errno, 'OTHER_ERROR')


def read_bounded(path, maximum):
    try:
        if path.is_symlink():
            return 'SYMLINK', None
        with path.open('rb') as stream:
            raw = stream.read(maximum + 1)
        return ('TOO_LARGE', None) if len(raw) > maximum else ('READ', raw)
    except OSError as error:
        return error_kind(error), None


def observe(device=Path('/dev/kvm'), cpu=Path('/proc/cpuinfo'), modules=Path('/sys/module')):
    metadata = dict(inspection='MISSING', characterDevice=None, symlink=None, permissionMode=None,
                    effectiveUserOwns=None, effectiveGroupMatches=None, readable=None, writable=None)
    try:
        info = device.lstat()
        metadata.update(inspection='INSPECTED', characterDevice=stat.S_ISCHR(info.st_mode),
            symlink=stat.S_ISLNK(info.st_mode), permissionMode=format(stat.S_IMODE(info.st_mode), '04o'),
            effectiveUserOwns=info.st_uid == os.geteuid(),
            effectiveGroupMatches=info.st_gid in {os.getegid(), *os.getgroups()})
        # Do not follow a substituted device. This does not open /dev/kvm or
        # establish that a subsequent KVM ioctl/emulator boot will succeed.
        if not metadata['symlink']:
            metadata.update(readable=os.access(device, os.R_OK, effective_ids=True),
                            writable=os.access(device, os.W_OK, effective_ids=True))
    except OSError as error:
        metadata['inspection'] = error_kind(error)
    status, raw = read_bounded(cpu, 4 * 1024 * 1024)
    flags = set()
    if raw is not None:
        for row in re.findall(rb'(?m)^(?:flags|Features)\s*:\s*([^\n]*)$', raw):
            flags.update(row.split())
    nested = {}
    for module in ('kvm_intel', 'kvm_amd'):
        inspected, content = read_bounded(modules / module / 'parameters/nested', 64)
        nested[module] = ({b'Y': 'ENABLED', b'1': 'ENABLED', b'N': 'DISABLED', b'0': 'DISABLED'}.get(
            content.strip(), 'OTHER_VALUE') if content is not None else inspected)
    return dict(schema=1, scope=SCOPE, device=metadata, effectiveUserIsRoot=os.geteuid() == 0,
                cpuFlagsInspection=status, vmxExposed=b'vmx' in flags, svmExposed=b'svm' in flags,
                nestedParameters=nested, deviceOpenAttempted=False, policyChanged=False,
                emulatorBooted=False, artQualified=False)


if __name__ == '__main__':
    print(json.dumps(observe(), sort_keys=True))
