import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case unauthorized
    case server(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "服务器地址无效。"
        case .invalidResponse:
            return "服务器返回的数据无效。"
        case .unauthorized:
            return "登录状态已过期，请重新登录。"
        case .server(let message):
            return message
        }
    }
}

private struct TopicUpdateRequest: Encodable {
    let text: String
}

private struct TopicCreateRequest: Encodable {
    let text: String
}

private struct EntryCreateRequest: Encodable {
    let text: String
}

private struct EntryUpdateRequest: Encodable {
    let text: String
}

private struct APIErrorPayload: Decodable {
    let error: String?
    let detail: String?
}

private final class UploadProgressDelegate: NSObject, URLSessionDataDelegate, URLSessionTaskDelegate {
    private let onProgress: (Double) -> Void
    private var responseData = Data()
    var continuation: CheckedContinuation<(Data, URLResponse), Error>?

    init(onProgress: @escaping (Double) -> Void) {
        self.onProgress = onProgress
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didSendBodyData bytesSent: Int64,
        totalBytesSent: Int64,
        totalBytesExpectedToSend: Int64
    ) {
        guard totalBytesExpectedToSend > 0 else { return }
        let progress = min(max(Double(totalBytesSent) / Double(totalBytesExpectedToSend), 0), 1)
        onProgress(progress)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        responseData.append(data)
    }

    func urlSession(
        _ session: URLSession,
        dataTask: URLSessionDataTask,
        didReceive response: URLResponse,
        completionHandler: @escaping (URLSession.ResponseDisposition) -> Void
    ) {
        completionHandler(.allow)
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let continuation else { return }
        self.continuation = nil

        if let error {
            continuation.resume(throwing: error)
            return
        }

        guard let response = task.response else {
            continuation.resume(throwing: APIError.invalidResponse)
            return
        }

        continuation.resume(returning: (responseData, response))
    }
}

final class APIClient {
    var baseURLString: String {
        didSet {
            baseURL = Self.makeBaseURL(from: baseURLString)
        }
    }
    private var baseURL: URL

    init(baseURLString: String = "http://127.0.0.1:8000") {
        self.baseURLString = baseURLString
        self.baseURL = Self.makeBaseURL(from: baseURLString)
    }

    private static func makeBaseURL(from rawValue: String) -> URL {
        let trimmed = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            return URL(string: "http://127.0.0.1:8000")!
        }

        let normalized: String
        if trimmed.hasPrefix("http://") || trimmed.hasPrefix("https://") {
            normalized = trimmed
        } else {
            normalized = "http://\(trimmed)"
        }

