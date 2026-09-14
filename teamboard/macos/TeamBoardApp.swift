import AppKit
import Foundation
import SwiftUI

struct AgentRecord: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let role: String
    let model: String
    let status: String
    let task: String
    let runtimeID: String?
    let updatedAt: String
    let summary: String?

    enum CodingKeys: String, CodingKey {
        case id, name, role, model, status, task, summary
        case runtimeID = "runtime_id"
        case updatedAt = "updated_at"
    }
}

struct EventRecord: Codable, Identifiable, Hashable {
    let id: String
    let time: String
    let kind: String
    let from: String
    let to: String
    let text: String
}

struct RunRecord: Codable, Identifiable, Hashable {
    let schema: Int
    let id: String
    let title: String
    let project: String
    let createdAt: String
    let updatedAt: String
    let status: String
    let agents: [AgentRecord]
    let events: [EventRecord]
    let eventsDropped: Int?
    let usageNote: String
    var sourceURL: URL?

    enum CodingKeys: String, CodingKey {
        case schema, id, title, project, status, agents, events
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case eventsDropped = "events_dropped"
        case usageNote = "usage_note"
    }
}

enum DateTools {
    private static let fractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()
    private static let standard = ISO8601DateFormatter()

    static func parse(_ value: String) -> Date? {
        fractional.date(from: value) ?? standard.date(from: value)
    }

    static func age(_ value: String, now: Date = Date()) -> String {
        guard let date = parse(value) else { return "unknown time" }
        let interval = now.timeIntervalSince(date)
        if interval < -5 { return "clock mismatch" }
        let seconds = max(0, Int(interval))
        if seconds < 5 { return "just now" }
        if seconds < 60 { return "\(seconds)s ago" }
        if seconds < 3_600 { return "\(seconds / 60)m ago" }
        if seconds < 86_400 { return "\(seconds / 3_600)h ago" }
        return "\(seconds / 86_400)d ago"
    }

    static func freshness(_ value: String, now: Date = Date()) -> Freshness {
        guard let date = parse(value) else { return .unknown }
        let seconds = now.timeIntervalSince(date)
        if seconds < -5 { return .unknown }
        if seconds <= 300 { return .recorded }
        return .noRecent
    }
}

enum Freshness: String {
    case recorded = "Recorded update"
    case noRecent = "No recent update"
    case unknown = "Unknown freshness"

    var color: Color {
        switch self {
        case .recorded, .noRecent, .unknown: return .secondary
        }
    }
}

@MainActor
final class TeamBoardStore: ObservableObject {
    @Published private(set) var runs: [RunRecord] = []
    @Published private(set) var unreadableCount = 0
    @Published private(set) var lastScan = Date()
    @Published var selectedRunID: String?

    let runsURL = URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)
        .appendingPathComponent(".local/share/agent-toolkit/teamboard/runs", isDirectory: true)

    init() { refresh() }

    func refresh() {
        let manager = FileManager.default
        let keys: [URLResourceKey] = [.isRegularFileKey]
        let candidates = (try? manager.contentsOfDirectory(
            at: runsURL,
            includingPropertiesForKeys: keys,
            options: [.skipsHiddenFiles]
        )) ?? []

        var loaded: [RunRecord] = []
        var failures = 0
        let decoder = JSONDecoder()
        for directory in candidates {
            let stateURL = directory.appendingPathComponent("state.json")
            guard manager.fileExists(atPath: stateURL.path) else { continue }
            do {
                let data = try Data(contentsOf: stateURL, options: [.mappedIfSafe])
                var run = try decoder.decode(RunRecord.self, from: data)
                guard run.schema == 1 else { failures += 1; continue }
                run.sourceURL = stateURL
                loaded.append(run)
            } catch {
                failures += 1
            }
        }
        runs = loaded.sorted { (DateTools.parse($0.updatedAt) ?? .distantPast) > (DateTools.parse($1.updatedAt) ?? .distantPast) }
        unreadableCount = failures
        lastScan = Date()
        if let selectedRunID, !runs.contains(where: { $0.id == selectedRunID }) {
            self.selectedRunID = runs.first?.id
        } else if selectedRunID == nil {
            selectedRunID = runs.first?.id
        }
    }
}

