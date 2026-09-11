#!/usr/bin/env ruby
require "yaml"
require "shellwords"
require "json"
require "tmpdir"
require "fileutils"
require "open3"
require "cgi"
require "digest"

ROOT = File.expand_path("../..", __dir__)
JSON_REPORT = "build/reports/cyclonedx/bom.json"
XML_REPORT = "build/reports/cyclonedx/bom.xml"
GRADLE = %w[./gradlew --no-daemon --no-build-cache --rerun-tasks --dependency-verification
            strict --max-workers=2 --no-parallel --console=plain cyclonedxBom].freeze

def steps(workflow)
    workflow.fetch("jobs").fetch("publish-release").fetch("steps")
end

def gate(workflow)
    matches = steps(workflow).select { |step| step["id"] == "publication-sbom" }
    raise "exactly one publisher SBOM gate is required" unless matches.size == 1
    matches.first
end

def named_step(workflow, name)
    matches = steps(workflow).select { |step| step["name"] == name }
    raise "exactly one #{name} step is required" unless matches.size == 1
    matches.first
end

def check_publication_sbom(workflow)
    publish = workflow.fetch("jobs").fetch("publish-release")
    raise "publisher failures cannot be ignored" if publish.key?("continue-on-error")
    raise "publisher must preserve explicit Bash error handling" unless
        workflow.fetch("defaults") == {"run" => {"shell" => "bash"}} && !publish.key?("defaults")
    sbom = gate(workflow)
    %w[if continue-on-error env shell working-directory].each do |key|
        raise "SBOM gate cannot override #{key}" if sbom.key?(key)
    end
    commands = sbom.fetch("run").gsub(/\\\n/, " ").lines.map(&:strip).reject(&:empty?)
    raise "SBOM gate must fail closed and always attempt wrapper stop" unless
        commands.size == 4 && commands[0] == "set -euo pipefail" &&
        commands[1] == "trap './gradlew --stop' EXIT"
    raise "publisher must freshly generate with strict verification and bounded workers" unless
        Shellwords.split(commands[2]) == GRADLE
    raise "gate must validate exactly the generated JSON/XML without another build" unless
        Shellwords.split(commands[3]) == ["scripts/check-sbom.sh", JSON_REPORT, XML_REPORT]

    build = named_step(workflow, "Build and inspect signed Central bundle")
    upload = named_step(workflow, "Upload once and wait for publication")
    raise "publication must not bypass a failed SBOM gate" if upload.key?("if") || upload.key?("continue-on-error")
    raise "SBOM gate must follow the signed build and precede upload" unless
        steps(workflow).index(build) < steps(workflow).index(sbom) &&
        steps(workflow).index(sbom) < steps(workflow).index(upload)
    evidence = named_step(workflow, "Upload publication evidence")
    raise "publication evidence must be attempted even after failure" unless
        evidence["if"] == "always()" && evidence.fetch("uses").start_with?("actions/upload-artifact@") &&
        steps(workflow).index(evidence) > steps(workflow).index(upload)
    inputs = evidence.fetch("with")
    paths = inputs.fetch("path").split
    raise "publication evidence must retain both publisher SBOM files" unless
        [JSON_REPORT, XML_REPORT].all? { |path| paths.include?(path) } &&
        paths.none? { |path| path.start_with?("!") }
    raise "publisher evidence must be distinct from verification evidence" unless
        inputs.fetch("name").start_with?("maven-central-publication-")
end

