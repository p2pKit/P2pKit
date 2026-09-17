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
    "preview shared default home" => ->(v) { step(v, "preview-output")["run"] = P.helper("prepare") },
    "preview pre-existing Gradle home" => ->(v) { step(v, "preview-output")["run"].sub!('[[ -e "$gradle_home" || -L "$gradle_home" ]]', "false") },
    "preview Windows chmod regression" => ->(v) { step(v, "preview-output")["run"].sub!(%q!"$python_bin" -I -B -S -c 'from pathlib import Path; import sys; Path(sys.argv[1]).mkdir(mode=0o700)'!, "mkdir -m 700") },
    "preview nonexclusive home creation" => ->(v) { step(v, "preview-output")["run"].sub!(".mkdir(mode=0o700)", ".mkdir(mode=0o700, exist_ok=True)") },
    "preview world-readable Unix home" => ->(v) { step(v, "preview-output")["run"].sub!("mode=0o700", "mode=0o755") },
    "unknown operation admitted" => ->(v) { ordinary(v)["steps"].shift },
    "credential checkout" => ->(v) { ordinary(v)["steps"][1]["with"]["persist-credentials"] = true },
    "moving checkout" => ->(v) { ordinary(v)["steps"][1]["with"]["ref"] = "main" },
    "old ordinary outputs admitted" => ->(v) { step(v, "ordinary-output")["run"] = "echo prepared" },
    "old preview outputs admitted" => ->(v) { step(v, "preview-output")["run"] = "echo prepared" },
    "implicit JDK acquisition" => ->(v) { step(v, "java")["with"]["java-version"] = "17" },
    "preview Kotlin cache restored" => ->(v) { step(v, "preview-gradle")["with"].delete("gradle-home-cache-excludes") },
    "preview cache on ordinary path" => ->(v) { step(v, "preview-gradle").delete("if") },
    "preview home on ordinary path" => ->(v) { step(v, "preview-output").delete("if") },
    "missing SDK37" => ->(v) { step(v, "sample-sdk")["run"].sub!("'platforms;android-37.0'", "") },
    "nonliteral SDK37 admission" => ->(v) { step(v, "sample-sdk")["run"].gsub!("grep -Fxq", "grep -xq") },
    "Android SDK on every host" => ->(v) { step(v, "sample-sdk").delete("if") },
    "Android on every host" => ->(v) { step(v, "sample-build")["run"].sub!('[[ "$RUNNER_OS" == Linux ]]', "true") },
    "build-only enabled for required verification" => ->(v) { step(v, "sample-build")["env"]["P2PKIT_SAMPLE_ONLY"] = "true" },
    "build-only outside explicit operation" => ->(v) { step(v, "sample-build")["env"]["P2PKIT_SAMPLE_ONLY"] = "${{ github.event_name == 'push' }}" },
    "build-only retains test task" => ->(v) {
        body = step(v, "sample-build")["run"]
        key = ":p2p-sample-desktop:installDist"
        body[body.rindex(key), key.length] = ":p2p-sample-desktop:check"
    },
    "missing APK task" => ->(v) { step(v, "sample-build")["run"].sub!(":p2p-sample-android:assembleDebug", ":p2p-sample-android:check") },
    "missing original CLI tests" => ->(v) { step(v, "sample-build")["run"].sub!(":p2p-sample-desktop:check", ":p2p-sample-desktop:classes") },
    "missing original UI tests" => ->(v) { step(v, "sample-build")["run"].sub!(":p2p-sample-desktop-ui:test", ":p2p-sample-desktop-ui:classes") },
    "installer instead of image" => ->(v) { step(v, "sample-build")["run"].sub!("createDistributable", "packageDistributionForCurrentOS") },
    "missing Debian installer" => ->(v) { step(v, "sample-build")["run"].sub!(":packageDeb", ":createDistributable") },
    "wrong Windows installer" => ->(v) { step(v, "sample-build")["run"].sub!(":packageMsi", ":packageDeb") },
    "missing macOS installer" => ->(v) { step(v, "sample-build")["run"].sub!(":packageDmg", ":createDistributable") },
    "offline assumptions" => ->(v) { step(v, "sample-build")["run"] += "./gradlew --offline check\n" },
    "lock mutation" => ->(v) { step(v, "sample-build")["run"].sub!("--no-daemon", "--write-locks") },
    "ignored build failure" => ->(v) { step(v, "sample-build")["continue-on-error"] = true },
    "changed source build" => ->(v) { step(v, "sample-build")["run"] = "git checkout main\n" + P::BUILD },
    "no strict verification" => ->(v) { step(v, "sample-build")["run"].sub!("--dependency-verification strict", "") },
    "build-cache reuse" => ->(v) { step(v, "sample-build")["run"].sub!("--no-build-cache", "--build-cache") },
    "unbounded workers" => ->(v) { step(v, "sample-build")["run"].sub!("--max-workers=2", "--max-workers=8") },
    "parallel Gradle" => ->(v) { step(v, "sample-build")["run"].sub!("--no-parallel", "--parallel") },
    "cleanup success-only" => ->(v) { step(v, "stop-sample-gradle")["if"] = "${{ success() }}" },
    "cleanup wrong home" => ->(v) { step(v, "stop-sample-gradle")["env"] = {"GRADLE_USER_HOME" => "other"} },
    "preview cleanup on ordinary path" => ->(v) { step(v, "stop-sample-gradle")["if"] = "${{ always() }}" },
    "ignored cleanup failure" => ->(v) { step(v, "stop-sample-gradle")["continue-on-error"] = true },
    "package after failed stop" => ->(v) { step(v, "sample-packaging")["if"] = "${{ always() }}" },
    "ordinary package before final acceptance" => ->(v) { step(v, "sample-packaging")["if"].sub!("steps.ordinary-required.outcome == 'success'", "steps.ordinary-run.outcome == 'success'") },
    "package stale outputs" => ->(v) { step(v, "sample-packaging")["run"] = "echo success" },
    "extra side effect" => ->(v) { ordinary(v)["steps"] << {"run" => "git push origin HEAD:main"} },
    "wrong native host" => ->(v) { ordinary(v)["strategy"]["matrix"]["os"][1] = "ubuntu-latest" },
    "overlapping heavy matrix" => ->(v) { ordinary(v)["strategy"]["max-parallel"] = 3 },
    "queue bypass" => ->(v) { ordinary(v).delete("concurrency") },
}
%w[pull_request].each do |event|
    %w[gradlew gradlew.bat .gitattributes .gitignore LICENSE].each do |path|
        mutations["omitted #{event} input #{path}"] = ->(v) { (v["on"] || v[true])[event]["paths"].delete(path) }
    end
end
["Upload native Desktop development apps", "Upload Android development APK"].each do |name|
    {"if-no-files-found" => "warn", "path" => "**/*", "name" => "latest", "retention-days" => 90,
     "include-hidden-files" => true, "overwrite" => true}.each do |key, value|
        mutations["#{name} #{key}"] = ->(v) { named_step(v, name)["with"][key] = value }
    end
    mutations["#{name} after failure"] = ->(v) { named_step(v, name)["if"] = "${{ always() }}" }
end

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
    [ci, release, workflow_test.sub('python3 -I -B -S "$ROOT/scripts/tests/package-sample-apps-test.py"', "true")],
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
