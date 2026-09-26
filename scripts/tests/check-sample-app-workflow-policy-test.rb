#!/usr/bin/env ruby
# Pure YAML/adverse controls. No Gradle, hosted execution, downloads or signing.
require_relative "../check-sample-app-workflow-policy"

P = SampleAppWorkflowPolicy
workflows = HeavyJobQueuePolicy.read_workflows(File.join(P::ROOT, ".github/workflows"))
workflow = workflows.fetch("desktop-cross-host.yml")
P.check(workflow)
checks = 1

def ordinary(value)
    value.fetch("jobs").fetch("verify")
end

def step(value, id)
    matches = ordinary(value).fetch("steps").select { |item| item["id"] == id }
    raise "expected one #{id} step" unless matches.length == 1
    matches.first
end

def named_step(value, name)
    ordinary(value).fetch("steps").find { |item| item["name"] == name } || raise("missing #{name} step")
end

mutations = {
    "missing main trigger" => ->(v) { (v["on"] || v[true]).delete("push") },
    "wrong main branch" => ->(v) { (v["on"] || v[true])["push"]["branches"] = ["work/candidate"] },
    "main path filter suppresses ordinary pushes" => ->(v) { (v["on"] || v[true])["push"]["paths"] = P::PATHS },
    "omitted Android PR coverage" => ->(v) { (v["on"] || v[true])["pull_request"]["paths"].delete("samples/p2p-sample-android/**") },
    "main ignored-path filter suppresses ordinary pushes" => ->(v) { (v["on"] || v[true])["push"]["paths-ignore"] = ["docs/**"] },
    "omitted shared KMP PR coverage" => ->(v) { (v["on"] || v[true])["pull_request"]["paths"].delete("samples/sample-kmp-shared/**") },
    "publisher permissions" => ->(v) { v["permissions"]["contents"] = "write" },
    "publisher environment" => ->(v) { ordinary(v)["environment"] = "release" },
    "secret scope" => ->(v) { ordinary(v)["env"] = {"TOKEN" => "${{ secrets.PUBLISH }}"} },
    "unsupported job context" => ->(v) { ordinary(v)["env"] = {"GRADLE_USER_HOME" => "${{ runner.temp }}/p2pkit-sample-gradle"} },
    "alternate preview job" => ->(v) { v["jobs"]["sample-apps"] = {"steps" => [{"run" => "./gradlew assemble"}]} },
    "conditional ordinary job" => ->(v) { ordinary(v)["if"] = "${{ success() }}" },
    "missing checkout" => ->(v) { ordinary(v)["steps"].shift },
    "credential checkout" => ->(v) { named_step(v, "Check out repository")["with"]["persist-credentials"] = true },
    "moving checkout" => ->(v) { named_step(v, "Check out repository")["with"]["ref"] = "main" },
    "old ordinary outputs admitted" => ->(v) { step(v, "ordinary-output")["run"] = "echo prepared" },
    "implicit JDK acquisition" => ->(v) { step(v, "java")["with"]["java-version"] = "17" },
    "preview cache on ordinary path" => ->(v) { ordinary(v)["steps"].insert(1, {"uses" => "gradle/actions/setup-gradle@#{'a' * 40}"}) },
    "preview home on ordinary path" => ->(v) { ordinary(v)["steps"].insert(1, {"run" => 'echo GRADLE_USER_HOME=other >> "$GITHUB_ENV"'}) },
    "missing SDK37" => ->(v) { step(v, "sample-sdk")["run"].sub!("'platforms;android-37.0'", "") },
    "nonliteral SDK37 admission" => ->(v) { step(v, "sample-sdk")["run"].gsub!("grep -Fxq", "grep -xq") },
    "Android SDK on every host" => ->(v) { step(v, "sample-sdk").delete("if") },
    "Android SDK for an unmarked ordinary commit" => ->(v) { step(v, "sample-sdk")["if"] = "runner.os == 'Linux'" },
    # Six original Desktop tasks, native installers, strict options and owned
    # stop now belong to the pinned controller, not a second preview build.
    # The maintained composition controls mutate those executable suppliers.
    "direct build replaces custody" => ->(v) { step(v, "ordinary-run")["run"] = "./gradlew :p2p-sample-desktop-ui:createDistributable" },
    "build-only bypasses required verification" => ->(v) { step(v, "ordinary-run")["env"]["P2PKIT_SAMPLE_ONLY"] = "true" },
    "ordinary selector changed" => ->(v) { step(v, "ordinary-run")["run"].sub!("--profile desktop", "--profile full") },
    "offline assumptions" => ->(v) { step(v, "ordinary-run")["run"] += "./gradlew --offline check\n" },
    "lock mutation" => ->(v) { step(v, "ordinary-run")["run"] += "./gradlew --write-locks\n" },
    "ignored build failure" => ->(v) { step(v, "ordinary-run")["continue-on-error"] = true },
    "changed source build" => ->(v) { step(v, "ordinary-run")["run"] = "git checkout main\n" + step(v, "ordinary-run")["run"] },
    "preview cleanup on ordinary path" => ->(v) { ordinary(v)["steps"] << {"if" => "${{ always() }}", "run" => "./gradlew --stop"} },
    "ordinary package before final acceptance" => ->(v) { step(v, "ordinary-package")["if"].sub!("steps.ordinary-required.outcome == 'success'", "steps.ordinary-run.outcome == 'success'") },
    "package stale outputs" => ->(v) { step(v, "ordinary-package")["run"] = "echo success" },
    "ordinary package guard becomes an unsealed writer" => ->(v) { step(v, "ordinary-package")["run"] = P.helper("package") },
    "ordinary package guard regains writer allowance" => ->(v) { step(v, "ordinary-package")["timeout-minutes"] = 2 },
    "ordinary package ignores failure" => ->(v) { step(v, "ordinary-package")["continue-on-error"] = true },
    "ordinary package unvalidated evidence delivery" => ->(v) { step(v, "ordinary-package")["env"].delete("P2PKIT_HOSTED_TEST_UPLOAD_AFTER_OUTCOME") },
    "ordinary package forged evidence outcome" => ->(v) { step(v, "ordinary-package")["env"]["P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME"] = "success" },
    "ordinary delivery omitted" => ->(v) { ordinary(v)["steps"].delete(step(v, "ordinary-delivery")) },
    "ordinary delivery success-only" => ->(v) { step(v, "ordinary-delivery")["if"] = "${{ success() }}" },
    "ordinary delivery no actual deadline check" => ->(v) { step(v, "ordinary-delivery")["run"].sub!("sample-delivery-guard", "echo") },
    "ordinary delivery ignores partial upload" => ->(v) { step(v, "ordinary-delivery")["run"].sub!('test "$ANDROID_UPLOAD_COMPLETE" = true', "true") },
    "ordinary delivery admits Android on nonLinux" => ->(v) { step(v, "ordinary-delivery")["run"].sub!('test "$P2PKIT_SAMPLE_ANDROID_UPLOAD_OUTCOME" = skipped', "true") },
    "extra side effect" => ->(v) { ordinary(v)["steps"] << {"run" => "git push origin HEAD:main"} },
    "wrong native host" => ->(v) { ordinary(v)["strategy"]["matrix"]["os"][1] = "ubuntu-latest" },
    "overlapping heavy matrix" => ->(v) { ordinary(v)["strategy"]["max-parallel"] = 3 },
    "queue bypass" => ->(v) { ordinary(v).delete("concurrency") },
}
%w[pull_request].each do |event|
    %w[gradlew gradlew.bat .gitattributes .gitignore LICENSE buildSrc/** gradle/** scripts/**].each do |path|
        mutations["omitted #{event} input #{path}"] = ->(v) { (v["on"] || v[true])[event]["paths"].delete(path) }
    end
end
%w[operation expected_sha expected_tree reviewed_base evidence_public_key evidence_fingerprint].each do |field|
    mutations["manual input #{field}"] = ->(v) {
        (v["on"] || v[true])["workflow_dispatch"] = {"inputs" => {field => {"type" => "string"}}}
    }
end
["Upload ordinary native Desktop development apps", "Upload ordinary Android development APK"].each do |name|
    {"if-no-files-found" => "warn", "path" => "**/*", "name" => "latest", "retention-days" => 90,
     "include-hidden-files" => true, "overwrite" => true}.each do |key, value|
        mutations["#{name} #{key}"] = ->(v) { named_step(v, name)["with"][key] = value }
    end
    mutations["#{name} after failure"] = ->(v) { named_step(v, name)["if"] = "${{ always() }}" }
