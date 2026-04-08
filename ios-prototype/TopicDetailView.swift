import AVKit
import PhotosUI
import QuickLook
import SwiftUI

struct TopicDetailView: View {
    @EnvironmentObject private var session: SessionStore
    @Environment(\.dismiss) private var dismiss

    let topic: Topic

    @State private var currentTopic: Topic
    @State private var entries: [Entry] = []
    @State private var isLoading = false
    @State private var hasLoaded = false
    @State private var errorMessage = ""
    @State private var showingNewEntrySheet = false
    @State private var showingEditTopicSheet = false
    @State private var showingDeleteTopicAlert = false
    @State private var showingDeleteEntryAlert = false
    @State private var pendingDeleteEntryID: Int?
    @State private var newEntryText = ""
    @State private var newEntryErrorMessage = ""
    @State private var editTopicText = ""
    @State private var editTopicErrorMessage = ""
    @State private var editingEntry: Entry?
    @State private var editEntryText = ""
    @State private var editEntryErrorMessage = ""
    @State private var isSubmittingNewEntry = false
    @State private var isSubmittingTopicEdit = false
    @State private var isSubmittingEntryEdit = false
    @State private var isDeletingTopic = false
    @State private var previewAttachment: AttachmentTarget?

    init(topic: Topic) {
        self.topic = topic
        _currentTopic = State(initialValue: topic)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if isLoading && entries.isEmpty {
                    loadingState
                } else if !errorMessage.isEmpty && entries.isEmpty {
                    errorState
                } else if entries.isEmpty {
                    emptyState
                } else {
                    LazyVStack(spacing: 10) {
                        ForEach(entries) { entry in
                            EntryCard(entry: entry) {
                                editEntryText = entry.text
                                editEntryErrorMessage = ""
                                editingEntry = entry
                            } onDelete: {
                                pendingDeleteEntryID = entry.id
                                showingDeleteEntryAlert = true
                            } onPreviewAttachment: { url in
                                previewAttachment = AttachmentTarget(
                                    url: url,
                                    title: "附件预览"
                                )
                            }
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 22)
        }
        .background(Color(.systemGroupedBackground).ignoresSafeArea())
        .navigationTitle(currentTopic.text)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button("写笔记") {
                    newEntryText = ""
                    newEntryErrorMessage = ""
                    showingNewEntrySheet = true
                }

                Menu {
                    Button("刷新") {
                        Task {
                            await loadEntries(force: true)
                        }
                    }

                    Button("修改主题") {
                        editTopicText = currentTopic.text
                        editTopicErrorMessage = ""
                        showingEditTopicSheet = true
                    }

                    Button("删除主题", role: .destructive) {
                        showingDeleteTopicAlert = true
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .task {
            await loadEntries()
        }
        .refreshable {
            await loadEntries(force: true)
        }
        .sheet(isPresented: $showingNewEntrySheet) {
            EntryComposerSheet(
                title: "写新笔记",
                placeholder: "输入本次学习记录...",
                submitTitle: "发布笔记",
                text: $newEntryText,
                errorMessage: newEntryErrorMessage,
                isSubmitting: isSubmittingNewEntry,
                onSubmit: {
                    Task {
                        await submitNewEntry()
                    }
                },
                onUploadImage: { data, filename, mimeType in
                    try await session.uploadMarkdownImage(
                        imageData: data,
                        filename: filename,
                        mimeType: mimeType
                    )
                },
                onUploadVideo: { data, filename, mimeType in
                    try await session.uploadMarkdownVideo(
                        videoData: data,
                        filename: filename,
                        mimeType: mimeType
                    )
                }
            )
        }
        .sheet(isPresented: $showingEditTopicSheet) {
            TopicEditorSheet(
                text: $editTopicText,
                errorMessage: editTopicErrorMessage,
                isSubmitting: isSubmittingTopicEdit,
                onSubmit: {
                    Task {
                        await submitTopicEdit()
                    }
                }
            )
        }
        .sheet(item: $editingEntry) { entry in
            EntryComposerSheet(
                title: "编辑笔记",
                placeholder: "更新你的学习记录...",
                submitTitle: "保存修改",
                text: $editEntryText,
                errorMessage: editEntryErrorMessage,
                isSubmitting: isSubmittingEntryEdit,
                onSubmit: {
                    Task {
                        await submitEntryEdit(entryID: entry.id)
                    }
                },
                onUploadImage: { data, filename, mimeType in
                    try await session.uploadMarkdownImage(
                        imageData: data,
                        filename: filename,
                        mimeType: mimeType
                    )
                },
                onUploadVideo: { data, filename, mimeType in
                    try await session.uploadMarkdownVideo(
                        videoData: data,
                        filename: filename,
                        mimeType: mimeType
                    )
                }
            )
        }
        .sheet(item: $previewAttachment) { target in
            AttachmentPreviewSheet(target: target)
        }
        .alert("确认删除主题？", isPresented: $showingDeleteTopicAlert) {
            Button("删除", role: .destructive) {
                Task {
                    await deleteCurrentTopic()
                }
            }
            Button("取消", role: .cancel) {}
        } message: {
            if isDeletingTopic {
                Text("正在删除...")
            } else {
                Text("删除后不可恢复，包含该主题下全部笔记。")
            }
        }
        .alert("确认删除这条笔记？", isPresented: $showingDeleteEntryAlert, presenting: pendingDeleteEntryID) { entryID in
            Button("删除", role: .destructive) {
                Task {
                    await deleteEntry(entryID)
                }
            }
            Button("取消", role: .cancel) {}
        } message: { _ in
            Text("删除后不可恢复。")
        }
    }

    private var loadingState: some View {
        HStack {
            Spacer()
            ProgressView("正在加载笔记...")
                .padding(.vertical, 24)
            Spacer()
        }
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color(.secondarySystemGroupedBackground))
        )
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "square.and.pencil")
                .font(.system(size: 30))
                .foregroundStyle(.secondary)
            Text("还没有笔记")
                .font(.headline)
            Text("你可以先在网页端添加笔记，iOS 端会同步显示。")
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

    private var errorState: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("加载失败")
                .font(.headline)
            Text(errorMessage)
                .font(.subheadline)
                .foregroundStyle(.red)
            Button("重试") {
                Task {
                    await loadEntries(force: true)
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

    private func loadEntries(force: Bool = false) async {
        if hasLoaded && !force {
            return
        }

        isLoading = true
        errorMessage = ""
        do {
            let response = try await session.topicDetail(topicID: currentTopic.id)
            currentTopic = response.topic
            entries = response.entries
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    private func submitNewEntry() async {
        let trimmed = newEntryText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            newEntryErrorMessage = "笔记内容不能为空。"
            return
        }

        isSubmittingNewEntry = true
        newEntryErrorMessage = ""
        do {
            let entry = try await session.createEntry(topicID: currentTopic.id, text: trimmed)
            entries.insert(entry, at: 0)
            newEntryText = ""
            showingNewEntrySheet = false
        } catch {
            newEntryErrorMessage = error.localizedDescription
        }
        isSubmittingNewEntry = false
    }

    private func submitTopicEdit() async {
        let trimmed = editTopicText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            editTopicErrorMessage = "主题名称不能为空。"
            return
        }

        isSubmittingTopicEdit = true
        editTopicErrorMessage = ""
        do {
            let updatedTopic = try await session.updateTopic(topicID: currentTopic.id, text: trimmed)
            currentTopic = updatedTopic
            if let index = session.topics.firstIndex(where: { $0.id == updatedTopic.id }) {
                session.topics[index] = updatedTopic
            }
            showingEditTopicSheet = false
        } catch {
            editTopicErrorMessage = error.localizedDescription
        }
        isSubmittingTopicEdit = false
    }

    private func deleteCurrentTopic() async {
        isDeletingTopic = true
        do {
            try await session.deleteTopic(topicID: currentTopic.id)
            session.topics.removeAll { $0.id == currentTopic.id }
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
        isDeletingTopic = false
    }

    private func deleteEntry(_ entryID: Int) async {
        do {
            try await session.deleteEntry(entryID: entryID)
            entries.removeAll { $0.id == entryID }
            pendingDeleteEntryID = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func submitEntryEdit(entryID: Int) async {
        let trimmed = editEntryText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            editEntryErrorMessage = "笔记内容不能为空。"
            return
        }

        isSubmittingEntryEdit = true
        editEntryErrorMessage = ""
        do {
            let updatedEntry = try await session.updateEntry(entryID: entryID, text: trimmed)
            if let index = entries.firstIndex(where: { $0.id == entryID }) {
                entries[index] = updatedEntry
            }
            editingEntry = nil
        } catch {
            editEntryErrorMessage = error.localizedDescription
        }
        isSubmittingEntryEdit = false
    }
}

private struct EntryCard: View {
    let entry: Entry
    let onEdit: () -> Void
    let onDelete: () -> Void
    let onPreviewAttachment: (URL) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(displayDate(from: entry.dateAdded))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("编辑") {
                    onEdit()
                }
                .font(.caption)
                Button("删除", role: .destructive) {
                    onDelete()
                }
                .font(.caption)
            }

            MarkdownContentView(markdown: entry.text)

            if let imageURL = URL(string: entry.imageURL ?? "") {
                AsyncImage(url: imageURL) { phase in
                    switch phase {
                    case .empty:
                        ProgressView()
                            .frame(maxWidth: .infinity, minHeight: 120)
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFit()
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    case .failure:
                        Text("图片加载失败")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, minHeight: 90)
                    @unknown default:
                        EmptyView()
                    }
                }
                .frame(maxWidth: .infinity)
            }

            if let videoURL = URL(string: entry.videoURL ?? "") {
                InlineVideoPlayer(url: videoURL)
                    .frame(maxWidth: .infinity)
            }

            HStack(spacing: 12) {
                if let documentURL = URL(string: entry.documentURL ?? "") {
                    Button {
                        onPreviewAttachment(documentURL)
                    } label: {
                        Label("预览附件", systemImage: "doc.text")
                            .font(.caption)
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(.secondarySystemGroupedBackground))
        )
    }
}

private struct MarkdownContentView: View {
    let markdown: String

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(parsedBlocks.enumerated()), id: \.offset) { _, block in
                blockView(block)
            }
        }
    }

