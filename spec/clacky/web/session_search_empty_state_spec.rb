# frozen_string_literal: true

require "open3"

RSpec.describe "Web session search empty state" do
  it "renders the no-match placeholder only once" do
    script = File.expand_path("../../support/session_search_empty_state_test.js", __dir__)
    output, status = Open3.capture2e("node", script)
    expect(status.success?).to be(true), output
  end
end
