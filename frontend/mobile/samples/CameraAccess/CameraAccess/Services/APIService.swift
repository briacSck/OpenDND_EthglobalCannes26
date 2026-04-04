import Foundation
import UIKit

enum APIError: Error {
  case invalidURL
  case noData
  case decodingError
  case serverError(Int)
}

final class APIService {
  static let shared = APIService()
  private let baseURL = "http://10.105.177.116:3002"
  private let decoder: JSONDecoder = {
    let d = JSONDecoder()
    d.keyDecodingStrategy = .convertFromSnakeCase
    d.dateDecodingStrategy = .custom { decoder in
      let container = try decoder.singleValueContainer()
      let str = try container.decode(String.self)
      let formatters: [DateFormatter] = {
        let f1 = DateFormatter()
        f1.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSZ"
        let f2 = DateFormatter()
        f2.dateFormat = "yyyy-MM-dd'T'HH:mm:ssZ"
        return [f1, f2]
      }()
      for f in formatters {
        if let date = f.date(from: str) { return date }
      }
      let iso = ISO8601DateFormatter()
      iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
      if let date = iso.date(from: str) { return date }
      iso.formatOptions = [.withInternetDateTime]
      if let date = iso.date(from: str) { return date }
      throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode date: \(str)")
    }
    return d
  }()

  private init() {}

  var currentUserId: String? {
    UserDefaults.standard.string(forKey: "userId")
  }

  // MARK: - Generic

  private func get<T: Decodable>(_ path: String) async throws -> T {
    guard let url = URL(string: "\(baseURL)\(path)") else { throw APIError.invalidURL }
    let (data, response) = try await URLSession.shared.data(from: url)
    guard let http = response as? HTTPURLResponse else { throw APIError.noData }
    guard (200...299).contains(http.statusCode) else { throw APIError.serverError(http.statusCode) }
    return try decoder.decode(T.self, from: data)
  }

  // MARK: - Quest

  func fetchActiveQuest(userId: String) async throws -> ActiveQuestResponse? {
    guard let url = URL(string: "\(baseURL)/api/quests/active/\(userId)") else { throw APIError.invalidURL }
    let (data, response) = try await URLSession.shared.data(from: url)
    guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
      throw APIError.serverError((response as? HTTPURLResponse)?.statusCode ?? 0)
    }
    let str = String(data: data, encoding: .utf8) ?? ""
    if str == "null" || str.isEmpty { return nil }
    return try decoder.decode(ActiveQuestResponse.self, from: data)
  }

  func fetchQuestHistory(userId: String) async throws -> [CompletedQuestResponse] {
    return try await get("/api/quests/history/\(userId)")
  }

  func generateQuest(userId: String, goal: String, location: String, duration: Int, difficulty: String) async throws -> ActiveQuestResponse {
    guard let url = URL(string: "\(baseURL)/api/quests/generate") else { throw APIError.invalidURL }
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.timeoutInterval = 300 // quest generation can take a while
    let body: [String: Any] = [
      "userId": userId,
      "goal": goal,
      "location": location,
      "duration": duration,
      "difficulty": difficulty,
    ]
    request.httpBody = try JSONSerialization.data(withJSONObject: body)
    let (data, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
      throw APIError.serverError((response as? HTTPURLResponse)?.statusCode ?? 0)
    }
    return try decoder.decode(ActiveQuestResponse.self, from: data)
  }

  // MARK: - Wallet

  func fetchWallet(userId: String) async throws -> WalletResponse {
    return try await get("/api/wallet/\(userId)")
  }

  // MARK: - Social

  func fetchLeaderboard() async throws -> [LeaderboardEntryResponse] {
    return try await get("/api/social/leaderboard")
  }

  func fetchActivity(userId: String) async throws -> [ActivityResponse] {
    return try await get("/api/social/activity/\(userId)")
  }

  func fetchBadges(userId: String) async throws -> [BadgeResponse] {
    return try await get("/api/social/badges/\(userId)")
  }

  func fetchPersonality(userId: String) async throws -> [PersonalityTraitResponse] {
    return try await get("/api/social/personality/\(userId)")
  }

  // MARK: - Step Verification

  func verifyStep(questId: String, stepOrder: Int, image: UIImage, step: QuestStepResponse) async throws -> VerifyStepResponse {
    guard let url = URL(string: "\(baseURL)/api/quests/\(questId)/steps/\(stepOrder)/verify") else { throw APIError.invalidURL }
    guard let imageData = image.jpegData(compressionQuality: 0.7) else { throw APIError.noData }

    let base64 = imageData.base64EncodedString()

    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.timeoutInterval = 30

    let body: [String: Any] = [
      "imageBase64": base64,
      "userId": currentUserId ?? "",
      "cameraPrompt": step.cameraPrompt ?? "",
      "successCondition": step.successCondition ?? "",
      "playerAction": step.playerAction ?? "",
      "stepTitle": step.title,
    ]
    request.httpBody = try JSONSerialization.data(withJSONObject: body)

    let (data, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
      throw APIError.serverError((response as? HTTPURLResponse)?.statusCode ?? 0)
    }
    return try decoder.decode(VerifyStepResponse.self, from: data)
  }

  func markStepDone(questId: String, stepOrder: Int) async throws {
    guard let url = URL(string: "\(baseURL)/api/quests/\(questId)/steps/\(stepOrder)/done") else { throw APIError.invalidURL }
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.httpBody = try JSONSerialization.data(withJSONObject: [:] as [String: String])
    let (_, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
      throw APIError.serverError((response as? HTTPURLResponse)?.statusCode ?? 0)
    }
  }

  func completeQuest(questId: String, xpEarned: Int, durationMinutes: Int) async throws {
    guard let url = URL(string: "\(baseURL)/api/quests/\(questId)/complete") else { throw APIError.invalidURL }
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    let body: [String: Any] = [
      "grade": "A",
      "xpEarned": xpEarned,
      "rewardAmount": 50,
      "durationMinutes": durationMinutes,
    ]
    request.httpBody = try JSONSerialization.data(withJSONObject: body)
    let (_, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
      throw APIError.serverError((response as? HTTPURLResponse)?.statusCode ?? 0)
    }
  }

  // MARK: - User

  func fetchUser(userId: String) async throws -> UserResponse {
    return try await get("/api/users/\(userId)")
  }
}

