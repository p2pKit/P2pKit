#!/usr/bin/env ruby
# Compatibility entrypoint; custom bootstrap policy retired by owner decision.
# Check the active modular producer/consumer invariants, never fabricate old PASS.
require_relative 'check-modular-ci-policy'
ModularCI.check(File.expand_path('..', __dir__))
puts 'PASS: active modular workflow contract'