@main
struct TeamBoardApp: App {
    @StateObject private var store = TeamBoardStore()
    @State private var sidebarProject: String?
    @State private var searchText = ""
    @State private var eventFilter = "All"
    private let timer = Timer.publish(every: 2, on: .main, in: .common).autoconnect()

    var body: some Scene {
        WindowGroup("Agent Team Board") {
            NavigationSplitView {
                SidebarView(store: store, project: $sidebarProject, now: store.lastScan)
                    .navigationSplitViewColumnWidth(min: 220, ideal: 260, max: 340)
            } detail: {
                if let run = selectedRun {
                    RunDetailView(run: run, now: store.lastScan, searchText: $searchText, eventFilter: $eventFilter, refresh: store.refresh)
                        .id(run.id)
                } else {
                    EmptyBoardView(unreadableCount: store.unreadableCount, refresh: store.refresh)
                }
            }
            .preferredColorScheme(.dark)
            .frame(minWidth: 980, minHeight: 650)
            .onReceive(timer) { _ in store.refresh() }
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 1200, height: 820)
        .commands {
            CommandGroup(after: .toolbar) {
                Button("Refresh") { store.refresh() }
                    .keyboardShortcut("r")
            }
        }
    }

    private var selectedRun: RunRecord? {
        store.runs.first { $0.id == store.selectedRunID }
    }
}

struct SidebarView: View {
    @ObservedObject var store: TeamBoardStore
    @Binding var project: String?
    let now: Date

    private var projects: [String] {
        Array(Set(store.runs.map { $0.project })).sorted { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }
    }
    private var visibleRuns: [RunRecord] {
        guard let project else { return store.runs }
        return store.runs.filter { $0.project == project }
    }

    var body: some View {
        List(selection: $store.selectedRunID) {
            Section("Projects") {
                Label("All runs", systemImage: "square.stack.3d.up")
                    .contentShape(Rectangle())
                    .onTapGesture { project = nil; store.selectedRunID = store.runs.first?.id }
                ForEach(projects, id: \.self) { item in
                    Label(URL(fileURLWithPath: item).lastPathComponent, systemImage: "folder")
                        .contentShape(Rectangle())
                        .onTapGesture {
                            project = item
                            store.selectedRunID = store.runs.first(where: { $0.project == item })?.id
                        }
                }
            }
            Section(project == nil ? "Runs" : "Project runs") {
                ForEach(visibleRuns) { run in
                    VStack(alignment: .leading, spacing: 5) {
                        HStack(spacing: 7) {
                            Circle().fill(statusColor(run.status)).frame(width: 7, height: 7)
                            Text(run.title).fontWeight(.medium).lineLimit(2)
                        }
                        Text("Reported \(run.status) · \(DateTools.age(run.updatedAt, now: now))")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                    .tag(run.id)
                }
            }
        }
        .listStyle(.sidebar)
        .safeAreaInset(edge: .bottom) {
            HStack(spacing: 7) {
                Image(systemName: "record.circle")
                Text("Recorded activity · refreshes every 2s")
            }
            .font(.caption2).foregroundStyle(.secondary)
            .padding(12).frame(maxWidth: .infinity, alignment: .leading)
            .background(.ultraThinMaterial)
        }
    }
}

struct RunDetailView: View {
    let run: RunRecord
    let now: Date
    @Binding var searchText: String
    @Binding var eventFilter: String
    let refresh: () -> Void