// MARK: - Response Models

struct ActiveQuestResponse: Codable {
  let id: String
  let title: String
  let description: String?
  let tone: String?
  let status: String
  let timeLimitMinutes: Int?
  let startedAt: Date?
  let steps: [QuestStepResponse]
  let actions: [QuestActionResponse]
  let completedSteps: Int
  let totalSteps: Int
  let progress: Double
}

struct QuestStepResponse: Codable, Identifiable {
  let id: Int
  let stepOrder: Int
  let type: String
  let title: String
  let subtitle: String?
  let icon: String?
  let done: Bool
  let active: Bool
  let content: String?
  let cameraPrompt: String?
  let successCondition: String?
  let playerAction: String?
  let narrativeIntro: String?

  enum CodingKeys: String, CodingKey {
    case id, stepOrder, type, title, subtitle, icon, done, active, content
    case cameraPrompt, successCondition, playerAction, narrativeIntro
  }

  init(from decoder: Decoder) throws {
    let c = try decoder.container(keyedBy: CodingKeys.self)
    id = try c.decode(Int.self, forKey: .id)
    stepOrder = try c.decode(Int.self, forKey: .stepOrder)
    type = try c.decode(String.self, forKey: .type)
    title = try c.decode(String.self, forKey: .title)
    subtitle = try c.decodeIfPresent(String.self, forKey: .subtitle)
    icon = try c.decodeIfPresent(String.self, forKey: .icon)
    done = try c.decode(Bool.self, forKey: .done)
    active = try c.decode(Bool.self, forKey: .active)
    content = try c.decodeIfPresent(String.self, forKey: .content)
    cameraPrompt = try c.decodeIfPresent(String.self, forKey: .cameraPrompt)
    successCondition = try c.decodeIfPresent(String.self, forKey: .successCondition)
    playerAction = try c.decodeIfPresent(String.self, forKey: .playerAction)
    narrativeIntro = try c.decodeIfPresent(String.self, forKey: .narrativeIntro)
  }
}

struct VerifyStepResponse: Codable {
  let validated: Bool
  let confidence: Double
  let narrativeReaction: String
  let xpEarned: Int
  let details: String
}

struct QuestActionResponse: Codable, Identifiable {
  let id: Int
  let action: String
  let xp: Int
  let createdAt: Date?
}

struct CompletedQuestResponse: Codable, Identifiable {
  let id: String
  let title: String
  let grade: String?
  let xpEarned: Int?
  let rewardAmount: Double?
  let durationMinutes: Int?
  let completedAt: Date?
}

struct WalletResponse: Codable {
  let walletAddress: String?
  let available: Double
  let locked: Double
  let pending: Double
  let transactions: [TransactionResponse]
}

struct TransactionResponse: Codable, Identifiable {
  let id: Int
  let type: String
  let label: String
  let amount: Double
  let date: Date?
}

struct LeaderboardEntryResponse: Codable, Identifiable {
  let rank: Int
  let id: String
  let name: String
  let avatar: String
  let xp: Int
  let level: Int
}

struct ActivityResponse: Codable, Identifiable {
  let id: Int
  let userId: String
  let name: String
  let avatar: String
  let action: String
  let grade: String?
  let time: Date?
}

struct BadgeResponse: Codable, Identifiable {
  let id: Int
  let name: String
  let emoji: String
  let description: String?
  let unlocked: Bool
  let unlockedAt: Date?
}

struct PersonalityTraitResponse: Codable {
  let label: String
  let value: Int
}

struct UserResponse: Codable {
  let id: String
  let firstName: String
  let email: String?
  let xp: Int?
  let level: Int?
  let walletAddress: String?
}
