#!/usr/bin/env ruby
# Focused helper controls only: no complete release gate, action code or network.
require "fileutils"
require "open3"
require "tmpdir"

root = File.expand_path("../..", __dir__)
source = File.read(File.join(root, "scripts/tests/release-workflow-test.sh"))
definitions = %w[is_local_workflow_reference is_local_action_reference check_workflow_action_pins].map do |name|
    matches = source.scan(/^#{name}\(\) \{\n.*?^\}/m)
    raise "expected exactly one maintained #{name} helper" unless matches.length == 1
    matches.first
end
harness = "set -euo pipefail\n#{definitions.join("\n\n")}\ncheck_workflow_action_pins \"$1\" \"$2\"\n"

def step_workflow(reference)
    "jobs:\n  check:\n    steps:\n      - uses: #{reference}\n"
end

def job_workflow(reference, key = "uses")
    "jobs:\n  reusable:\n    #{key}: #{reference}\n"
end

def fixture_git(root, *args)
    out, err, status = Open3.capture3("git", *args, chdir: root)
    raise "owned fixture git failed: #{args.inspect}: #{status.inspect}: #{out.inspect}: #{err.inspect}" unless
        status.exitstatus == 0 && out.empty? && err.empty?
end

sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"
remote = "actions/checkout@#{sha}"
local_workflow = "./.github/workflows/source.yml"
provider = "./.github/actions/ordinary-cache-provider"
diagnostics = {
    pin: "FATAL: workflow action is not pinned by full commit",
    local: "FATAL: invalid local workflow/Action reference",
    decode: "FATAL: cannot decode workflow action references",
}

controls = [
    ["plain_remote_step_full_sha", 0, :pin, step_workflow(remote)],
    ["single_quoted_remote_pin", 0, :pin, step_workflow("'#{remote}'")],
    ["double_quoted_remote_pin", 0, :pin, <<~YAML],
        jobs:
          check:
            steps:
              - name: Check out exact source
                uses: "#{remote}"
    YAML
    ["plain_pin_outside_comment", 0, :pin, step_workflow("#{remote} # outside YAML comment")],
    ["single_quoted_pin_outside_comment", 0, :pin, step_workflow("'#{remote}' # outside YAML comment")],
    ["double_quoted_pin_outside_comment", 0, :pin, step_workflow("\"#{remote}\" # outside YAML comment")],
    ["quoted_reusable_job_pin", 0, :pin, job_workflow("\"example/repository/.github/workflows/reusable.yml@#{sha}\"", '"uses"')],
    ["plain_tracked_local_workflow", 0, :local, job_workflow(local_workflow)],
    ["single_quoted_local_workflow", 0, :local, job_workflow("'#{local_workflow}'")],
    ["double_quoted_local_workflow_comment", 0, :local, job_workflow("\"#{local_workflow}\" # outside YAML comment")],
    ["plain_local_initializer_action", 0, :local, step_workflow("./.github/actions/initial-recipient-initialize")],
    ["single_quoted_local_provider_action", 0, :local, step_workflow("'#{provider}'")],
    ["double_quoted_local_provider_comment", 0, :local, step_workflow("\"#{provider}\" # outside YAML comment")],
    ["run_block_has_no_actual_uses", 0, :zero, <<~YAML],
        jobs:
          check:
            steps:
              - run: |
                  uses: example/action@v7
    YAML
    ["plain_mutable_tag", 1, :pin, step_workflow("actions/checkout@v4")],
    ["single_quoted_mutable_tag", 1, :pin, step_workflow("'actions/checkout@v4'")],
    ["double_quoted_mutable_tag", 1, :pin, step_workflow('"actions/checkout@v4"')],
    ["mutable_branch_ref", 1, :pin, step_workflow("actions/checkout@main")],
    ["sha39", 1, :pin, step_workflow("actions/checkout@#{sha[0, 39]}")],
    ["sha41", 1, :pin, step_workflow("actions/checkout@#{sha}0")],
    ["nonhex_sha", 1, :pin, step_workflow("actions/checkout@#{sha[0, 39]}g")],
    ["uppercase_sha", 1, :pin, step_workflow("actions/checkout@#{sha.upcase}")],
    ["missing_ref", 1, :pin, step_workflow("actions/checkout")],
    ["quoted_trailing_suffix", 1, :pin, step_workflow("\"#{remote} trailing\"")],
    ["quoted_literal_comment", 1, :pin, step_workflow("\"#{remote} # literal comment\"")],
    ["malformed_yaml", 1, :decode, step_workflow('"unterminated')],
    ["null_uses", 1, :decode, step_workflow("null")],
    ["integer_uses", 1, :decode, step_workflow("123")],
    ["sequence_uses", 1, :decode, step_workflow("[#{remote}]")],
    ["mapping_uses", 1, :decode, step_workflow("{action: checkout}")],
    ["empty_quoted_uses", 1, :decode, step_workflow('""')],
    ["embedded_lf", 1, :decode, step_workflow("\"#{remote}\\nsecond\"")],
    ["embedded_cr", 1, :decode, step_workflow("\"#{remote}\\rsecond\"")],
    ["embedded_nul", 1, :decode, step_workflow("\"#{remote}\\0\"")],
    ["embedded_tab", 1, :decode, step_workflow("\"#{remote}\\tsecond\"")],
    ["mutable_reusable_job_ref", 1, :pin, job_workflow('"example/repository/.github/workflows/reusable.yml@main"')],
    ["later_invalid_step", 1, :pin, <<~YAML],
        jobs:
          check:
            steps:
              - uses: #{remote}
              - uses: actions/checkout@v4
    YAML
    ["unknown_quoted_local_action", 1, :local, step_workflow('"./.github/actions/not-allowed"')],
    ["local_workflow_traversal", 1, :local, job_workflow("./.github/workflows/../workflows/source.yml")],
    ["provider_index_missing", 1, :local, step_workflow(provider)],
    ["provider_index_symlink", 1, :local, step_workflow(provider)],
    ["provider_index_untracked", 1, :local, step_workflow(provider)],
]
raise "unexpected focused control roster" unless controls.length == 42 &&
    controls.map(&:first).uniq.length == 42 &&
    controls.first(14).all? { |_, expected, _, _| expected == 0 } &&
    controls.drop(14).all? { |_, expected, _, _| expected == 1 }

checks = 0
Dir.mktmpdir("workflow-action-pins-") do |temporary|
    fixture = File.realpath(temporary)
    index_relative = ".github/actions/ordinary-cache-provider/index.cjs"
    index_contents = "// Inert owned fixture; never executed.\n"
    tracked = {
        ".github/workflows/source.yml" => "name: Inert referenced workflow\n",
        ".github/actions/initial-recipient-initialize/action.yml" => "name: Inert initializer fixture\n",
        ".github/actions/ordinary-cache-provider/action.yml" => "name: Inert provider fixture\n",
        index_relative => index_contents,
    }
    tracked.each do |relative, contents|
        path = File.join(fixture, relative)
        FileUtils.mkdir_p(File.dirname(path))
        File.binwrite(path, contents)
    end
    fixture_git(fixture, "-c", "init.defaultBranch=main", "init", "--quiet", "--template=", ".")
    fixture_git(fixture, "add", "--", *tracked.keys)
    workflow = File.join(fixture, ".github/workflows/control.yml")
    index = File.join(fixture, index_relative)

    controls.each do |id, expected_status, diagnostic, yaml|
        case id
        when "provider_index_missing"
            File.unlink(index)
        when "provider_index_symlink"
            File.symlink("action.yml", index)
        when "provider_index_untracked"
            File.unlink(index)
            File.binwrite(index, index_contents)
            fixture_git(fixture, "rm", "--cached", "--quiet", "--", index_relative)
        end
        File.binwrite(workflow, yaml)
        out, err, status = Open3.capture3("bash", "-c", harness, "workflow-action-pin-control", fixture, workflow)
        raise "#{id}: expected exit#{expected_status}, got #{status.inspect}: #{err.inspect}" unless
            status.exitstatus == expected_status
        raise "#{id}: unexpected helper stdout: #{out.inspect}" unless out.empty?
        if expected_status == 0
            raise "#{id}: unexpected helper stderr: #{err.inspect}" unless err.empty?
        else
            raise "#{id}: wrong diagnostic: #{err.inspect}" unless err.start_with?(diagnostics.fetch(diagnostic))
        end
        checks += 1
    end
end
raise "focused control run incomplete" unless checks == 42
puts "PASS: workflow action pin policy (#{checks} checks; 14 positive, 28 negative)"