path = ARGV.fetch(0, File.join(ROOT, ".github/workflows/publish-maven-central.yml"))
workflow = YAML.safe_load(File.read(path), aliases: true)
check_publication_sbom(workflow)
mutations = {
    "missing gate" => ->(w) { steps(w).delete(gate(w)) },
    "duplicate gate" => ->(w) { steps(w) << gate(w).dup },
    "gate in verification job only" => ->(w) {
        w["jobs"]["verify-release"]["steps"] << steps(w).delete(gate(w))
    },
    "gate before signed build" => ->(w) { steps(w).unshift(steps(w).delete(gate(w))) },
    "gate after publication" => ->(w) { steps(w) << steps(w).delete(gate(w)) },
    "ignored job failure" => ->(w) { w["jobs"]["publish-release"]["continue-on-error"] = true },
    "upload after failure" => ->(w) {
        named_step(w, "Upload once and wait for publication")["if"] = "always()"
    },
    "success-only evidence" => ->(w) { named_step(w, "Upload publication evidence")["if"] = "success()" },
    "verification artifact name" => ->(w) {
        named_step(w, "Upload publication evidence")["with"]["name"] = "maven-central-verification-test"
    },
}
%w[if continue-on-error env shell working-directory].each do |key|
    mutations["gate overrides #{key}"] = ->(w) { gate(w)[key] = true }
end
["--no-build-cache", "--rerun-tasks", "--dependency-verification strict", "set -euo pipefail",
 "trap './gradlew --stop' EXIT", "scripts/check-sbom.sh"].each do |text|
    mutations["missing #{text}"] = ->(w) { gate(w)["run"] = gate(w)["run"].sub(text, "") }
end
{
    "non-executed generator" => ["./gradlew --no-daemon", "echo ./gradlew --no-daemon"],
    "non-executed validator" => ["scripts/check-sbom.sh", "echo scripts/check-sbom.sh"],
    "different JSON" => [JSON_REPORT, "verification/bom.json"],
    "different XML" => [XML_REPORT, "verification/bom.xml"],
    "suppressed failure" => [XML_REPORT, XML_REPORT + " || true"],
}.each do |name, (from, to)|
    mutations[name] = ->(w) { gate(w)["run"] = gate(w)["run"].sub(from, to) }
end
[JSON_REPORT, XML_REPORT].each do |report|
    mutations["missing evidence #{report}"] = ->(w) {
        evidence = named_step(w, "Upload publication evidence")["with"]
        evidence["path"] = evidence["path"].split.reject { |p| p == report }.join("\n")
    }
end
mutations.each do |name, mutate|
    copy = Marshal.load(Marshal.dump(workflow))
    mutate.call(copy)
    rejected = false
    begin
        check_publication_sbom(copy)
    rescue KeyError, RuntimeError, ArgumentError
        rejected = true
    end
    raise "unsafe publication SBOM policy accepted: #{name}" unless rejected
end

# Execute the actual YAML shell with fake Gradle and the real content checker.
# The marker models a subsequent command; this is not a hosted scheduler,
# signing/publication rehearsal, or real dependency-generation test.
properties = File.read(File.join(ROOT, "gradle.properties"))
group = properties.match(/^GROUP=(.*)$/)[1].strip
version = properties.match(/^VERSION_NAME=(.*)$/)[1].strip
modules = %w[p2p-core p2p-transport-lan p2p-network-provisioning-android p2p-network-provisioning-desktop]
names = modules + %w[kotlinx-coroutines-core jmdns slf4j-api cryptography-provider-jdk-jvm
                     cryptography-provider-cryptokit-iosarm64 cryptography-provider-cryptokit-iossimulatorarm64
                     cryptography-provider-cryptokit-iosx64]
vendor_path = "library/p2p-transport-lan/vendor/jmdns"
producer_path = "library/p2p-transport-lan/build/embedded-jmdns/p2pkit-internal-jmdns.jar"
producer_bytes = "controlled publication fixture producer bytes, not a compiled JAR\n"
# Reuse the real, checked vendor contract for this shell-controller fixture.
# The producer is deliberately synthetic; this is still not a packaging/build test.
fixture_code = <<~'PY'
  import importlib.util, json, pathlib, sys
  sys.dont_write_bytecode = True
  root = pathlib.Path(sys.argv[1])
  spec = importlib.util.spec_from_file_location("sbom_fixture", root / "scripts/validate-sbom.py")
  validator = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(validator)
  manifest, digest = validator.load_vendor_manifest(root / validator.VENDOR_RELATIVE)
  print(json.dumps(validator.embedded_component(manifest, digest, sys.argv[2])))
