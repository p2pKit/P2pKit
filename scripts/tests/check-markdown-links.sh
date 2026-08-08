#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

ruby - "$ROOT" <<'RUBY'
require "open3"
require "pathname"
require "uri"

root = Pathname.new(ARGV.fetch(0)).realpath
output, status = Open3.capture2("git", "-C", root.to_s, "ls-files", "-z", "--", "*.md")
abort("FATAL: could not enumerate tracked Markdown files") unless status.success?

files = output.split("\0").reject(&:empty?).reject { |path| path.start_with?("docs/archive/") }
errors = []
checked = 0

files.each do |relative|
  file = root.join(relative)
  fenced = false
  file.each_line.with_index(1) do |line, line_number|
    if line.lstrip.start_with?("```", "~~~")
      fenced = !fenced
      next
    end
    next if fenced

    line.scan(/!?\[[^\]]*\]\(([^)]+)\)/).each do |match|
      raw = match.fetch(0).strip
      target = if raw.start_with?("<") && raw.include?(">")
        raw[1...raw.index(">")]
      else
        raw.split(/\s+/, 2).first
      end
      next if target.nil? || target.empty? || target.start_with?("#")
      next if target.match?(/\A(?:https?|mailto|app):/i)

      path_text = target.split("#", 2).first
      next if path_text.empty?
      begin
        path_text = URI::DEFAULT_PARSER.unescape(path_text)
      rescue ArgumentError
        errors << "#{relative}:#{line_number}: invalid escaped link #{target}"
        next
      end
      resolved = if path_text.start_with?("/")
        root.join(path_text.delete_prefix("/"))
      else
        file.dirname.join(path_text).cleanpath
      end
      checked += 1
      errors << "#{relative}:#{line_number}: missing link target #{target}" unless resolved.exist?
    end
  end
end

unless errors.empty?
  warn errors.join("\n")
  abort("FATAL: #{errors.length} relative Markdown links are broken")
end

puts "RESULT: PASS — #{checked} relative links across #{files.length} active Markdown files resolve"
RUBY