    private var filteredEvents: [EventRecord] {
        run.events.filter { event in
            let kindMatches = eventFilter == "All" || (eventFilter == "Messages" && event.kind == "message") || (eventFilter == "Status" && ["status", "run_started", "run_finished"].contains(event.kind)) || (eventFilter == "Notes" && ["note", "agent_registered"].contains(event.kind))
            let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
            let textMatches = query.isEmpty || [event.text, event.from, event.to, event.kind].joined(separator: " ").localizedCaseInsensitiveContains(query)
            return kindMatches && textMatches
        }
        .sorted { (DateTools.parse($0.time) ?? .distantPast) > (DateTools.parse($1.time) ?? .distantPast) }
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    agentsSection
                    timelineSection
                    disclosure
                }
                .padding(24)
            }
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .toolbar {
            ToolbarItemGroup {
                Button { copyProject() } label: { Label("Copy project path", systemImage: "doc.on.doc") }
                    .help("Copy project path")
                Button { revealJSON() } label: { Label("Reveal state JSON", systemImage: "doc.text.magnifyingglass") }
                    .help("Reveal selected state.json in Finder")
                Button(action: refresh) { Label("Refresh", systemImage: "arrow.clockwise") }
                    .help("Refresh now")
            }
        }
    }

    private var header: some View {
        HStack(alignment: .top, spacing: 18) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 10) {
                    Text(run.title).font(.system(size: 27, weight: .semibold, design: .rounded))
                    StatusPill(text: "Reported \(run.status)", color: statusColor(run.status))
                }
                Text(run.project).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
                HStack(spacing: 8) {
                    let freshness = DateTools.freshness(run.updatedAt, now: now)
                    Circle().fill(freshness.color).frame(width: 7, height: 7)
                    Text("Last recorded update \(DateTools.age(run.updatedAt, now: now)) · \(freshness.rawValue)")
                    Text("Status is last reported, not a liveness check.").foregroundStyle(.tertiary)
                }
                .font(.caption)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 6) {
                Text("\(run.agents.count) agent\(run.agents.count == 1 ? "" : "s")")
                    .font(.headline)
                Text("Started \(DateTools.age(run.createdAt, now: now))").font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(24)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.38))
    }

    private var agentsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionTitle(title: "Agents", subtitle: "Tasks and latest reported state")
            if run.agents.isEmpty {
                Text("No agents have been recorded for this run.").foregroundStyle(.secondary).padding(.vertical, 12)
            } else {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 260), spacing: 12)], spacing: 12) {
                    ForEach(run.agents) { agent in AgentCard(agent: agent, now: now) }
                }
            }
        }
    }

    private var timelineSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .bottom) {
                SectionTitle(title: "Activity", subtitle: "Messages, handoffs, notes, and state changes")
                Spacer()
                Picker("Filter", selection: $eventFilter) {
                    ForEach(["All", "Messages", "Status", "Notes"], id: \.self, content: Text.init)
                }
                .pickerStyle(.segmented).frame(width: 330)
            }
            TextField("Search activity", text: $searchText)
                .textFieldStyle(.roundedBorder)
            if let dropped = run.eventsDropped, dropped > 0 {
                Label("\(dropped) older event\(dropped == 1 ? " was" : "s were") trimmed from this run record.", systemImage: "clock.arrow.circlepath")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if filteredEvents.isEmpty {
                VStack(spacing: 9) {
                    Image(systemName: searchText.isEmpty ? "clock" : "magnifyingglass")
                        .font(.system(size: 28)).foregroundStyle(.secondary)
                    Text(searchText.isEmpty ? "No recorded activity" : "No matches")
                        .font(.headline)
                    Text(searchText.isEmpty ? "Events will appear after the workflow recorder writes them." : "Try a different search or filter.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity).padding(.vertical, 30)
            } else {
                LazyVStack(spacing: 0) {
                    ForEach(Array(filteredEvents.enumerated()), id: \.element.id) { index, event in
                        EventRow(event: event, showLine: index < filteredEvents.count - 1, now: now)
                    }
                }
            }
        }
    }

    private var disclosure: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Recorded activity · refreshes every 2s · native Codex is execution source", systemImage: "info.circle")
                .font(.callout).fontWeight(.medium)
            Text("This board records workflow summaries, not every internal message or private chain of thought. It is a read-only viewer and cannot launch, stop, or steer agents. Control agents in Codex.")
                .font(.caption).foregroundStyle(.secondary)
            if !run.usageNote.isEmpty {
                Text(run.usageNote).font(.caption).foregroundStyle(.tertiary)
            }
        }
        .padding(14).background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private func copyProject() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(run.project, forType: .string)
    }
    private func revealJSON() {
        guard let url = run.sourceURL else { return }
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }
}

struct AgentCard: View {
    let agent: AgentRecord
    let now: Date
    var body: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(agent.name).font(.headline)
                    Text(agent.role).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                StatusPill(text: agent.status.capitalized, color: statusColor(agent.status))
            }
            Text(agent.task).font(.callout).lineLimit(3).frame(maxWidth: .infinity, alignment: .leading)
            if let summary = agent.summary, !summary.isEmpty {
                Text(summary).font(.caption).foregroundStyle(.secondary).lineLimit(3)
            }
            Divider()
            HStack {
                Label(agent.model.isEmpty ? "Unknown model" : agent.model, systemImage: "cpu")
                    .lineLimit(1)
                Spacer()
                let freshness = DateTools.freshness(agent.updatedAt, now: now)
                Circle().fill(freshness.color).frame(width: 6, height: 6)
                Text("\(DateTools.age(agent.updatedAt, now: now)) · \(agent.status == "completed" ? "Final update" : freshness.rawValue)")
            }
            .font(.caption2).foregroundStyle(.secondary)
        }
        .padding(15)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(.white.opacity(0.06)))
    }
}

