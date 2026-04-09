import Foundation

struct TokenPair: Decodable {
    let access: String
    let refresh: String
}

struct AccessTokenResponse: Decodable {
    let access: String
}

struct LoginRequest: Encodable {
    let username: String
    let password: String
}

struct Topic: Decodable, Identifiable {
    let id: Int
    let text: String
    let dateAdded: String

    enum CodingKeys: String, CodingKey {
        case id
        case text
        case dateAdded = "date_added"
    }
}

struct TopicListResponse: Decodable {
    let topics: [Topic]
}

struct Entry: Decodable, Identifiable {
    let id: Int
    let text: String
    let dateAdded: String
    let imageURL: String?
    let videoURL: String?
    let documentURL: String?

    enum CodingKeys: String, CodingKey {
        case id
        case text
        case dateAdded = "date_added"
        case imageURL = "image_url"
        case videoURL = "video_url"
        case documentURL = "document_url"
    }
}

struct TopicDetailResponse: Decodable {
    let topic: Topic
    let entries: [Entry]
}

struct TopicResponse: Decodable {
    let topic: Topic
}

struct EntryResponse: Decodable {
    let entry: Entry
}

struct EntryDetailResponse: Decodable {
    let topic: Topic
    let entry: Entry
}

struct ImageUploadResponse: Decodable {
    struct UploadData: Decodable {
        let filePath: String
    }

    let data: UploadData
    let url: String?
}

struct UserProfile: Decodable {
    let id: Int
    let username: String
}

struct CurrentUserResponse: Decodable {
    let user: UserProfile
}
