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

struct RegisterResponse: Decodable {
    struct RegisterTokens: Decodable {
        let access: String
        let refresh: String
    }

    let user: UserProfile
    let tokens: RegisterTokens
}

struct Topic: Decodable, Identifiable {
    let id: Int
    let text: String
    let dateAdded: String
    let isPublic: Bool
    let ownerUsername: String?

    enum CodingKeys: String, CodingKey {
        case id
        case text
        case dateAdded = "date_added"
        case isPublic = "is_public"
        case ownerUsername = "owner_username"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        text = try container.decode(String.self, forKey: .text)
        dateAdded = try container.decode(String.self, forKey: .dateAdded)
        isPublic = try container.decodeIfPresent(Bool.self, forKey: .isPublic) ?? false
        ownerUsername = try container.decodeIfPresent(String.self, forKey: .ownerUsername)
    }
}

struct TopicListResponse: Decodable {
    let topics: [Topic]
}

struct Entry: Decodable, Identifiable {
    let id: Int
    let topicID: Int?
    let topicText: String?
    let topicIsPublic: Bool
    let text: String
    let contentFormat: String
    let dateAdded: String
    let isPublic: Bool
    let effectiveIsPublic: Bool
    let ownerUsername: String?
    let imageURL: String?
    let videoURL: String?
    let documentURL: String?

    enum CodingKeys: String, CodingKey {
        case id
        case topicID = "topic_id"
        case topicText = "topic_text"
        case topicIsPublic = "topic_is_public"
        case text
        case contentFormat = "content_format"
        case dateAdded = "date_added"
        case isPublic = "is_public"
        case effectiveIsPublic = "effective_is_public"
        case ownerUsername = "owner_username"
        case imageURL = "image_url"
        case videoURL = "video_url"
        case documentURL = "document_url"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        topicID = try container.decodeIfPresent(Int.self, forKey: .topicID)
        topicText = try container.decodeIfPresent(String.self, forKey: .topicText)
        topicIsPublic = try container.decodeIfPresent(Bool.self, forKey: .topicIsPublic) ?? false
        text = try container.decode(String.self, forKey: .text)
        contentFormat = try container.decodeIfPresent(String.self, forKey: .contentFormat) ?? "markdown"
        dateAdded = try container.decode(String.self, forKey: .dateAdded)
        isPublic = try container.decodeIfPresent(Bool.self, forKey: .isPublic) ?? false
        effectiveIsPublic =
            try container.decodeIfPresent(Bool.self, forKey: .effectiveIsPublic)
            ?? (isPublic || topicIsPublic)
        ownerUsername = try container.decodeIfPresent(String.self, forKey: .ownerUsername)
        imageURL = try container.decodeIfPresent(String.self, forKey: .imageURL)
        videoURL = try container.decodeIfPresent(String.self, forKey: .videoURL)
        documentURL = try container.decodeIfPresent(String.self, forKey: .documentURL)
    }

    var isHTMLPage: Bool {
        contentFormat.lowercased() == "html"
    }
}

struct TopicDetailResponse: Decodable {
    let topic: Topic
    let entries: [Entry]
}

struct EntryListResponse: Decodable {
    let entries: [Entry]
}

struct StreamItem: Decodable, Identifiable {
    let id: Int
    let eventID: String
    let eventType: String
    let displayTitle: String
    let displaySummary: String
    let occurredAt: String
    let visibility: String
    let sourceObjectIDs: [String]
    let relatedEntryID: Int?
    let archiveURL: String?
    let actorType: String?

    enum CodingKeys: String, CodingKey {
        case id
        case eventID = "event_id"
        case eventType = "event_type"
        case displayTitle = "display_title"
        case displaySummary = "display_summary"
        case occurredAt = "occurred_at"
        case visibility
        case sourceObjectIDs = "source_object_ids"
        case relatedEntryID = "related_entry_id"
        case archiveURL = "archive_url"
        case actorType = "actor_type"
    }
}

struct StreamListResponse: Decodable {
    let streamItems: [StreamItem]

    enum CodingKeys: String, CodingKey {
        case streamItems = "stream_items"
    }
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
