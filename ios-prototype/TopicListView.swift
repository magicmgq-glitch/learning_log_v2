import SwiftUI

struct TopicListView: View {
    @EnvironmentObject private var session: SessionStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if session.topics.isEmpty && !session.isLoading {
                    emptyState
                } else {
                    LazyVStack(spacing: 10) {
                        ForEach(session.topics) { topic in
                            NavigationLink {
                                TopicDetailView(topic: topic)
                            } label: {
                                TopicCard(topic: topic)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 22)
        }
        .background(Color(.systemGroupedBackground).ignoresSafeArea())
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                if let username = session.currentUser?.username {
                    Text("你好, \(username)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            ToolbarItemGroup(placement: .topBarTrailing) {
                Button("刷新") {
                    Task {
                        await session.reloadTopics()
                    }
                }

                Button("退出") {
                    session.logout()
                }
            }
        }
        .navigationTitle("学习主题")
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "book.closed")
                .font(.system(size: 34))
                .foregroundStyle(.secondary)
            Text("还没有主题")
                .font(.headline)
            Text("你可以先在网页端添加主题，iOS 端会同步显示。")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 14)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 28)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color(.secondarySystemGroupedBackground))
        )
    }
}

private struct TopicCard: View {
    let topic: Topic

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "book")
                .foregroundStyle(.blue)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 6) {
                Text(topic.text)
                    .font(.headline)
                Text("创建于 \(displayTopicDate(from: topic.dateAdded))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()
            Text("查看")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .padding(.top, 2)
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(.secondarySystemGroupedBackground))
        )
    }
}

private func displayTopicDate(from isoDate: String) -> String {
    let isoFormatter = ISO8601DateFormatter()
    isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let date = isoFormatter.date(from: isoDate) {
        return zhTopicDateTimeString(from: date)
    }

    isoFormatter.formatOptions = [.withInternetDateTime]
    if let date = isoFormatter.date(from: isoDate) {
        return zhTopicDateTimeString(from: date)
    }

    let fallback = DateFormatter()
    fallback.locale = Locale(identifier: "en_US_POSIX")
    fallback.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXXXX"
    if let date = fallback.date(from: isoDate) {
        return zhTopicDateTimeString(from: date)
    }

    fallback.dateFormat = "yyyy-MM-dd'T'HH:mm:ssXXXXX"
    if let date = fallback.date(from: isoDate) {
        return zhTopicDateTimeString(from: date)
    }

    return isoDate
}

private func zhTopicDateTimeString(from date: Date) -> String {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "zh_CN")
    formatter.dateFormat = "yyyy年M月d日 HH:mm"
    return formatter.string(from: date)
}
