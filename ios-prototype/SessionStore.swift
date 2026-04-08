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
        guard let accessToken else { return }
        isLoading = true
        errorMessage = ""

        do {
            let topicResponse = try await apiClient.topics(accessToken: accessToken)
            topics = topicResponse.topics
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func topicDetail(topicID: Int) async throws -> TopicDetailResponse {
        guard let accessToken else {
            throw APIError.unauthorized
        }
        return try await apiClient.topicDetail(topicID: topicID, accessToken: accessToken)
    }

    func updateTopic(topicID: Int, text: String) async throws -> Topic {
        guard let accessToken else {
            throw APIError.unauthorized
        }
        let response = try await apiClient.updateTopic(topicID: topicID, text: text, accessToken: accessToken)
        return response.topic
    }

    func deleteTopic(topicID: Int) async throws {
        guard let accessToken else {
            throw APIError.unauthorized
        }
        try await apiClient.deleteTopic(topicID: topicID, accessToken: accessToken)
    }

    func createEntry(topicID: Int, text: String) async throws -> Entry {
        guard let accessToken else {
            throw APIError.unauthorized
        }
        let response = try await apiClient.createEntry(topicID: topicID, text: text, accessToken: accessToken)
        return response.entry
    }

    func deleteEntry(entryID: Int) async throws {
        guard let accessToken else {
            throw APIError.unauthorized
        }
        try await apiClient.deleteEntry(entryID: entryID, accessToken: accessToken)
    }

    func updateEntry(entryID: Int, text: String) async throws -> Entry {
        guard let accessToken else {
            throw APIError.unauthorized
        }
        let response = try await apiClient.updateEntry(entryID: entryID, text: text, accessToken: accessToken)
        return response.entry
    }

    func uploadMarkdownImage(imageData: Data, filename: String, mimeType: String) async throws -> URL {
        guard let accessToken else {
            throw APIError.unauthorized
        }
        return try await apiClient.uploadMarkdownImage(
            imageData: imageData,
            filename: filename,
            mimeType: mimeType,
            accessToken: accessToken
        )
    }

    func uploadMarkdownVideo(videoData: Data, filename: String, mimeType: String) async throws -> URL {
        guard let accessToken else {
            throw APIError.unauthorized
        }
        return try await apiClient.uploadMarkdownVideo(
            videoData: videoData,
            filename: filename,
            mimeType: mimeType,
            accessToken: accessToken
        )
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
