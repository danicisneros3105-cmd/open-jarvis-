# frozen_string_literal: true

require "open3"

RSpec.describe "Web workspace tree reveal" do
  it "expands parent folders and highlights a file opened from a nested path" do
    script = File.expand_path("../../support/workspace_tree_reveal_test.js", __dir__)
    output, status = Open3.capture2e("node", script)
    expect(status.success?).to be(true), output
  end
end
