import SwiftUI

struct StreamListView: View {
    @EnvironmentObject private var session: SessionStore

    @State private var streamItems: [StreamItem] = []
    @State private var isLoading = false
    @State private var hasLoaded = false
    @State private var errorMessage = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if isLoading && streamItems.isEmpty {
                    loadingState
                } else if !errorMessage.isEmpty && streamItems.isEmpty {
                    errorState
                } else if streamItems.isEmpty {
                    emptyState
                } else {
                    LazyVStack(spacing: 10) {
                        ForEach(streamItems) { item in
                            StreamItemCard(item: item)
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 22)
        }
        .background(Color(.systemGroupedBackground).ignoresSafeArea())
        .navigationTitle("信息流")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await loadStream()
        }
        .refreshable {
            await loadStream(force: true)
        }
    }

    private var loadingState: some View {
        HStack {
            Spacer()
            ProgressView("正在加载信息流...")
                .padding(.vertical, 24)
            Spacer()
        }
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color(.secondarySystemGroupedBackground))
        )
    }

    private var errorState: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("加载失败")
                .font(.headline)
            Text(errorMessage)
                .font(.subheadline)
                .foregroundStyle(.red)
            Button("重试") {
                Task {
                    await loadStream(force: true)
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color(.secondarySystemGroupedBackground))
        )
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "dot.radiowaves.left.and.right")
                .font(.system(size: 30))
                .foregroundStyle(.secondary)
            Text("暂时还没有信息流")
                .font(.headline)
            Text("系统发布晨报或执行结果后，会显示在这里。")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 28)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color(.secondarySystemGroupedBackground))
        )
    }

    private func loadStream(force: Bool = false) async {
        if hasLoaded && !force {
            return
        }

        isLoading = true
        errorMessage = ""
        do {
            streamItems = try await session.fetchPublicStream()
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

private struct StreamItemCard: View {
    let item: StreamItem
    @Environment(\.openURL) private var openURL

    var body: some View {
        Button {
            openArchiveURLIfAvailable()
        } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .top, spacing: 8) {
                    Label(streamTypeLabel, systemImage: streamTypeIcon)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(streamTypeColor)
                    Spacer()
                    Text(displayStreamDate(from: item.occurredAt))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Text(item.displayTitle)
                    .font(.headline)
                    .foregroundStyle(.primary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Text(item.displaySummary)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(4)
                    .frame(maxWidth: .infinity, alignment: .leading)

                HStack(spacing: 6) {
                    Label("系统发布", systemImage: "sparkles")
                    if item.archiveURL != nil {
                        Text("· 可查看详情")
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color(.secondarySystemGroupedBackground))
            )
        }
        .buttonStyle(.plain)
        .disabled(item.archiveURL == nil)
    }

    private var streamTypeLabel: String {
        switch item.eventType {
        case "signal_item":
            return "信号"
        case "theme_update":
            return "主题"
        case "action_result":
            return "结果"
        case "briefing_release":
            return "晨报"
        case "artifact_release":
            return "执行结果"
        default:
            return "信息"
        }
    }

    private var streamTypeIcon: String {
        switch item.eventType {
        case "signal_item":
            return "dot.radiowaves.left.and.right"
        case "theme_update":
            return "point.3.connected.trianglepath.dotted"
        case "action_result":
            return "checkmark.circle"
        case "briefing_release":
            return "sun.max"
        case "artifact_release":
            return "checkmark.seal"
        default:
            return "circle.grid.cross"
        }
    }

    private var streamTypeColor: Color {
        switch item.eventType {
        case "signal_item":
            return .blue
        case "theme_update":
            return .purple
        case "action_result":
            return .green
        case "briefing_release":
            return .orange
        case "artifact_release":
            return .green
        default:
            return .blue
        }
    }

    private func openArchiveURLIfAvailable() {
        guard let archiveURL = item.archiveURL, let url = URL(string: archiveURL) else {
            return
        }
        openURL(url)
    }
}

private func displayStreamDate(from isoDate: String) -> String {
    let isoFormatter = ISO8601DateFormatter()
    isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let date = isoFormatter.date(from: isoDate) {
        return zhStreamDateTimeString(from: date)
    }

    isoFormatter.formatOptions = [.withInternetDateTime]
    if let date = isoFormatter.date(from: isoDate) {
        return zhStreamDateTimeString(from: date)
    }

    return isoDate
}

private func zhStreamDateTimeString(from date: Date) -> String {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "zh_CN")
    formatter.dateFormat = "MM-dd HH:mm"
    return formatter.string(from: date)
}
