#!/usr/bin/env ruby
require_relative "../check-version-input-policy"

ROOT = File.expand_path("../..", __dir__)
CONSUMER = File.read(File.join(ROOT, "scripts/check-published-consumers.sh"))

def reject(name, diagnostic)
    begin
        yield
    rescue VersionInputPolicy::Violation => error
        raise "#{name}: wrong rejection: #{error.message}" unless error.message.include?(diagnostic)
        return
    end
    raise "#{name}: mutation was accepted"
end

def replace_once(source, before, after)
    raise "fixture no longer has one #{before.inspect}" unless source.scan(before).size == 1
    source.sub(before, after)
end

VersionInputPolicy.check_consumer(CONSUMER)
count = 0
%w[jvm multiplatform].each do |plugin|
    %w[2.2.0 9.9.9].each do |version|
        candidate = replace_once(CONSUMER, "kotlin(\"#{plugin}\") version \"$KOTLIN_VERSION\"",
                                 "kotlin(\"#{plugin}\") version \"#{version}\"")
        reject("#{plugin} literal #{version}", "must use their catalog input variables") do
            VersionInputPolicy.check_consumer(candidate)
        end
        count += 1
    end
end
%w[com.android.application com.android.library com.android.kotlin.multiplatform.library].each do |plugin|
    candidate = replace_once(CONSUMER, "id(\"#{plugin}\") version \"$AGP_VERSION\"",
                             "id(\"#{plugin}\") version \"9.9.9\"")
    reject("#{plugin} literal", "must use their catalog input variables") do
        VersionInputPolicy.check_consumer(candidate)
    end
    count += 1
end
declaration = 'kotlin("jvm") version "$KOTLIN_VERSION" apply false'
["", "# #{declaration}", declaration.sub("KOTLIN_VERSION", "AGP_VERSION"),
 "#{declaration}\n    #{declaration}"].each do |replacement|
    reject("missing/commented/wrong-input/duplicate declaration", "must use their catalog input variables") do
        VersionInputPolicy.check_consumer(replace_once(CONSUMER, declaration, replacement))
    end
    count += 1
end
header = 'cat > "$FIXTURE_DIR/build.gradle.kts" <<EOF'
["# #{header}", header.sub("<<EOF", "<<'EOF'"), header.sub("<<EOF", "<<'OTHER'")].each do |replacement|
    reject("non-expanding/missing heredoc", "expected one expanding") do
        VersionInputPolicy.check_consumer(replace_once(CONSUMER, header, replacement))
    end
    count += 1
end
root_block = CONSUMER[/^cat > "\$FIXTURE_DIR\/build\.gradle\.kts" <<EOF\n.*?^EOF$/m]
reject("duplicate root generator", "expected one expanding") do
    VersionInputPolicy.check_consumer(CONSUMER + "\n" + root_block + "\n")
end
count += 1
['kotlin("jvm") version "9.9.9"', 'id("org.jetbrains.kotlin.jvm").version("9.9.9")',
 "kotlin(\"jvm\") version\n    \"9.9.9\""].each do |pin|
    reject("literal elsewhere #{pin.inspect}", "literal plugin version") do
        VersionInputPolicy.check_consumer(CONSUMER + "\n#{pin}\n")
    end
    count += 1
end

# Synthetic future pins are inputs, not copies of the real independent release
# expectation. Reusing the guard after a floor bump must keep rejecting drift.
minimum = "7.2.100.Final"
http = "io.netty:netty-codec-http:#{minimum}=fixture\n"
VersionInputPolicy.check_netty_lock(http, minimum)
%w[7.2.101.Final 7.3.0.Final 8.0.0.Final 7.2.1000.Final].each do |higher|
    VersionInputPolicy.check_netty_lock("io.netty:netty-codec-http:#{higher}=fixture\n", minimum)
end
%w[6.99.999.Final 7.1.999.Final 7.2.99.Final 7.2.9.Final].each do |older|
    %w[netty-codec-http netty-handler].each do |artifact|
        reject("mixed older #{artifact}:#{older}", "below the reviewed floor") do
            VersionInputPolicy.check_netty_lock(http + "io.netty:#{artifact}:#{older}=fixture\n", minimum)
        end
        count += 1
    end
end
%w[7.2.100.Beta1 7.2.100.CR1 7.2.100 7.2.100.Final-SNAPSHOT latest.release 07.2.100.Final].each do |version|
    reject("unsupported version #{version}", "unsupported Netty version") do
        VersionInputPolicy.check_netty_lock(http + "io.netty:netty-codec-http:#{version}=fixture\n", minimum)
    end
    count += 1
end
["io.netty:netty-codec-http:#{minimum}=\n", "io.netty:netty-codec-http:#{minimum}\n",
 "io.netty:netty-codec-http:#{minimum}=a=b\n"].each do |malformed|
    reject("malformed lock", "malformed Netty lock entry") do
        VersionInputPolicy.check_netty_lock(http + malformed, minimum)
    end
    count += 1
end
["", "# #{http}", "other.group:netty-codec-http:#{minimum}=fixture\n"].each do |missing|
    reject("missing active HTTP lock", "must include an active") do
        VersionInputPolicy.check_netty_lock(missing, minimum)
    end
    count += 1
end
reject("unsupported minimum", "unsupported Netty version") do
    VersionInputPolicy.check_netty_lock(http, "7.2.100.Beta1")
end
count += 1
VersionInputPolicy.check_netty_lock("# io.netty:netty-codec-http:1.0.0.Final=obsolete\n" + http, minimum)
VersionInputPolicy.check_netty_lock(http + "other.group:some-module:1.0=fixture\n", minimum)

puts "RESULT: PASS — consumer input and numeric Netty-floor policy; #{count} negative controls"
