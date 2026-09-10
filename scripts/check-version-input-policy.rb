#!/usr/bin/env ruby
# Input consistency, not dependency approval: reviewed pin expectations stay
# independent in check-kotlin-toolchain-policy-test.sh/release-workflow-test.sh.
module VersionInputPolicy
    class Violation < StandardError; end

    def self.require_policy(condition, message)
        raise Violation, message unless condition
    end

    def self.check_consumer(source)
        # This is the maintained shell heredoc recipe, not an arbitrary Bash or
        # Kotlin parser. A new generator shape must be reviewed with this guard.
        blocks = source.scan(/^cat > "\$FIXTURE_DIR\/build\.gradle\.kts" <<EOF\n(.*?)^EOF$/m).flatten
        require_policy(blocks.size == 1, "expected one expanding root consumer build heredoc")
        declarations = blocks.first.lines.map(&:strip).reject(&:empty?)
        expected = [
            'plugins {',
            'kotlin("jvm") version "$KOTLIN_VERSION" apply false',
            'kotlin("multiplatform") version "$KOTLIN_VERSION" apply false',
            'id("com.android.application") version "$AGP_VERSION" apply false',
            'id("com.android.kotlin.multiplatform.library") version "$AGP_VERSION" apply false',
            '}',
        ]
        require_policy(declarations == expected, "consumer plugin versions must use their catalog input variables")
        # Also reject numeric pins added elsewhere, including method-call and
        # multiline spelling. Do not keep a finite list of obsolete versions.
        require_policy(!source.match?(/\bversion\s*(?:\(\s*)?"[0-9]/),
                       "consumer contains a literal plugin version instead of a catalog input")
    end

    def self.stable_netty_version(value)
        match = value.match(/\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.Final\z/)
        require_policy(match, "unsupported Netty version #{value.inspect}; review the stable-version policy")
        match.captures.map(&:to_i)
    end

    def self.check_netty_lock(source, minimum)
        floor = stable_netty_version(minimum)
        found_http = false
        source.each_line.with_index(1) do |line, number|
            entry = line.strip
            next if entry.empty? || entry.start_with?("#") || !entry.start_with?("io.netty:")

            match = entry.match(/\Aio\.netty:([^:=\s]+):([^:=\s]+)=([^=\s]+)\z/)
            require_policy(match, "malformed Netty lock entry at line #{number}")
            version = stable_netty_version(match[2])
            require_policy((version <=> floor) >= 0,
                           "Netty #{match[1]} at line #{number} is below the reviewed floor #{minimum}")
            found_http ||= match[1] == "netty-codec-http"
        end
        require_policy(found_http, "Netty lock must include an active netty-codec-http entry")
    end
end

if $PROGRAM_NAME == __FILE__
    begin
        case ARGV.shift
        when "consumer"
            raise ArgumentError, "consumer requires a script path" unless ARGV.size == 1
            VersionInputPolicy.check_consumer(File.read(ARGV.fetch(0)))
        when "netty"
            raise ArgumentError, "netty requires a lock path and independent minimum" unless ARGV.size == 2
            VersionInputPolicy.check_netty_lock(File.read(ARGV.fetch(0)), ARGV.fetch(1))
        else
            raise ArgumentError, "usage: check-version-input-policy.rb consumer SCRIPT | netty LOCK MINIMUM"
        end
    rescue VersionInputPolicy::Violation, ArgumentError, SystemCallError => error
        warn "FATAL: #{error.message}"
        exit 1
    end
    puts "RESULT: PASS — version inputs satisfy the persistent source/lock policy"
end