    private var parsedBlocks: [MarkdownBlock] {
        parseMarkdownBlocks(from: normalizedMarkdownForDisplay(markdown))
    }

    @ViewBuilder
    private func blockView(_ block: MarkdownBlock) -> some View {
        switch block {
        case .heading(let level, let text):
            inlineMarkdownText(text)
                .font(headingFont(level))
                .fontWeight(.semibold)
                .padding(.top, 6)
                .padding(.bottom, 2)
                .frame(maxWidth: .infinity, alignment: .leading)
        case .paragraph(let text):
            inlineMarkdownText(text)
                .frame(maxWidth: .infinity, alignment: .leading)
        case .blank:
            Color.clear
                .frame(height: 10)
        case .code(let text):
            ScrollView(.horizontal, showsIndicators: false) {
                Text(text)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(10)
            }
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color(.tertiarySystemGroupedBackground))
            )
            .padding(.vertical, 4)
            .frame(maxWidth: .infinity, alignment: .leading)
        case .image(let url):
            AsyncImage(url: url) { phase in
                switch phase {
                case .empty:
                    ProgressView()
                        .frame(maxWidth: .infinity, minHeight: 120)
                case .success(let image):
                    image
                        .resizable()
                        .scaledToFit()
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                case .failure:
                    Text("Markdown 图片加载失败")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, minHeight: 90)
                @unknown default:
                    EmptyView()
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
        case .video(let url):
            InlineVideoPlayer(url: url)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
        }
    }

    @ViewBuilder
    private func inlineMarkdownText(_ text: String) -> some View {
        if let attributed = styledInlineMarkdown(text) {
            Text(attributed)
        } else {
            Text(text)
        }
    }

    private func styledInlineMarkdown(_ text: String) -> AttributedString? {
        guard var attributed = try? AttributedString(
            markdown: text,
            options: AttributedString.MarkdownParsingOptions(
                interpretedSyntax: .inlineOnlyPreservingWhitespace
            )
        ) else {
            return nil
        }

        for run in attributed.runs {
            guard
                let intent = run.inlinePresentationIntent,
                intent.contains(.code)
            else {
                continue
            }

            let range = run.range
            attributed[range].font = .system(.body, design: .monospaced)
            attributed[range].foregroundColor = Color(red: 0.22, green: 0.26, blue: 0.31)
            attributed[range].backgroundColor = Color(red: 0.93, green: 0.94, blue: 0.96)
        }

        return attributed
    }

    private func headingFont(_ level: Int) -> Font {
        switch level {
        case 1:
            return .title
        case 2:
            return .title2
        case 3:
            return .title3
        case 4:
            return .headline
        case 5:
            return .subheadline
        default:
            return .footnote
        }
    }

    private func parseMarkdownBlocks(from source: String) -> [MarkdownBlock] {
        let lines = source.components(separatedBy: "\n")
        var blocks: [MarkdownBlock] = []
        var inCodeFence = false
        var codeLines: [String] = []

        for line in lines {
            switch codeFenceMarkerType(for: line, inCodeFence: inCodeFence) {
            case .open:
                inCodeFence = true
                continue
            case .close:
                if inCodeFence {
                    blocks.append(.code(codeLines.joined(separator: "\n")))
                    codeLines.removeAll()
                }
                inCodeFence = false
                continue
            case .none:
                break
            }

            if inCodeFence {
                codeLines.append(line)
                continue
            }

            let trimmed = line.trimmingCharacters(in: .whitespaces)

            if trimmed.isEmpty {
                blocks.append(.blank)
                continue
            }

            if let singleLineCode = parseSingleLineFencedCode(from: line) {
                blocks.append(.code(singleLineCode))
                continue
            }

            if let mediaBlock = parseMediaBlock(from: trimmed) {
                blocks.append(mediaBlock)
                continue
            }

            if let (level, headingText) = parseHeading(from: line) {
                blocks.append(.heading(level: level, text: headingText))
            } else {
                blocks.append(.paragraph(text: line))
            }
        }

        if !codeLines.isEmpty {
            blocks.append(.code(codeLines.joined(separator: "\n")))
        }

        return blocks
    }

    private func parseHeading(from line: String) -> (Int, String)? {
        guard
            let regex = try? NSRegularExpression(pattern: #"^\s{0,3}(#{1,6})\s*(.*?)\s*$"#)
        else { return nil }

        let source = line as NSString
        let range = NSRange(location: 0, length: source.length)
        guard let match = regex.firstMatch(in: line, range: range), match.numberOfRanges > 2 else {
            return nil
        }

        let hashes = source.substring(with: match.range(at: 1))
        let text = source.substring(with: match.range(at: 2)).trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return nil }
        return (hashes.count, text)
    }

    private func parseSingleLineFencedCode(from line: String) -> String? {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        guard trimmed.hasPrefix("```"), trimmed.hasSuffix("```"), trimmed.count > 6 else {
            return nil
        }

        let start = trimmed.index(trimmed.startIndex, offsetBy: 3)
        let end = trimmed.index(trimmed.endIndex, offsetBy: -3)
        let inner = String(trimmed[start..<end])

        guard !inner.contains("```") else { return nil }

        let normalized = inner.trimmingCharacters(in: .whitespacesAndNewlines)
        return normalized.isEmpty ? nil : normalized
    }

    private func parseMediaBlock(from line: String) -> MarkdownBlock? {
        if let imageURLString = firstCapturedValue(
            in: line,
            pattern: #"^\s*!\[[^\]]*\]\(([^)\s]+)[^)]*\)\s*$"#
        ), let url = URL(string: imageURLString) {
            return .image(url)
        }

        if let videoURLString = firstCapturedValue(
            in: line,
            pattern: #"^\s*@\[(?:video|视频)\]\(([^)\s]+)[^)]*\)\s*$"#
        ), let url = URL(string: videoURLString) {
            return .video(url)
        }

        return nil
    }

    private func firstCapturedValue(in line: String, pattern: String) -> String? {
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return nil }
        let source = line as NSString
        let range = NSRange(location: 0, length: source.length)
        guard let match = regex.firstMatch(in: line, range: range), match.numberOfRanges > 1 else {
            return nil
        }
        return source.substring(with: match.range(at: 1))
    }

    private enum MarkdownBlock {
        case heading(level: Int, text: String)
        case paragraph(text: String)
        case blank
        case code(String)
        case image(URL)
        case video(URL)
    }
}

