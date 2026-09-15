#!/usr/bin/env ruby
# Maintained shell-recipe tripwire, not a general Bash parser or daemon-retirement proof.
module ConsumerGradlePolicy
    class Violation < StandardError; end

    CALLS = [
        '(cd "$ROOT" && run_audit_consumer_gradle consumer-publish "$CONSUMER_RECEIPT_DIR/consumer-publish.json" ' \
            '--no-daemon --console=plain "${publish_tasks[@]}" -Dmaven.repo.local="$REPO_DIR")',
        '(cd "$ROOT" && ./gradlew --no-daemon --console=plain "${publish_tasks[@]}" -Dmaven.repo.local="$REPO_DIR")',
        '(cd "$ROOT" && run_consumer_gradle run_audit_consumer_gradle consumer-build ' \
            '"$CONSUMER_RECEIPT_DIR/consumer-build.json" --no-daemon --console=plain -p "$FIXTURE_DIR" ' \
            '-PconsumerRepo="$CONSUMER_REPOSITORY" ${REMOTE_REPOSITORY_URL:+--refresh-dependencies} "${consumer_tasks[@]}")',
        '(cd "$ROOT" && run_consumer_gradle ./gradlew --no-daemon --console=plain -p "$FIXTURE_DIR" ' \
            '-PconsumerRepo="$CONSUMER_REPOSITORY" ${REMOTE_REPOSITORY_URL:+--refresh-dependencies} "${consumer_tasks[@]}")',
    ].freeze
    # Independent task-selection expectation; do not read it out of the checked script.
    PUBLICATION_SELECTION = [
        'publish_tasks=(publishToMavenLocal)',
        'if [[ "$CONSUMER_PROFILE" == lan-jvm-android ]]; then',
        'publish_tasks=(',
        ':p2p-core:publishJvmPublicationToMavenLocal',
        ':p2p-core:publishAndroidPublicationToMavenLocal',
        ':p2p-transport-lan:publishJvmPublicationToMavenLocal',
        ':p2p-transport-lan:publishAndroidPublicationToMavenLocal',
        ':p2p-core:publishKotlinMultiplatformPublicationToMavenLocal',
        ')',
        'fi',
    ].freeze
    INVOCATION = 'ruby "$ROOT/scripts/check-consumer-gradle-policy.rb" "$CONSUMER_GATE"'.freeze

    def self.require_policy(condition, message)
        raise Violation, message unless condition
    end

    def self.logical_lines(source)
        source.lines.reject { |line| line.lstrip.start_with?("#") }.join
            .gsub(/\\\n[ \t]*/, "").lines.map(&:strip).reject(&:empty?)
    end

    def self.check(source)
        lines = logical_lines(source)
        calls = lines.select { |line| line.start_with?('(cd "$ROOT" &&') }
        require_policy(calls == CALLS,
                       "consumer publication/build must retain all four exact non-daemon ordinary/executor calls")
        require_policy(lines.each_cons(PUBLICATION_SELECTION.length).count { |block| block == PUBLICATION_SELECTION } == 1 &&
                       lines.grep(/\Apublish_tasks(?:\+)?=/) == ['publish_tasks=(publishToMavenLocal)', 'publish_tasks=('],
                       "consumer publication must keep complete default and the five fixed explicit LAN-profile tasks")
    end

    def self.check_entrypoint(source)
        require_policy(source.lines.map(&:chomp).count(INVOCATION) == 1,
                       "Kotlin policy must invoke the consumer Gradle-call guard exactly once without ignoring failure")
    end
end

if $PROGRAM_NAME == __FILE__
    begin
        raise ArgumentError, "usage: check-consumer-gradle-policy.rb CONSUMER_SCRIPT" unless ARGV.size == 1
        ConsumerGradlePolicy.check(File.read(ARGV.first))
    rescue ConsumerGradlePolicy::Violation, ArgumentError, SystemCallError => error
        abort "FATAL: #{error.message}"
    end
    puts "RESULT: PASS — maintained consumer non-daemon/task-selection source policy only"
end
