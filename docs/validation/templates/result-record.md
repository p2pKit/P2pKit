# Validation result record

Copy this template into the exact candidate's `docs/validation/results/`
directory. One file represents one immutable run.

```yaml
schema_version: 1
candidate:
  version: ""
  commit_sha: ""
  tree_sha: ""
  clean_checkout: false
artifacts:
  - name: ""
    coordinates_or_path: ""
    sha256: ""
test:
  area: ""
  test_id: ""
  scenario_id: ""
  run_id: ""
  session_id: ""
  connection_ids: []
  transfer_ids: []
  started_at_utc: ""
  ended_at_utc: ""
participants:
  - role: ""
    platform: ""
    safe_device_id: ""
    model: ""
    architecture: ""
    os_version_and_build: ""
    app_version_and_build: ""
network:
  topology: ""
  router_or_ap: ""
  impairment_tool_and_version: ""
  impairment_configuration_and_seed: ""
configuration:
  protocol_version: ""
  timeouts: {}
  retries: {}
  packet_limits: {}
  fault_injection: ""
observations:
  ui: []
  expected_events: []
  observed_events: []
  warnings_or_anomalies: []
files:
  sender_size: null
  sender_sha256: ""
  receiver_size: null
  receiver_sha256: ""
outcome: PENDING
decision_reason: ""
cleanup_result: ""
evidence:
  private_immutable_uri: ""
  manifest_sha256: ""
  redactions: []
review:
  tester: ""
  reviewer: ""
  reviewed_at_utc: ""
  decision: PENDING
```

Required attachments remain governed by the test catalog and the applicable
area handbook. A completed template without those artifacts does not pass.
