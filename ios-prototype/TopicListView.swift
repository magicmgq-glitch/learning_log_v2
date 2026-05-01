import SwiftUI

struct TopicListView: View {
    @EnvironmentObject private var session: SessionStore
    @State private var showingNewTopicSheet = false
    @State private var newTopicText = ""
    @State private var newTopicIsPublic = false
    @State private var newTopicErrorMessage = ""
    @State private var isSubmittingNewTopic = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                headerRow
                publicSquareEntry

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

            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    NavigationLink {
                        StreamListView()
                    } label: {
                        Label("信息流", systemImage: "dot.radiowaves.left.and.right")
                    }

                    Button {
                        Task {
                            await session.reloadTopics()
                        }
                    } label: {
                        Label("刷新", systemImage: "arrow.clockwise")
                    }

                    Divider()

                    Button(role: .destructive) {
                        session.logout()
                    } label: {
                        Label("退出", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                } label: {
                    Image(systemName: "line.3.horizontal")
                        .font(.headline)
                        .frame(width: 28, height: 28)
                }
                .accessibilityLabel("更多操作")
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showingNewTopicSheet) {
            NavigationStack {
                VStack(alignment: .leading, spacing: 12) {
                    TextField("主题名称", text: $newTopicText)
                        .textFieldStyle(.roundedBorder)

                    Toggle("公开主题（主题下笔记默认可见）", isOn: $newTopicIsPublic)
                        .font(.subheadline)

                    if !newTopicErrorMessage.isEmpty {
                        Text(newTopicErrorMessage)
                            .font(.subheadline)
                            .foregroundStyle(.red)
                    }

                    Spacer()
                }
                .padding(16)
                .navigationTitle("新建主题")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button("取消") {
                            showingNewTopicSheet = false
                        }
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            Task {
                                await submitNewTopic()
                            }
                        } label: {
                            if isSubmittingNewTopic {
                                ProgressView()
                            } else {
                                Text("保存")
                            }
                        }
                        .disabled(isSubmittingNewTopic)
                    }
                }
            }
        }
    }

    private var headerRow: some View {
        HStack(alignment: .center) {
            Text("学习主题")
                .font(.title2.weight(.semibold))

            Spacer()

            Button("添加新主题") {
                newTopicText = ""
                newTopicIsPublic = false
                newTopicErrorMessage = ""
                showingNewTopicSheet = true
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
        }
        .padding(.vertical, 2)
    }

    private var publicSquareEntry: some View {
        NavigationLink {
            PublicSquareView()
        } label: {
            HStack(spacing: 10) {
                Image(systemName: "globe.asia.australia.fill")
                    .foregroundStyle(.blue)
                VStack(alignment: .leading, spacing: 2) {
                    Text("笔记广场")
                        .font(.subheadline.weight(.semibold))
                    Text("浏览所有公开笔记")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.tertiary)
            }
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color(.secondarySystemGroupedBackground))
            )
        }
        .buttonStyle(.plain)
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "book.closed")
                .font(.system(size: 34))
                .foregroundStyle(.secondary)
            Text("还没有主题")
                .font(.headline)
            Text("你可以点击上方“添加新主题”创建第一条主题。")
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

    private func submitNewTopic() async {
        let trimmed = newTopicText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            newTopicErrorMessage = "主题名称不能为空。"
            return
        }

        isSubmittingNewTopic = true
        newTopicErrorMessage = ""
        do {
            let topic = try await session.createTopic(text: trimmed, isPublic: newTopicIsPublic)
            session.topics.append(topic)
            showingNewTopicSheet = false
        } catch {
            newTopicErrorMessage = error.localizedDescription
        }
        isSubmittingNewTopic = false
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
                HStack(spacing: 8) {
                    Text(topic.text)
                        .font(.headline)
                    if topic.isPublic {
                        Text("已公开")
                            .font(.caption2.weight(.semibold))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .foregroundStyle(.green)
                            .background(
                                Capsule(style: .continuous)
                                    .fill(Color.green.opacity(0.14))
                            )
                    }
                }
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
