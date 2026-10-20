#!/usr/bin/env python3
"""Use the maintained hosted marker domain for scoped Apple issue commands.

The first genuine native attempt hit only the legacy whole-host unobserved-parent
rule, including inside Xcode's mandatory provenance phase. Reuse the reviewed
ordinary hosted boundary; do not filter receipts or ignore known-child failures.
The legacy executor still owns argv, budgets, source, streams and finalization.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ci_evidence as evidence


def require_hosted_context(environment):
    # Called only by the source-owned CI dispatcher/callee, not a generic opt-out.
    workflow = environment.get('GITHUB_WORKFLOW_REF', '').partition('@')[0]
    if not (evidence._hosted_darwin_context(environment) and
            workflow == 'p2pKit/P2pKit/.github/workflows/ci.yml' and
            environment.get('GITHUB_JOB') == 'native'):
        raise ValueError('Apple issue commands require the actual source-bound hosted CI native job')


class HostedAppleScope(evidence._HostedDarwinScope):
    def description(self):
        return {**super().description(), 'scope': 'routine-github-hosted-marker-domain',
                'ownershipBoundary': evidence.HOSTED_DARWIN_BOUNDARY,
                'outsideDomainObservations': self.outside_domain_observations}


def make_scope(job, invocation, state, home):
    require_hosted_context(os.environ)
    return HostedAppleScope(job, invocation, state, home)


def load_executor():
    spec = importlib.util.spec_from_file_location('apple_hosted_leaf', ROOT / 'scripts/run-audit-command.py')
    executor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(executor)
    return executor


def main(argv=None):
    require_hosted_context(os.environ)  # Refuse before even starting an executor command.
    executor = load_executor()
    executor.make_scope = make_scope
    return executor.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