struct EventRow: View {
    let event: EventRecord
    let showLine: Bool
    let now: Date
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(spacing: 0) {
                ZStack {
                    Circle().fill(eventColor).frame(width: 28, height: 28)
                    Image(systemName: eventIcon).font(.caption).foregroundStyle(.white)
                }
                if showLine { Rectangle().fill(.white.opacity(0.09)).frame(width: 1, height: 52) }
            }
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 7) {
                    Text(event.from.isEmpty ? "Unknown" : event.from).fontWeight(.semibold)
                    Image(systemName: "arrow.right").font(.caption2).foregroundStyle(.tertiary)
                    Text(event.to.isEmpty ? "Unknown" : event.to).fontWeight(.medium)
                    Spacer()
                    Text(DateTools.age(event.time, now: now)).font(.caption).foregroundStyle(.secondary)
                }
                Text(event.text).font(.callout).textSelection(.enabled)
                Text(event.kind.replacingOccurrences(of: "_", with: " ").uppercased())
                    .font(.system(size: 9, weight: .bold)).foregroundStyle(.tertiary)
            }
            .padding(.bottom, showLine ? 16 : 0)
        }
    }
    private var eventIcon: String {
        switch event.kind {
        case "message": return "bubble.left.fill"
        case "status": return "waveform.path.ecg"
        case "run_started": return "play.fill"
        case "run_finished": return "checkmark"
        case "agent_registered": return "person.badge.plus"
        default: return "note.text"
        }
    }
    private var eventColor: Color {
        switch event.kind {
        case "message": return .blue
        case "status": return .purple
        case "run_started": return .green
        case "run_finished": return .teal
        default: return .gray
        }
    }
}

struct EmptyBoardView: View {
    let unreadableCount: Int
    let refresh: () -> Void
    var body: some View {
        VStack(spacing: 18) {
            ZStack {
                Circle().fill(.blue.opacity(0.12)).frame(width: 92, height: 92)
                Image(systemName: "person.3.sequence.fill").font(.system(size: 38)).foregroundStyle(.blue)
            }
            Text("No live runs").font(.system(size: 27, weight: .semibold, design: .rounded))
            Text("When a Codex workflow records a run, its agents and activity will appear here.")
                .foregroundStyle(.secondary).multilineTextAlignment(.center).frame(maxWidth: 430)
            if unreadableCount > 0 {
                Label("\(unreadableCount) state file\(unreadableCount == 1 ? "" : "s") could not be read or used schema other than 1.", systemImage: "exclamationmark.triangle")
                    .font(.caption).foregroundStyle(.orange)
            }
            Button("Refresh now", action: refresh).buttonStyle(.borderedProminent)
            VStack(spacing: 5) {
                Text("Recorded activity · refreshes every 2s · native Codex is execution source")
                    .font(.caption).fontWeight(.medium)
                Text("Workflow summaries only; this viewer does not expose every internal message or thoughts.")
                    .font(.caption2).foregroundStyle(.secondary)
            }
        }
        .padding(40).frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

struct SectionTitle: View {
    let title: String
    let subtitle: String
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.title2).fontWeight(.semibold)
            Text(subtitle).font(.caption).foregroundStyle(.secondary)
        }
    }
}

struct StatusPill: View {
    let text: String
    let color: Color
    var body: some View {
        Text(text).font(.caption).fontWeight(.semibold)
            .padding(.horizontal, 9).padding(.vertical, 4)
            .foregroundStyle(color)
            .background(color.opacity(0.13), in: Capsule())
    }
}

func statusColor(_ status: String) -> Color {
    switch status.lowercased() {
    case "active", "running": return .green
    case "queued": return .blue
    case "blocked": return .orange
    case "failed": return .red
    case "completed": return .teal
    case "stopped": return .gray
    default: return .secondary
    }
}
