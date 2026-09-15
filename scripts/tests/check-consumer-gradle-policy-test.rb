#!/usr/bin/env ruby
# Pure source/mutation controls: never execute Gradle, generated shell or downloads.
require_relative "../check-consumer-gradle-policy"

P = ConsumerGradlePolicy
ROOT = File.expand_path("../..", __dir__)
source = File.read(File.join(ROOT, "scripts/check-published-consumers.sh"))
entry = File.read(File.join(ROOT, "scripts/tests/check-kotlin-toolchain-policy-test.sh"))
P.check(source)
P.check_entrypoint(entry)
checks = 2
normalized = P.logical_lines(source).join("\n") + "\n"
P.check(normalized)
checks += 1
calls = P.logical_lines(source).select { |line| line.start_with?('(cd "$ROOT" &&') }
raise "fixture requires all four real caller forms" unless calls.length == 4
mutations = {}
calls.each_with_index do |call, index|
    {
        "missing no-daemon" => call.sub("--no-daemon", ""),
        "enabling daemon" => call.sub("--no-daemon", "--no-daemon --daemon"),
        "omitted call" => "",
        "commented call" => "# " + call,
        "ignored failure" => call + " || true",
        "changed task array" => call.sub(/\$\{(?:publish|consumer)_tasks\[@\]\}/, "changed_tasks"),
    }.each do |label, replacement|
        raise "ineffective caller mutation" if replacement == call
        mutations["caller #{index + 1}: #{label}"] = normalized.sub(call, replacement)
    end
end
mutations["changed complete default"] = normalized.sub("publish_tasks=(publishToMavenLocal)", "publish_tasks=(check)")
mutations["focused tasks implicitly selected"] = normalized.sub('if [[ "$CONSUMER_PROFILE" == lan-jvm-android ]]; then', "if true; then")
mutations["additional task mutation"] = normalized + "publish_tasks+=(check)\n"
mutations["duplicated call"] = normalized + calls.first + "\n"
[
    ":p2p-core:publishJvmPublicationToMavenLocal",
    ":p2p-core:publishAndroidPublicationToMavenLocal",
    ":p2p-transport-lan:publishJvmPublicationToMavenLocal",
    ":p2p-transport-lan:publishAndroidPublicationToMavenLocal",
    ":p2p-core:publishKotlinMultiplatformPublicationToMavenLocal",
].each do |task|
    mutations["missing fixed task #{task}"] = normalized.sub(task, "")
end
mutations.each do |label, altered|
    raise "ineffective mutation #{label}" if altered == normalized
    begin
        P.check(altered)
    rescue P::Violation
        checks += 1
        next
    end
    raise "Unsafe consumer Gradle-call policy accepted: #{label}"
end

invocation = 'ruby "$ROOT/scripts/check-consumer-gradle-policy.rb" "$CONSUMER_GATE"'
["", "# " + invocation, invocation + " || true", invocation + "\n" + invocation,
 invocation.sub('"$CONSUMER_GATE"', '"unrelated-script"')].each do |replacement|
    begin
        P.check_entrypoint(entry.sub(invocation, replacement))
    rescue P::Violation
        checks += 1
        next
    end
    raise "Missing/commented/ignored/changed consumer guard invocation accepted"
end

# Independent outer callers keep these controls reachable if the Kotlin guard is removed.
{
    "scripts/run-release-gate.sh" => "ruby scripts/tests/check-consumer-gradle-policy-test.rb",
    "scripts/tests/release-workflow-test.sh" => 'ruby "$ROOT/scripts/tests/check-consumer-gradle-policy-test.rb"',
}.each do |file, command|
    raise "consumer Gradle-call controls missing from #{file}" unless
        File.read(File.join(ROOT, file)).lines.map(&:chomp).count(command) == 1
    checks += 1
end
puts "RESULT: PASS — consumer Gradle-call policy (#{checks} pure controls; no build/runtime claim)"