PY
embedded_json, fixture_error, fixture_status = Open3.capture3(
    "python3", "-c", fixture_code, ROOT, Digest::SHA256.hexdigest(producer_bytes))
raise "cannot prepare vendor-bound publication fixture: #{fixture_error}" unless fixture_status.success?
embedded = JSON.parse(embedded_json)
components = names.map do |name|
    if name == "jmdns"
        embedded
    elsif name == "slf4j-api"
        {"type" => "library", "group" => "org.slf4j", "name" => name, "version" => "2.0.7", "bom-ref" => name}
    else
        {"type" => "library", "group" => group, "name" => name, "version" => version, "bom-ref" => name}
    end
end
document = {
    "bomFormat" => "CycloneDX", "specVersion" => "1.6", "version" => 1,
    "metadata" => {"component" => {"type" => "library", "group" => group, "name" => "p2pkit",
                                  "version" => version, "bom-ref" => "root"}},
    "components" => components,
    "dependencies" => [
        {"ref" => "root", "dependsOn" => modules},
        {"ref" => "p2p-transport-lan", "dependsOn" => [embedded.fetch("bom-ref")]},
        {"ref" => embedded.fetch("bom-ref"), "dependsOn" => ["slf4j-api"]},
    ],
}
xml_hashes = ->(hashes) {
    next "" if hashes.nil? || hashes.empty?
    "<hashes>" + hashes.map { |hash|
        %(<hash alg="#{CGI.escapeHTML(hash.fetch("alg"))}">#{CGI.escapeHTML(hash.fetch("content"))}</hash>)
    }.join + "</hashes>"
}
xml_component = ->(component) {
    body = %(<component type="library" bom-ref="#{CGI.escapeHTML(component.fetch("bom-ref"))}">)
    %w[group name version purl].each do |key|
        body += "<#{key}>#{CGI.escapeHTML(component.fetch(key))}</#{key}>" if component.key?(key)
    end
    body += xml_hashes.call(component["hashes"])
    body += "<modified>#{component.fetch("modified")}</modified>" if component.key?("modified")
    if component.key?("pedigree")
        pedigree = component.fetch("pedigree")
        body += "<pedigree><ancestors>" + pedigree.fetch("ancestors").map { |c| xml_component.call(c) }.join
        body += "</ancestors><patches>" + pedigree.fetch("patches").map { |patch|
            %(<patch type="#{CGI.escapeHTML(patch.fetch("type"))}"><diff><url>) +
                CGI.escapeHTML(patch.fetch("diff").fetch("url")) + "</url></diff></patch>"
        }.join + "</patches></pedigree>"
    end
    if component.key?("externalReferences")
        body += "<externalReferences>" + component.fetch("externalReferences").map { |reference|
            %(<reference type="#{CGI.escapeHTML(reference.fetch("type"))}"><url>) +
                CGI.escapeHTML(reference.fetch("url")) + "</url>" +
                xml_hashes.call(reference["hashes"]) + "</reference>"
        }.join + "</externalReferences>"
    end
    if component.key?("properties")
        body += "<properties>" + component.fetch("properties").map { |property|
            %(<property name="#{CGI.escapeHTML(property.fetch("name"))}">) +
                CGI.escapeHTML(property.fetch("value")) + "</property>"
        }.join + "</properties>"
    end
    body + "</component>"
}
xml = '<bom xmlns="http://cyclonedx.org/schema/bom/1.6" version="1"><metadata>' +
    xml_component.call(document.fetch("metadata").fetch("component")) + "</metadata><components>" +
    components.map { |component| xml_component.call(component) }.join +
    "</components><dependencies>" + document.fetch("dependencies").map { |entry|
        %(<dependency ref="#{CGI.escapeHTML(entry.fetch("ref"))}">) +
            entry.fetch("dependsOn").map { |ref| %(<dependency ref="#{CGI.escapeHTML(ref)}"/>) }.join +
            "</dependency>"
    }.join + "</dependencies></bom>"
cases = {
    "valid" => nil,
    "generation-failure-with-stale-reports" => nil,
    "missing-xml" => "FATAL: missing XML SBOM",
    "malformed-xml" => "parser error",
    "missing-component" => "FATAL: JSON SBOM content gate failed",
    "disconnected-root" => "FATAL: JSON SBOM content gate failed",
    "stop-failure" => nil,
}
cases.each do |mode, expected_error|
    Dir.mktmpdir("p2pkit-publication-sbom-test-") do |dir|
        FileUtils.mkdir_p(File.join(dir, "scripts"))
        FileUtils.cp(File.join(ROOT, "scripts/check-sbom.sh"), File.join(dir, "scripts/check-sbom.sh"))
        FileUtils.cp(File.join(ROOT, "scripts/validate-sbom.py"), File.join(dir, "scripts/validate-sbom.py"))
        FileUtils.mkdir_p(File.dirname(File.join(dir, vendor_path)))
        FileUtils.cp_r(File.join(ROOT, vendor_path), File.join(dir, vendor_path))
        FileUtils.mkdir_p(File.dirname(File.join(dir, producer_path)))
        File.write(File.join(dir, producer_path), producer_bytes)
        File.write(File.join(dir, "gradle.properties"), "GROUP=#{group}\nVERSION_NAME=#{version}\n")
        data = Marshal.load(Marshal.dump(document))
        data["components"].reject! { |c| c["name"] == "jmdns" } if mode == "missing-component"
        data["dependencies"][0]["dependsOn"].pop if mode == "disconnected-root"
        File.write(File.join(dir, "fixture.json"), JSON.generate(data))
        File.write(File.join(dir, "fixture.xml"), mode == "malformed-xml" ? "<broken" : xml)
        if mode == "generation-failure-with-stale-reports"
            FileUtils.mkdir_p(File.join(dir, "build/reports/cyclonedx"))
            File.write(File.join(dir, JSON_REPORT), JSON.generate(document))
            File.write(File.join(dir, XML_REPORT), xml)
        end
        File.write(File.join(dir, "gradlew"), <<~'SH')
            #!/usr/bin/env bash
            set -euo pipefail
            printf '%s\n' "$*" >> gradle-calls.txt
            if [[ "$*" == "--stop" ]]; then
                [[ "$MODE" != "stop-failure" ]] || exit 17
                exit 0
            fi
            [[ "$MODE" != "generation-failure-with-stale-reports" ]] || exit 23
            mkdir -p build/reports/cyclonedx
            cp fixture.json build/reports/cyclonedx/bom.json
            if [[ "$MODE" != "missing-xml" ]]; then
                cp fixture.xml build/reports/cyclonedx/bom.xml
            fi
        SH
        FileUtils.chmod(0755, File.join(dir, "gradlew"))
        File.write(File.join(dir, "gate.sh"), gate(workflow).fetch("run"))
        out, status = Open3.capture2e(
            {"MODE" => mode}, "bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c",
            "bash --noprofile --norc -e -o pipefail gate.sh\nprintf reached > publication-marker",
            chdir: dir
        )
        valid = mode == "valid"
        raise "#{mode}: wrong gate exit #{status.exitstatus}: #{out}" unless status.success? == valid
        raise "#{mode}: later command crossed failed gate" unless
            File.exist?(File.join(dir, "publication-marker")) == valid
        raise "#{mode}: failure did not reach expected boundary: #{out}" if expected_error && !out.include?(expected_error)
        raise "#{mode}: valid fixture did not reach real validator" if valid && !out.include?("RESULT: PASS")
        calls = File.readlines(File.join(dir, "gradle-calls.txt")).map(&:strip)
        raise "#{mode}: generator/stop calls changed: #{calls.inspect}" unless
            calls == [GRADLE.drop(1).join(" "), "--stop"]
    end
end
puts "RESULT: PASS — publisher SBOM gate (1 current policy, #{mutations.size} rejected mutations, " +
    "#{cases.size} real-validator/fake-Gradle shell cases)"