private struct InlineVideoPlayer: View {
    let url: URL
    @State private var player: AVPlayer?

    var body: some View {
        VideoPlayer(player: player)
            .frame(height: adaptiveVideoHeight())
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            .onAppear {
                if player == nil {
                    player = AVPlayer(url: url)
                }
            }
            .onDisappear {
                player?.pause()
            }
    }
}

private struct EntryComposerSheet: View {
    private let imageMaxBytes = 5 * 1024 * 1024
    private let videoMaxBytes = 500 * 1024 * 1024

    @Environment(\.dismiss) private var dismiss

    let title: String
    let placeholder: String
    let submitTitle: String
    @Binding var text: String
    let errorMessage: String
    let isSubmitting: Bool
    let onSubmit: () -> Void
    let onUploadImage: (_ data: Data, _ filename: String, _ mimeType: String) async throws -> URL
    let onUploadVideo: (_ data: Data, _ filename: String, _ mimeType: String) async throws -> URL

    @State private var selectedImage: PhotosPickerItem?
    @State private var selectedVideo: PhotosPickerItem?
    @State private var isUploadingImage = false
    @State private var isUploadingVideo = false
    @State private var localErrorMessage = ""
    @State private var showPreview = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 12) {
                Picker("模式", selection: $showPreview) {
                    Text("编辑").tag(false)
                    Text("预览").tag(true)
                }
                .pickerStyle(.segmented)

                if showPreview {
                    ScrollView {
                        MarkdownContentView(markdown: text)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: .infinity)
                } else {
                    ZStack(alignment: .topLeading) {
                        TextEditor(text: $text)
                            .frame(minHeight: 220)
                            .padding(8)
                            .background(Color(.secondarySystemGroupedBackground))
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

                        if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            Text(placeholder)
                                .foregroundStyle(.secondary)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 16)
                        }
                    }

                    HStack(spacing: 10) {
                        PhotosPicker(selection: $selectedImage, matching: .images) {
                            Label("插入图片", systemImage: "photo.badge.plus")
                        }
                        .disabled(isUploadingImage || isUploadingVideo || isSubmitting)

                        PhotosPicker(selection: $selectedVideo, matching: .videos) {
                            Label("插入视频", systemImage: "video.badge.plus")
                        }
                        .disabled(isUploadingImage || isUploadingVideo || isSubmitting)

                        if isUploadingImage || isUploadingVideo {
                            ProgressView()
                                .scaleEffect(0.9)
                        }
                    }

                    Text("支持 Markdown：加粗、标题、列表、链接、图片、视频（图片 ≤ 5MB，视频 ≤ 500MB）。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if !errorMessage.isEmpty {
                    Text(errorMessage)
                        .font(.subheadline)
                        .foregroundStyle(.red)
                }

                if !localErrorMessage.isEmpty {
                    Text(localErrorMessage)
                        .font(.subheadline)
                        .foregroundStyle(.red)
                }

                Spacer()
            }
            .padding(16)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("取消") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        onSubmit()
                    } label: {
                        if isSubmitting {
                            ProgressView()
                        } else {
                            Text(submitTitle)
                        }
                    }
                    .disabled(isSubmitting || isUploadingImage || isUploadingVideo)
                }
            }
            .onChange(of: selectedImage) { newItem in
                guard let newItem else { return }
                Task {
                    await uploadAndInsertMarkdownImage(item: newItem)
                }
            }
            .onChange(of: selectedVideo) { newItem in
                guard let newItem else { return }
                Task {
                    await uploadAndInsertMarkdownVideo(item: newItem)
                }
            }
        }
    }

    private func uploadAndInsertMarkdownImage(item: PhotosPickerItem) async {
        isUploadingImage = true
        localErrorMessage = ""
        defer {
            isUploadingImage = false
            selectedImage = nil
        }

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                throw APIError.server("无法读取所选图片。")
            }
            if data.count > imageMaxBytes {
                throw APIError.server("图片不能超过 5MB。")
            }

            let fileExtension = item.supportedContentTypes.first?.preferredFilenameExtension ?? "jpg"
            let filename = "ios-\(UUID().uuidString).\(fileExtension)"
            let uploadedURL = try await onUploadImage(
                data,
                filename,
                mimeType(for: fileExtension)
            )

            if !text.isEmpty && !text.hasSuffix("\n") {
                text += "\n"
            }
            text += "![图片](\(uploadedURL.absoluteString))\n"
        } catch {
            localErrorMessage = error.localizedDescription
        }
    }

    private func uploadAndInsertMarkdownVideo(item: PhotosPickerItem) async {
        isUploadingVideo = true
        localErrorMessage = ""
        defer {
            isUploadingVideo = false
            selectedVideo = nil
        }

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                throw APIError.server("无法读取所选视频。")
            }
            if data.count > videoMaxBytes {
                throw APIError.server("视频不能超过 500MB。")
            }

            let fileExtension = item.supportedContentTypes.first?.preferredFilenameExtension ?? "mp4"
            let filename = "ios-video-\(UUID().uuidString).\(fileExtension)"
            let uploadedURL = try await onUploadVideo(
                data,
                filename,
                videoMimeType(for: fileExtension)
            )

            if !text.isEmpty && !text.hasSuffix("\n") {
                text += "\n"
            }
            text += "@[video](\(uploadedURL.absoluteString))\n"
        } catch {
            localErrorMessage = error.localizedDescription
        }
    }
}

