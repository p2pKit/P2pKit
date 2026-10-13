#!/usr/bin/env ruby
# Documentation uses the catalog as input, not as a dependency approval oracle.
# Keep the independent toolchain/wrapper/security tripwires in their existing gates.
require "shellwords"
require "yaml"

ROOT = File.expand_path("../..", __dir__)
CATALOG = "gradle/libs.versions.toml"
LOCAL = "docs/testing/local.md"
CI = ".github/workflows/ci.yml"
ENTRY_POINTS = {
    "CONTRIBUTING.md" => ["## Development setup", "docs/testing/local.md#android-sdk-setup"],
    "docs/validation/test-catalog.md" => ["### 1.1 Required tools and accounts", "../testing/local.md#android-sdk-setup"],
}.freeze

class SetupPolicyError < StandardError; end

def require_setup(condition, message)
    raise SetupPolicyError, message unless condition
end

def section(text, heading)
    lines = text.lines
    starts = lines.each_index.select { |i| lines[i].strip == heading }
    require_setup(starts.size == 1, "missing/duplicate #{heading}")
    depth = heading[/\A#+/].size
    fenced = false
    lines.drop(starts.first + 1).take_while do |line|
        if line.start_with?("```")
            fenced = !fenced
            true
        else
            fenced || !line.match?(/\A\#{1,#{depth}} /)
        end
    end.join
end

def check_setup(files)
    catalog = files.fetch(CATALOG)
    require_setup(catalog.scan(/^\[versions\]\s*$/).size == 1, "missing/duplicate catalog versions table")
    versions = catalog.split(/^\[versions\]\s*$/, 2).last.split(/^\[/, 2).first
    values = %w[android-compileSdk android-sample-compileSdk android-minSdk].to_h do |key|
        entries = versions.lines.grep(/^\s*#{Regexp.escape(key)}\s*=/)
        match = entries.first&.match(/^\s*#{Regexp.escape(key)}\s*=\s*"([1-9][0-9]*)"\s*(?:#.*)?$/)
        require_setup(entries.size == 1 && match, "missing/invalid catalog #{key}")
        [key, match[1]]
    end
    setup = section(files.fetch(LOCAL), "## Android SDK setup")
    packages = %w[android-compileSdk android-sample-compileSdk].map do |key|
        rows = setup.lines.grep(/^\|/).map { |line| line.strip.split("|").drop(1).map(&:strip) }
            .select { |row| row[1] == "`#{key}`" }
        require_setup(rows.size == 1, "missing/duplicate setup row #{key}")
        row = rows.first
        require_setup(row.size == 4 && row[2] == "Android SDK Platform #{values.fetch(key)}",
                      "setup platform does not match #{key}")
        package = row[3][/\A`(platforms;android-#{values.fetch(key)}(?:\.0)?)`\z/, 1]
        require_setup(package, "SDK Manager package does not match #{key}")
        package
    end.uniq
    require_setup(setup.include?("**Android API #{values.fetch('android-minSdk')}+** (`android-minSdk`)"),
                  "runtime minimum does not match android-minSdk")
    blocks = setup.scan(/^```bash\s*\n(.*?)^```\s*$/m).flatten
    require_setup(blocks.size == 1, "expected one Android installation block")
    commands = blocks.first.gsub(/\\\n\s*/, " ").lines.map { |line| Shellwords.split(line.strip) }
    manager = "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
    installers = commands.select { |cmd| cmd.first == manager }
    require_setup(installers == [[manager, "--sdk_root=$ANDROID_HOME", "--licenses"],
                                [manager, "--sdk_root=$ANDROID_HOME", *packages, "platform-tools"]],
                  "installation commands must accept licenses and install both catalog platforms")
    # Both fixture publication and platform verification run Gradle on separate
    # runners. Validate each job's actual setup, never borrow another job's SDK.
    jobs = YAML.safe_load(files.fetch(CI), aliases: true).fetch("jobs")
    conditions = {"repository-checks" => nil}
    %w[ios-checks platform-checks artifact-checks].each do |name|
        conditions[name] = "needs.repository-checks.outputs.full == 'true'"
    end
    conditions.each do |name, condition|
        steps = jobs.fetch(name).fetch("steps")
        installers = steps.select do |step|
            step.fetch("run", "").lines.any? do |line|
                line.include?("/cmdline-tools/latest/bin/sdkmanager") &&
                    !line.lstrip.start_with?("#") && Shellwords.split(line.strip).first == manager
            end
        end
        require_setup(installers.size == 1 && installers.first["if"] == condition &&
                      !installers.first.key?("continue-on-error"),
                      "#{name} must have one blocking CI installer")
        commands = installers.first.fetch("run").lines.map { |line| Shellwords.split(line.strip) }
        require_setup(commands == [[manager, *packages]],
                      "documented platform packages differ from the CI installer in #{name}")
    end
    ENTRY_POINTS.each do |path, (heading, target)|
        text = section(files.fetch(path), heading)
        require_setup(text.include?("](#{target})"), "#{path} must link to canonical Android setup")
        require_setup(!text.match?(/Android SDK Platform\s+[0-9]/), "#{path} duplicates the SDK prerequisite pins")
    end
end

files = ([CATALOG, LOCAL, CI] + ENTRY_POINTS.keys).to_h { |path| [path, File.read(File.join(ROOT, path))] }
check_setup(files)

def reject_mutation(files, name, expected)
    candidate = files.transform_values(&:dup)
    yield candidate
    begin
        check_setup(candidate)
    rescue SetupPolicyError => error
        raise "#{name} rejected for wrong reason: #{error.message}" unless error.message.include?(expected)
        return
    end
    raise "#{name} mutation was accepted"
end

count = 0
%w[android-compileSdk android-sample-compileSdk].each do |key|
    reject_mutation(files, "#{key} catalog drift", "setup platform does not match #{key}") do |f|
        f[CATALOG].sub!(/^(#{key} = )"[0-9]+"/, '\1"99"')
    end
    reject_mutation(files, "#{key} missing row", "missing/duplicate setup row #{key}") do |f|
        f[LOCAL] = f[LOCAL].lines.reject { |line| line.start_with?("|") && line.include?("`#{key}`") }.join
    end
    reject_mutation(files, "#{key} malformed catalog", "missing/invalid catalog #{key}") do |f|
        f[CATALOG].sub!(/^(#{key} = )"[0-9]+"/, '\1"invalid"')
    end
    count += 3
end
ENTRY_POINTS.each_key do |path|
    reject_mutation(files, "#{path} missing link", "#{path} must link") do |f|
        f[path].sub!(ENTRY_POINTS.fetch(path).last, "wrong.md")
    end
    reject_mutation(files, "#{path} stale prerequisites", "#{path} duplicates") do |f|
        f[path].sub!(ENTRY_POINTS.fetch(path).first, ENTRY_POINTS.fetch(path).first + "\nAndroid SDK Platform 1 only.\n")
    end
    count += 2
end
reject_mutation(files, "minimum drift", "runtime minimum does not match") do |f|
    f[CATALOG].sub!(/^(android-minSdk = )"[0-9]+"/, '\1"99"')
end
reject_mutation(files, "missing sample installation", "installation commands") do |f|
    f[LOCAL].sub!(/"platforms;android-[0-9]+(?:\.0)?" "platform-tools"/, '"platform-tools"')
end
reject_mutation(files, "commented installation", "installation commands") do |f|
    f[LOCAL].sub!(/^"\$ANDROID_HOME\/cmdline-tools\/latest\/bin\/sdkmanager"/, '# disabled sdkmanager')
end
reject_mutation(files, "wrong package", "SDK Manager package does not match") do |f|
    f[LOCAL].sub!(/`platforms;android-[0-9]+(?:\.0)?`/, '`platforms;invalid`')
end
reject_mutation(files, "CI misses sample package", "differ from the CI installer") do |f|
    f[CI].sub!(/ 'platforms;android-[0-9]+\.0'/, "")
end
count += 5

%w[repository-checks ios-checks platform-checks artifact-checks].each do |name|
    %w[missing commented ignored conditional].each do |mutation|
        reject_mutation(files, "#{name} #{mutation} installer", "blocking CI installer") do |f|
            workflow = YAML.safe_load(f[CI], aliases: true)
            steps = workflow.fetch("jobs").fetch(name).fetch("steps")
            installer = steps.find { |step| step["name"] == "Install Android SDK platforms" }
            case mutation
            when "missing" then steps.delete(installer)
            when "commented" then installer["run"] = "# " + installer.fetch("run")
            when "ignored" then installer["continue-on-error"] = true
            when "conditional" then installer["if"] = false
            end
            f[CI] = YAML.dump(workflow)
        end
        count += 1
    end
    [" || true", " --uninstall"].each do |suffix|
        reject_mutation(files, "#{name} unsafe installer arguments", "differ from the CI installer") do |f|
            workflow = YAML.safe_load(f[CI], aliases: true)
            installer = workflow.fetch("jobs").fetch(name).fetch("steps").find do |step|
                step["name"] == "Install Android SDK platforms"
            end
            installer["run"] = installer.fetch("run").strip + suffix + "\n"
            f[CI] = YAML.dump(workflow)
        end
        count += 1
    end
end

unrelated = files.transform_values(&:dup)
workflow = YAML.safe_load(unrelated[CI], aliases: true)
workflow.fetch("jobs").fetch("complete-gate").fetch("steps") << {"run" => "echo \"unrelated\nmultiline value\"\n"}
unrelated[CI] = YAML.dump(workflow)
check_setup(unrelated)

# A coherent future input change passes this consistency test (but still requires
# independent dependency/toolchain approval). Do not pin today's SDKs in this gate.
future = files.transform_values(&:dup)
%w[android-compileSdk android-sample-compileSdk].zip(%w[98 99]).each do |key, version|
    old = future[CATALOG].match(/^#{key} = "([0-9]+)"/)[1]
    future[CATALOG].sub!(/^(#{key} = )"[0-9]+"/, "\\1\"#{version}\"")
    future[LOCAL].gsub!("Platform #{old}", "Platform #{version}")
    [LOCAL, CI].each { |path| future[path].gsub!("platforms;android-#{old}", "platforms;android-#{version}") }
end
check_setup(future)
puts "RESULT: PASS — Android setup follows both catalog SDKs, CI packages and entry links; #{count} negative controls"
