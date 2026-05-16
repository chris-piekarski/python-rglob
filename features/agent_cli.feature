Feature: New agent-friendly CLI commands
  As a developer or coding agent
  I want to use the new rglob CLI commands (grep, count, describe, schema, capabilities)
  So that I can perform structured searches and introspect the tool reliably

  Background:
    Given I create a root directory
    And I create 3 subdirectories in each directory
    And I create 2 .py files in each directory
    And I create 1 .txt file in each directory

  Scenario: Grep for content and receive structured JSON
    When I run "rglob grep . --json"
    Then the command succeeds
    And the JSON output should contain a "results" list
    And the JSON output should contain "truncated" and "errors" fields

  Scenario: Count lines with filters using the new count command
    When I run "rglob count '*.py' --no-empty --no-comments --json"
    Then the command succeeds
    And the JSON output should contain "files", "lines", and "bytes"

  Scenario: Describe a subcommand
    When I run "rglob describe find"
    Then the command succeeds
    And the output should be valid JSON
    And the JSON should contain the key "arguments"

  Scenario: Retrieve JSON Schema for a subcommand
    When I run "rglob schema grep"
    Then the command succeeds
    And the output should be valid JSON Schema Draft 2020-12
    And the JSON should contain an "$id" field

  Scenario: Capabilities reports installed features and versions
    When I run "rglob capabilities --json"
    Then the command succeeds
    And the JSON should contain "agent_api_version"
    And the JSON should contain "extras"
    And the JSON should contain "predicates"

  Scenario: Grep respects --limit and reports truncation
    When I run "rglob grep . --limit 1 --json"
    Then the command succeeds
    And the JSON output should indicate that results were truncated
