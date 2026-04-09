import Foundation

@MainActor
final class SessionStore: ObservableObject {
    private static let serverBaseURLKey = "serverBaseURL"

    @Published var username = ""
    @Published var password = ""
    @Published var serverBaseURL: String {
        didSet {
            apiClient.baseURLString = serverBaseURL
            UserDefaults.standard.set(serverBaseURL, forKey: Self.serverBaseURLKey)
        }
    }
    @Published var currentUser: UserProfile?
    @Published var topics: [Topic] = []
    @Published var errorMessage = ""
    @Published var isLoading = false
    @Published var isAuthenticated = false

    private let apiClient: APIClient
    private(set) var accessToken: String?
    private(set) var refreshToken: String?

    init() {
        let savedURL = UserDefaults.standard.string(forKey: Self.serverBaseURLKey)
        let defaultURL = "http://127.0.0.1:8000"
        self.serverBaseURL = savedURL ?? defaultURL
        self.apiClient = APIClient(baseURLString: savedURL ?? defaultURL)
    }

    func login() async {
        errorMessage = ""
        isLoading = true

        do {
            let tokens = try await apiClient.login(username: username, password: password)
            accessToken = tokens.access
            refreshToken = tokens.refresh

            let profile = try await apiClient.currentUser(accessToken: tokens.access)
            currentUser = profile.user

            let topicResponse = try await apiClient.topics(accessToken: tokens.access)
            topics = topicResponse.topics
            isAuthenticated = true
        } catch {
            errorMessage = error.localizedDescription
            isAuthenticated = false
        }

        isLoading = false
    }

    func reloadTopics() async {
        isLoading = true
        errorMessage = ""

        do {
            let topicResponse = try await performAuthorizedRequest { accessToken in
                try await self.apiClient.topics(accessToken: accessToken)
            }
            topics = topicResponse.topics
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func topicDetail(topicID: Int) async throws -> TopicDetailResponse {
        try await performAuthorizedRequest { accessToken in
            try await self.apiClient.topicDetail(topicID: topicID, accessToken: accessToken)
        }
    }

    func updateTopic(topicID: Int, text: String) async throws -> Topic {
        let response = try await performAuthorizedRequest { accessToken in
            try await self.apiClient.updateTopic(
                topicID: topicID,
                text: text,
                accessToken: accessToken
            )
        }
        return response.topic
    }

    func deleteTopic(topicID: Int) async throws {
        try await performAuthorizedRequest { accessToken in
            try await self.apiClient.deleteTopic(topicID: topicID, accessToken: accessToken)
            return ()
        }
    }

    func createEntry(topicID: Int, text: String) async throws -> Entry {
        let response = try await performAuthorizedRequest { accessToken in
            try await self.apiClient.createEntry(
                topicID: topicID,
                text: text,
                accessToken: accessToken
            )
        }
        return response.entry
    }

    func deleteEntry(entryID: Int) async throws {
        try await performAuthorizedRequest { accessToken in
            try await self.apiClient.deleteEntry(entryID: entryID, accessToken: accessToken)
            return ()
        }
    }

    func updateEntry(entryID: Int, text: String) async throws -> Entry {
        let response = try await performAuthorizedRequest { accessToken in
            try await self.apiClient.updateEntry(
                entryID: entryID,
                text: text,
                accessToken: accessToken
            )
        }
        return response.entry
    }

    func uploadMarkdownImage(imageData: Data, filename: String, mimeType: String) async throws -> URL {
        try await performAuthorizedRequest { accessToken in
            try await self.apiClient.uploadMarkdownImage(
                imageData: imageData,
                filename: filename,
                mimeType: mimeType,
                accessToken: accessToken
            )
        }
    }

    func uploadMarkdownVideo(
        videoData: Data,
        filename: String,
        mimeType: String,
        onProgress: ((Double) -> Void)? = nil
    ) async throws -> URL {
        try await performAuthorizedRequest { accessToken in
            try await self.apiClient.uploadMarkdownVideo(
                videoData: videoData,
                filename: filename,
                mimeType: mimeType,
                accessToken: accessToken,
                onProgress: onProgress
            )
        }
    }

    private func performAuthorizedRequest<T>(
        _ operation: @escaping (String) async throws -> T
    ) async throws -> T {
        guard let accessToken else {
            throw APIError.unauthorized
        }

        do {
            return try await operation(accessToken)
        } catch APIError.unauthorized {
            let refreshedAccessToken = try await refreshAccessToken()
            return try await operation(refreshedAccessToken)
        }
    }

    private func refreshAccessToken() async throws -> String {
        guard let refreshToken else {
            logout()
            throw APIError.unauthorized
        }

        do {
            let response = try await apiClient.refreshAccessToken(refreshToken: refreshToken)
            accessToken = response.access
            return response.access
        } catch {
            logout()
            throw APIError.unauthorized
        }
    }

    func logout() {
        accessToken = nil
        refreshToken = nil
        currentUser = nil
        topics = []
        password = ""
        isAuthenticated = false
        errorMessage = ""
    }
}