private struct TopicEditorSheet: View {
    @Environment(\.dismiss) private var dismiss

    @Binding var text: String
    let errorMessage: String
    let isSubmitting: Bool
    let onSubmit: () -> Void

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 12) {
                TextField("主题名称", text: $text)
                    .textFieldStyle(.roundedBorder)

                if !errorMessage.isEmpty {
                    Text(errorMessage)
                        .font(.subheadline)
                        .foregroundStyle(.red)
                }

                Spacer()
            }
            .padding(16)
            .navigationTitle("修改主题")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("取消") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        onSubmit()
                    } label: {
                        if isSubmitting {
                            ProgressView()
                        } else {
                            Text("保存")
                        }
                    }
                    .disabled(isSubmitting)
                }
            }
        }
    }
}

private struct AttachmentTarget: Identifiable {
    let id = UUID()
    let url: URL
    let title: String
}

private struct AttachmentPreviewSheet: View {
    let target: AttachmentTarget

    @State private var localFileURL: URL?
    @State private var isLoading = false
    @State private var errorMessage = ""

    var body: some View {
        NavigationStack {
            Group {
                if let localFileURL {
                    QuickLookContainer(url: localFileURL, title: target.title)
                        .ignoresSafeArea(edges: .bottom)
                } else if isLoading {
                    ProgressView("正在准备附件预览...")
                } else {
                    VStack(spacing: 12) {
                        Text("附件预览失败")
                            .font(.headline)
                        if !errorMessage.isEmpty {
                            Text(errorMessage)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        Link("在外部打开", destination: target.url)
                    }
                    .padding()
                }
            }
            .navigationTitle(target.title)
            .navigationBarTitleDisplayMode(.inline)
            .task {
                await preparePreview()
            }
        }
    }

    private func preparePreview() async {
        guard localFileURL == nil else { return }
        isLoading = true
        errorMessage = ""
        do {
            let (downloadedURL, _) = try await URLSession.shared.download(from: target.url)
            let suffix = target.url.pathExtension
            let destination = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathExtension(suffix)

            if FileManager.default.fileExists(atPath: destination.path) {
                try FileManager.default.removeItem(at: destination)
            }
            try FileManager.default.moveItem(at: downloadedURL, to: destination)
            localFileURL = destination
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

private struct QuickLookContainer: UIViewControllerRepresentable {
    let url: URL
    let title: String

    func makeCoordinator() -> Coordinator {
        Coordinator(url: url, title: title)
    }

    func makeUIViewController(context: Context) -> QLPreviewController {
        let controller = QLPreviewController()
        controller.dataSource = context.coordinator
        return controller
    }

    func updateUIViewController(_ uiViewController: QLPreviewController, context: Context) {
        context.coordinator.item = PreviewItem(url: url, title: title)
        uiViewController.reloadData()
    }

    final class Coordinator: NSObject, QLPreviewControllerDataSource {
        var item: PreviewItem

        init(url: URL, title: String) {
            item = PreviewItem(url: url, title: title)
        }

        func numberOfPreviewItems(in controller: QLPreviewController) -> Int {
            1
        }

        func previewController(
            _ controller: QLPreviewController,
            previewItemAt index: Int
        ) -> QLPreviewItem {
            item
        }
    }
}

private final class PreviewItem: NSObject, QLPreviewItem {
    let previewItemURL: URL?
    let previewItemTitle: String?

    init(url: URL, title: String) {
        previewItemURL = url
        previewItemTitle = title
    }
}

private func displayDate(from isoDate: String) -> String {
    let isoFormatter = ISO8601DateFormatter()
    isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let date = isoFormatter.date(from: isoDate) {
        return zhDateTimeString(from: date)
    }

    isoFormatter.formatOptions = [.withInternetDateTime]
    if let date = isoFormatter.date(from: isoDate) {
        return zhDateTimeString(from: date)
    }

    let fallback = DateFormatter()
    fallback.locale = Locale(identifier: "en_US_POSIX")
    fallback.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXXXX"
    if let date = fallback.date(from: isoDate) {
        return zhDateTimeString(from: date)
    }

    fallback.dateFormat = "yyyy-MM-dd'T'HH:mm:ssXXXXX"
    if let date = fallback.date(from: isoDate) {
        return zhDateTimeString(from: date)
    }

    return isoDate
}

private func zhDateTimeString(from date: Date) -> String {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "zh_CN")
    formatter.dateFormat = "yyyy年M月d日 HH:mm"
    return formatter.string(from: date)
}

private func mimeType(for fileExtension: String) -> String {
    switch fileExtension.lowercased() {
    case "png":
        return "image/png"
    case "gif":
        return "image/gif"
    case "heic":
        return "image/heic"
    case "webp":
        return "image/webp"
    default:
        return "image/jpeg"
    }
}

private func adaptiveVideoHeight() -> CGFloat {
    let screenWidth = UIScreen.main.bounds.width
    let contentWidth = max(screenWidth - 40, 240)
    let ideal = contentWidth * 9 / 16
    return min(max(ideal, 180), 340)
}

private func videoMimeType(for fileExtension: String) -> String {
    switch fileExtension.lowercased() {
    case "mov":
        return "video/quicktime"
    case "m4v":
        return "video/x-m4v"
    case "webm":
        return "video/webm"
    default:
        return "video/mp4"
    }
}

private func normalizedMarkdownForDisplay(_ raw: String) -> String {
    let normalized = raw
        .replacingOccurrences(of: "\r\n", with: "\n")
        .replacingOccurrences(of: "\r", with: "\n")
    let lines = normalized.components(separatedBy: "\n")
    var output: [String] = []
    output.reserveCapacity(lines.count)

    var inCodeFence = false
    for line in lines {
        let displayLine = inCodeFence ? line : normalizeHeadingSyntaxIfNeeded(line)
        output.append(displayLine)

        switch codeFenceMarkerType(for: displayLine, inCodeFence: inCodeFence) {
        case .open:
            inCodeFence.toggle()
        case .close:
            inCodeFence.toggle()
        case .none:
            break
        }
    }

    return output.joined(separator: "\n")
}

private func normalizeHeadingSyntaxIfNeeded(_ line: String) -> String {
    guard let regex = try? NSRegularExpression(pattern: #"^(\s{0,3})(#{1,6})([^#\s].*)$"#) else {
        return line
    }
    let range = NSRange(location: 0, length: (line as NSString).length)
    if regex.firstMatch(in: line, range: range) == nil {
        return line
    }
    return regex.stringByReplacingMatches(
        in: line,
        range: range,
        withTemplate: "$1$2 $3"
    )
}

private enum CodeFenceMarkerType {
    case open
    case close
    case none
}

private func codeFenceMarkerType(for line: String, inCodeFence: Bool) -> CodeFenceMarkerType {
    let trimmed = line.trimmingCharacters(in: .whitespaces)
    guard trimmed.hasPrefix("```") else { return .none }

    let firstMarkerLength = 3
    let suffix = String(trimmed.dropFirst(firstMarkerLength))
    let hasAnotherMarker = suffix.contains("```")
    if hasAnotherMarker {
        // Inline markdown like ```code``` should not toggle fenced-code mode.
        return .none
    }

    if inCodeFence {
        return trimmed == "```" ? .close : .none
    }

    return .open
}