        if let url = URL(string: normalized) {
            return url
        }
        return URL(string: "http://127.0.0.1:8000")!
    }

    func login(username: String, password: String) async throws -> TokenPair {
        let requestBody = LoginRequest(username: username, password: password)
        return try await send(
            path: "/api/v1/auth/token/",
            method: "POST",
            body: requestBody,
            accessToken: nil,
            responseType: TokenPair.self
        )
    }

    func refreshAccessToken(refreshToken: String) async throws -> AccessTokenResponse {
        struct RefreshRequest: Encodable {
            let refresh: String
        }

        return try await send(
            path: "/api/v1/auth/token/refresh/",
            method: "POST",
            body: RefreshRequest(refresh: refreshToken),
            accessToken: nil,
            responseType: AccessTokenResponse.self
        )
    }

    func currentUser(accessToken: String) async throws -> CurrentUserResponse {
        try await send(
            path: "/api/v1/auth/me/",
            method: "GET",
            body: Optional<String>.none,
            accessToken: accessToken,
            responseType: CurrentUserResponse.self
        )
    }

    func topics(accessToken: String) async throws -> TopicListResponse {
        try await send(
            path: "/api/v1/topics/",
            method: "GET",
            body: Optional<String>.none,
            accessToken: accessToken,
            responseType: TopicListResponse.self
        )
    }

    func topicDetail(topicID: Int, accessToken: String) async throws -> TopicDetailResponse {
        try await send(
            path: "/api/v1/topics/\(topicID)/",
            method: "GET",
            body: Optional<String>.none,
            accessToken: accessToken,
            responseType: TopicDetailResponse.self
        )
    }

    func createTopic(text: String, accessToken: String) async throws -> TopicResponse {
        let requestBody = TopicCreateRequest(text: text)
        return try await send(
            path: "/api/v1/topics/",
            method: "POST",
            body: requestBody,
            accessToken: accessToken,
            responseType: TopicResponse.self
        )
    }

    func updateTopic(topicID: Int, text: String, accessToken: String) async throws -> TopicResponse {
        let requestBody = TopicUpdateRequest(text: text)
        return try await send(
            path: "/api/v1/topics/\(topicID)/",
            method: "PATCH",
            body: requestBody,
            accessToken: accessToken,
            responseType: TopicResponse.self
        )
    }

    func deleteTopic(topicID: Int, accessToken: String) async throws {
        struct EmptyResponse: Decodable {}
        _ = try await send(
            path: "/api/v1/topics/\(topicID)/",
            method: "DELETE",
            body: Optional<String>.none,
            accessToken: accessToken,
            responseType: EmptyResponse.self
        )
    }

    func createEntry(topicID: Int, text: String, accessToken: String) async throws -> EntryResponse {
        let requestBody = EntryCreateRequest(text: text)
        return try await send(
            path: "/api/v1/topics/\(topicID)/entries/",
            method: "POST",
            body: requestBody,
            accessToken: accessToken,
            responseType: EntryResponse.self
        )
    }

    func deleteEntry(entryID: Int, accessToken: String) async throws {
        struct EmptyResponse: Decodable {}
        _ = try await send(
            path: "/api/v1/entries/\(entryID)/",
            method: "DELETE",
            body: Optional<String>.none,
            accessToken: accessToken,
            responseType: EmptyResponse.self
        )
    }

    func updateEntry(entryID: Int, text: String, accessToken: String) async throws -> EntryDetailResponse {
        let requestBody = EntryUpdateRequest(text: text)
        return try await send(
            path: "/api/v1/entries/\(entryID)/",
            method: "PATCH",
            body: requestBody,
            accessToken: accessToken,
            responseType: EntryDetailResponse.self
        )
    }

    func uploadMarkdownImage(
        imageData: Data,
        filename: String,
        mimeType: String,
        accessToken: String
    ) async throws -> URL {
        guard let url = URL(string: "/api/v1/uploads/images/", relativeTo: baseURL)?.absoluteURL else {
            throw APIError.invalidURL
        }

        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append(
            "Content-Disposition: form-data; name=\"image\"; filename=\"\(filename)\"\r\n".data(
                using: .utf8
            )!
        )
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        let (data, response) = try await URLSession.shared.upload(for: request, from: body)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }

        if !(200...299).contains(httpResponse.statusCode) {
            let message = userFriendlyServerMessage(
                statusCode: httpResponse.statusCode,
                data: data,
                fallback: "图片上传失败，请稍后重试。"
            )
            throw APIError.server(message)
        }

        let payload = try JSONDecoder().decode(ImageUploadResponse.self, from: data)
        guard let uploadedURL = URL(string: payload.data.filePath) else {
            throw APIError.server("Invalid uploaded image URL.")
        }
        return uploadedURL
    }

    func uploadMarkdownVideo(
        videoData: Data,
        filename: String,
        mimeType: String,
        accessToken: String,
        onProgress: ((Double) -> Void)? = nil
    ) async throws -> URL {
        guard let url = URL(string: "/api/v1/uploads/videos/", relativeTo: baseURL)?.absoluteURL else {
            throw APIError.invalidURL
        }

        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append(
            "Content-Disposition: form-data; name=\"video\"; filename=\"\(filename)\"\r\n".data(
                using: .utf8
            )!
        )
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(videoData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        request.timeoutInterval = 15 * 60

        let (data, response) = try await uploadMultipart(
            request: request,
            body: body,
            onProgress: onProgress
        )
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }

        if !(200...299).contains(httpResponse.statusCode) {
            if httpResponse.statusCode >= 500 {
                throw APIError.server("视频已上传，但服务器转码超时。请稍后重试。")
            }
            let message = userFriendlyServerMessage(
                statusCode: httpResponse.statusCode,
                data: data,
                fallback: "视频上传失败，请稍后重试。"
            )
            throw APIError.server(message)
        }

        let payload = try JSONDecoder().decode(ImageUploadResponse.self, from: data)
        guard let uploadedURL = URL(string: payload.data.filePath) else {
            throw APIError.server("Invalid uploaded video URL.")
        }
        return uploadedURL
    }

    private func uploadMultipart(
        request: URLRequest,
        body: Data,
        onProgress: ((Double) -> Void)?
    ) async throws -> (Data, URLResponse) {
        guard let onProgress else {
            return try await URLSession.shared.upload(for: request, from: body)
        }

        onProgress(0)
        let delegate = UploadProgressDelegate(onProgress: onProgress)
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 15 * 60
        configuration.timeoutIntervalForResource = 30 * 60
        let session = URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)
        defer {
            session.finishTasksAndInvalidate()
        }

        let result: (Data, URLResponse) = try await withCheckedThrowingContinuation { continuation in
            delegate.continuation = continuation
            let task = session.uploadTask(with: request, from: body)
            task.resume()
        }
        onProgress(1)
        return result
    }

    private func send<RequestBody: Encodable, ResponseBody: Decodable>(
        path: String,
        method: String,
        body: RequestBody?,
        accessToken: String?,
        responseType: ResponseBody.Type
    ) async throws -> ResponseBody {
        let trimmedPath = path.trimmingCharacters(in: .whitespacesAndNewlines)
        let normalizedPath = trimmedPath.hasPrefix("/") ? trimmedPath : "/\(trimmedPath)"
        guard let url = URL(string: normalizedPath, relativeTo: baseURL)?.absoluteURL else {
            throw APIError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let accessToken {
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }

        if let body {
            request.httpBody = try JSONEncoder().encode(body)
        }

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }

        if !(200...299).contains(httpResponse.statusCode) {
            let fallback = path.contains("/auth/token/")
                ? "登录失败，请检查账号或密码。"
                : "请求失败，请稍后重试。"
            let message = userFriendlyServerMessage(
                statusCode: httpResponse.statusCode,
                data: data,
                fallback: fallback
            )
            throw APIError.server(message)
        }

        return try JSONDecoder().decode(ResponseBody.self, from: data)
    }

    private func userFriendlyServerMessage(
        statusCode: Int,
        data: Data,
        fallback: String
    ) -> String {
        if statusCode == 413 {
            return "上传文件过大，请压缩后重试。"
        }
        if statusCode >= 500 {
            return "服务器暂时不可用，请稍后再试。"
        }

        if let payload = try? JSONDecoder().decode(APIErrorPayload.self, from: data) {
            let raw = (payload.error ?? payload.detail ?? "").lowercased()
            if raw.contains("invalid or expired token") {
                return "登录状态已过期，请重新登录。"
            }
            if raw.contains("authentication required") {
                return "请先登录后再操作。"
            }
            if raw.contains("no active account found") {
                return "用户名或密码不正确。"
            }
            if raw.contains("image") && (raw.contains("exceeds") || raw.contains("large") || raw.contains("超过")) {
                return "图片不能超过 5MB。"
            }
            if raw.contains("video") && (raw.contains("exceeds") || raw.contains("large") || raw.contains("超过")) {
                return "视频不能超过 500MB。"
            }
        }

        return fallback
    }
}
