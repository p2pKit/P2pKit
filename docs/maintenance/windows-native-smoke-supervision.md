# Fixed native smoke adapter

The canonical installed supervisor also accepts `native-custody` and
`native-restart`. These select only the existing
`p2pkit-windows-profile-smoke.exe` with, respectively,
`--disposable-custody-smoke` or `--disposable-custody-restart-smoke`.
They do not select the installed application or JNI provider.

Before execution, independently review/bind the exact source, maintained build
recipe, MSVC/SDK inputs, executable hash, ordinary interactive account and disposable
profile context. A caller-supplied hash or filename cannot authorize itself.
Preserve previous profiles, failures and smoke fixtures. No account, ACL, runtime,
firewall, directory-root or deadline override is provided.

After those prerequisites are admitted, use:

```powershell
python -I -B -S scripts/run-windows-installed-admission.py `
  --expected-source <full-reviewed-source-sha> --operation native-custody `
  --native-directory <private-directory-with-reviewed-fixed-executable> `
  --native-sha256 <independently-verified-executable-sha256> `
  --private-parent <new-private-evidence-directory> --python <same-python-exe>
```

The original-file reader verifies bounded AMD64 EXE bytes and the supplied
independent digest. It retains the original executable and ancestor handles,
denies write/delete sharing, and rejects unsupported ACLs, reparse points, hard
links and streams until observed process/descendant retirement. Close uncertainty
fails. Native output has a separate 64 KiB bound and exact mode/result grammar;
the installed operation's 4 KiB limit is unchanged.

The adapter reuses the same WindowsScope atomic job admission, QPC watchdog,
bounded captures, process witnesses, cleanup and final observed exit. Its outer
acceptance budget remains **30,000 ms**; the payload's own longer inner budget
cannot extend it. Native receipts have a distinct scope and retain the payload
hash. `appSource` in the existing envelope denotes the native source for these
two operations, not a claim about the installed MSI.

`scripts/tests/windows-native-smoke-payload-test.py` covers fixed selection,
mode/result substitution, hash-before-execution, original-owner retention and
failure/close handling. Re-run the canonical harmless Windows supervisor controls
after adapter changes. Source/model success does not qualify protected execution;
the actual smoke, negative filesystem/lock/fault matrices and application tests
need their own results. **NOT_READY** remains the campaign verdict.
