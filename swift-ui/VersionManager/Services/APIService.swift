import Foundation

actor APIService {
    static let shared = APIService()

    private let baseURL = "http://127.0.0.1:8765/api"
    private let session: URLSession

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: config)
    }

    // MARK: - Generic Request Methods

    private func request<T: Decodable>(_ endpoint: String, method: String = "GET", body: Data? = nil) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let body = body {
            request.httpBody = body
        }

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        if httpResponse.statusCode == 404 {
            throw APIError.notFound
        }

        if httpResponse.statusCode >= 400 {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.serverError(errorResponse.detail)
            }
            throw APIError.serverError("Status code: \(httpResponse.statusCode)")
        }

        let decoder = JSONDecoder()
        return try decoder.decode(T.self, from: data)
    }

    private func requestVoid(_ endpoint: String, method: String = "POST", body: Data? = nil) async throws {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let body = body {
            request.httpBody = body
        }

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        if httpResponse.statusCode >= 400 {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.serverError(errorResponse.detail)
            }
            throw APIError.serverError("Status code: \(httpResponse.statusCode)")
        }
    }

    // MARK: - File Operations

    func getFiles(includeArchived: Bool = false) async throws -> [TrackedFile] {
        let endpoint = "/files?include_archived=\(includeArchived)"
        return try await request(endpoint)
    }

    func getFile(id: String) async throws -> TrackedFile {
        return try await request("/files/\(id)")
    }

    func registerFile(path: String, commitMessage: String, displayName: String? = nil) async throws -> TrackedFile {
        struct RegisterRequest: Encodable {
            let file_path: String
            let commit_message: String
            let display_name: String?
        }

        let body = RegisterRequest(file_path: path, commit_message: commitMessage, display_name: displayName)
        let data = try JSONEncoder().encode(body)
        return try await request("/files", method: "POST", body: data)
    }

    func deleteFile(id: String) async throws {
        try await requestVoid("/files/\(id)", method: "DELETE")
    }

    func verifyFile(id: String) async throws -> TrackedFile {
        return try await request("/files/\(id)/verify", method: "POST")
    }

    func openFile(id: String) async throws {
        try await requestVoid("/files/\(id)/open", method: "POST")
    }

    func revealFile(id: String) async throws {
        try await requestVoid("/files/\(id)/reveal", method: "POST")
    }

    func toggleFavorite(id: String) async throws -> Bool {
        struct FavoriteResponse: Decodable {
            let is_favorite: Bool
        }
        let response: FavoriteResponse = try await request("/files/\(id)/favorite", method: "PUT")
        return response.is_favorite
    }

    func setArchived(id: String, archived: Bool) async throws {
        try await requestVoid("/files/\(id)/archive?archived=\(archived)", method: "PUT")
    }

    func updateName(id: String, name: String) async throws {
        let encodedName = name.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? name
        try await requestVoid("/files/\(id)/name?name=\(encodedName)", method: "PUT")
    }

    // MARK: - Version Operations

    func getVersions(fileId: String) async throws -> [Version] {
        return try await request("/files/\(fileId)/versions")
    }

    func createVersion(fileId: String, commitMessage: String) async throws -> Version {
        struct VersionRequest: Encodable {
            let commit_message: String
        }

        let body = VersionRequest(commit_message: commitMessage)
        let data = try JSONEncoder().encode(body)
        return try await request("/files/\(fileId)/versions", method: "POST", body: data)
    }

    func restoreVersion(fileId: String, versionNumber: Int) async throws {
        try await requestVoid("/files/\(fileId)/versions/\(versionNumber)/restore", method: "POST")
    }

    func openVersion(fileId: String, versionNumber: Int) async throws {
        try await requestVoid("/files/\(fileId)/versions/\(versionNumber)/open", method: "POST")
    }

    func revealVersion(fileId: String, versionNumber: Int) async throws {
        try await requestVoid("/files/\(fileId)/versions/\(versionNumber)/reveal", method: "POST")
    }

    func verifyVersion(fileId: String, versionNumber: Int) async throws -> VerificationResult {
        return try await request("/files/\(fileId)/versions/\(versionNumber)/verify", method: "POST")
    }

    func togglePin(fileId: String, versionNumber: Int) async throws -> PinResponse {
        return try await request("/files/\(fileId)/versions/\(versionNumber)/pin", method: "POST")
    }

    func revealPinnedVersion(fileId: String, versionNumber: Int) async throws {
        try await requestVoid("/files/\(fileId)/versions/\(versionNumber)/reveal-pinned", method: "POST")
    }

    // MARK: - Tag Operations

    func getTags(fileId: String) async throws -> [Tag] {
        return try await request("/files/\(fileId)/tags")
    }

    func addTag(fileId: String, tagName: String) async throws -> Tag {
        struct TagRequest: Encodable {
            let tag_name: String
        }

        let body = TagRequest(tag_name: tagName)
        let data = try JSONEncoder().encode(body)
        return try await request("/files/\(fileId)/tags", method: "POST", body: data)
    }

    func removeTag(fileId: String, tagId: String) async throws {
        try await requestVoid("/files/\(fileId)/tags/\(tagId)", method: "DELETE")
    }

    func getAllTags() async throws -> [Tag] {
        return try await request("/tags")
    }

    // MARK: - Event Operations

    func getEvents(fileId: String, limit: Int? = nil) async throws -> [FileEvent] {
        var endpoint = "/files/\(fileId)/events"
        if let limit = limit {
            endpoint += "?limit=\(limit)"
        }
        return try await request(endpoint)
    }

    // MARK: - Project Operations

    func getProjects() async throws -> [Project] {
        return try await request("/projects")
    }

    func createProject(name: String, description: String?, color: String) async throws -> Project {
        struct CreateRequest: Encodable {
            let name: String
            let description: String?
            let color: String
        }

        let body = CreateRequest(name: name, description: description, color: color)
        let data = try JSONEncoder().encode(body)
        return try await request("/projects", method: "POST", body: data)
    }

    func updateProject(id: String, name: String?, description: String?, color: String?) async throws -> Project {
        struct UpdateRequest: Encodable {
            let name: String?
            let description: String?
            let color: String?
        }

        let body = UpdateRequest(name: name, description: description, color: color)
        let data = try JSONEncoder().encode(body)
        return try await request("/projects/\(id)", method: "PUT", body: data)
    }

    func deleteProject(id: String) async throws {
        try await requestVoid("/projects/\(id)", method: "DELETE")
    }

    func setFileProject(fileId: String, projectId: String?) async throws {
        let endpoint = projectId != nil
            ? "/files/\(fileId)/project?project_id=\(projectId!)"
            : "/files/\(fileId)/project"
        try await requestVoid(endpoint, method: "PUT")
    }

    // MARK: - Metadata Operations

    func getMetadata(fileId: String) async throws -> [String: Any] {
        guard let url = URL(string: "\(baseURL)/files/\(fileId)/metadata") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        if httpResponse.statusCode == 404 {
            return [:]
        }

        if httpResponse.statusCode >= 400 {
            return [:]
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return [:]
        }

        return json
    }

    func extractMetadata(fileId: String) async throws -> [String: Any] {
        guard let url = URL(string: "\(baseURL)/files/\(fileId)/metadata") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        if httpResponse.statusCode >= 400 {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.serverError(errorResponse.detail)
            }
            throw APIError.serverError("Status code: \(httpResponse.statusCode)")
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return [:]
        }

        return json
    }

    // MARK: - Utility Operations

    func healthCheck() async throws -> Bool {
        struct HealthResponse: Decodable {
            let status: String
        }
        let response: HealthResponse = try await request("/health")
        return response.status == "healthy"
    }

    func verifyAllFiles() async throws -> VerifyAllResponse {
        return try await request("/verify-all", method: "POST")
    }
}

// MARK: - Error Types

enum APIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case notFound
    case serverError(String)
    case decodingError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .invalidResponse:
            return "Invalid response from server"
        case .notFound:
            return "Resource not found"
        case .serverError(let message):
            return message
        case .decodingError(let error):
            return "Decoding error: \(error.localizedDescription)"
        }
    }
}

struct ErrorResponse: Decodable {
    let detail: String
}
