# frozen_string_literal: true

require "spec_helper"
require "tmpdir"
require "fileutils"
require "json"
require "time"

# Sessions written while the serializer still fell back to the updated_at it
# captured at restore time sit on disk months behind their own conversation.
# Reading them back must report the newest message instead: the sidebar sorts
# by updated_at, so a stale stamp hides an active session at the bottom of the
# list and ranks it for deletion by cleanup.
RSpec.describe Clacky::SessionManager, "#load_session_file updated_at heal" do
  let(:temp_dir) { Dir.mktmpdir("clacky_sm_updated_at_spec") }
  subject(:manager) { described_class.new(sessions_dir: temp_dir) }

  after { FileUtils.rm_rf(temp_dir) if Dir.exist?(temp_dir) }

  def write_session(id:, created_at:, updated_at:, messages: [])
    filename = manager.send(:generate_filename, id, created_at)
    File.write(File.join(temp_dir, filename), JSON.generate(
      session_id: id,
      name:       id,
      created_at: created_at,
      updated_at: updated_at,
      messages:   messages
    ))
  end

  def loaded(id)
    manager.load(id)
  end

  it "derives updated_at from the newest message when the stored stamp is stale" do
    last_message = Time.parse("2026-09-14 20:56:06 +0800")
    write_session(
      id:         "aaaa0001",
      created_at: "2026-06-09T09:38:18+08:00",
      updated_at: "2026-06-09T10:32:46+08:00",
      messages:   [
        { role: "assistant", created_at: Time.parse("2026-06-09 10:30:00 +0800").to_f },
        { role: "assistant", created_at: last_message.to_f },
        { role: "tool", created_at: nil },
        { role: "user", created_at: "not-a-timestamp" }
      ]
    )

    # The heal stamps the zone of whichever machine runs it, exactly like the
    # save path's Time.now.iso8601, so compare the instant, not the offset text.
    expect(Time.parse(loaded("aaaa0001")[:updated_at])).to eq(last_message)
  end

  it "sorts a healed session by its real last activity" do
    write_session(id: "bbbb0002", created_at: "2026-09-01T09:00:00+08:00",
                  updated_at: "2026-09-01T09:00:00+08:00")
    write_session(id: "cccc0003", created_at: "2026-06-09T09:38:18+08:00",
                  updated_at: "2026-06-09T10:32:46+08:00",
                  messages: [{ role: "assistant", created_at: Time.parse("2026-09-14 20:56:06 +0800").to_f }])

    expect(manager.all_sessions.map { |s| s[:session_id] }).to eq(%w[cccc0003 bbbb0002])
  end

  it "leaves a session with no message timestamps untouched" do
    write_session(id: "dddd0004", created_at: "2026-06-09T09:38:18+08:00",
                  updated_at: "2026-06-09T10:32:46+08:00",
                  messages: [{ role: "assistant", content: "hi" }])

    expect(loaded("dddd0004")[:updated_at]).to eq("2026-06-09T10:32:46+08:00")
  end

  it "never moves a fresh updated_at backwards" do
    write_session(id: "eeee0005", created_at: "2026-09-14T20:00:00+08:00",
                  updated_at: "2026-09-15T08:00:00+08:00",
                  messages: [{ role: "assistant", created_at: Time.parse("2026-09-14 20:56:06 +0800").to_f }])

    expect(loaded("eeee0005")[:updated_at]).to eq("2026-09-15T08:00:00+08:00")
  end

  it "tolerates sub-second drift instead of rewriting a stamp that is already right" do
    write_session(id: "55550012", created_at: "2026-08-09T14:40:00+08:00",
                  updated_at: "2026-08-09T14:40:00.500+08:00",
                  messages: [{ role: "assistant", created_at: Time.parse("2026-08-09 14:40:01.100 +0800").to_f }])

    expect(loaded("55550012")[:updated_at]).to eq("2026-08-09T14:40:00.500+08:00")
  end

  it "still heals once the drift exceeds the tolerance" do
    write_session(id: "66660013", created_at: "2026-08-09T14:40:00+08:00",
                  updated_at: "2026-08-09T14:40:00+08:00",
                  messages: [{ role: "assistant", created_at: Time.parse("2026-08-09 14:40:02.500 +0800").to_f }])

    expect(Time.parse(loaded("66660013")[:updated_at])).to eq(Time.parse("2026-08-09 14:40:02 +0800"))
  end

  it "does not let cleanup_by_count evict a stale-stamped session that was active recently" do
    write_session(id: "ffff0006", created_at: "2026-09-15T09:00:00+08:00",
                  updated_at: "2026-09-15T09:00:00+08:00")
    write_session(id: "99990007", created_at: "2026-06-09T09:38:18+08:00",
                  updated_at: "2026-06-09T10:32:46+08:00",
                  messages: [{ role: "assistant", created_at: Time.parse("2026-09-15 10:00:00 +0800").to_f }])

    expect(manager.cleanup_by_count(keep: 1, grouped_keep: 1)).to eq(0)
    expect(loaded("99990007")).not_to be_nil
  end

  it "does not hard-delete a stale-stamped session that was active recently" do
    write_session(id: "22220010", created_at: "2026-01-01T09:00:00+08:00",
                  updated_at: "2026-01-01T09:00:00+08:00")
    recent_activity = (Time.now - (3 * 24 * 60 * 60)).to_f
    write_session(id: "33330011", created_at: "2026-06-09T09:38:18+08:00",
                  updated_at: "2026-06-09T10:32:46+08:00",
                  messages: [{ role: "assistant", created_at: recent_activity }])

    expect(manager.cleanup(days: 90)).to eq(1)
    expect(loaded("22220010")).to be_nil
    expect(loaded("33330011")).not_to be_nil
  end
end