end
%w[desktop android].each do |kind|
    before, action, after = %W[ordinary-#{kind}-before ordinary-#{kind}-apps ordinary-#{kind}-after]
    mutations["#{kind} before omitted"] = ->(v) { ordinary(v)["steps"].delete(step(v, before)) }
    mutations["#{kind} before has no original package hash"] = ->(v) { step(v, before)["env"].delete("P2PKIT_SAMPLE_PACKAGE_SHA256") }
    mutations["#{kind} before accepts failed package"] = ->(v) { step(v, before)["if"] = "${{ always() }}" }
    mutations["#{kind} independent fresh upload allowance"] = ->(v) { step(v, action)["timeout-minutes"] = 3 }
    mutations["#{kind} wrong original upload allowance"] = ->(v) { step(v, action)["timeout-minutes"] = "${{ fromJSON(steps.ordinary-upload-before.outputs.upload_timeout_minutes) }}" }
    mutations["#{kind} upload cap widened"] = ->(v) { step(v, action)["if"].sub!("upload_timeout_minutes == '3'", "upload_timeout_minutes == '4'") }
    mutations["#{kind} after omitted"] = ->(v) { ordinary(v)["steps"].delete(step(v, after)) }
    mutations["#{kind} after success-only"] = ->(v) { step(v, after)["if"] = "${{ success() }}" }
    mutations["#{kind} after no original guard hash"] = ->(v) { step(v, after)["env"].delete("P2PKIT_SAMPLE_UPLOAD_GUARD_SHA256") }
    mutations["#{kind} after forged action success"] = ->(v) { step(v, after)["env"]["P2PKIT_SAMPLE_UPLOAD_OUTCOME"] = "success" }
    mutations["#{kind} terminal uses conclusion"] = ->(v) { step(v, "ordinary-delivery")["env"]["P2PKIT_SAMPLE_#{kind.upcase}_UPLOAD_OUTCOME"] = "${{ steps.#{action}.conclusion }}" }
end
%w[ordinary-output ordinary-package ordinary-desktop-before ordinary-desktop-apps ordinary-desktop-after
   ordinary-android-before ordinary-android-apps ordinary-android-after ordinary-delivery].each do |id|
    mutations["#{id} bypasses admitted release intent"] = ->(v) {
        step(v, id)["if"].sub!(" && " + P::CUSTODY::SAMPLE_INTENT, "")
    }
    mutations["#{id} trusts provisional release intent"] = ->(v) {
        step(v, id)["if"].sub!("steps.ordinary-admission.outcome == 'success' && ", "")
    }
end
mutations["Android loses shared-window predecessor"] = ->(v) {
    step(v, "ordinary-android-before")["env"].delete("P2PKIT_SAMPLE_DESKTOP_AFTER_OUTCOME")
}
mutations["Android proceeds after failed Desktop upload"] = ->(v) {
    step(v, "ordinary-android-before")["if"].sub!("steps.ordinary-desktop-after.outcome == 'success'", "true")
}

mutations.each do |name, mutate|
    altered = Marshal.load(Marshal.dump(workflow))
    mutate.call(altered)
    raise "sample mutation had no effect: #{name}" if altered == workflow
    begin
        P.check(altered)
    rescue P::Error
        checks += 1
        next
    end
    raise "Unsafe sample workflow policy accepted: #{name}"
end

ci = workflows.fetch("ci.yml")
release = File.read(File.join(P::ROOT, "scripts/run-release-gate.sh"))
workflow_test = File.read(File.join(P::ROOT, "scripts/tests/release-workflow-test.sh"))
P.entrypoints(ci, release, workflow_test)
checks += 1
conditional = Marshal.load(Marshal.dump(ci))
conditional["jobs"]["complete-gate"]["steps"].find { |s| s["name"] == P::STEP_NAME }["if"] = "false"
[
    [conditional, release, workflow_test],
    [ci, release.sub(P::RUBY_CHECK, "true"), workflow_test],
    [ci, release, workflow_test.sub('python3 -I -B "$ROOT/scripts/tests/package-sample-apps-test.py"', "true")],
].each do |inputs|
    begin
        P.entrypoints(*inputs)
    rescue P::Error
        checks += 1
        next
    end
    raise "Sample policy/packager check bypass accepted"
end
puts "RESULT: PASS — sample app workflow (#{checks} pure policy controls; no hosted build claim)"
